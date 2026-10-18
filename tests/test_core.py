from __future__ import annotations

import numpy as np
import pytest

from eeg_scientist.cases import build_public_case, generate_case, hash_dataset
from eeg_scientist.experiments import (
    build_pipeline,
    compute_baselines,
    fit_and_score,
    labels_for_windows,
    make_trial_random_labels,
    make_window_random_labels,
    make_within_subject_permutation,
    score_prediction,
)
from eeg_scientist.schema import (
    CaseSpec,
    ExperimentContext,
    ExperimentRequest,
    ExperimentResult,
    FeatureDataset,
    Prediction,
    SplitIndices,
)
from eeg_scientist.splits import audit_split, build_all_splits, build_split


@pytest.fixture(scope="module")
def t_spec() -> CaseSpec:
    return CaseSpec(
        case_id="case_T_test",
        family="T",
        data_seed=1101,
        split_seed=2101,
        label_seed=3101,
        model_seed=4101,
    )


@pytest.fixture(scope="module")
def t_dataset(t_spec: CaseSpec) -> FeatureDataset:
    return generate_case(t_spec)


@pytest.fixture(scope="module")
def d_dataset() -> FeatureDataset:
    return generate_case(
        CaseSpec(case_id="case_D_test", family="D", data_seed=1102, split_seed=2102, label_seed=3102, model_seed=4102)
    )


def _small_dataset(labels: list[int], trial_ids: list[str], sample_ids: list[str]) -> FeatureDataset:
    n = len(labels)
    return FeatureDataset(
        x=np.zeros((n, 4), dtype=np.float64),
        y=np.asarray(labels, dtype=np.int64),
        sample_ids=sample_ids,
        subject_ids=["sub-00"] * n,
        session_uids=["sub-00_ses-00"] * n,
        trial_uids=trial_ids,
        feature_names=["f0", "f1", "f2", "f3"],
        case_id="synthetic_test",
    )


def test_trial_uid_is_globally_unique(t_dataset: FeatureDataset) -> None:
    assert len(set(t_dataset.trial_uids)) == 512
    splits = build_all_splits(t_dataset, 2101)
    audit = audit_split(t_dataset, splits["trial"])
    assert audit["overlap"]["trial"] == 0
    assert audit["overlap"]["sample"] == 0


def test_subject_split_disjoint(t_dataset: FeatureDataset) -> None:
    splits = build_all_splits(t_dataset, 2101)
    indices = splits["subject"]
    train_subjects = {t_dataset.subject_ids[int(i)] for i in indices.train_indices}
    test_subjects = {t_dataset.subject_ids[int(i)] for i in indices.test_indices}
    assert not (train_subjects & test_subjects)
    audit = audit_split(t_dataset, indices)
    assert audit["overlap"] == {"sample": 0, "trial": 0, "session": 0, "subject": 0}


def test_label_constant_within_trial(t_dataset: FeatureDataset) -> None:
    labels: dict[str, int] = {}
    for trial, label in zip(t_dataset.trial_uids, t_dataset.y.tolist(), strict=True):
        assert labels.setdefault(trial, label) == label


def test_array_lengths_match(t_dataset: FeatureDataset) -> None:
    with pytest.raises(ValueError):
        FeatureDataset(
            x=t_dataset.x[:-1],
            y=t_dataset.y,
            sample_ids=t_dataset.sample_ids,
            subject_ids=t_dataset.subject_ids,
            session_uids=t_dataset.session_uids,
            trial_uids=t_dataset.trial_uids,
            feature_names=t_dataset.feature_names,
            case_id="bad",
        )


def test_duplicate_samples_are_rejected() -> None:
    with pytest.raises(ValueError):
        _small_dataset([1, 1, 1, 1], ["t0", "t0", "t1", "t1"], ["s", "s", "s1", "s2"])


def test_same_seed_reproduces_data(t_spec: CaseSpec) -> None:
    first = generate_case(t_spec)
    second = generate_case(t_spec)
    assert hash_dataset(first) == hash_dataset(second)
    changed = t_spec.model_copy(update={"data_seed": 9999})
    assert hash_dataset(generate_case(changed)) != hash_dataset(first)


def test_public_case_has_no_private_fields() -> None:
    spec = CaseSpec(
        case_id="case_x",
        family="N",
        data_seed=1,
        split_seed=2,
        label_seed=3,
        model_seed=4,
        params={"sentinel_param": 1.0},
    )
    dataset = generate_case(spec)
    baseline = compute_baselines(dataset, build_all_splits(dataset, spec.split_seed))
    public = build_public_case(dataset, baseline)
    text = public.model_dump_json()
    for forbidden in ("family", "data_seed", "split_seed", "label_seed", "generator_version", "sentinel_param"):
        assert forbidden not in text
    assert public.data_source_type == "synthetic_features"


def test_default_split_sizes(t_dataset: FeatureDataset) -> None:
    for level in ("window", "trial", "subject"):
        indices = build_split(t_dataset, level, 2101)
        assert len(indices.train_indices) == 3072
        assert len(indices.test_indices) == 1024


def test_window_allows_trial_overlap_and_trial_isolates(t_dataset: FeatureDataset) -> None:
    window_audit = audit_split(t_dataset, build_split(t_dataset, "window", 2101))
    trial_audit = audit_split(t_dataset, build_split(t_dataset, "trial", 2101))
    assert window_audit["overlap"]["trial"] > 0
    assert window_audit["overlap"]["sample"] == 0
    assert trial_audit["overlap"]["trial"] == 0
    assert trial_audit["overlap"]["sample"] == 0


