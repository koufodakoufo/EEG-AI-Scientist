"""Minimal feature-table entry point for future real EEG features (Task E2).

The format is intentionally narrow and documented: one row per window/sample,
binary labels (-1 or 1) defined at the trial level, with subject, session, and
trial identifiers kept for split auditing.

Limitations are deliberate in this handoff:

* labels are binary only; decimal labels are rejected, never truncated;
* the implemented splits are window, trial, and subject; there is **no
  session-held-out split** yet, even though ``session_id`` is retained for audit;
* the included fixture is artificial and only proves that the loader and split
  checks work; it is not EEG evidence.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np

from .schema import FeatureDataset, SplitLevel
from .splits import audit_all_splits, build_all_splits

META_COLUMNS = ("sample_id", "subject_id", "session_id", "trial_id", "label")
INTEGER_LABEL_PATTERN = re.compile(r"^[+-]?[0-9]+$")
SUPPORTED_SPLIT_LEVELS: tuple[str, ...] = ("window", "trial", "subject")


class DatasetFormatError(ValueError):
    """The feature table does not satisfy the documented format."""


def load_feature_table(path: Path | str, *, case_id: str | None = None) -> FeatureDataset:
    table_path = Path(path)
    if not table_path.exists():
        raise DatasetFormatError(f"feature table not found: {table_path}")
    with table_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DatasetFormatError("feature table has no header")
        missing = [column for column in META_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise DatasetFormatError(f"missing required columns: {', '.join(missing)}")
        feature_names = [column for column in reader.fieldnames if column not in META_COLUMNS]
        if not feature_names:
            raise DatasetFormatError("feature table has no feature columns")
        rows = list(reader)
    if not rows:
        raise DatasetFormatError("feature table has no data rows")

    sample_ids: list[str] = []
    subject_ids: list[str] = []
    session_uids: list[str] = []
    trial_uids: list[str] = []
    labels: list[int] = []
    feature_rows: list[list[float]] = []
    for index, row in enumerate(rows, start=2):
        label_text = (row.get("label") or "").strip()
        if not INTEGER_LABEL_PATTERN.fullmatch(label_text):
            raise DatasetFormatError(
                f"line {index}: label must be the integer -1 or 1; decimal or non-integer labels are rejected"
            )
        label = int(label_text)
        if label not in {-1, 1}:
            raise DatasetFormatError(f"line {index}: label must be -1 or 1")
        try:
            values = [float(row[name]) for name in feature_names]
        except (TypeError, ValueError) as error:
            raise DatasetFormatError(f"line {index}: non-numeric feature value") from error
        sample_ids.append((row.get("sample_id") or "").strip())
        subject_ids.append((row.get("subject_id") or "").strip())
        session_uids.append((row.get("session_id") or "").strip())
        trial_uids.append((row.get("trial_id") or "").strip())
        labels.append(label)
        feature_rows.append(values)
    x = np.asarray(feature_rows, dtype=np.float64)
    return FeatureDataset(
        x=x,
        y=np.asarray(labels, dtype=np.int64),
        sample_ids=sample_ids,
        subject_ids=subject_ids,
        session_uids=session_uids,
        trial_uids=trial_uids,
        feature_names=feature_names,
        case_id=case_id or table_path.stem,
    )


def check_feature_table(
    path: Path | str,
    *,
    split_seed: int = 20261020,
) -> dict[str, object]:
    dataset = load_feature_table(path)
    splits = build_all_splits(dataset, split_seed)
    audits = audit_all_splits(dataset, splits)
    name = Path(path).stem.lower()
    fixture_only = "fixture" in name or "artificial" in name
    summary: dict[str, object] = {
        "path": str(Path(path)),
        "case_id": dataset.case_id,
        "n_rows": len(dataset.sample_ids),
        "n_subjects": len(set(dataset.subject_ids)),
        "n_sessions": len(set(dataset.session_uids)),
        "n_trials": len(set(dataset.trial_uids)),
        "n_features": len(dataset.feature_names),
        "labels": {str(value): int((dataset.y == value).sum()) for value in (-1, 1)},
        "label_domain": "binary_-1_1",
        "split_levels_supported": list(SUPPORTED_SPLIT_LEVELS),
        "session_split_supported": False,
        "split_seed": split_seed,
        "splits": {},
        "audits": {},
        "real_eeg_experiment_executed": False,
        "fixture_only": fixture_only,
    }
    split_summary: dict[str, object] = {}
    for level in SUPPORTED_SPLIT_LEVELS:
        indices = splits[level]  # type: ignore[index]
        split_summary[level] = {
            "n_train": int(len(indices.train_indices)),
            "n_test": int(len(indices.test_indices)),
            "n_train_trials": len({dataset.trial_uids[int(i)] for i in indices.train_indices}),
            "n_test_trials": len({dataset.trial_uids[int(i)] for i in indices.test_indices}),
            "n_train_subjects": len({dataset.subject_ids[int(i)] for i in indices.train_indices}),
            "n_test_subjects": len({dataset.subject_ids[int(i)] for i in indices.test_indices}),
        }
    summary["splits"] = split_summary
    summary["audits"] = {
        level: {
            "overlap": audits[level].get("overlap", {}),
            "label_counts": audits[level].get("label_counts", {}),
            "n_groups": audits[level].get("n_groups", {}),
            "invalid_reason": audits[level].get("invalid_reason"),
        }
        for level in SUPPORTED_SPLIT_LEVELS
    }
    return summary


def write_artificial_fixture(path: Path | str, *, seed: int = 20261020) -> Path:
    """Write a small, clearly artificial table used only for format checks."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    feature_names = [f"f_{index:02d}" for index in range(6)]
    rows: list[dict[str, str]] = []
    for subject in range(4):
        for session in range(2):
            labels = [-1, -1, -1, -1, 1, 1, 1, 1]
            rng.shuffle(labels)
            for trial, label in enumerate(labels):
                session_uid = f"sub-{subject:02d}_ses-{session:02d}"
                trial_uid = f"{session_uid}_trial-{trial:02d}"
                for window in range(4):
                    values = rng.normal(0.0, 1.0, size=len(feature_names))
                    values[0] += 0.8 * label
                    row = {
                        "sample_id": f"{trial_uid}_win-{window:02d}",
                        "subject_id": f"sub-{subject:02d}",
                        "session_id": session_uid,
                        "trial_id": trial_uid,
                        "label": str(label),
                    }
                    row.update({name: f"{value:.8f}" for name, value in zip(feature_names, values, strict=True)})
                    rows.append(row)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(META_COLUMNS) + feature_names)
        writer.writeheader()
        writer.writerows(rows)
    return target


def split_levels() -> tuple[SplitLevel, ...]:
    return ("window", "trial", "subject")
