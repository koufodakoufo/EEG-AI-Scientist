"""Paired, CPU-only EEGMAT continuing-training pilot. Run from the formal checkout."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import torch
from threadpoolctl import threadpool_limits

from eegfm.common import ROOT, append_jsonl, atomic_write, now, read_json, read_jsonl, sha256, write_json
from eegfm.eeg import data, statistics

PROTOCOL = ROOT / "tasks/masked_objective_eegmat/protocol.json"
RUNS = ROOT / ".local/research-renewal"
DEFAULT_RUN = RUNS / "masked-objective-eegmat-public-v1"
BANDS = ((1, 4), (4, 8), (8, 13))
TARGETS = ("occipital_alpha", "central_beta")
OCCIPITAL = (data.CHANNELS.index("EEG O1"), data.CHANNELS.index("EEG O2"))
CENTRAL = (data.CHANNELS.index("EEG C3"), data.CHANNELS.index("EEG C4"))


def band_log_energy(x: torch.Tensor, bands: tuple[tuple[int, int], ...]) -> torch.Tensor:
    """One-second EEG at 200 Hz. Return one log energy per frequency interval."""
    if x.shape[-1] != 200:
        raise ValueError("expected 200 samples per one-second patch")
    taper = torch.hann_window(200, dtype=x.dtype, device=x.device)
    spectrum = torch.fft.rfft((x - x.mean(dim=-1, keepdim=True)) * taper)
    power = spectrum.abs().square() / taper.sum().square()
    return torch.stack([(power[..., lo:hi].sum(dim=-1) + 1e-8).log() for lo, hi in bands], dim=-1)


def masked_objective(
    prediction: torch.Tensor, truth: torch.Tensor, mask: torch.Tensor, arm: str,
    *, spectral_mix: float | None = None, bands: tuple[tuple[int, int], ...] = BANDS,
) -> torch.Tensor:
    """Identical masked waveform output; only the comparison target differs."""
    if prediction.shape != truth.shape or mask.shape != truth.shape[:-1] or mask.dtype != torch.bool:
        raise ValueError("misaligned prediction, target or mask")
    if not mask.any():
        raise ValueError("empty mask")
    predicted, actual = prediction[mask], truth[mask]
    if spectral_mix is None:
        if arm not in {"recon", "spectral"}:
            raise ValueError(f"unknown training objective {arm}")
        spectral_mix = float(arm == "spectral")
    if spectral_mix == 0:
        return (predicted - actual).square().mean()
    spectral = (band_log_energy(predicted, bands) - band_log_energy(actual, bands)).square().mean()
    if spectral_mix == 1:
        return spectral
    waveform = (predicted - actual).square().mean()
    return (1 - spectral_mix) * waveform + spectral_mix * spectral


def plan_for_seed(
    n: int, seed: int, steps: int, batch: int, channels: int, patches: int, mask_fraction: float = 0.5
) -> list[tuple[torch.Tensor, torch.Tensor]]:
    if not 0 < batch <= n or steps <= 0 or channels * patches < 2:
        raise ValueError("invalid paired training schedule")
    g = torch.Generator().manual_seed(seed)
    tokens = channels * patches
    plan = []
    for _ in range(steps):
        indices = torch.randperm(n, generator=g)[:batch]
        ranks = torch.rand((batch, tokens), generator=g).argsort(dim=1)
        mask = (ranks < int(tokens * mask_fraction)).reshape(batch, channels, patches)
        plan.append((indices, mask))
    return plan


def resource_dir(config: dict[str, Any]) -> Path:
    """An existing private cache may be used without copying data or weights."""
    return Path(os.environ.get("EEGFM_EEGMAT_RESOURCES", ROOT / config["dataset_root"])).resolve()


def bindings(config: dict[str, Any]) -> dict[str, str]:
    paths = [
        PROTOCOL,
        Path(__file__),
        Path(data.__file__),
        Path(statistics.__file__),
    ]
    bound = {p.relative_to(ROOT).as_posix(): sha256(p) for p in paths}
    cache = resource_dir(config)
    for spec in data.MODEL_RESOURCES:
        bound["resources/" + spec.relative_path] = sha256(cache / spec.relative_path)
    return bound


def event(run: Path, action: str, **values: Any) -> None:
    append_jsonl(run / "trajectory.jsonl", {"action": action, **values})


@contextmanager
def exclusive(run: Path) -> Iterator[None]:
    """OS lock releases on process exit; previous completed stages stay reusable."""
    with (run / "execution.lock").open("a+b") as f:
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def prepare(run: Path, cfg: dict[str, Any]) -> None:
    if (run / "admission.json").exists():
        raise FileExistsError("run already admitted; use train or evaluate to continue")
    if (run / "protocol.json").exists():
        raise RuntimeError("incomplete previous admission; retain it and start a new run")
    files = bindings(cfg)
    weight = resource_dir(cfg) / "pretrained_weights.pth"
    if sha256(weight) != cfg["checkpoint_sha256"]:
        raise ValueError("initial checkpoint mismatch")
    shutil.copyfile(PROTOCOL, run / "protocol.json")
    shutil.copyfile(Path(__file__), run / "runner_snapshot.py")
    event(
        run,
        "protocol_frozen",
        sha256=sha256(PROTOCOL),
        parent=cfg["parent"],
        reason="available authorized CPU, authenticated weight and real EEG; choose paired objectives and unchanged baseline",
        discarded=[
            "CPU budget suffices",
            "single-source controlled comparison",
            "padding alone does not compare learning targets",
        ],
        normal_research=True,
        skill_promoted=False,
    )
    hashes = make_data(run, cfg, ("train", "validation"))
    batch = torch.from_numpy(read_split(run, "train")["x"][:1])
    encoder, head = load_model(cfg)
    encoder.eval()
    head.eval()
    _, mask = plan_for_seed(1, 0, 1, 1, batch.shape[1], batch.shape[2])[0]
    with torch.inference_mode():
        output = head(encoder(batch, mask=mask))
        if output.shape != batch.shape or not torch.isfinite(output).all():
            raise ValueError("real data smoke check failed")
        smoke = {arm: float(masked_objective(output, batch, mask, arm)) for arm in cfg["arms"]}
        if not np.isfinite(list(smoke.values())).all():
            raise ValueError("nonfinite smoke loss")
    event(
        run,
        "smoke_passed",
        training_split_only=True,
        input_shape=list(batch.shape),
        losses=smoke,
        optimizer_steps=0,
    )
    write_json(
        run / "admission.json",
        {
            "at": now(),
            "bindings": files,
            "prepared": hashes,
            "python": sys.version,
            "platform": platform.platform(),
            "device": "cpu",
            "threads": cfg["threads"],
            "gpu_hours": 0,
            "git_head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "packages": {
                k: importlib.metadata.version(k)
                for k in ("torch", "numpy", "scipy", "mne", "scikit-learn", "threadpoolctl")
            },
        },
    )
    event(run, "training_inputs_admitted", split_hashes=hashes)


def make_data(run: Path, cfg: dict[str, Any], splits: tuple[str, ...]) -> dict[str, str]:
    dest = run / ("evaluation_data" if "test" in splits else "development_data")
    data.prepare_eegmat(
        resource_dir(cfg),
        dest,
        allowed_parent=run,
        splits=splits,
        allow_test="test" in splits,
        max_windows=cfg["window_cap"],
    )
    return {
        f.relative_to(run).as_posix(): sha256(f)
        for split in splits
        for f in (dest / f"{split}.npz", dest / f"{split}.json")
    }


def read_split(run: Path, split: str) -> dict[str, np.ndarray]:
    dirname = "evaluation_data" if split == "test" else "development_data"
    with np.load(run / dirname / f"{split}.npz", allow_pickle=False) as z:
        if tuple(z["channels"]) != data.CHANNELS:
            raise ValueError("unexpected electrode order")
        return {
            "x": np.ascontiguousarray(z["x"][:, :19]),
            "y": z["y"],
            "subjects": z["subject_ids"],
            "windows": z["sample_ids"],
        }


def load_model(cfg: dict[str, Any]) -> tuple[torch.nn.Module, torch.nn.Module]:
    model = data.load_cbramod_model(resource_dir(cfg), threads=cfg["threads"], frozen=False)
    head = model.proj_out
    model.proj_out = torch.nn.Identity()
    return model, head


def check_admission(run: Path, cfg: dict[str, Any]) -> None:
    record = read_json(run / "admission.json")
    if (
        not record
        or sha256(run / "protocol.json") != sha256(PROTOCOL)
        or record["bindings"] != bindings(cfg)
    ):
        raise ValueError("protocol, input model, runner, or code has changed since admission")
    for path, expected in record["prepared"].items():
        if sha256(run / path) != expected:
            raise ValueError(f"changed input {path}")


def schedule_file(run: Path, seed: int, plan: list[tuple[torch.Tensor, torch.Tensor]],
                  filename: str = "paired_schedule.json") -> str:
    path = run / f"seed-{seed}" / filename
    value = [
        {
            "rows": ids.tolist(),
            "masked_positions": [m.flatten().nonzero().flatten().tolist() for m in mask],
        }
        for ids, mask in plan
    ]
    if path.exists() and read_json(path) != value:
        raise ValueError("schedule changed")
    if not path.exists():
        write_json(path, value)
    return sha256(path)


def train_arm(
    run: Path,
    cfg: dict[str, Any],
    seed: int,
    arm: str,
    x: torch.Tensor,
    plan: list[tuple[torch.Tensor, torch.Tensor]],
    schedule_hash: str,
    stop_at: float,
    *, objective: dict[str, Any] | None = None, protocol_path: Path = PROTOCOL,
) -> None:
    dest = run / f"seed-{seed}" / arm
    receipt = dest / "trained.json"
    if receipt.exists():
        if sha256(dest / "final.pt") != read_json(receipt)["checkpoint_sha256"]:
            raise ValueError("completed checkpoint changed")
        return
    dest.mkdir(parents=True, exist_ok=False)
    effective = {
        "seed": seed,
        "arm": arm,
        "initial_sha256": cfg["checkpoint_sha256"],
        "schedule_sha256": schedule_hash,
        "protocol_sha256": sha256(protocol_path),
        **{
            k: cfg[k]
            for k in (
                "steps",
                "batch_size",
                "lr",
                "weight_decay",
                "clip_norm",
                "threads",
                "optimizer",
                "loss",
            )
        },
    }
    if objective is not None:
        effective["objective"] = objective
    write_json(dest / "config.json", effective)
    event(run, "training_started", seed=seed, arm=arm, schedule_sha256=schedule_hash)
    wall, cpu = time.monotonic(), time.process_time()
    torch.manual_seed(seed)
    encoder, head = load_model(cfg)
    encoder.train()
    head.train()
    params = [p for layer in (encoder, head) for p in layer.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    torch.manual_seed(seed)
    for step, (indices, mask) in enumerate(plan, 1):
        if time.monotonic() >= stop_at or shutil.disk_usage(dest).free < 2 * 1024**3:
            raise RuntimeError("training wall or storage guard reached")
        batch = x[indices]
        optimizer.zero_grad(set_to_none=True)
        predicted = head(encoder(batch, mask=mask))
        if objective is None:
            loss = masked_objective(predicted, batch, mask, arm)
        else:
            loss = masked_objective(predicted, batch, mask, arm, spectral_mix=objective["spectral_mix"],
                                    bands=tuple(tuple(b) for b in objective["bands"]))
        if not torch.isfinite(loss):
            raise ValueError("nonfinite training loss")
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(params, cfg["clip_norm"], error_if_nonfinite=True)
        optimizer.step()
        append_jsonl(
            dest / "steps.jsonl",
            {
                "step": step,
                "loss": float(loss.detach()),
                "grad_norm_before_clip": float(norm),
                "examples": len(indices),
                "masked_tokens": int(mask.sum()),
                "wall_s": time.monotonic() - wall,
                "cpu_s": time.process_time() - cpu,
            },
        )
    pending = dest / "final.pending"
    torch.save(
        {
            "encoder": encoder.state_dict(),
            "head": head.state_dict(),
            "optimizer": optimizer.state_dict(),
            "step": step,
            "rng_after": torch.get_rng_state(),
            "config": effective,
        },
        pending,
    )
    pending.rename(dest / "final.pt")
    result = {
        "checkpoint_sha256": sha256(dest / "final.pt"),
        "step_log_sha256": sha256(dest / "steps.jsonl"),
        "config_sha256": sha256(dest / "config.json"),
        "steps": step,
        "trainable_parameters": sum(p.numel() for p in params),
        "wall_s": time.monotonic() - wall,
        "cpu_s": time.process_time() - cpu,
        "gpu_hours": 0,
    }
    write_json(receipt, result)
    event(run, "training_complete", arm=arm, seed=seed, **result)


def training(run: Path, cfg: dict[str, Any], *, objectives: dict[str, dict[str, Any]] | None = None,
             protocol_path: Path = PROTOCOL) -> None:
    x = torch.from_numpy(read_split(run, "train")["x"])
    spent = sum(read_json(f)["wall_s"] for f in run.glob("seed-*/*/trained.json"))
    stop = time.monotonic() + cfg["training_wall_cap_s"] - spent
    for seed in cfg["seeds"]:
        for arm in cfg["arms"]:
            objective = objectives[arm] if objectives else None
            fraction = objective["mask_fraction"] if objective else 0.5
            plan = plan_for_seed(len(x), seed, cfg["steps"], cfg["batch_size"], x.shape[1], x.shape[2], fraction)
            filename = f"schedule-{arm}.json" if objective else "paired_schedule.json"
            fingerprint = schedule_file(run, seed, plan, filename)
            arm_cfg = {**cfg, "lr": objective["lr"]} if objective else cfg
            train_arm(run, arm_cfg, seed, arm, x, plan, fingerprint, stop,
                      objective=objective, protocol_path=protocol_path)
    frozen = {
        f"seed-{s}/{a}/final.pt": read_json(run / f"seed-{s}" / a / "trained.json")["checkpoint_sha256"]
        for s in cfg["seeds"]
        for a in cfg["arms"]
    }
    if (run / "frozen.json").exists():
        existing = read_json(run / "frozen.json")
        if existing["candidates"] != frozen or existing["protocol_sha256"] != sha256(protocol_path):
            raise ValueError("frozen candidate mismatch")
        return
    write_json(
        run / "frozen.json", {"at": now(), "candidates": frozen, "protocol_sha256": sha256(protocol_path)}
    )
    event(run, "all_candidates_frozen", candidates=frozen)


@torch.inference_mode()
def representations(
    encoder: torch.nn.Module, split: dict[str, np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    encoder.eval()
    for index in range(0, len(split["x"]), 4):
        x = torch.from_numpy(split["x"][index : index + 4])
        z = encoder(x)
        xs.append(
            torch.stack(
                [z[:, OCCIPITAL].mean((1, 2)), z[:, CENTRAL].mean((1, 2)), z.mean((1, 2))], dim=1
            ).numpy()
        )
        alpha = band_log_energy(x[:, OCCIPITAL], ((8, 13),)).mean((1, 2, 3))
        beta = band_log_energy(x[:, CENTRAL], ((13, 30),)).mean((1, 2, 3))
        condition = torch.from_numpy(split["y"][index : index + 4]).to(alpha)
        ys.append(torch.stack([alpha, beta, condition], dim=1).numpy())
    return np.concatenate(xs), np.concatenate(ys)


def write_csv(path: Path, fields: tuple[str, ...], rows: list[tuple[Any, ...]]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(fields)
    writer.writerows(rows)
    contents = buffer.getvalue()
    if path.exists():
        if path.read_text(encoding="utf-8") != contents:
            raise ValueError(f"existing evidence differs: {path.name}")
    else:
        atomic_write(path, contents)


def evaluate_seed(
    run: Path,
    cfg: dict[str, Any],
    seed: int,
    splits: dict[str, dict[str, np.ndarray]],
    frozen: dict[str, str],
    *, evaluation_split: str = "test",
) -> None:
    seed_dir = run / f"seed-{seed}"
    if (seed_dir / "evaluated.json").exists():
        saved = read_json(seed_dir / "evaluated.json")
        if any(sha256(seed_dir / p) != h for p, h in saved["artifacts"].items()):
            raise ValueError("existing evaluation artifacts changed")
        return
    predictions: list[tuple[Any, ...]] = []
    conditions: list[tuple[Any, ...]] = []
    valid: dict[str, Any] = {}
    for arm in ["init", *cfg["arms"]]:
        encoder, _ = load_model(cfg)
        dest = seed_dir / arm
        dest.mkdir(exist_ok=True)
        if arm != "init":
            relative = f"seed-{seed}/{arm}/final.pt"
            if sha256(run / relative) != frozen[relative]:
                raise ValueError("checkpoint failed frozen hash check")
            state = torch.load(run / relative, map_location="cpu", weights_only=True)
            encoder.load_state_dict(state["encoder"], strict=True)
        arrays = {part: representations(encoder, block) for part, block in splits.items()}
        inputs = {
            f"{prefix}_{part}": array
            for part, pair in arrays.items()
            for prefix, array in zip(("x", "y"), pair)
        }
        archive = dest / "readout_inputs.npz"
        assessment = splits[evaluation_split]
        bundle = {**inputs, f"subject_{evaluation_split}": assessment["subjects"],
                  f"window_{evaluation_split}": assessment["windows"]}
        if archive.exists():
            with np.load(archive, allow_pickle=False) as prior:
                if set(prior.files) != set(bundle) or any(
                    not np.array_equal(prior[k], v) for k, v in bundle.items()
                ):
                    raise ValueError("partial evaluation differs from current recomputation")
        else:
            pending = dest / "readout_inputs.pending"
            with pending.open("wb") as h:
                np.savez(h, **bundle)
            pending.rename(archive)
        valid[arm] = {}
        for j, target in enumerate([*TARGETS, "condition"]):
            fit = statistics.fit_probe(
                inputs["x_train"][:, j], inputs["y_train"][:, j : j + 1], alpha=cfg["ridge_alpha"]
            )
            yv = inputs["y_validation"][:, j : j + 1]
            pv = statistics.predict_probe(fit, inputs["x_validation"][:, j])
            valid[arm][target] = (
                float(statistics.r2_columns(yv, pv)[0])
                if j < 2
                else float(np.mean([((pv[yv == k] >= 0.5) == bool(k)).mean() for k in (0, 1)]))
            )
            pt = pv.ravel() if evaluation_split == "validation" else statistics.predict_probe(
                fit, inputs[f"x_{evaluation_split}"][:, j]).ravel()
            for i, (pid, wid) in enumerate(zip(assessment["subjects"], assessment["windows"])):
                truth = float(inputs[f"y_{evaluation_split}"][i, j])
                if j < 2:
                    predictions.append((pid, wid, arm, target, truth, float(pt[i])))
                else:
                    conditions.append((pid, wid, arm, int(truth), float(pt[i])))
    write_csv(
        seed_dir / "predictions.csv",
        ("subject", "window", "arm", "target", "truth", "prediction"),
        predictions,
    )
    write_csv(
        seed_dir / "condition_predictions.csv",
        ("subject", "window", "arm", "truth", "prediction"),
        conditions,
    )
    write_csv(
        seed_dir / f"{evaluation_split}_windows.csv",
        ("subject", "window"),
        list(zip(splits[evaluation_split]["subjects"], splits[evaluation_split]["windows"])),
    )
    write_json(seed_dir / "validation.json", valid)
    files = ["predictions.csv", "condition_predictions.csv", f"{evaluation_split}_windows.csv", "validation.json"] + [
        f"{a}/readout_inputs.npz" for a in ["init", *cfg["arms"]]
    ]
    write_json(
        seed_dir / "evaluated.json",
        {"at": now(), "artifacts": {name: sha256(seed_dir / name) for name in files}},
    )
    event(run, "evaluated", seed=seed, rows=len(predictions), condition_rows=len(conditions))


def evaluation(run: Path, cfg: dict[str, Any]) -> None:
    freeze = read_json(run / "frozen.json")
    if not freeze or freeze["protocol_sha256"] != sha256(PROTOCOL):
        raise ValueError("evaluation requires all paired candidates frozen")
    expected = {f"seed-{s}/{arm}/final.pt" for s in cfg["seeds"] for arm in cfg["arms"]}
    if set(freeze["candidates"]) != expected or any(
        sha256(run / p) != v for p, v in freeze["candidates"].items()
    ):
        raise ValueError("incomplete or changed frozen candidates")
    if not (run / "evaluation_inputs.json").exists():
        hashes = make_data(run, cfg, ("test",))
        write_json(run / "evaluation_inputs.json", hashes)
        event(run, "evaluation_inputs_opened", freeze_sha256=sha256(run / "frozen.json"))
    for p, v in read_json(run / "evaluation_inputs.json").items():
        if sha256(run / p) != v:
            raise ValueError("test split hash changed")
    splits = {s: read_split(run, s) for s in ("train", "validation", "test")}
    statistics.validate_partitions({s: z["subjects"] for s, z in splits.items()})
    for seed in cfg["seeds"]:
        evaluate_seed(run, cfg, seed, splits, freeze["candidates"])


def validate_research_plan(plan: dict[str, Any]) -> None:
    """Accept only bounded numeric choices; never execute researcher-provided code."""
    if not isinstance(plan, dict) or plan.get("primary") not in (*TARGETS, "condition"):
        raise ValueError("primary must name a supported validation endpoint")
    steps = plan.get("steps")
    if type(steps) is not int or not 8 <= steps <= 32:
        raise ValueError("require 8..32 steps per arm")
    arms = plan.get("arms")
    if not isinstance(arms, list) or len(arms) != 2:
        raise ValueError("exactly two arms, A and B, are required")
    treatments = []
    for name, arm in zip(("A", "B"), arms):
        if not isinstance(arm, dict) or arm.get("name") != name:
            raise ValueError("arms must be named A and B in order")
        for key, low, high in (("spectral_mix", 0, 1), ("mask_fraction", .1, .9), ("lr", 1e-7, 1e-3)):
            value = arm.get(key)
            if type(value) not in (int, float) or not low <= value <= high:
                raise ValueError(f"{key} must be numeric and in [{low}, {high}]")
        bands = arm.get("bands")
        if not isinstance(bands, list) or len(bands) > 8 or (arm["spectral_mix"] > 0 and not bands):
            raise ValueError("supply 1..8 frequency bands for spectral supervision")
        end = 1
        for band in bands:
            if (not isinstance(band, list) or len(band) != 2 or any(type(v) is not int for v in band)
                    or not end <= band[0] < band[1] <= 100):
                raise ValueError("bands must be ordered, disjoint integer [lo, hi) intervals within 1..100")
            end = band[1]
        treatments.append((arm["spectral_mix"], bands if arm["spectral_mix"] else [],
                           int(95 * arm["mask_fraction"]), arm["lr"]))
    if treatments[0] == treatments[1]:
        raise ValueError("A and B must differ in at least one effective training setting")


def _research_scores(seed_dir: Path) -> dict[str, Any]:
    """Re-score paired saved predictions by participant, independently of model fitting."""
    from eegfm.eeg.verify_objective_pilot import _r2, _ba
    arms = ("init", "A", "B")
    with (seed_dir / "validation_windows.csv").open(encoding="utf-8") as stream:
        keys = [(r["subject"], r["window"]) for r in csv.DictReader(stream)]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate validation window")
    index = {key: i for i, key in enumerate(keys)}
    n = len(keys)
    samples = statistics.cluster_bootstrap_indices(np.array([s for s, _ in keys]), resamples=2000, seed=20261124)
    result = {}
    for filename, targets in (("predictions.csv", TARGETS), ("condition_predictions.csv", ("condition",))):
        with (seed_dir / filename).open(encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        for target in targets:
            truths, preds = np.full((n, 3), np.nan), np.full((n, 3), np.nan)
            for row in rows:
                if row.get("target", "condition") == target:
                    i, j = index[row["subject"], row["window"]], arms.index(row["arm"])
                    if np.isfinite(preds[i, j]):
                        raise ValueError("duplicate prediction")
                    truths[i, j], preds[i, j] = float(row["truth"]), float(row["prediction"])
            if (not np.isfinite(truths).all() or not np.isfinite(preds).all()
                    or not (truths == truths[:, :1]).all()):
                raise ValueError("incomplete or inconsistent paired predictions")
            y = truths[:, 0]
            scorer = _ba if target == "condition" else _r2
            point = scorer(y, preds)
            draws = np.array([scorer(y[ix], preds[ix]) for ix in samples])
            delta = draws[:, 2] - draws[:, 1]
            if not np.isfinite(point).all() or not np.isfinite(delta).all():
                raise ValueError("undefined evaluation or bootstrap estimate")
            result[target] = {"by_arm": dict(zip(arms, map(float, point))),
                              "B_minus_A": float(point[2] - point[1]),
                              "A_minus_init": float(point[1] - point[0]), "B_minus_init": float(point[2] - point[0]),
                              "B_minus_A_ci95": statistics.interval(delta), "metric": "BA" if target == "condition" else "R2"}
    return result


def execute_research_plan(run: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Trusted CPU service for an actor's already frozen proposal; ordinary exploratory validation."""
    validate_research_plan(plan)
    protocol = run / "plan.json"
    if read_json(protocol) != plan:
        raise ValueError("research proposal must be frozen before execution")
    experiment = run / "experiment"
    experiment.mkdir(exist_ok=True)
    cfg = read_json(PROTOCOL)
    cfg.update(steps=plan["steps"], arms=["A", "B"], seeds=[42, 43], threads=4, training_wall_cap_s=1800,
               loss="(1-spectral_mix)*masked-waveform MSE + spectral_mix*masked-log-band-energy MSE")
    if os.environ.get("EEGFM_EEGMAT_RESOURCES"):
        cfg["dataset_root"] = os.environ["EEGFM_EEGMAT_RESOURCES"]
    objectives = {arm["name"]: arm for arm in plan["arms"]}
    with exclusive(experiment), threadpool_limits(limits=4):
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        admission = experiment / "admission.json"
        identity = {"plan_sha256": sha256(protocol), "sources": bindings(cfg)}
        if not admission.exists():
            if (experiment / "development_data").exists():
                raise RuntimeError("incomplete preparation retained; inspect before a new execution")
            prepared = make_data(experiment, cfg, ("train", "validation"))
            write_json(admission, {"at": now(), **identity, "prepared": prepared})
        receipt = read_json(admission)
        if any(receipt[k] != v for k, v in identity.items()) or any(
            sha256(experiment / p) != h for p, h in receipt["prepared"].items()
        ):
            raise ValueError("admitted proposal, code, or EEG inputs changed")
        training(experiment, cfg, objectives=objectives, protocol_path=protocol)
        frozen = read_json(experiment / "frozen.json")["candidates"]
        splits = {s: read_split(experiment, s) for s in ("train", "validation")}
        counts = statistics.validate_partitions({s: block["subjects"] for s, block in splits.items()})
        result = {"plan_sha256": identity["plan_sha256"], "primary": plan["primary"], "seeds": {},
                  "participants": counts, "windows": {s: len(b["x"]) for s,b in splits.items()},
                  "assessment": "known EEGMAT validation people; exploratory, no historical test used",
                  "uncertainty": "2000 paired participant bootstrap draws, conditioned on fitted models; seeds share people",
                  "gpu_hours": 0, "steps_per_arm_seed": cfg["steps"]}
        for seed in cfg["seeds"]:
            evaluate_seed(experiment, cfg, seed, splits, frozen, evaluation_split="validation")
            seed_dir = experiment / f"seed-{seed}"
            cost = {a: {k: v for k,v in read_json(seed_dir / a / "trained.json").items()
                        if k in ("steps", "wall_s", "cpu_s")} for a in cfg["arms"]}
            result["seeds"][str(seed)] = {"metrics": _research_scores(seed_dir), "training_cost_by_arm": cost}
        return result


