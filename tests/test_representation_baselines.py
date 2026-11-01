"""Scientific integrity checks for the separate exploratory baseline extension."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest


def extension_module() -> ModuleType:
    from eegfm.eeg import baselines
    return baselines


def test_misaligned_identity_is_rejected_before_comparison() -> None:
    module = extension_module()
    left = {name: np.array(["a", "b"]) for name in module.IDENTITY_KEYS}
    right = {name: value.copy() for name, value in left.items()}
    module.validate_alignment(left, right)
    right["sample_ids"] = right["sample_ids"][::-1]
    with pytest.raises(ValueError, match="sample_ids"):
        module.validate_alignment(left, right)


def test_lock_tamper_and_second_test_reservation_rejected(tmp_path: Path) -> None:
    module = extension_module()
    source = tmp_path / "source.txt"
    source.write_text("frozen", encoding="utf-8")
    lock = {"files": [{"path": str(source), "sha256": module.sha256_file(source)}]}
    module.save_json(tmp_path / "EXTENSION_LOCK.json", lock)
    module.reserve_test(tmp_path)
    with pytest.raises(FileExistsError):
        module.reserve_test(tmp_path)
    source.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        module.verify_lock(tmp_path)


def test_bootstrap_sufficient_statistics_match_duplicate_participant_rows() -> None:
    module = extension_module()
    rng = np.random.default_rng(2)
    targets = rng.normal(size=(9, 4))
    predictions = targets + rng.normal(size=targets.shape) / 3
    subjects = np.repeat(["a", "b", "c"], 3)
    counts = np.array([[2, 1, 0], [0, 1, 2], [1, 1, 1]])
    observed = module.q1_bootstrap(targets, predictions, subjects, counts)
    for index, draw in enumerate(counts):
        rows = np.concatenate([np.tile(np.flatnonzero(subjects == subject), count)
                               for subject, count in zip(np.unique(subjects), draw)])
        np.testing.assert_allclose(observed[index], module.r2_columns(targets[rows], predictions[rows]), atol=1e-12)
