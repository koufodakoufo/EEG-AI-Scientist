"""Paired, CPU-only EEGMAT continuing-training pilot. Run from the formal checkout."""

from __future__ import annotations

import argparse
import csv
import io
import importlib.metadata
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

from eegfm.common import ROOT, append_jsonl, atomic_write, now, read_json, sha256, write_json
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
