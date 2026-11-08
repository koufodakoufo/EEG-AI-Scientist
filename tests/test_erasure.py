"""Algebraic checks; these synthetic cases are not EEG scientific evidence."""
from __future__ import annotations

import numpy as np
import pytest

from eegfm.eeg import erasure


def correlated() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(713)
    x = rng.normal(size=(300, 3))
    x[:, 1] = 0.8 * x[:, 0] + 0.6 * x[:, 1]
    x += np.array([4., -8., 2.])
    return x, x[:, :1]


def test_leace_removes_training_cross_covariance_and_preserves_mean() -> None:
    x, z = correlated()
    fitted = erasure.fit_leace(x, z)
    changed = erasure.apply_erasure(fitted, x)
    centered_z = z - z.mean(0)
    np.testing.assert_allclose((changed - changed.mean(0)).T @ centered_z / len(x), 0, atol=1e-12)
    np.testing.assert_allclose(changed.mean(0), x.mean(0), atol=1e-12)
    np.testing.assert_allclose(erasure.apply_erasure(fitted, changed), changed, atol=1e-12)
    assert fitted['rank'] == 1


def test_probe_direction_removal_can_leave_information() -> None:
    x, z = correlated()
    centered = x - x.mean(0)
    coefficient = np.linalg.lstsq(centered, z-z.mean(0), rcond=None)[0]
    direction = coefficient[:, 0] / np.linalg.norm(coefficient)
    naive = x - (centered @ direction)[:, None] * direction
    assert abs(float(np.cov(naive[:, 1], z[:, 0])[0, 1])) > 0.5
    changed = erasure.apply_erasure(erasure.fit_leace(x, z), x)
    assert np.max(np.abs(np.cov(changed.T, z.T)[:3, 3:])) < 1e-12


def test_leace_has_no_more_training_distortion_than_covariance_projection() -> None:
    x, z = correlated()
    centered = x - x.mean(0)
    covariance = centered.T @ (z-z.mean(0))
    q = covariance / np.linalg.norm(covariance)
    orthogonal = x - centered @ q @ q.T
    changed = erasure.apply_erasure(erasure.fit_leace(x, z), x)
    assert np.sum((changed-x)**2) <= np.sum((orthogonal-x)**2) + 1e-10


def test_singular_representation_and_constant_concept_are_explicit() -> None:
    x, z = correlated()
    x = np.column_stack([x, x[:, 0], np.ones(len(x))])
    fitted = erasure.fit_leace(x, z)
    assert fitted['covariance_rank'] == 3
    np.testing.assert_allclose((erasure.apply_erasure(fitted, x)-x.mean(0)).T @ (z-z.mean(0)), 0, atol=1e-9)
    identity = erasure.fit_leace(x, np.ones((len(x), 2)))
    assert identity['rank'] == 0
    np.testing.assert_array_equal(erasure.apply_erasure(identity, x), x)


def test_linear_removal_does_not_claim_nonlinear_information_removal() -> None:
    x = np.arange(-10., 11.)[:, None]
    z = x**2
    fitted = erasure.fit_leace(x, z)
    assert fitted['rank'] == 0
    np.testing.assert_array_equal(erasure.apply_erasure(fitted, x), x)


def test_fit_and_apply_do_not_mutate_inputs_or_fit_on_new_rows() -> None:
    x, z = correlated()
    original = x.copy()
    fitted = erasure.fit_leace(x, z)
    shifted = x[:2] + 100
    actual = erasure.apply_erasure(fitted, shifted)
    np.testing.assert_allclose(actual, shifted - (shifted-np.asarray(fitted['mean'])) @ np.asarray(fitted['removal']).T)
    np.testing.assert_array_equal(x, original)


@pytest.mark.parametrize('bad', [np.ones(3), np.ones((0, 3)), np.array([[np.nan], [1.]]), np.array([[1j], [2j]])])
def test_invalid_training_data_rejected(bad: np.ndarray) -> None:
    with pytest.raises(ValueError):
        erasure.fit_leace(bad, np.ones((len(bad), 1)))


def test_mismatched_rows_and_bad_tolerance_rejected() -> None:
    x, z = correlated()
    with pytest.raises(ValueError):
        erasure.fit_leace(x, z[:-1])
    for tolerance in (0., -1., np.nan, True):
        with pytest.raises(ValueError):
            erasure.fit_leace(x, z, rcond=tolerance)


def test_apply_rejects_wrong_dimension_and_nonfinite_operator() -> None:
    x, z = correlated()
    fitted = erasure.fit_leace(x, z)
    with pytest.raises(ValueError):
        erasure.apply_erasure(fitted, x[:, :2])
    fitted['removal'][0][0] = float('inf')
    with pytest.raises(ValueError):
        erasure.apply_erasure(fitted, x)
