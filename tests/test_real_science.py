"""Scientific invariants for the real-data adaptation study."""
from __future__ import annotations

import numpy as np
import pytest


def test_probe_fits_training_transform_and_reports_unclipped_r2() -> None:
    from eegfm.eeg.statistics import fit_probe
    from eegfm.eeg.statistics import predict_probe
    from eegfm.eeg.statistics import r2_columns
    rng = np.random.default_rng(4)
    train = rng.normal(size=(50, 8))
    targets = train[:, :2] * np.array([2, 20]) + 7
    fit = fit_probe(train, targets, alpha=0.01)
    np.testing.assert_allclose(fit['x_mean'], train.mean(0))
    assert np.min(r2_columns(targets, predict_probe(fit, train))) > 0.999
    assert np.max(r2_columns(targets, np.full_like(targets, 10000))) < 0


def test_erasure_and_random_control_match_actual_rank_and_per_row_strength() -> None:
    from eegfm.eeg.statistics import subspace
    from eegfm.eeg.statistics import perturb
    rng = np.random.default_rng(5)
    z = rng.normal(size=(10, 20, 5, 8))
    w = np.column_stack([np.arange(8), 2*np.arange(8), np.ones(8)])
    basis = subspace(w)
    assert basis.shape == (8, 2)
    altered, metadata = perturb(z, basis, np.zeros(8))
    random, control = perturb(z, basis, np.zeros(8), random_seed=19)
    assert metadata['rank'] == control['rank'] == 2
    np.testing.assert_allclose(np.linalg.norm(altered-z, axis=-1), np.linalg.norm(random-z, axis=-1), atol=1e-11)
    assert not np.allclose(altered, random)
    np.testing.assert_allclose(altered.mean((1, 2)) @ basis, 0, atol=1e-12)


def test_participant_permutation_is_effective_and_block_preserving() -> None:
    from eegfm.eeg.statistics import permute_subject_blocks
    subjects = np.repeat(['a','b','c','d'], 4)
    indices = permute_subject_blocks(subjects, seed=21)
    assert sorted(indices) == list(range(16))
    assert np.all(subjects[indices] != subjects)
    for start in range(0,16,4):
        assert len(set(subjects[indices[start:start+4]])) == 1
    condition = np.tile([0,0,1,1],4)
    assert not np.array_equal(condition[indices],condition), 'Negative control must break condition alignment too'
    with pytest.raises(ValueError):
        permute_subject_blocks(np.array(['a','a','b']), seed=1)


def test_cluster_bootstrap_keeps_all_windows_of_sampled_participants() -> None:
    from eegfm.eeg.statistics import cluster_bootstrap_indices
    subjects = np.repeat(['a','b','c'], [2,3,4])
    rows = cluster_bootstrap_indices(subjects, resamples=12, seed=6)
    assert len(rows) == 12
    for row in rows:
        for subject in np.unique(subjects):
            original = np.flatnonzero(subjects == subject)
            counts = [(row == index).sum() for index in original]
            assert len(set(counts)) == 1


def test_split_overlap_and_nonfinite_targets_rejected() -> None:
    from eegfm.eeg.statistics import validate_partitions
    from eegfm.eeg.statistics import fit_probe
    with pytest.raises(ValueError, match='overlap'):
        validate_partitions({'train':np.array(['a']), 'validation':np.array(['a'])})
    with pytest.raises(ValueError, match='finite'):
        fit_probe(np.zeros((3,2)), np.array([[1],[float('nan')],[2]]), alpha=1)
