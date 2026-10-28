"""Immutable validation-only LP/FT and post-lock evaluation of saved states.

Development entrypoints never infer test predictions or select with test labels.
Each fold is an independently seeded process and every condition uses the same
head topology, optimizer, budget, stopping and validation checkpoint rule.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import time

import numpy as np
import torch

from artifact_io import (atomic_json, atomic_torch_save, check_deadline, file_lock, fingerprint,
                         publish_completion, read_json, sha256_file, verify_completion, verify_completion_metadata)
from data_contract import RELEASES
from evaluation_contract import EVALUATION, EVALUATION_HASH, EpochSelection, sample_metrics, training_statistics
from gpu_diagnostics import Telemetry, require_cuda, seed_process, utilization
from official_model import build_head, flatten_for_evaluation, load_official, prepare_input


def feature_identity(release, initialization, rows):
    return {"release": release.identity, "encoder": initialization,
            "evaluation_hash": EVALUATION_HASH, "row_indices": np.asarray(rows).tolist(),
            "feature_dim": 337920, "dtype": "float32"}


def build_validation_features(release, folds, directory, *, device, encoder_checkpoint, deadline):
    """Cache only the union of approved training/validation rows across splits."""
    directory = Path(directory)
    device = require_cuda(device)
    model, positions, initialization = load_official(release.channel_names, device=device, encoder_checkpoint=encoder_checkpoint)
    permitted = np.unique(np.concatenate([release.partitions(fold)[part] for fold in folds for part in ("train", "val")]))
    identity = feature_identity(release, initialization, permitted)
    with file_lock(directory / "cache.lock"):
        if (directory / "COMPLETE.json").is_file():
            verify_completion_metadata(directory, identity)
            del model
            return directory / "features.npy"
        directory.mkdir(parents=True, exist_ok=True)
        required = len(release.labels) * 337920 * 4
        if shutil.disk_usage(directory).free < required * 1.1:
            raise OSError("Insufficient artifacts storage for a complete LP feature cache")
        pending = directory / "features.pending.npy"
        cache = np.lib.format.open_memmap(pending, mode="w+", dtype=np.float32,
                                         shape=(len(release.labels), 337920))
        telemetry = Telemetry(device)
        model.eval()
        with torch.no_grad():
            for offset in range(0, len(permitted), 128):
                check_deadline(deadline)
                rows = permitted[offset:offset+128]
                start_read = time.monotonic()
                values = release.load_signals(rows)
                telemetry.data_wait_seconds += time.monotonic() - start_read
                tensor, before, after = telemetry.copy(values)
                start_step = time.monotonic()
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    output = model(prepare_input(tensor), positions.expand(len(rows), -1, -1))
                cache[rows] = flatten_for_evaluation(output).cpu().numpy()
                after.synchronize()
                telemetry.h2d_seconds += before.elapsed_time(after) / 1000
                telemetry.step_seconds += time.monotonic() - start_step
                telemetry.steps += 1
                telemetry.samples += len(rows)
                if offset % (128 * 20) == 0:
                    telemetry.utilization_samples.append(utilization(device))
        cache.flush()
        del cache, model
        import os
        os.replace(pending, directory / "features.npy")
        (directory / "features.npy").chmod(0o444)
        atomic_json(directory / "features.json", {"identity": identity, "telemetry": telemetry.report(),
                                                   "scope": "union of per-fold training and validation rows; no test prediction calls",
                                                   "test_evaluations": 0})
        publish_completion(directory, identity, ["features.npy", "features.json"])
    return directory / "features.npy"


def copy_cpu_batch(values, device):
    return torch.as_tensor(np.asarray(values, dtype=np.float32)).pin_memory().to(device, non_blocking=True)


def predict_validation(*, mode, model, positions, head, release, rows, features, mean, std, device, deadline):
    """No split-name dispatch or test fallback: caller supplies checked val rows."""
    predictions = []
    head.eval()
    if model is not None:
        model.eval()
    with torch.no_grad():
        for offset in range(0, len(rows), 128):
            check_deadline(deadline)
            selected = rows[offset:offset+128]
            if mode == "lp":
                values = (np.asarray(features[selected], dtype=np.float32) - mean) / std
                x = copy_cpu_batch(values, device)
            else:
                tensor = copy_cpu_batch(release.load_signals(selected), device)
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    tokens = model(prepare_input(tensor), positions.expand(len(selected), -1, -1))
                x = flatten_for_evaluation(tokens)
            logits = head(x.float())
            if not torch.isfinite(logits).all():
                raise ValueError("Nonfinite validation logits")
            predictions.append(logits.argmax(dim=1).cpu().numpy())
    return np.concatenate(predictions)


def train_validation_unit(release, fold, mode, directory, *, condition_identity, encoder_checkpoint,
                          feature_path, device, deadline):
    directory = Path(directory)
    identity = {"condition": condition_identity, "release": release.identity,
                "evaluation_hash": EVALUATION_HASH, "fold": fold, "mode": mode,
                "initial_encoder_sha256": sha256_file(encoder_checkpoint) if encoder_checkpoint else None}
    if (directory / "COMPLETE.json").is_file():
        verify_completion(directory, identity)
        return read_json(directory / "validation.json")
    device = require_cuda(device)
    seed_process(42 + fold["fold"])
    partitions = release.partitions(fold)
    train_rows, val_rows = partitions["train"], partitions["val"]
    classes = RELEASES[release.target][3]
    model = positions = features = mean = std = None
    initialization = None
    if mode == "lp":
        features = np.load(feature_path, mmap_mode="r")
        manifest = verify_completion_metadata(Path(feature_path).parent)
        available_rows = set(manifest["identity"]["row_indices"])
        if not set(train_rows.tolist()+val_rows.tolist()) <= available_rows:
            raise ValueError("LP cache lacks required development rows")
        mean, std = training_statistics(features, train_rows)
    elif mode == "ft":
        model, positions, initialization = load_official(release.channel_names, device=device, encoder_checkpoint=encoder_checkpoint)
        for parameter in model.parameters():
            parameter.requires_grad_(True)
    else:
        raise ValueError("Unknown evaluation mode")
    head = build_head(mode, 337920, classes).to(device)
    parameters = list(head.parameters()) + (list(model.parameters()) if model else [])
    config = EVALUATION[mode]
    optimizer_class = torch.optim.Adam if mode == "lp" else torch.optim.AdamW
    optimizer = optimizer_class(parameters, lr=config["lr"], weight_decay=EVALUATION["weight_decay"],
                                betas=(0.9, 0.999), eps=1e-8)
    selection = EpochSelection()
    lp_generator = torch.Generator(device="cpu").manual_seed(42 + fold["fold"])
    ft_generator = np.random.default_rng(42 + fold["fold"] * 997)
    telemetry = Telemetry(device)
    epoch_records, updates, best_metrics = [], 0, None
    directory.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, config["epochs"] + 1):
        head.train()
        if model:
            model.train()
        if mode == "lp":
            order = torch.randperm(len(train_rows), generator=lp_generator).numpy()
        else:
            order = ft_generator.permutation(len(train_rows))
        loss_sum = torch.zeros((), device=device, dtype=torch.float64)
        for offset in range(0, len(order), 128):
            check_deadline(deadline)
            rows = train_rows[order[offset:offset+128]]
            start_read = time.monotonic()
            if mode == "lp":
                values = (np.asarray(features[rows], dtype=np.float32) - mean) / std
            else:
                values = release.load_signals(rows)
            telemetry.data_wait_seconds += time.monotonic() - start_read
            tensor, before, after = telemetry.copy(values)
            start_step = time.monotonic()
            optimizer.zero_grad(set_to_none=True)
            if mode == "lp":
                x = tensor.float()
            else:
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    tokens = model(prepare_input(tensor), positions.expand(len(rows), -1, -1))
                x = flatten_for_evaluation(tokens)
            logits = head(x)
            labels = torch.as_tensor(release.labels[rows], dtype=torch.long, device=device)
            loss = torch.nn.functional.cross_entropy(logits.float(), labels)
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite downstream training loss")
            loss.backward()
            if mode == "ft":
                norm = torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True)
                if norm <= 0:
                    raise ValueError("FT gradients are zero")
            optimizer.step()
            loss_sum += loss.detach().double() * len(rows)
            updates += 1
            telemetry.steps += 1
            telemetry.samples += len(rows)
            after.synchronize()
            telemetry.h2d_seconds += before.elapsed_time(after) / 1000
            telemetry.step_seconds += time.monotonic() - start_step
        epoch_loss = float((loss_sum / len(train_rows)).cpu())
        predictions = predict_validation(mode=mode, model=model, positions=positions, head=head, release=release,
                                         rows=val_rows, features=features, mean=mean, std=std, device=device, deadline=deadline)
        metrics = sample_metrics(release.labels[val_rows], predictions, classes)
        selected, stop = selection.observe(epoch, training_loss=epoch_loss, validation_bacc=metrics["balanced_accuracy"])
        epoch_records.append({"epoch": epoch, "training_loss": epoch_loss, "validation": metrics,
                              "updates_completed": updates, "selected": selected})
        telemetry.utilization_samples.append({"epoch": epoch, **utilization(device)})
        if selected:
            checkpoint_value = {"identity": identity,
                                "head": {key: value.detach().cpu() for key, value in head.state_dict().items()},
                                "encoder": {key: value.detach().cpu() for key, value in model.state_dict().items()} if model else None,
                                "mean": torch.from_numpy(mean.copy()) if mean is not None else None,
                                "std": torch.from_numpy(std.copy()) if std is not None else None,
                                "initial_encoder_checkpoint": str(encoder_checkpoint) if encoder_checkpoint else None,
                                "selected_epoch": epoch, "validation": metrics}
            atomic_torch_save(directory / "val_best.pt", checkpoint_value)
            atomic_json(directory / "validation_predictions.json", {"row_indices": val_rows.tolist(),
                                                                      "labels": release.labels[val_rows].tolist(),
                                                                      "predictions": predictions.tolist()})
            best_metrics = metrics
        atomic_json(directory / "epochs.json", epoch_records)
        if stop:
            break
    if best_metrics is None:
        raise ValueError("No validation checkpoint selected")
    report = {"identity": identity, "mode": mode, "fold": fold["fold"], "split_seed": fold["split_seed"],
              "training_seed": 42 + fold["fold"], "batch_order_seed": 42 + fold["fold"] * (997 if mode == "ft" else 1),
              "target": release.target, "validation": best_metrics,
              "selected_epoch": selection.best_epoch, "epochs_requested": config["epochs"],
              "epochs_completed": len(epoch_records), "updates_completed": updates,
              "stop_reason": "relative_training_loss_patience" if stop else "max_epochs",
              "initialization": initialization, "checkpoint_sha256": sha256_file(directory / "val_best.pt"),
              "checkpoint_path": str(directory / "val_best.pt"), "config": EVALUATION,
              "train_samples": len(train_rows), "validation_samples": len(val_rows),
              "telemetry": telemetry.report(), "test_evaluations": 0}
    atomic_json(directory / "validation.json", report)
    publish_completion(directory, identity, ["val_best.pt", "validation.json", "epochs.json", "validation_predictions.json"])
    return report


def final_test_unit(release, fold, mode, unit_directory, output_directory, *, method_lock, device, deadline):
    """One real test call, after verifying a global method lock and val-best state."""
    unit_directory, output_directory = Path(unit_directory), Path(output_directory)
    from evaluation_contract import locked_round_limit
    locked_round_limit(method_lock)
    verified = verify_completion(unit_directory)
    report = read_json(unit_directory / "validation.json")
    value = torch.load(unit_directory / "val_best.pt", map_location="cpu", weights_only=True)
    if value["identity"] != verified["identity"] or report["identity"] != verified["identity"]:
        raise ValueError("Final evaluation state provenance differs")
    if (value["identity"]["release"] != release.identity or value["identity"]["fold"] != fold
            or value["identity"]["mode"] != mode or value["identity"]["evaluation_hash"] != EVALUATION_HASH):
        raise ValueError("Final evaluation release, split, mode or common evaluation contract differs")
    initial_checkpoint = value["initial_encoder_checkpoint"]
    expected_initial_hash = value["identity"]["initial_encoder_sha256"]
    if ((initial_checkpoint is None) != (expected_initial_hash is None)
            or (initial_checkpoint is not None and sha256_file(initial_checkpoint) != expected_initial_hash)):
        raise ValueError("Initial encoder changed since validation checkpoint selection")
    identity = {"validation_unit": verified["identity"], "method_lock_hash": fingerprint(method_lock)}
    if (output_directory / "COMPLETE.json").is_file():
        verify_completion(output_directory, identity)
        return read_json(output_directory / "test.json")
    device = require_cuda(device)
    model, positions, initialization = load_official(release.channel_names, device=device,
                                                    encoder_checkpoint=value["initial_encoder_checkpoint"])
    if mode == "ft":
        from official_model import load_exact_state
        load_exact_state(model, value["encoder"])
    head = build_head(mode, 337920, RELEASES[release.target][3]).to(device)
    head.load_state_dict(value["head"], strict=True)
    model.eval()
    head.eval()
    rows = release.partitions(fold)["test"]
    predictions = []
    with torch.no_grad():
        for offset in range(0, len(rows), 128):
            check_deadline(deadline)
            selected = rows[offset:offset+128]
            tensor = copy_cpu_batch(release.load_signals(selected), device)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                tokens = model(prepare_input(tensor), positions.expand(len(selected), -1, -1))
            features = flatten_for_evaluation(tokens)
            if mode == "lp":
                features = (features - value["mean"].to(device)) / value["std"].to(device)
            logits = head(features.float())
            if not torch.isfinite(logits).all():
                raise ValueError("Nonfinite final test logits")
            predictions.append(logits.argmax(dim=1).cpu().numpy())
    predictions = np.concatenate(predictions)
    metrics = sample_metrics(release.labels[rows], predictions, RELEASES[release.target][3])
    # Exactly one full fold call; minibatches are not separate evaluations.
    test_report = {"identity": identity, "target": release.target, "mode": mode, "fold": fold["fold"],
                   "split_seed": fold["split_seed"], "metrics": metrics, "test_evaluations": 1,
                   "selected_epoch": value["selected_epoch"], "checkpoint_sha256": report["checkpoint_sha256"],
                   "method_lock_hash": fingerprint(method_lock), "initialization": initialization}
    atomic_json(output_directory / "predictions.json", {"row_indices": rows.tolist(),
                                                        "labels": release.labels[rows].tolist(), "predictions": predictions.tolist()})
    atomic_json(output_directory / "test.json", test_report)
    publish_completion(output_directory, identity, ["test.json", "predictions.json"])
    return test_report
