"""Synthetic checks of the fixed readout experiment; no EEG or weights are read."""
from __future__ import annotations

import copy
import json

import numpy as np
import pytest


def _split(x: np.ndarray, y: np.ndarray, name: str) -> dict[str, np.ndarray]:
    return {"x": x, "y": y, "sample_ids": np.array([f"{name}-{i}" for i in range(len(y))]),
            "subject_ids": np.array([f"{name}-p{i // 2}" for i in range(len(y))])}


def _training() -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    rng = np.random.default_rng(12)
    x = rng.normal(size=(80, 325))
    y = np.tile([0, 1], 40)
    x[:, 0] = 3 * (2 * y - 1) + rng.normal(0, 0.2, len(y))
    x[:, 200] = x[:, 0]
    x[:, 262] = x[:, 0] + 5  # Good ranking, systematically wrong zero threshold.
    vx = rng.normal(size=(40, 325))
    vy = np.tile([0, 1], 20)
    vx[:, 0] = 3 * (2 * vy - 1) + rng.normal(0, 0.2, len(vy))
    vx[:, 200] = vx[:, 0]
    vx[:, 262] = vx[:, 0] + 5
    return _split(x, y, "train"), _split(vx, vy, "validation")


def test_readouts_preserve_old_logits_and_use_training_statistics_only() -> None:
    from eegfm.eeg.readout_study import fit_readouts, predict_readouts

    train, validation = _training()
    originals = {name: value.copy() for name, value in train.items()}
    fits = fit_readouts(train, validation)
    changed = {**validation, "x": validation["x"] + 100, "y": 1 - validation["y"]}
    other = fit_readouts(train, changed)
    for name, start, stop in [("B", 262, 263), ("C", 0, 200), ("D", 200, 262), ("E", 263, 325)]:
        model = fits["models"][name]
        np.testing.assert_allclose(model["mean"], train["x"][:, start:stop].mean(0))
        np.testing.assert_allclose(model["scale"], train["x"][:, start:stop].std(0))
        # Selection may change, but every candidate fit must remain train-only.
        for left, right in zip(model["selection_grid"], other["models"][name]["selection_grid"]):
            assert left["C"] == right["C"]
            np.testing.assert_array_equal(left["coefficient"], right["coefficient"])
            assert left["intercept"] == right["intercept"]
    for name, value in originals.items():
        np.testing.assert_array_equal(train[name], value)
    restored = json.loads(json.dumps(fits, allow_nan=False))
    scores = predict_readouts(restored, validation["x"])
    assert scores.shape == (40, 5)
    np.testing.assert_array_equal(scores[:, 0], validation["x"][:, 262])
    shifted = predict_readouts(restored, np.vstack([validation["x"], train["x"]]))
    np.testing.assert_allclose(shifted[:40], scores, rtol=0, atol=1e-13)


def test_each_readout_selects_validation_accuracy_with_small_c_ties() -> None:
    from eegfm.eeg.readout_study import fit_readouts
    from sklearn.linear_model import LogisticRegression

    # Independent library fits check grid scoring and model-specific selection.
    rng = np.random.default_rng(9)
    x, vx = rng.normal(size=(90, 325)), rng.normal(size=(100, 325))
    y = (x[:, 0] + 0.5 * rng.normal(size=90) > 0).astype(int)
    vy = (vx[:, 0] + 0.5 * rng.normal(size=100) > 0).astype(int)
    fits = fit_readouts(_split(x, y, "t"), _split(vx, vy, "v"))
    chosen = []
    for name, start, stop in [("C", 0, 200), ("D", 200, 262), ("E", 263, 325)]:
        tx = x[:, start:stop]
        z = (tx - tx.mean(0)) / tx.std(0)
        zv = (vx[:, start:stop] - tx.mean(0)) / tx.std(0)
        expected = []
        for c in [0.01, 0.1, 1.0, 10.0]:
            model = LogisticRegression(C=c, solver="lbfgs", max_iter=2000, tol=1e-9).fit(z, y)
            pred = model.decision_function(zv) >= 0
            expected.append(float(np.mean([np.mean(pred[vy == label] == label) for label in (0, 1)])))
        actual = fits["models"][name]
        assert [item["validation_balanced_accuracy"] for item in actual["selection_grid"]] == expected
        assert actual["C"] == [0.01, 0.1, 1.0, 10.0][int(np.argmax(expected))]
        chosen.append(actual["C"])
    assert len(set(chosen)) > 1

    # Every candidate is equivalent with constant features, including calibration.
    constant = np.zeros((20, 325))
    tied = fit_readouts(_split(constant, np.tile([0, 1], 10), "t"),
                        _split(constant, np.tile([0, 1], 10), "v"))
    assert all(tied["models"][name]["C"] == 0.01 for name in "BCDE")
    assert all(np.all(np.array(tied["models"][name]["scale"]) == 1) for name in "BCDE")


