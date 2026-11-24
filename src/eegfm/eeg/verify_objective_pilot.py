"""Recompute the frozen EEG objective pilot's metrics from paired predictions."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from eegfm.eeg.statistics import cluster_bootstrap_indices, interval, r2_columns


ARMS = ("init", "recon", "spectral")
TARGETS = ("occipital_alpha", "central_beta")
SEED = 20261124
RESAMPLES = 2000
Window = tuple[str, str]
ArmRows = dict[str, tuple[float, float]]


def _table(path: Path, required: set[str]) -> tuple[csv.DictReader, str]:
    data = path.read_bytes()
    table = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    fields = table.fieldnames or []
    if not required.issubset(fields) or len(fields) != len(set(fields)):
        raise ValueError(f"{path.name}: incomplete or duplicate column names")
    return table, hashlib.sha256(data).hexdigest()


def _window(row: dict[str, str]) -> Window:
    if None in row or any(value is None for value in row.values()):
        raise ValueError("CSV row width does not match the header")
    subject, window = row["subject"], row["window"]
    if not subject.strip() or not window.strip():
        raise ValueError("Missing subject or window identifier")
    return subject, window


def _predictions(path: Path, *, condition: bool = False) -> tuple[dict[str, dict[Window, ArmRows]], str]:
    required = {"subject", "window", "arm", "truth", "prediction"}
    if not condition:
        required.add("target")
    table, digest = _table(path, required)
    targets = ("condition",) if condition else TARGETS
    result: dict[str, dict[Window, ArmRows]] = {target: {} for target in targets}
    for row in table:
        key = _window(row)
        target = "condition" if condition else row["target"]
        arm = row["arm"]
        if target not in targets or arm not in ARMS:
            raise ValueError(f"{path.name}:{table.line_num}: unexpected target or arm")
        group = result[target].setdefault(key, {})
        if arm in group:
            raise ValueError(f"{path.name}:{table.line_num}: duplicate window / target / arm")
        truth, pred = float(row["truth"]), float(row["prediction"])
        if not math.isfinite(truth) or not math.isfinite(pred):
            raise ValueError(f"{path.name}:{table.line_num}: nonfinite truth or prediction")
        if condition and truth not in (0.0, 1.0):
            raise ValueError(f"{path.name}:{table.line_num}: expected binary condition label")
        group[arm] = truth, pred
    return result, digest


def _arrays(groups: dict[Window, ArmRows], keys: list[Window]) -> tuple[np.ndarray, np.ndarray]:
    if set(keys) != groups.keys():
        raise ValueError("Subjects/windows differ between frozen manifest, targets or condition file")
    y = np.empty(len(keys))
    pred = np.empty((len(keys), len(ARMS)))
    for i, key in enumerate(keys):
        group = groups[key]
        if set(ARMS) != group.keys():
            raise ValueError(f"Incomplete arms for window {key}")
        truths = {pair[0] for pair in group.values()}
        if len(truths) != 1:
            raise ValueError(f"Truth differs across arms for window {key}")
        y[i] = truths.pop()
        pred[i] = [group[arm][1] for arm in ARMS]
    return y, pred


def _nullable(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def _scores(values: np.ndarray) -> dict[str, Any]:
    init, recon, spectral = values
    return {
        "by_arm": {arm: _nullable(score) for arm, score in zip(ARMS, values)},
        "spectral_minus_recon": _nullable(spectral - recon),
        "recon_minus_init": _nullable(recon - init),
        "spectral_minus_init": _nullable(spectral - init),
    }


def _r2(y: np.ndarray, pred: np.ndarray) -> np.ndarray:
    return r2_columns(np.broadcast_to(y[:, None], pred.shape), pred)


def _ba(y: np.ndarray, pred: np.ndarray) -> np.ndarray:
    if np.unique(y).size != 2:
        return np.full(len(ARMS), np.nan)
    predicted = pred >= 0.5
    return ((~predicted[y == 0]).mean(axis=0) + predicted[y == 1].mean(axis=0)) / 2


def verify(predictions: Path, condition: Path | None = None, windows: Path | None = None) -> dict[str, Any]:
    groups, digest = _predictions(predictions)
    hashes = {"predictions_csv": digest}
    if windows is None:
        keys = sorted(groups[TARGETS[0]])
    else:
        table, hashes["expected_windows_csv"] = _table(windows, {"subject", "window"})
        keys = sorted(_window(row) for row in table)
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate window in expected test manifest")
    subjects = np.array([key[0] for key in keys])
    by_subject = {s: np.flatnonzero(subjects == s) for s in sorted(set(subjects.tolist()))}
    if len(by_subject) < 2:
        raise ValueError("Expected at least two participants for a paired subject bootstrap")
    samples = cluster_bootstrap_indices(subjects, seed=SEED, resamples=RESAMPLES)
    targets = {}
    for target, rows in groups.items():
        truth, predicted = _arrays(rows, keys)
        pooled = _r2(truth, predicted)
        if not np.isfinite(pooled).all():
            raise ValueError(f"Undefined pooled R2 for {target}")
        deltas = np.empty(RESAMPLES)
        for i, index in enumerate(samples):
            _, recon, spectral = _r2(truth[index], predicted[index])
            deltas[i] = spectral - recon
        targets[target] = {
            "pooled_r2": _scores(pooled),
            "spectral_minus_recon_percentile_ci95": interval(deltas),
            "defined_bootstrap_draws": int(np.isfinite(deltas).sum()),
            "by_subject_r2": {s: _scores(_r2(truth[ix], predicted[ix])) for s, ix in by_subject.items()},
        }
    result = {
        "input_sha256": hashes,
        "windows": len(keys),
        "subjects": len(by_subject),
        "windows_per_subject": {s: len(ix) for s, ix in by_subject.items()},
        "bootstrap": {"unit": "subject", "seed": SEED, "resamples": RESAMPLES},
        "targets": targets,
    }
    if condition is not None:
        cond_rows, hashes["condition_predictions_csv"] = _predictions(condition, condition=True)
        truth, predicted = _arrays(cond_rows["condition"], keys)
        if np.unique(truth).size != 2:
            raise ValueError("Condition BA requires both classes in the test set")
        result["secondary_condition_ba"] = {
            "threshold": 0.5,
            "pooled": _scores(_ba(truth, predicted)),
            "by_subject": {s: _scores(_ba(truth[ix], predicted[ix])) for s, ix in by_subject.items()},
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--condition", type=Path, help="Secondary pre/during-task prediction CSV")
    parser.add_argument("--windows", type=Path, help="Optional frozen test window inventory (subject,window)")
    parser.add_argument("--output", type=Path, help="Write JSON to a new file; defaults to stdout")
    args = parser.parse_args()
    result = verify(args.predictions, args.condition, args.windows)
    text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output is None:
        print(text)
    else:
        with args.output.open("x", encoding="utf-8") as out:
            print(text, file=out)


if __name__ == "__main__":
    main()