def test_scaler_fit_uses_training_rows_only(t_dataset: FeatureDataset, monkeypatch: pytest.MonkeyPatch) -> None:
    import eeg_scientist.experiments as experiments

    captured: dict[str, np.ndarray] = {}

    def spy() -> object:
        pipeline = build_pipeline()
        original_fit = pipeline.fit

        def fit(x: np.ndarray, y: np.ndarray) -> object:
            captured["x"] = np.asarray(x).copy()
            return original_fit(x, y)

        pipeline.fit = fit  # type: ignore[method-assign]
        return pipeline

    monkeypatch.setattr(experiments, "build_pipeline", spy)
    indices = build_split(t_dataset, "trial", 2101)
    score = fit_and_score(t_dataset, indices)
    assert score["valid"] is True
    assert np.allclose(captured["x"], t_dataset.x[indices.train_indices])


def test_trial_random_labels_shared_across_windows(t_dataset: FeatureDataset) -> None:
    mapping = make_trial_random_labels(t_dataset, 101)
    labels = labels_for_windows(t_dataset, mapping)
    grouped: dict[str, set[int]] = {}
    for trial, label in zip(t_dataset.trial_uids, labels.tolist(), strict=True):
        grouped.setdefault(trial, set()).add(int(label))
    assert all(len(values) == 1 for values in grouped.values())
    assert any(mapping[trial] != int(label) for trial, label in zip(t_dataset.trial_uids, t_dataset.y.tolist(), strict=True))


def test_within_subject_permutation_preserves_counts(t_dataset: FeatureDataset) -> None:
    mapping, reason = make_within_subject_permutation(t_dataset, 101)
    assert reason is None and mapping is not None
    original: dict[str, dict[int, int]] = {}
    changed: dict[str, dict[int, int]] = {}
    for trial, subject, label in zip(t_dataset.trial_uids, t_dataset.subject_ids, t_dataset.y.tolist(), strict=True):
        original.setdefault(subject, {})
        original[subject][int(label)] = original[subject].get(int(label), 0) + 1
        changed.setdefault(subject, {})
        new = mapping[trial]
        changed[subject][new] = changed[subject].get(new, 0) + 1
    assert original == changed
    invalid = _small_dataset([1, 1, 1, 1], ["t0", "t0", "t1", "t1"], ["a", "b", "c", "d"])
    invalid_mapping, invalid_reason = make_within_subject_permutation(invalid, 1)
    assert invalid_mapping is None
    assert invalid_reason is not None


def test_window_randomization_is_distinct_from_trial_randomization(t_dataset: FeatureDataset) -> None:
    trial_mapping = make_trial_random_labels(t_dataset, 101)
    trial_labels = labels_for_windows(t_dataset, trial_mapping)
    window_labels = make_window_random_labels(t_dataset, 101)
    first_trial = t_dataset.trial_uids[0]
    trial_positions = [i for i, trial in enumerate(t_dataset.trial_uids) if trial == first_trial]
    assert len({int(trial_labels[i]) for i in trial_positions}) == 1
    assert len({int(window_labels[i]) for i in trial_positions}) > 1


def test_ids_never_enter_feature_classifier(t_dataset: FeatureDataset, monkeypatch: pytest.MonkeyPatch) -> None:
    import eeg_scientist.experiments as experiments

    captured: dict[str, np.ndarray] = {}

    def spy() -> object:
        pipeline = build_pipeline()
        original_fit = pipeline.fit

        def fit(x: np.ndarray, y: np.ndarray) -> object:
            captured["x"] = np.asarray(x).copy()
            return original_fit(x, y)

        pipeline.fit = fit  # type: ignore[method-assign]
        return pipeline

    monkeypatch.setattr(experiments, "build_pipeline", spy)
    fit_and_score(t_dataset, build_split(t_dataset, "trial", 2101))
    assert captured["x"].dtype == np.float64
    assert captured["x"].shape[1] == len(t_dataset.feature_names)


def test_invalid_class_support_is_reported() -> None:
    dataset = _small_dataset([1, 1, 1, 1], ["t0", "t0", "t1", "t1"], ["a", "b", "c", "d"])
    indices = SplitIndices(
        train_indices=np.asarray([0, 1], dtype=np.int64),
        test_indices=np.asarray([2, 3], dtype=np.int64),
        split_level="trial",
        split_seed=1,
    )
    score = fit_and_score(dataset, indices)
    assert score["valid"] is False
    audit = audit_split(dataset, indices)
    assert audit["invalid_reason"] is not None


def test_nonfinite_metric_rejected(t_dataset: FeatureDataset) -> None:
    with pytest.raises(Exception):
        ExperimentResult(
            request_id="x",
            tool_id="split_audit",
            valid=True,
            metrics={"x": float("nan")},
            data_hash="d",
            config_hash="c",
            elapsed_seconds=0.1,
        )


def test_prediction_reference_and_hits() -> None:
    prediction = Prediction(
        scoring_status="numeric",
        metric_key="trial_random_trial_ba_mean",
        primary_direction="near_zero",
        threshold=0.05,
    )
    result = ExperimentResult(
        request_id="r",
        tool_id="trial_random_labels",
        valid=True,
        metrics={"trial_random_trial_ba_mean": 0.508},
        data_hash="d",
        config_hash="c",
        elapsed_seconds=0.1,
    )
    score = score_prediction(prediction, result)
    assert score["status"] == "scored"
    assert score["hit"] is True
    assert score["reference"] == 0.5