def test_positive_calibration_preserves_ranking_even_for_adversarial_labels() -> None:
    from eegfm.eeg.readout_study import fit_readouts, predict_readouts
    from sklearn.metrics import roc_auc_score

    train, validation = _training()
    for reversed_labels in [False, True]:
        if reversed_labels:
            train = {**train, "y": 1 - train["y"]}
        fits = fit_readouts(train, validation)
        assert fits["models"]["B"]["coefficient"][0] > 0
        scores = predict_readouts(fits, validation["x"])
        assert roc_auc_score(validation["y"], scores[:, 0]) == roc_auc_score(validation["y"], scores[:, 1])
        np.testing.assert_array_equal(np.argsort(scores[:, 0]), np.argsort(scores[:, 1]))
        if not reversed_labels:
            assert np.mean((scores[:, 0] >= 0) == validation["y"]) == 0.5
            assert np.mean((scores[:, 1] >= 0) == validation["y"]) == 1.0


def test_calibration_intercept_precision_preserves_near_threshold_validation_decisions() -> None:
    from eegfm.eeg.readout_study import fit_readouts
    from scipy.special import expit

    rng = np.random.default_rng(12)
    original_y, validation_y = np.tile([0, 1], 40), np.tile([0, 1], 20)
    x, validation_x = rng.normal(size=(80, 325)), rng.normal(size=(40, 325))
    x[:, 262] = 3 * (2 * original_y - 1) + rng.normal(0, 0.2, 80) + 5
    mean, scale = x[:, 262].mean(), x[:, 262].std()
    # Reversed training labels force the positive slope to its fixed floor.
    # A small intercept error can then overwhelm these legitimate small logits.
    validation_x[:, 262] = mean + scale * 0.001 * (2 * validation_y - 1)
    train_y = 1 - original_y
    fits = fit_readouts(_split(x, train_y, "t"), _split(validation_x, validation_y, "v"))
    for candidate in fits["models"]["B"]["selection_grid"]:
        assert candidate["coefficient"][0] == 1e-8
        assert candidate["validation_balanced_accuracy"] == 1.0
        logits = candidate["coefficient"][0] * (x[:, 262] - mean) / scale + candidate["intercept"]
        # The unpenalized intercept must solve its training score equation.
        assert abs(np.sum(expit(logits) - train_y)) < 1e-12


def test_gaussian_control_cannot_use_signal_in_other_input_columns() -> None:
    from eegfm.eeg.readout_study import fit_readouts, predict_readouts

    train, validation = _training()
    fits = fit_readouts(train, validation)
    x = validation["x"].copy()
    before = predict_readouts(fits, x)
    x[:, :263] *= -17
    after = predict_readouts(fits, x)
    np.testing.assert_array_equal(before[:, 4], after[:, 4])
    assert not np.allclose(before[:, 2], after[:, 2])
    # Duplicate Gaussian rows with opposite labels give exact chance accuracy.
    paired = np.repeat(validation["x"][::2], 2, axis=0)
    scores = predict_readouts(fits, paired)
    assert np.mean((scores[:, 4] >= 0) == np.tile([0, 1], 20)) == 0.5


def _evaluation_fixture() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = np.tile([0, 0, 1, 1], 4)
    subject = np.repeat(["a", "b", "c", "d"], 4)
    correct = np.array([[1, 1, 1, 1], [1, 0, 1, 0], [0, 0, 0, 0], [0, 1, 0, 1]], bool).ravel()
    a = np.where(correct, 2 * y - 1, 1 - 2 * y)
    c = 2 * y - 1
    return y, np.column_stack([a, a, c, -c, np.ones(len(y))]), subject


