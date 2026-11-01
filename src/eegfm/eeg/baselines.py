"""Separate Builder-only exploratory EEGMAT representation baselines.

The original reference is read-only. `prepare` freezes development fits and
source/data hashes. `test` consumes a new one-shot reservation before touching
extension test arrays. Reusing this already observed cohort is exploratory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Mapping

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
import numpy as np

from eegfm.eeg.data import CBraModCPU
from eegfm.eeg.data import FEATURE_COLUMNS
from eegfm.eeg.data import FEATURE_IDS
from eegfm.eeg.data import MODEL_RESOURCES
from eegfm.eeg.data import load_cbramod
from eegfm.eeg.data import sha256_file
from eegfm.eeg.reference import array_fit
from eegfm.eeg.reference import choose_probe
from eegfm.eeg.reference import save_json
from eegfm.eeg.statistics import classification_metrics
from eegfm.eeg.statistics import cluster_bootstrap_indices
from eegfm.eeg.statistics import fit_head
from eegfm.eeg.statistics import head_logits
from eegfm.eeg.statistics import interval
from eegfm.eeg.statistics import predict_probe
from eegfm.eeg.statistics import r2_columns
from eegfm.eeg.statistics import validate_partitions

IDENTITY_KEYS = ("y", "sample_ids", "subject_ids", "recording_ids", "window_indices")
RANDOM_SEEDS = (20261030, 20261031, 20261032)
METHODS = ("transparent62", "pretrained200") + tuple(f"random200_s{s}" for s in RANDOM_SEEDS)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_alignment(left: Mapping[str, np.ndarray], right: Mapping[str, np.ndarray]) -> None:
    for key in IDENTITY_KEYS:
        if not np.array_equal(left[key], right[key]):
            raise ValueError(f"Representation identity mismatch: {key}")


def verify_lock(output: Path) -> dict[str, Any]:
    lock = json.loads((output / "EXTENSION_LOCK.json").read_text(encoding="utf-8"))
    if not lock.get("files"):
        raise ValueError("Empty extension lock")
    for item in lock["files"]:
        path = Path(item["path"])
        if not path.is_file() or path.is_symlink() or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Frozen extension bytes changed: {path.name}")
    return lock


def reserve_test(output: Path) -> None:
    verify_lock(output)
    save_json(output / "TEST_RESERVATION.json", {
        "at": now(), "one_shot": True, "status": "reserved_before_test_access",
        "extension_lock_sha256": sha256_file(output / "EXTENSION_LOCK.json"),
        "study_status": "EXPLORATORY_ALREADY_OBSERVED_COHORT",
    })


def checked_reference(reference: Path, prepared: Path, split: str) -> dict[str, np.ndarray]:
    path = reference / f"{split}-representations.npz"
    receipt = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if sha256_file(path) != receipt["sha256"]:
        raise ValueError("Reference cache hash mismatch")
    if sha256_file(prepared / f"{split}.npz") != receipt["input_sha256"]:
        raise ValueError("Prepared data do not match reference cache")
    source_root = Path(__file__).resolve().parent
    for name, digest in receipt["producer"]["code_sha256"].items():
        if sha256_file(source_root / name) != digest:
            raise ValueError("Reference scientific code changed")
    with np.load(path, allow_pickle=False) as data:
        result = {key: data[key] for key in IDENTITY_KEYS + ("features", "embedding")}
        result.update({f"pooled_{layer}": data[f"layer_{layer}"].mean((1, 2)) for layer in (6, 12)})
    if any(not np.isfinite(result[key]).all() for key in ("features", "embedding", "pooled_6", "pooled_12")):
        raise ValueError("Nonfinite reference representation")
    return result


def state_hash(model: Any) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(str(tuple(value.shape)).encode("ascii"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def random_model(resources: Path, seed: int) -> tuple[CBraModCPU, str]:
    import torch
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    # Verifies/imports the official pinned source. The second constructor below
    # receives no checkpoint, and all its weights are freshly initialized.
    pretrained = load_cbramod(resources, threads=4)
    constructor = type(pretrained.model)
    del pretrained
    torch.manual_seed(seed)
    model = constructor()
    model.proj_out = torch.nn.Identity()
    wrapped = CBraModCPU(model)
    return wrapped, state_hash(model)


def extract_random(resources: Path, prepared: Path, output: Path, split: str, seed: int) -> dict[str, np.ndarray]:
    target = output / f"random-{seed}-{split}.npz"
    if target.exists():
        raise FileExistsError("Random extraction output already exists")
    start = time.monotonic()
    model, digest = random_model(resources, seed)
    with np.load(prepared / f"{split}.npz", allow_pickle=False) as data:
        x = data["x"]
        result = {name: data[name] for name in IDENTITY_KEYS}
    pooled: dict[int, list[np.ndarray]] = {6: [], 12: []}
    embeddings: list[np.ndarray] = []
    for offset in range(0, len(x), 8):
        acts = model.activations(x[offset:offset + 8], layers=(6, 12))
        for layer in pooled:
            pooled[layer].append(acts[layer].mean((1, 2)))
        embeddings.append(model.continue_from(acts[12], layer=12).mean((1, 2)))
    result.update({f"pooled_{layer}": np.concatenate(values) for layer, values in pooled.items()})
    result["embedding"] = np.concatenate(embeddings)
    if any(not np.isfinite(result[key]).all() for key in ("embedding", "pooled_6", "pooled_12")):
        raise ValueError("Nonfinite random representation")
    np.savez(target, **result)
    save_json(target.with_suffix(".json"), {
        "split": split, "seed": seed, "state_sha256": digest,
        "sha256": sha256_file(target), "input_sha256": sha256_file(prepared / f"{split}.npz"),
        "samples": len(x), "seconds": time.monotonic() - start, "cpu_threads": 4,
        "checkpoint_loaded_into_random_model": False, "pooled_layers": [6, 12],
    })
    print(json.dumps({"extracted": target.name, "seconds": time.monotonic() - start}), flush=True)
    return result


def method_inputs(reference: dict[str, np.ndarray], random: dict[int, dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    return {"transparent62": reference["features"], "pretrained200": reference["embedding"],
            **{f"random200_s{seed}": value["embedding"] for seed, value in random.items()}}


def feature_columns(feature: str) -> list[int]:
    return [i for i, name in enumerate(FEATURE_COLUMNS) if name == feature or name.startswith(feature + ":")]


def prepare(resources: Path, prepared: Path, reference: Path, output: Path) -> dict[str, Any]:
    import sklearn
    import torch
    from threadpoolctl import threadpool_limits
    threadpool_limits(limits=4)
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "PROTOCOL.json", {
        "schema": "representation_baselines_v1", "registered_at": now(),
        "status": "EXPLORATORY_ALREADY_OBSERVED_COHORT", "builder_only": True,
        "rationale": "Matched transparent, official pretrained and random-initialized frozen backbone probes",
        "prior_test_knowledge": "Builder has already observed original EEGMAT reference test results; this is not new confirmation",
        "split_policy": "Reuse fixed original participant-disjoint train/validation/test; no new data or resplitting",
        "methods": METHODS, "random_seeds": RANDOM_SEEDS, "threads": 4, "device": "cpu",
        "classification": {"primary_metric": "balanced_accuracy", "secondary_metric": "auroc",
            "scaling": "training mean and population std only", "classifier": "sklearn LogisticRegression lbfgs max_iter=2000 random_state=20261029",
            "C_grid": [0.01, 0.1, 1.0, 10.0], "selection": "highest validation balanced accuracy, tie first/smallest C",
            "threshold": "fixed logit 0", "refit_train_plus_validation": False,
            "primary_differences": ["pretrained200-minus-transparent62", "pretrained200-minus-random_seed_mean", "transparent62-minus-random_seed_mean"],
            "random_aggregation": "mean of metrics across three fixed seeds; no probability ensemble; also report each seed"},
        "q1": {"layers": [6, 12], "groups": list(FEATURE_IDS), "columns": list(FEATURE_COLUMNS),
            "probe": "train-standardized multivariate Ridge", "alpha_grid": [1, 10, 100],
            "selection": "validation mean R2 over training-active columns separately for each model/layer/group",
            "comparison": "pretrained R2 minus mean R2 across fixed random seeds; no target or group selection on test"},
        "uncertainty": {"unit": "participant, all paired windows retained", "resamples": 2000,
            "seed": 20261030, "pointwise_confidence": 0.95, "classification_family_size": 3,
            "q1_family_size": 24, "seed_uncertainty": "reported dispersion only; bootstrap conditional on three fixed initializations",
            "limits": "only six test participants; percentile bootstrap conditional on fixed training/validation cohort"},
        "runtime": {"python": sys.version, "numpy": np.__version__, "torch": torch.__version__,
            "sklearn": sklearn.__version__, "platform": platform.platform()},
        "paths": {"resources": str(resources.resolve()), "prepared": str(prepared.resolve()), "reference": str(reference.resolve())},
        "script_sha256": sha256_file(Path(__file__)),
    })
    original = {split: checked_reference(reference, prepared, split) for split in ("train", "validation")}
    counts = validate_partitions({split: value["subject_ids"] for split, value in original.items()})
    random: dict[str, dict[int, dict[str, np.ndarray]]] = {"train": {}, "validation": {}}
    for seed in RANDOM_SEEDS:
        for split in random:
            random[split][seed] = extract_random(resources, prepared, output, split, seed)
            validate_alignment(original[split], random[split][seed])
    train, val = original["train"], original["validation"]
    tx, vx = method_inputs(train, random["train"]), method_inputs(val, random["validation"])
    heads = {name: fit_head(tx[name], train["y"], vx[name], val["y"]) for name in METHODS}
    q1_fits: list[dict[str, Any]] = []
    for name in METHODS[1:]:
        seed = int(name.split("_s")[1]) if "_s" in name else None
        rt = random["train"][seed] if seed is not None else train
        rv = random["validation"][seed] if seed is not None else val
        for layer in (6, 12):
            for feature in FEATURE_IDS:
                cols = feature_columns(feature)
                fit, score = choose_probe(rt[f"pooled_{layer}"], train["features"][:, cols], rv[f"pooled_{layer}"], val["features"][:, cols])
                q1_fits.append({"method": name, "layer": layer, "feature": feature, "columns": cols,
                               "fit": fit, "validation_r2": score})
    save_json(output / "FROZEN_FITS.json", {"heads": heads, "q1": q1_fits})
    save_json(output / "DEVELOPMENT.json", {
        "participant_counts": counts, "samples": {s: len(v["y"]) for s, v in original.items()},
        "classification": {name: {**classification_metrics(val["y"], head_logits(heads[name], vx[name])),
                                    "C": heads[name]["C"], "grid": heads[name]["selection_grid"]} for name in METHODS},
        "seconds": time.monotonic() - started,
    })
    source_root = Path(__file__).resolve().parent
    paths = [Path(__file__), Path(__file__).resolve().parents[1] / "arguments.py", output / "PROTOCOL.json", output / "FROZEN_FITS.json", output / "DEVELOPMENT.json"]
    paths += [source_root / name for name in ("data.py", "reference.py", "statistics.py")]
    paths += [resources / item.relative_path for item in MODEL_RESOURCES]
    paths += [prepared / f"{split}.npz" for split in original]
    paths += [reference / f"{split}-representations.{suffix}" for split in original for suffix in ("npz", "json")]
    paths += list(output.glob("random-*"))
    save_json(output / "EXTENSION_LOCK.json", {"schema": "representation_baselines_lock_v1", "at": now(),
        "extension_test_accessed": False, "files": [{"path": str(p.resolve()), "sha256": sha256_file(p)} for p in paths]})
    return {"status": "frozen_before_extension_test", "seconds": time.monotonic() - started, "methods": METHODS}


def ba(y: np.ndarray, logits: np.ndarray) -> float:
    return float(np.mean([np.mean((logits[y == label] >= 0) == label) for label in (0, 1)]))


def q1_bootstrap(targets: np.ndarray, prediction: np.ndarray, subjects: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """Exactly equivalent to resampling all windows of sampled participants."""
    blocks = [np.flatnonzero(subjects == s) for s in np.unique(subjects)]
    sums = np.array([targets[b].sum(0) for b in blocks])
    squares = np.array([np.square(targets[b]).sum(0) for b in blocks])
    errors = np.array([np.square(targets[b] - prediction[b]).sum(0) for b in blocks])
    n = counts @ np.array([len(b) for b in blocks])
    denom = counts @ squares - np.square(counts @ sums) / n[:, None]
    result = np.full_like(denom, np.nan)
    np.divide(counts @ errors, denom, out=result, where=denom > 1e-20)
    return 1 - result


def evaluate(resources: Path, prepared: Path, reference: Path, output: Path) -> dict[str, Any]:
    from threadpoolctl import threadpool_limits
    threadpool_limits(limits=4)
    start = time.monotonic()
    reserve_test(output)
    test = checked_reference(reference, prepared, "test")
    subjects = {"test": test["subject_ids"]}
    for split in ("train", "validation"):
        with np.load(prepared / f"{split}.npz", allow_pickle=False) as data:
            subjects[split] = data["subject_ids"]
    counts = validate_partitions(subjects)
    random = {seed: extract_random(resources, prepared, output, "test", seed) for seed in RANDOM_SEEDS}
    for seed, value in random.items():
        validate_alignment(test, value)
        states = [json.loads((output / f"random-{seed}-{s}.json").read_text(encoding="utf-8"))["state_sha256"] for s in ("train", "validation", "test")]
        if len(set(states)) != 1:
            raise ValueError("Random initialization differs across splits")
    fits = json.loads((output / "FROZEN_FITS.json").read_text(encoding="utf-8"))
    inputs = method_inputs(test, random)
    logits = {name: head_logits(array_fit(fits["heads"][name]), inputs[name]) for name in METHODS}
    samples = cluster_bootstrap_indices(test["subject_ids"], resamples=2000, seed=20261030)
    boot = {name: np.array([ba(test["y"][rows], values[rows]) for rows in samples]) for name, values in logits.items()}
    metrics = {name: {**classification_metrics(test["y"], values), "C": fits["heads"][name]["C"],
                         "balanced_accuracy_ci95": interval(boot[name]), "dimensions": inputs[name].shape[1]} for name, values in logits.items()}
    random_names = METHODS[2:]
    boot["random_seed_mean"] = np.mean([boot[name] for name in random_names], axis=0)
    metrics["random_seed_mean"] = {key: float(np.mean([metrics[name][key] for name in random_names])) for key in ("accuracy", "balanced_accuracy", "auroc")}
    metrics["random_seed_mean"]["balanced_accuracy_ci95"] = interval(boot["random_seed_mean"])
    metrics["random_seed_mean"]["balanced_accuracy_seed_range"] = [min(metrics[n]["balanced_accuracy"] for n in random_names), max(metrics[n]["balanced_accuracy"] for n in random_names)]
    differences = []
    for left, right in (("pretrained200", "transparent62"), ("pretrained200", "random_seed_mean"), ("transparent62", "random_seed_mean")):
        differences.append({"comparison": f"{left}-minus-{right}",
            "balanced_accuracy_difference": metrics[left]["balanced_accuracy"] - metrics[right]["balanced_accuracy"],
            "paired_subject_ci95": interval(boot[left] - boot[right]),
            "paired_subject_family_adjusted_ci": interval(boot[left] - boot[right], confidence=1 - .05 / 3)})
    unique = np.unique(test["subject_ids"])
    bootstrap_counts = np.array([[np.count_nonzero(test["subject_ids"][rows] == s) // np.count_nonzero(test["subject_ids"] == s) for s in unique] for rows in samples])
    q1: list[dict[str, Any]] = []
    q1_samples: dict[tuple[str, int, str], np.ndarray] = {}
    saved = {"subject_ids": test["subject_ids"], "sample_ids": test["sample_ids"], "y": test["y"]}
    saved.update({f"logits_{name}": values for name, values in logits.items()})
    for index, item in enumerate(fits["q1"]):
        name, layer, feature = item["method"], item["layer"], item["feature"]
        seed = int(name.split("_s")[1]) if "_s" in name else None
        representation = random[seed] if seed is not None else test
        fit = array_fit(item["fit"])
        targets = test["features"][:, item["columns"]].astype(np.float64)
        predicted = predict_probe(fit, representation[f"pooled_{layer}"])
        active = fit["active_columns"].astype(bool)
        row_boot = np.nanmean(q1_bootstrap(targets, predicted, test["subject_ids"], bootstrap_counts)[:, active], axis=1)
        q1_samples[(name, layer, feature)] = row_boot
        q1.append({"method": name, "layer": layer, "feature": feature, "alpha": fit["alpha"],
            "r2": float(np.nanmean(r2_columns(targets, predicted)[active])), "r2_ci95": interval(row_boot),
            "active_train_columns": int(active.sum()), "validation_r2": item["validation_r2"]})
        saved[f"q1_prediction_{index}"] = predicted
    q1_comparisons = []
    for layer in (6, 12):
        for feature in FEATURE_IDS:
            original = next(r for r in q1 if r["method"] == "pretrained200" and r["layer"] == layer and r["feature"] == feature)
            rnd = [r["r2"] for r in q1 if r["method"] in random_names and r["layer"] == layer and r["feature"] == feature]
            delta = q1_samples[("pretrained200", layer, feature)] - np.mean([q1_samples[(name, layer, feature)] for name in random_names], axis=0)
            q1_comparisons.append({"layer": layer, "feature": feature, "pretrained_r2": original["r2"],
                "random_seed_mean_r2": float(np.mean(rnd)), "random_seed_r2_range": [min(rnd), max(rnd)],
                "r2_difference": original["r2"] - float(np.mean(rnd)), "paired_subject_ci95": interval(delta),
                "paired_subject_family_adjusted_ci": interval(delta, confidence=1 - .05 / 24)})
    np.savez(output / "TEST_ARRAYS_PRIVATE.npz", **saved)
    result = {"status": "EXPLORATORY_COMPLETE", "builder_only": True, "at": now(),
        "participant_counts": counts, "test_windows": len(test["y"]),
        "classification": metrics, "classification_differences": differences,
        "q1": q1, "q1_pretrained_minus_random": q1_comparisons,
        "uncertainty": "Participant cluster bootstrap; 2000 draws, seed 20261030. Conditional on fixed train/validation and three random seeds; six test participants.",
        "seconds": time.monotonic() - start,
        "provenance": {"protocol_sha256": sha256_file(output / "PROTOCOL.json"), "lock_sha256": sha256_file(output / "EXTENSION_LOCK.json"),
            "script_sha256": sha256_file(Path(__file__)), "test_input_sha256": sha256_file(prepared / "test.npz"),
            "test_reference_sha256": sha256_file(reference / "test-representations.npz"),
            "private_arrays_sha256": sha256_file(output / "TEST_ARRAYS_PRIVATE.npz")}}
    save_json(output / "RESULT.json", result)
    verify_lock(output)
    return {"status": result["status"], "classification": metrics, "classification_differences": differences, "seconds": result["seconds"]}


def main() -> None:
    from eegfm.arguments import task_parser
    parser = task_parser('baselines', description=__doc__)
    args = parser.parse_args()
    action = prepare if args.phase == "prepare" else evaluate
    print(json.dumps(action(args.resources, args.prepared, args.reference, args.output), indent=2), flush=True)


if __name__ == "__main__":
    main()
