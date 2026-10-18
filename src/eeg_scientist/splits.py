"""Grouped splits and identity-intersection audits."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from .schema import FeatureDataset, SplitIndices, SplitLevel

SPLIT_OFFSETS: dict[str, int] = {"window": 0, "trial": 1, "subject": 2}


def _take(rows: list[int], train: list[int], test: list[int]) -> list[int]:
    return train if rows is not None else test


def _split_rows_by_group(
    group_to_rows: dict[str, list[int]],
    rng: np.random.Generator,
    train_fraction: float = 0.75,
) -> tuple[list[int], list[int]]:
    groups = sorted(group_to_rows)
    rng.shuffle(groups)
    n_train = max(1, int(round(len(groups) * train_fraction)))
    if n_train >= len(groups):
        n_train = len(groups) - 1
    train_groups = groups[:n_train]
    test_groups = groups[n_train:]
    train_rows = [row for group in train_groups for row in group_to_rows[group]]
    test_rows = [row for group in test_groups for row in group_to_rows[group]]
    return sorted(train_rows), sorted(test_rows)


def build_split(dataset: FeatureDataset, level: SplitLevel, seed: int) -> SplitIndices:
    rng = np.random.default_rng(seed + SPLIT_OFFSETS[level])
    if level == "window":
        trial_to_rows: dict[str, list[int]] = defaultdict(list)
        for row, trial_uid in enumerate(dataset.trial_uids):
            trial_to_rows[trial_uid].append(row)
        train: list[int] = []
        test: list[int] = []
        for trial_uid in sorted(trial_to_rows):
            rows = trial_to_rows[trial_uid]
            order = rng.permutation(len(rows))
            n_train = max(1, int(round(len(rows) * 0.75)))
            if n_train >= len(rows):
                n_train = len(rows) - 1
            train.extend(rows[int(i)] for i in order[:n_train])
            test.extend(rows[int(i)] for i in order[n_train:])
        return SplitIndices(
            train_indices=np.asarray(sorted(train), dtype=np.int64),
            test_indices=np.asarray(sorted(test), dtype=np.int64),
            split_level=level,
            split_seed=seed,
        )

    if level == "trial":
        session_label_trials: dict[tuple[str, int], list[str]] = defaultdict(list)
        seen: set[tuple[str, int]] = set()
        trial_label: dict[str, int] = {}
        for trial_uid, session_uid, label in zip(dataset.trial_uids, dataset.session_uids, dataset.y.tolist(), strict=True):
            key = (session_uid, int(label))
            if trial_uid not in trial_label:
                trial_label[trial_uid] = int(label)
                session_label_trials[key].append(trial_uid)
        train_trials: set[str] = set()
        test_trials: set[str] = set()
        for key in sorted(session_label_trials):
            trials = sorted(set(session_label_trials[key]))
            rng.shuffle(trials)
            n_train = max(1, int(round(len(trials) * 0.75)))
            if n_train >= len(trials):
                n_train = len(trials) - 1
            train_trials.update(trials[:n_train])
            test_trials.update(trials[n_train:])
        if train_trials & test_trials:
            raise ValueError("trial split produced trial overlap")
        train = [row for row, trial_uid in enumerate(dataset.trial_uids) if trial_uid in train_trials]
        test = [row for row, trial_uid in enumerate(dataset.trial_uids) if trial_uid in test_trials]
        return SplitIndices(
            train_indices=np.asarray(sorted(train), dtype=np.int64),
            test_indices=np.asarray(sorted(test), dtype=np.int64),
            split_level=level,
            split_seed=seed,
        )

    if level == "subject":
        subject_to_rows: dict[str, list[int]] = defaultdict(list)
        for row, subject_id in enumerate(dataset.subject_ids):
            subject_to_rows[subject_id].append(row)
        train, test = _split_rows_by_group(subject_to_rows, rng)
        return SplitIndices(
            train_indices=np.asarray(train, dtype=np.int64),
            test_indices=np.asarray(test, dtype=np.int64),
            split_level=level,
            split_seed=seed,
        )

    raise ValueError(f"unknown split level {level}")


def build_all_splits(dataset: FeatureDataset, split_seed: int) -> dict[str, SplitIndices]:
    return {level: build_split(dataset, level, split_seed) for level in ("window", "trial", "subject")}  # type: ignore[arg-type]


def _unique(values: list[str], indices: np.ndarray) -> set[str]:
    return {values[int(index)] for index in indices.tolist()}


def audit_split(dataset: FeatureDataset, indices: SplitIndices) -> dict[str, object]:
    train = indices.train_indices
    test = indices.test_indices
    train_samples = {dataset.sample_ids[int(i)] for i in train.tolist()}
    test_samples = {dataset.sample_ids[int(i)] for i in test.tolist()}
    train_trials = _unique(dataset.trial_uids, train)
    test_trials = _unique(dataset.trial_uids, test)
    train_sessions = _unique(dataset.session_uids, train)
    test_sessions = _unique(dataset.session_uids, test)
    train_subjects = _unique(dataset.subject_ids, train)
    test_subjects = _unique(dataset.subject_ids, test)

    overlap = {
        "sample": len(train_samples & test_samples),
        "trial": len(train_trials & test_trials),
        "session": len(train_sessions & test_sessions),
        "subject": len(train_subjects & test_subjects),
    }
    counts = {
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_trials": len(train_trials),
        "test_trials": len(test_trials),
        "train_sessions": len(train_sessions),
        "test_sessions": len(test_sessions),
        "train_subjects": len(train_subjects),
        "test_subjects": len(test_subjects),
    }
    train_labels = np.bincount((dataset.y[train] == 1).astype(np.int64), minlength=2)
    test_labels = np.bincount((dataset.y[test] == 1).astype(np.int64), minlength=2)
    label_counts = {
        "train": {"negative": int(train_labels[0]), "positive": int(train_labels[1])},
        "test": {"negative": int(test_labels[0]), "positive": int(test_labels[1])},
    }
    n_groups = {
        "window": len(train) // max(len(train_trials), 1),
        "trial": len(train_trials),
        "subject": len(train_subjects),
    }
    expected = {
        "window": {"sample": 0},
        "trial": {"sample": 0, "trial": 0},
        "subject": {"sample": 0, "trial": 0, "subject": 0},
    }[indices.split_level]
    invalid_reasons: list[str] = []
    for key, expected_value in expected.items():
        if overlap[key] != expected_value:
            invalid_reasons.append(f"unexpected {key} overlap {overlap[key]}")
    if label_counts["train"]["negative"] == 0 or label_counts["train"]["positive"] == 0:
        invalid_reasons.append("training split has a single class")
    if label_counts["test"]["negative"] == 0 or label_counts["test"]["positive"] == 0:
        invalid_reasons.append("test split has a single class")
    return {
        "split_level": indices.split_level,
        "split_seed": indices.split_seed,
        "overlap": overlap,
        "expected_overlap": expected,
        "counts": counts,
        "label_counts": label_counts,
        "n_groups": n_groups,
        "invalid_reason": "; ".join(invalid_reasons) if invalid_reasons else None,
    }


def audit_all_splits(dataset: FeatureDataset, splits: dict[str, SplitIndices]) -> dict[str, dict[str, object]]:
    return {level: audit_split(dataset, indices) for level, indices in splits.items()}
