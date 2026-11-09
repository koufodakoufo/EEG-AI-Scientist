import numpy as np
import pytest

from eegfm.eeg.residual_recovery import fixed_target_mask, score_recovery


def _predictions(y, model_count=4):
    return np.broadcast_to(y[:, None, None, :], (len(y), 5, model_count, 6)).copy()


def test_r2_and_fixed_mask():
    train = np.tile([[-1.0], [1.0]], (4, 6))
    y = train + 2
    train[:, 1] = 0
    y[:, 2] = 2
    preds = _predictions(y, 2)
    preds[:, :, 1, :] = y.mean(0)
    result = score_recovery(train, y, preds, np.repeat(["a", "b"], 4), bootstrap_resamples=16)

    assert fixed_target_mask(train, y).tolist() == [True, False, False, True, True, True]
    assert result["target_mask"] == [True, False, False, True, True, True]
    for view in result["views"].values():
        assert view["linear"]["r2"] == 1
        assert view["linear_shuffled"]["r2"] == 0
        assert view["train_mean"]["r2"] == -4
        assert view["linear"]["per_column_r2"] == [1, None, None, 1, 1, 1]
    assert result["gates"]["registered_useful_effect"] == "not_applicable"
    assert result["primary"] is None


def test_relative_variance_floor_applies_to_b_and_evaluation():
    train = np.tile([[-1.0], [1.0]], (2, 6))
    y = train.copy()
    train[:, 0] += 2e6
    y[:, 1] += 2e6
    assert fixed_target_mask(train, y).tolist() == [False, False, True, True, True, True]


def test_nonfinite_prediction_cannot_hide_in_excluded_column():
    y = np.tile([[-1.0], [1.0]], (2, 6))
    y[:, 0] = 0
    preds = _predictions(y)
    preds[0, 0, 0, 0] = np.nan
    with pytest.raises(ValueError, match="Nonfinite"):
        score_recovery(y, y, preds, np.repeat(["a", "b"], 2), bootstrap_resamples=5)


def test_empty_fixed_mask_is_rejected():
    y = np.ones((4, 6))
    with pytest.raises(ValueError, match="target mask"):
        score_recovery(y, y, _predictions(y), np.repeat(["a", "b"], 2), bootstrap_resamples=5)


def test_one_undefined_column_invalidates_shared_draws_and_loo():
    y = np.tile([[-1.0], [1.0]], (2, 6))
    y[:, 0] = [-1, -1, 1, 1]
    preds = _predictions(y)
    result = score_recovery(y, y, preds, np.repeat(["a", "b"], 2), bootstrap_resamples=16)
    # PCG64(230419) first 16 paired draws over [a,b] contain 9 repeated blocks.
    assert result["bootstrap"] == {"requested": 16, "valid": 7, "invalid": 9, "intervals_valid": False}
    assert result["primary"] == {"delta": 0, "ci95": None}
    assert all(score["ci95"] is None for view in result["views"].values() for score in view.values())
    assert [item["status"] for item in result["leave_one_participant_out"]] == ["undefined", "undefined"]
    assert result["gates"]["registered_useful_effect"] == "inconclusive"


def test_bootstrap_pools_whole_unequal_subject_blocks_and_is_reproducible():
    y = np.tile(np.array([-1., 1., -1., 1., -1., 1.])[:, None], (1, 6))
    subjects = np.array(["z", "z", "a", "a", "a", "a"])
    preds = _predictions(y)
    preds[:2, :, 0, :] += 2
    # Both subject blocks have unit variance. Linear R2 is -3 for z+z,
    # 1 for a+a, and 1 - 8/6 for a+z (pool windows, not subject scores).
    expected_draws = np.random.Generator(np.random.PCG64(230419)).integers(0, 2, (32, 2))
    expected = np.where(expected_draws.sum(1) == 2, -3.,
                        np.where(expected_draws.sum(1) == 0, 1., -1/3))
    one = score_recovery(y, y, preds, subjects, bootstrap_resamples=32)
    two = score_recovery(y, y, preds, subjects, bootstrap_resamples=32)
    assert one == two
    assert one["views"]["leace"]["linear"]["ci95"] == pytest.approx(np.quantile(expected, [.025, .975]))
    assert one["views"]["leace"]["linear"]["r2"] == pytest.approx(-1/3)
    assert one["leave_one_participant_out"][0]["views"]["leace"]["linear"] == -3


@pytest.mark.parametrize("failure, expected", [
    (None, "passed"),
    ("negative_absolute", "descriptive"),
    ("own_shuffle", "descriptive"),
    ("identity", "descriptive"),
    ("strict_margin", "descriptive"),
])
def test_registered_useful_effect_requires_all_strict_gates(failure, expected):
    y = np.tile([[-1.0], [1.0]], (4, 6))
    preds = _predictions(y)
    preds[:, :, 0, :] += .5
    preds[:, :, [1, 3], :] += 2
    if failure == "negative_absolute":
        preds[:, 1, 0, :] = y + 2
        preds[:, 1, 2, :] = y + 1.5
    elif failure == "own_shuffle":
        preds[:, 1, 3, :] = preds[:, 1, 2, :]
    elif failure == "identity":
        preds[:, 0, 3, :] = preds[:, 0, 2, :]
    elif failure == "strict_margin":
        y[:, 5] = 0
        preds[:, 1, [0, 2], :] = y[:, None, :] + 1
        preds[[3, 7], 1, 2, 0] = y[[3, 7], 0]
    result = score_recovery(y, y, preds, np.repeat(["a", "b"], 4), bootstrap_resamples=16)
    assert result["gates"]["registered_useful_effect"] == expected
    assert result["gates"]["identity_gate_passed"] == ("descriptive" if failure == "identity" else "passed")
    assert result["gates"]["registered_linear_recovery"] == (
        "descriptive" if failure in {"negative_absolute", "strict_margin"} else "passed")
    if failure == "strict_margin":
        assert result["primary"]["delta"] == .05
        assert result["primary"]["ci95"] == [.05, .05]
    if failure == "negative_absolute":
        assert result["primary"]["delta"] > 0
        assert result["views"]["leace"]["flexible"]["r2"] < 0


def test_useful_point_with_imprecise_paired_interval_is_inconclusive():
    y = np.tile([[-1.0], [1.0]], (4, 6))
    preds = _predictions(y)
    preds[:, :, 0, :] += .5
    preds[:, :, [1, 3], :] += 2
    preds[:4, 1, 2, :] += .5
    result = score_recovery(y, y, preds, np.repeat(["a", "b"], 4), bootstrap_resamples=64)
    assert result["primary"]["delta"] == .125
    assert result["primary"]["ci95"] == [0, .25]
    assert result["gates"]["identity_gate_passed"] == "passed"
    assert result["gates"]["registered_useful_effect"] == "inconclusive"