def test_bootstrap_is_paired_and_resamples_complete_participants() -> None:
    from eegfm.eeg.readout_study import evaluate_readouts
    from sklearn.metrics import roc_auc_score, log_loss

    y, scores, subjects = _evaluation_fixture()
    result = evaluate_readouts(y, scores, subjects, resamples=400, seed=23)
    # Independent literal row duplication, not the implementation's sufficient statistics.
    draws = np.random.default_rng(23).integers(0, 4, size=(400, 4))
    contrast = []
    for draw in draws:
        rows = np.concatenate([np.flatnonzero(subjects == "abcd"[i]) for i in draw])
        metrics = [np.mean([np.mean((scores[rows, k] >= 0)[y[rows] == label] == label)
                           for label in (0, 1)]) for k in range(5)]
        contrast.append(np.array(metrics) - metrics[0])
    np.testing.assert_allclose(result["contrasts"]["C-A"]["ci95"], np.quantile(np.array(contrast)[:, 2], [0.025, 0.975]))
    assert result["contrasts"]["B-A"]["ci95"] == [0.0, 0.0]
    assert result["contrasts"]["D-A"]["difference"] == -0.5
    assert result["contrasts"]["D-C"]["difference"] == -1.0
    assert result["contrasts"]["D-E"]["difference"] == -0.5
    np.testing.assert_allclose(result["contrasts"]["D-A"]["ci98_75"], np.quantile(np.array(contrast)[:, 3], [0.00625, 0.99375]))
    assert result["contrasts"]["C-A"]["primary"] is True
    assert "ci98_75" not in result["contrasts"]["C-A"]
    for k, name in enumerate("ABCDE"):
        actual = result["metrics"][name]
        assert actual["auroc"] == roc_auc_score(y, scores[:, k])
        assert actual["log_loss"] == pytest.approx(log_loss(y, 1 / (1 + np.exp(-scores[:, k]))))
    assert result == evaluate_readouts(y, scores, subjects, resamples=400, seed=23)
    json.dumps(result, allow_nan=False)


def test_closure_preserves_negative_and_above_one_ratios() -> None:
    from eegfm.eeg.readout_study import evaluate_readouts

    y = np.tile([0, 0, 1, 1], 3)
    subjects = np.repeat(["a", "b", "c"], 4)
    truth = 2 * y - 1
    a = truth.copy()
    a[::4] *= -1  # BA .75; E .5; D 1 => ratio 2.
    scores = np.column_stack([a, a, truth, truth, np.ones(len(y))])
    result = evaluate_readouts(y, scores, subjects, resamples=100)
    old = result["closure"]["old"]
    assert old["numerator"] == 0.5 and old["denominator"] == 0.25
    assert old["status"] == "stable" and old["ratio"] == 2.0
    assert old["ci95"] == [2.0, 2.0]
    scores[:, 3] = -truth
    negative = evaluate_readouts(y, scores, subjects, resamples=100)
    assert negative["closure"]["old"]["ratio"] == -2.0
    assert negative["closure"]["old"]["ci95"] == [-2.0, -2.0]


def test_closure_marks_weak_denominator_and_never_drops_undefined_draws() -> None:
    from eegfm.eeg.readout_study import evaluate_readouts

    y, scores, subjects = _evaluation_fixture()
    result = evaluate_readouts(y, scores, subjects, resamples=400, seed=23)
    old = result["closure"]["old"]
    assert old["status"] == "unstable"
    assert old["denominator_ci95"][0] <= 0.03
    assert old["ratio"] is None and old["ci95"] is None
    assert old["undefined_bootstrap_ratios"] > 0
    # A nonzero but weak point denominator remains visible, including its ratio.
    scores[:4, 0] = scores[:4, 2]
    scores[4:8, 0] = scores[4:8, 2]
    result = evaluate_readouts(y, scores, subjects, resamples=400, seed=23)
    old = result["closure"]["old"]
    assert old["status"] == "unstable"
    assert old["denominator"] == 0.125 and old["ratio"] == -4.0
    assert old["undefined_bootstrap_ratios"] > 0 and old["ci95"] is None


def test_default_bootstrap_invalidates_ratio_interval_even_when_denominator_is_stable() -> None:
    from eegfm.eeg.readout_study import evaluate_readouts

    y = np.tile([0, 0, 1, 1], 4)
    truth = 2 * y - 1
    subjects = np.repeat(["a", "b", "c", "d"], 4)
    old = truth.copy()
    old[:4] = 1
    scores = np.column_stack([old, old, truth, truth, np.ones(len(y))])
    result = evaluate_readouts(y, scores, subjects)
    closure = result["closure"]["old"]
    assert result["bootstrap"]["resamples"] == 10000
    assert result["bootstrap"]["seed"] == 161803
    assert closure["denominator_ci95"][0] > 0.03
    assert closure["status"] == "stable"
    draws = np.random.default_rng(161803).integers(0, 4, size=(10000, 4))
    assert closure["undefined_bootstrap_ratios"] == np.count_nonzero(np.all(draws == 0, axis=1))
    assert closure["undefined_bootstrap_ratios"] > 0
    assert closure["ci95"] is None


