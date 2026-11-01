"""Independent row/permutation checks for exact empirical bootstrap statistics."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from itertools import product

import numpy as np
import pytest

import eegfm.eeg.bootstrap as exact


def test_six_participant_mass_and_ordered_toy_distribution() -> None:
    counts, weights = exact.enumerate_counts(6)
    assert counts.shape == (462, 6)
    assert weights.sum() == 46656
    np.testing.assert_array_equal(counts.sum(axis=1), 6)
    np.testing.assert_allclose(weights.sum() / 6**6, 1.0, atol=0, rtol=0)
    toy_counts, toy_weights = exact.enumerate_counts(3)
    ordered = Counter(tuple(np.bincount(draw, minlength=3)) for draw in product(range(3), repeat=3))
    assert {tuple(c): int(w) for c, w in zip(toy_counts, toy_weights, strict=True)} == ordered


def test_weighted_inverse_cdf_keeps_boundary_and_does_not_interpolate() -> None:
    values = np.array([9.0, 1.0, 4.0])
    weights = np.array([1, 2, 1])
    assert exact.weighted_quantile(values, weights, Fraction(1, 2)) == 1.0
    assert exact.weighted_quantile(values, weights, Fraction(3, 4)) == 4.0
    assert exact.weighted_quantile(values, weights, Fraction(4, 5)) == 9.0
    expanded = np.repeat(values, weights)
    for q in (Fraction(1, 20), Fraction(1, 2), Fraction(19, 20)):
        assert exact.weighted_quantile(values, weights, q, linear=True) == pytest.approx(np.quantile(expanded, float(q)))
    assert exact.weighted_quantile(np.array([np.nan, 1.0]), np.array([3, 1]), Fraction(1, 2)) == 1.0


def test_count_statistics_match_expanded_rows_with_unequal_clusters() -> None:
    subjects = np.array([0, 0, 1, 1, 1, 2, 2, 2, 2])
    target = np.array([[1., 2., 7.], [3., 5., 7.], [2., 7., 7.], [4., 2., 7.], [8., 8., 7.],
                       [2., 3., 7.], [6., 9., 7.], [1., 8., 7.], [5., 4., 7.]])
    prediction = target + np.array([.5, -.7, 4.])
    labels = np.array([0, 1, 0, 0, 1, 0, 1, 1, 1])
    logits = np.array([-1., 1., 1., -1., 1., 1., -1., 1., -1.])
    counts, weights = exact.enumerate_counts(3)
    curves = exact.r2_distribution(target, prediction, subjects, counts, np.array([True, False, True]))
    balanced = exact.ba_distribution(labels, logits, subjects, counts)
    blocks = [np.flatnonzero(subjects == s) for s in range(3)]
    ordered_r2: list[float] = []
    ordered_ba: list[float] = []
    for draw in product(range(3), repeat=3):
        rows = np.concatenate([blocks[s] for s in draw])
        yt, yp = target[rows, 0], prediction[rows, 0]
        ordered_r2.append(float(1 - np.square(yt - yp).sum() / np.square(yt - yt.mean()).sum()))
        y = labels[rows]
        ordered_ba.append(float(np.mean([np.mean((logits[rows][y == c] >= 0) == c) for c in (0, 1)])))
    np.testing.assert_allclose(np.sort(np.repeat(curves, weights)), np.sort(ordered_r2), atol=1e-13)
    np.testing.assert_allclose(np.sort(np.repeat(balanced, weights)), np.sort(ordered_ba), atol=1e-13)
    # A pooled ratio of total SSE/SST is not the requested mean of column R².
    both = exact.r2_distribution(target[:, :2], prediction[:, :2], subjects, np.array([[1, 1, 1]]), np.array([True, True]))
    expected = np.mean(1 - np.square(target[:, :2] - prediction[:, :2]).sum(0) / np.square(target[:, :2] - target[:, :2].mean(0)).sum(0))
    assert both[0] == pytest.approx(expected)


def test_invalid_cluster_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        exact.enumerate_counts(0)