def validate_diagnostic_plan(plan: dict, parent_plan: dict) -> None:
    """Only replay the paired four-band contrast that this diagnostic tests."""
    validate_research_plan(parent_plan)
    a, b = parent_plan["arms"]
    if (a["spectral_mix"] != 1 or b["spectral_mix"] != 1 or a["lr"] != b["lr"]
            or a["mask_fraction"] != b["mask_fraction"] or len(a["bands"]) != 4
            or len(b["bands"]) != 4 or a["bands"][:3] != b["bands"][:3]
            or a["bands"][3] == b["bands"][3] or parent_plan["steps"] > 24):
        raise ValueError("diagnostic needs a paired pure spectral four-band replacement, at most 24 steps")
    steps = plan.get("measure_steps")
    if (plan.get("action") != "diagnose" or not isinstance(steps, list) or not 1 <= len(steps) <= 4
            or any(type(s) is not int or not 1 <= s <= parent_plan["steps"] for s in steps)
            or steps != sorted(set(steps))):
        raise ValueError("measure_steps must contain 1..4 distinct increasing parent step numbers")


def _angle(x: torch.Tensor, y: torch.Tensor) -> float | None:
    norm = x.norm() * y.norm()
    return float(torch.dot(x, y) / norm) if norm > 0 else None