def test_bootstrap_pools_unequal_participant_windows_and_loss_is_stable() -> None:
    from eegfm.eeg.readout_study import evaluate_readouts

    y = np.array([0, 1, 0, 0, 0, 1])
    subjects = np.array(["a", "a", "b", "b", "b", "b"])
    truth = 2 * y - 1
    old = truth.copy()
    old[:2] *= -1
    scores = np.column_stack([old, old, truth, -truth, truth]) * 1e300
    result = evaluate_readouts(y, scores, subjects, resamples=100, seed=1)
    # Pooling class recalls yields (.75 + .5)/2; averaging subject BA gives .5.
    assert result["metrics"]["A"]["balanced_accuracy"] == 0.625
    assert result["metrics"]["D"]["log_loss"] == pytest.approx(1e300)
    assert result["metrics"]["C"]["log_loss"] == 0
    draws = np.random.default_rng(1).integers(0, 2, size=(100, 2))
    literal = [0.0 if np.all(draw == 0) else 1.0 if np.all(draw == 1) else 0.625 for draw in draws]
    np.testing.assert_allclose(result["metrics"]["A"]["balanced_accuracy_ci95"], np.quantile(literal, [0.025, 0.975]))
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("fault", ["width", "nan", "labels", "overlap", "duplicate_samples", "missing", "misaligned"])
def test_fit_rejects_malformed_or_overlapping_partitions(fault: str) -> None:
    from eegfm.eeg.readout_study import fit_readouts

    train, validation = _training()
    if fault == "width":
        train["x"] = train["x"][:, :-1]
    elif fault == "nan":
        train["x"][0, 0] = np.nan
    elif fault == "labels":
        train["y"] = np.full(80, 2)
    elif fault == "overlap":
        validation["subject_ids"][0] = train["subject_ids"][0]
    elif fault == "duplicate_samples":
        train["sample_ids"][1] = train["sample_ids"][0]
    elif fault == "missing":
        del train["y"]
    elif fault == "misaligned":
        train["subject_ids"] = train["subject_ids"][:-1]
    with pytest.raises(ValueError):
        fit_readouts(train, validation)


def test_prediction_rejects_corrupt_fits_and_input() -> None:
    from eegfm.eeg.readout_study import fit_readouts, predict_readouts

    train, validation = _training()
    fits = fit_readouts(train, validation)
    for name, field, value in [("B", "coefficient", [-1.0]), ("C", "scale", [0.0] * 200),
                               ("D", "coefficient", [1.0]), ("E", "intercept", np.inf),
                               ("A", "column", 0)]:
        broken = copy.deepcopy(fits)
        broken["models"][name][field] = value
        with pytest.raises(ValueError):
            predict_readouts(broken, validation["x"])
    with pytest.raises(ValueError):
        predict_readouts(fits, np.zeros((2, 324)))
    for field, value in [("training_samples", np.inf), ("validation_samples", 2.5),
                         ("training_subjects", 0), ("validation_subjects", 999)]:
        broken = copy.deepcopy(fits)
        broken[field] = value
        with pytest.raises(ValueError):
            predict_readouts(broken, validation["x"])


@pytest.mark.parametrize("fault", ["labels", "scores", "nan", "subject_shape", "single_subject", "missing_class", "resamples", "seed"])
def test_evaluation_rejects_invalid_schema_and_undefined_subject_metrics(fault: str) -> None:
    from eegfm.eeg.readout_study import evaluate_readouts

    y, scores, subjects = _evaluation_fixture()
    kwargs = {"resamples": 10, "seed": 3}
    if fault == "labels":
        y = np.ones(len(y))
    elif fault == "scores":
        scores = scores[:, :4]
    elif fault == "nan":
        scores[0, 1] = np.nan
    elif fault == "subject_shape":
        subjects = subjects[:, None]
    elif fault == "single_subject":
        subjects[:] = "a"
    elif fault == "missing_class":
        subjects[y == 0] = "a"
        subjects[y == 1] = "b"
    elif fault == "resamples":
        kwargs["resamples"] = 0
    elif fault == "seed":
        kwargs["seed"] = -1
    with pytest.raises(ValueError):
        evaluate_readouts(y, scores, subjects, **kwargs)
