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
    prediction: torch.Tensor, truth: torch.Tensor, mask: torch.Tensor, arm: str
) -> torch.Tensor:
    """Identical masked waveform output; only the comparison target differs."""
    if prediction.shape != truth.shape or mask.shape != truth.shape[:-1] or mask.dtype != torch.bool:
        raise ValueError("misaligned prediction, target or mask")
    if not mask.any():
        raise ValueError("empty mask")
    predicted, actual = prediction[mask], truth[mask]
    if arm == "spectral":
        predicted = band_log_energy(predicted, BANDS)
        actual = band_log_energy(actual, BANDS)
    elif arm != "recon":
        raise ValueError(f"unknown training objective {arm}")
    return (predicted - actual).square().mean()


def plan_for_seed(
    n: int, seed: int, steps: int, batch: int, channels: int, patches: int
) -> list[tuple[torch.Tensor, torch.Tensor]]:
    if not 0 < batch <= n or steps <= 0 or channels * patches < 2:
        raise ValueError("invalid paired training schedule")
    g = torch.Generator().manual_seed(seed)
    tokens = channels * patches
    plan = []
    for _ in range(steps):
        indices = torch.randperm(n, generator=g)[:batch]
        ranks = torch.rand((batch, tokens), generator=g).argsort(dim=1)
        mask = (ranks < tokens // 2).reshape(batch, channels, patches)
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


def schedule_file(run: Path, seed: int, plan: list[tuple[torch.Tensor, torch.Tensor]]) -> str:
    path = run / f"seed-{seed}" / "paired_schedule.json"
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
        "protocol_sha256": sha256(PROTOCOL),
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
        loss = masked_objective(head(encoder(batch, mask=mask)), batch, mask, arm)
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


def training(run: Path, cfg: dict[str, Any]) -> None:
    x = torch.from_numpy(read_split(run, "train")["x"])
    spent = sum(read_json(f)["wall_s"] for f in run.glob("seed-*/*/trained.json"))
    stop = time.monotonic() + cfg["training_wall_cap_s"] - spent
    for seed in cfg["seeds"]:
        plan = plan_for_seed(len(x), seed, cfg["steps"], cfg["batch_size"], x.shape[1], x.shape[2])
        fingerprint = schedule_file(run, seed, plan)
        for arm in cfg["arms"]:
            train_arm(run, cfg, seed, arm, x, plan, fingerprint, stop)
    frozen = {
        f"seed-{s}/{a}/final.pt": read_json(run / f"seed-{s}" / a / "trained.json")["checkpoint_sha256"]
        for s in cfg["seeds"]
        for a in cfg["arms"]
    }
    if (run / "frozen.json").exists():
        if read_json(run / "frozen.json")["candidates"] != frozen:
            raise ValueError("frozen candidate mismatch")
        return
    write_json(
        run / "frozen.json", {"at": now(), "candidates": frozen, "protocol_sha256": sha256(PROTOCOL)}
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
        bundle = dict(
            inputs, subject_test=splits["test"]["subjects"], window_test=splits["test"]["windows"]
        )
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
            pt = statistics.predict_probe(fit, inputs["x_test"][:, j]).ravel()
            for i, (pid, wid) in enumerate(zip(splits["test"]["subjects"], splits["test"]["windows"])):
                truth = float(inputs["y_test"][i, j])
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
        seed_dir / "test_windows.csv",
        ("subject", "window"),
        list(zip(splits["test"]["subjects"], splits["test"]["windows"])),
    )
    write_json(seed_dir / "validation.json", valid)
    files = ["predictions.csv", "condition_predictions.csv", "test_windows.csv", "validation.json"] + [
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