def _band_gradients(predicted, batch, mask, bands, parameters):
    """Observe the existing forward pass; autograd.grad leaves parameter .grad untouched."""
    target = band_log_energy(batch[mask], bands)
    losses = (band_log_energy(predicted[mask], bands) - target).square().mean(0)
    grads = []
    for loss in losses.unbind():
        g = torch.autograd.grad(loss, parameters, retain_graph=True, allow_unused=True)
        grads.append(torch.cat([(v if v is not None else torch.zeros_like(p)).reshape(-1)
                                for p, v in zip(parameters, g)]).double())
    common = sum(grads[:3])
    common_square = torch.dot(common, common)
    norms = [float(g.norm()) for g in grads]
    details = {
        "masked_tokens": len(target), "target_mean": target.mean(0).tolist(),
        "target_var": target.var(0, unbiased=False).tolist(),
        "target_q10_q50_q90": torch.quantile(target, target.new_tensor([.1, .5, .9]), dim=0).T.tolist(),
        "band_mse": losses.detach().tolist(), "raw_band_encoder_grad_norm": norms,
        "pairwise_grad_cos": [_angle(grads[i], grads[j]) for i in range(4) for j in range(i+1, 4)],
        "shared_three_sum_norm": float(common.norm()), "fourth_vs_shared_cos": _angle(grads[3], common),
        "fourth_opposing_fraction": float(-torch.dot(grads[3], common)/common_square) if common_square > 0 else None,
    }
    return details, common + grads[3]


