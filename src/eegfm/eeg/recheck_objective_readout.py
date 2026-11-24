"""Independently refit the objective pilot's linear readouts from saved features."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np

from eegfm.eeg.verify_objective_pilot import ARMS, TARGETS, _predictions


READOUTS = (*TARGETS, "condition")
ALPHA = 100.0
TOLERANCE = 1e-8


def _features_and_targets(archive, split: str) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(archive[f"x_{split}"], dtype=np.float64)
    y = np.asarray(archive[f"y_{split}"], dtype=np.float64)
    if x.ndim != 3 or not len(x) or x.shape[1:] != (3, 200) or y.shape != x.shape[:2]:
        raise ValueError(f"{split}: expected features [N,3,200] and targets [N,3] with N>0")
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError(f"{split}: non-finite readout inputs")
    if not np.isin(y[:, 2], [0.0, 1.0]).all():
        raise ValueError(f"{split}: non-binary condition label")
    return x, y


def _ridge_prediction(train: np.ndarray, y_train: np.ndarray, test: np.ndarray) -> np.ndarray:
    x_mean = train.mean(axis=0)
    x_std = train.std(axis=0)
    x_scale = np.where(x_std <= 1e-12, 1.0, x_std)
    y_mean = y_train.mean()
    y_std = y_train.std()
    y_scale = 1.0 if y_std <= 1e-12 else y_std
    # Filtering singular values solves the penalized least-squares problem
    # without constructing the matrix of feature cross-products.
    u, singular, vt = np.linalg.svd((train - x_mean) / x_scale, full_matrices=False)
    direction = (singular / (singular**2 + ALPHA)) * (u.T @ ((y_train - y_mean) / y_scale))
    return (((test - x_mean) / x_scale) @ vt.T @ direction) * y_scale + y_mean


def _ids(array: np.ndarray, n: int) -> list[str]:
    if array.shape != (n,) or array.dtype.kind not in "USiu":
        raise ValueError("Expected one text or integer identifier per test row")
    return array.astype(str).tolist()


def recheck(seed_dir: Path) -> dict:
    reg, reg_hash = _predictions(seed_dir / "predictions.csv")
    condition, cond_hash = _predictions(seed_dir / "condition_predictions.csv", condition=True)
    tables = {**reg, **condition}
    keys = set(reg[TARGETS[0]])
    if not keys:
        raise ValueError("Empty predictions")
    for table in tables.values():
        if table.keys() != keys or any(row.keys() != set(ARMS) for row in table.values()):
            raise ValueError("CSV arms or test windows differ between targets")
        if any(len({value[0] for value in row.values()}) != 1 for row in table.values()):
            raise ValueError("CSV truth differs between arms")
    arms = {}
    for arm in ARMS:
        path = seed_dir / arm / "readout_inputs.npz"
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
            x_train, y_train = _features_and_targets(archive, "train")
            x_test, y_test = _features_and_targets(archive, "test")
            order = list(zip(_ids(archive["subject_test"], len(x_test)),
                             _ids(archive["window_test"], len(x_test))))
        if set(order) != keys or len(order) != len(keys):
            raise ValueError(f"{arm}: feature windows differ from the paired CSV windows")
        errors = {}
        for j, target in enumerate(READOUTS):
            expected = np.array([tables[target][key][arm] for key in order])
            if not np.allclose(y_test[:, j], expected[:, 0], rtol=TOLERANCE, atol=TOLERANCE):
                raise ValueError(f"{arm}/{target}: saved test labels differ from CSV")
            fitted = _ridge_prediction(x_train[:, j], y_train[:, j], x_test[:, j])
            delta = float(np.max(np.abs(fitted - expected[:, 1])))
            if not np.allclose(fitted, expected[:, 1], rtol=TOLERANCE, atol=TOLERANCE):
                raise ValueError(f"{arm}/{target}: readout predictions differ (max abs {delta:.6g})")
            errors[target] = delta
        arms[arm] = {"readout_inputs_sha256": digest, "train_windows": len(x_train),
                     "test_windows": len(order), "max_abs_prediction_error": errors}
    return {"status": "verified_from_saved_features", "arms": arms, "alpha": ALPHA,
            "absolute_tolerance": TOLERANCE, "relative_tolerance": TOLERANCE,
            "predictions_sha256": reg_hash, "condition_predictions_sha256": cond_hash}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed_dir", type=Path)
    parser.add_argument("--output", type=Path, help="Write a new JSON receipt (default: stdout)")
    args = parser.parse_args()
    result = json.dumps(recheck(args.seed_dir), indent=2, allow_nan=False)
    if args.output is None:
        print(result)
    else:
        with args.output.open("x", encoding="utf-8") as output:
            print(result, file=output)


if __name__ == "__main__":
    main()