def _state_identical(a, b) -> bool:
    if isinstance(a, torch.Tensor):
        return isinstance(b, torch.Tensor) and a.dtype == b.dtype and torch.equal(a, b)
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(_state_identical(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return type(a) is type(b) and len(a) == len(b) and all(_state_identical(x, y) for x, y in zip(a, b))
    return a == b


def _diagnose_arm(src, seed, arm, cfg, x, schedule, measure, deadline):
    """Replay the original AdamW path and compare every step, then verify the terminal state."""
    recorded = read_jsonl(src / "steps.jsonl")
    if len(recorded) != len(schedule) or len(schedule) != cfg["steps"]:
        raise ValueError("parent schedule or step log length mismatch")
    torch.manual_seed(seed)
    encoder, head = load_model(cfg)
    encoder.train()
    head.train()
    enc = [p for p in encoder.parameters() if p.requires_grad]
    params = enc + [p for p in head.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    bands = tuple(tuple(b) for b in cfg["objective"]["bands"])
    torch.manual_seed(seed)
    observations = []
    for step, (entry, reference) in enumerate(zip(schedule, recorded), 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("diagnostic wall budget reached")
        batch = x[entry["rows"]]
        mask = torch.zeros(batch.shape[:-1], dtype=torch.bool)
        for row, positions in zip(mask.flatten(1), entry["masked_positions"], strict=True):
            row[positions] = True
        opt.zero_grad(set_to_none=True)
        prediction = head(encoder(batch, mask=mask))
        loss = masked_objective(prediction, batch, mask, arm, spectral_mix=1, bands=bands)
        if step in measure:
            rng = torch.get_rng_state()
            observation, grad_sum = _band_gradients(prediction, batch, mask, bands, enc)
            if not torch.equal(rng, torch.get_rng_state()):
                raise ValueError("diagnostic consumed training randomness")
            before = torch.nn.utils.parameters_to_vector(enc).detach()
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(params, cfg["clip_norm"], error_if_nonfinite=True)
        if (reference["step"] != step or reference["loss"] != loss.detach().item()
                or reference["grad_norm_before_clip"] != norm.item() or reference["masked_tokens"] != int(mask.sum())
                or reference["examples"] != len(batch)):
            raise ValueError(f"parent numerical trajectory mismatch at seed {seed}, arm {arm}, step {step}")
        if step in measure:
            after_clip = float(torch.linalg.vector_norm(torch.stack([
                torch.linalg.vector_norm(p.grad, dtype=torch.float64) for p in params if p.grad is not None
            ])))
        opt.step()
        if step in measure:
            update = (torch.nn.utils.parameters_to_vector(enc).detach() - before).double()
            clip = float((cfg["clip_norm"] / (norm + 1e-6)).clamp(max=1))
            observation.update(step=step, whole_grad_before_clip=float(norm), whole_grad_after_clip=after_clip,
                               clip_multiplier=clip, actual_encoder_update_norm=float(update.norm()),
                               update_vs_descent_cos=_angle(update, -grad_sum),
                               clipped_weighted_band_grad_norm=[v*clip/len(bands)
                                                                for v in observation["raw_band_encoder_grad_norm"]])
            observations.append(observation)
    state = torch.load(src / "final.pt", map_location="cpu", weights_only=True)
    if (state["step"] != len(recorded) or state["config"] != read_json(src / "config.json")
            or not _state_identical(encoder.state_dict(), state["encoder"])
            or not _state_identical(head.state_dict(), state["head"])
            or not _state_identical(opt.state_dict(), state["optimizer"])
            or not torch.equal(torch.get_rng_state(), state["rng_after"])):
        raise ValueError("replayed encoder, head, optimizer, RNG or config differs from frozen checkpoint")
    return observations


def _diagnostic_worker() -> None:
    """Standalone CPU process with a fresh native numerical runtime for exactly one trajectory."""
    request = json.load(sys.stdin)
    exp = Path(request["experiment"])
    seed, arm = request["seed"], request["arm"]
    src = exp / f"seed-{seed}" / arm
    cfg = {**read_json(PROTOCOL), **read_json(src / "config.json")}
    with threadpool_limits(limits=4):
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        x = torch.from_numpy(read_split(exp, "train")["x"])
        rows = _diagnose_arm(src, seed, arm, cfg, x, read_json(src.parent / f"schedule-{arm}.json"),
                             request["measure"], time.monotonic() + request["remaining_s"])
    print(json.dumps({"rows": rows, "cpu_s": time.process_time()}, allow_nan=False), flush=True)


def _arm_process(exp, seed, arm, measure, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("diagnostic wall budget reached")
    cmd = [sys.executable, "-B", "-X", "faulthandler", "-c",
           "from eegfm.eeg.objective_pilot import _diagnostic_worker; _diagnostic_worker()"]
    env = {**os.environ, "OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4",
           "OPENBLAS_NUM_THREADS": "4", "CUDA_VISIBLE_DEVICES": "-1", "PYTHONPATH": str(ROOT / "src")}
    request = {"experiment": str(exp.resolve()), "seed": seed, "arm": arm, "measure": measure,
               "remaining_s": remaining}
    # Leave stderr on the parent's executor.log, including any native crash traceback.
    completed = subprocess.run(cmd, input=json.dumps(request), stdout=subprocess.PIPE, text=True,
                               env=env, cwd=ROOT, timeout=remaining, check=True)
    return json.loads(completed.stdout)


def _record_digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def execute_band_diagnostic(run: Path, plan: dict, parent: Path, cpu_threads: int = 4, *,
                            isolated_arms: bool = False) -> dict:
    """Read only the parent's training inputs and log replay; no validation/test data or new weights."""
    parent_plan = read_json(parent / "plan.json")
    validate_diagnostic_plan(plan, parent_plan)
    if (cpu_threads != 4 or run.resolve() == parent.resolve() or read_json(run / "plan.json") != plan):
        raise ValueError("diagnostic needs a separate frozen episode and the original four CPU threads")
    exp = parent / "experiment"
    source, frozen = read_json(exp / "admission.json"), read_json(exp / "frozen.json")
    parent_hash = sha256(parent / "plan.json")
    if source["plan_sha256"] != parent_hash or frozen["protocol_sha256"] != parent_hash:
        raise ValueError("parent evidence does not match frozen plan")
    start, cpu_start = time.monotonic(), time.process_time()
    deadline = start + min(600, int(os.environ.get("EEGFM_DIAGNOSTIC_WALL_S", "600")))
    cfg = read_json(PROTOCOL)
    live = bindings(cfg)
    runner_name = Path(__file__).relative_to(ROOT).as_posix()
    if any(live.get(k) != v for k, v in source["sources"].items() if k != runner_name):
        raise ValueError("parent model, resources, protocol or supporting code changed")
    train_file = "development_data/train.npz"
    if sha256(exp / train_file) != source["prepared"][train_file]:
        raise ValueError("parent training data hash mismatch")
    block = read_split(exp, "train")
    x = torch.from_numpy(block["x"])
    evidence = {"plan_sha256": sha256(run / "plan.json"), "parent_plan_sha256": parent_hash,
                "parent_frozen_sha256": sha256(exp / "frozen.json"), "admission_sha256": sha256(exp / "admission.json"),
                "train_sha256": source["prepared"][train_file], "original_runner_sha256": source["sources"][runner_name],
                "diagnostic_runner_sha256": live[runner_name], "parent_artifacts": {}}
    reports = {}
    child_cpu = 0.0
    cache = run / ".band-replay-progress.json"
    progress = read_json(cache, {}) if isolated_arms else {}
    verified = {e["sha256"] for e in read_jsonl(run / "trajectory.jsonl")
                if e.get("action") == "diagnostic_arm_verified"}
    with threadpool_limits(limits=cpu_threads):
        torch.set_num_threads(cpu_threads)
        torch.use_deterministic_algorithms(True)
        for seed in (42, 43):
            records = {}
            paired_schedule = None
            for outcome in parent_plan["arms"]:
                arm = outcome["name"]
                subdir = f"seed-{seed}/{arm}"
                src = exp / subdir
                config, receipt = read_json(src / "config.json"), read_json(src / "trained.json")
                schedule_path = src.parent / f"schedule-{arm}.json"
                hashes = {n: sha256(src / n) for n in ("final.pt", "config.json", "steps.jsonl", "trained.json")}
                hashes["schedule"] = sha256(schedule_path)
                evidence["parent_artifacts"][subdir] = hashes
                if (hashes["final.pt"] != frozen["candidates"][subdir + "/final.pt"]
                        or hashes["final.pt"] != receipt["checkpoint_sha256"] or hashes["config.json"] != receipt["config_sha256"]
                        or hashes["steps.jsonl"] != receipt["step_log_sha256"] or hashes["schedule"] != config["schedule_sha256"]
                        or config["protocol_sha256"] != parent_hash or config["initial_sha256"] != cfg["checkpoint_sha256"]
                        or config["objective"] != outcome or config["threads"] != cpu_threads or config["seed"] != seed
                        or config["arm"] != arm or config["steps"] != parent_plan["steps"] or config["lr"] != outcome["lr"]):
                    raise ValueError("parent checkpoint, config, schedule or log differs from admitted contrast")
                if paired_schedule is not None and paired_schedule != hashes["schedule"]:
                    raise ValueError("arms did not share windows and mask positions")
                paired_schedule = hashes["schedule"]
                print(f"replaying seed {seed} arm {arm}", flush=True)
                if isolated_arms:
                    identity = _record_digest({**evidence, "parent_artifacts": {subdir: hashes}})
                    if subdir in progress:
                        entry = progress[subdir]
                        if entry["identity"] != identity or _record_digest(entry) not in verified:
                            raise ValueError("diagnostic progress binding or verified receipt changed")
                    else:
                        completed = _arm_process(exp, seed, arm, plan["measure_steps"], deadline)
                        entry = {"identity": identity, "result": completed}
                        event(run, "diagnostic_arm_verified", seed=seed, arm=arm, sha256=_record_digest(entry))
                        progress[subdir] = entry
                        write_json(cache, progress)
                    records[arm] = entry["result"]["rows"]
                    child_cpu += entry["result"]["cpu_s"]
                else:
                    records[arm] = _diagnose_arm(src, seed, arm, {**cfg, **config}, x, read_json(schedule_path),
                                                  plan["measure_steps"], deadline)
                print(f"verified seed {seed} arm {arm} against frozen checkpoint", flush=True)
            reports[str(seed)] = records
    if time.monotonic() > deadline:
        raise TimeoutError("diagnostic wall budget reached")
    return {"action": "diagnose", "parent_plan_sha256": parent_hash, "plan_sha256": evidence["plan_sha256"],
            "measure_steps": plan["measure_steps"], "bands": {a["name"]: a["bands"] for a in parent_plan["arms"]},
            "training_scope": {"windows": len(x), "participants": len(np.unique(block["subjects"])),
                               "unit": "masked channel x one-second patch in one training batch; descriptive"},
            "definitions": "Band arrays in listed order. Pair cosines 12,13,14,23,24,34. Population variance and "
                           "quantiles of target log energies. Raw encoder gradients are per single-band MSE; clipped "
                           "contributions include the 1/4 objective weight and joint encoder/head clipping factor. "
                           "fourth_opposing_fraction = -dot(g4, g123)/||g123||^2. Update cosine compares "
                           "the actual AdamW encoder step with the negative sum of raw gradients.",
            "checkpoints_reproduced": 4, "max_step_loss_error": 0, "max_step_grad_error": 0,
            "gpu_hours": 0, "cpu_threads": cpu_threads, "wall_s": time.monotonic() - start,
            "cpu_s": time.process_time() - cpu_start + child_cpu, "source_bindings": evidence, "by_seed_arm": reports}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "train", "evaluate"))
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    args = parser.parse_args()
    run = args.run.resolve()
    if run.parent != RUNS.resolve():
        raise ValueError("use a new direct child of the private research run directory")
    cfg = read_json(PROTOCOL)
    run.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(cfg["threads"])
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    with exclusive(run), threadpool_limits(limits=cfg["threads"]):
        wall, cpu = time.monotonic(), time.process_time()
        try:
            if args.stage == "prepare":
                prepare(run, cfg)
            else:
                check_admission(run, cfg)
                if args.stage == "train":
                    training(run, cfg)
                else:
                    evaluation(run, cfg)
        except BaseException as exc:
            event(run, "failed", stage=args.stage, error=repr(exc), wall_s=time.monotonic() - wall)
            raise
        event(
            run,
            "stage_complete",
            stage=args.stage,
            wall_s=time.monotonic() - wall,
            cpu_s=time.process_time() - cpu,
        )
        print(f"{args.stage} complete: {run}")


if __name__ == "__main__":
    main()
