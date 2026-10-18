"""Fixed classifier, diagnostic tools, randomization controls, and scoring."""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from typing import cast

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .cases import ALLOWED_TOOLS, hash_dataset
from .schema import (
    BaselineBundle,
    Decision,
    ExperimentContext,
    ExperimentRequest,
    ExperimentResult,
    FeatureDataset,
    Prediction,
    SplitIndices,
    SplitLevel,
)
from .splits import audit_all_splits, audit_split

SPLIT_LEVELS: tuple[SplitLevel, ...] = ("window", "trial", "subject")

SUPPORTED_METRIC_KEYS: dict[str, set[str]] = {
    "split_audit": {
        "window_balanced_accuracy",
        "trial_balanced_accuracy",
        "subject_balanced_accuracy",
        "gap_window_minus_trial",
        "gap_window_minus_subject",
        "gap_trial_minus_subject",
    },
    "trial_random_labels": {
        "trial_random_window_ba_mean",
        "trial_random_trial_ba_mean",
        "trial_random_gap_mean",
    },
    "trial_shuffle_within_subject": {
        "trial_shuffle_window_ba_mean",
        "trial_shuffle_trial_ba_mean",
        "trial_shuffle_gap_mean",
    },
    "window_random_labels": {
        "window_random_ba_mean",
        "window_random_ba_minus_chance",
    },
    "metadata_only": {
        "metadata_only_balanced_accuracy",
        "metadata_only_ba_minus_chance",
    },
}


class ExperimentError(RuntimeError):
    """Raised for an invalid experiment request or sealed request."""


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("knn", KNeighborsClassifier(n_neighbors=1)),
        ]
    )


def _finite(value: float) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError("non-finite metric")
    return number


def _trial_aggregate(
    dataset: FeatureDataset,
    test_indices: np.ndarray,
    probabilities: np.ndarray,
    classes: np.ndarray,
) -> tuple[float, int]:
    trial_probs: dict[str, list[np.ndarray]] = defaultdict(list)
    trial_truth: dict[str, int] = {}
    for row_pos, row in enumerate(test_indices.tolist()):
        trial_uid = dataset.trial_uids[int(row)]
        trial_probs[trial_uid].append(probabilities[row_pos])
        trial_truth[trial_uid] = int(dataset.y[int(row)])
    y_true: list[int] = []
    y_pred: list[int] = []
    for trial_uid in sorted(trial_probs):
        mean_prob = np.mean(np.stack(trial_probs[trial_uid], axis=0), axis=0)
        y_pred.append(int(classes[int(np.argmax(mean_prob))]))
        y_true.append(trial_truth[trial_uid])
    if len(set(y_true)) < 2:
        return float("nan"), len(y_true)
    return float(balanced_accuracy_score(y_true, y_pred)), len(y_true)


def fit_and_score(
    dataset: FeatureDataset,
    indices: SplitIndices,
    *,
    y_override: np.ndarray | None = None,
    x_override: np.ndarray | None = None,
) -> dict[str, object]:
    x = dataset.x if x_override is None else x_override
    y = dataset.y if y_override is None else y_override
    train = indices.train_indices
    test = indices.test_indices
    if x.shape[0] != len(y) or x.shape[0] != len(dataset.sample_ids):
        return {"valid": False, "invalid_reason": "row count mismatch", "metrics": {}}
    if len(set(y[train].tolist())) < 2:
        return {"valid": False, "invalid_reason": "training split has a single class", "metrics": {}}
    if len(set(y[test].tolist())) < 2:
        return {"valid": False, "invalid_reason": "test split has a single class", "metrics": {}}
    pipeline = build_pipeline()
    pipeline.fit(x[train], y[train])
    prediction = pipeline.predict(x[test])
    probabilities = pipeline.predict_proba(x[test])
    classes = np.asarray(pipeline.classes_)
    metrics: dict[str, float] = {
        "balanced_accuracy": _finite(balanced_accuracy_score(y[test], prediction)),
        "accuracy": _finite(accuracy_score(y[test], prediction)),
        "n_train": float(len(train)),
        "n_test": float(len(test)),
        "n_train_trials": float(len({dataset.trial_uids[int(i)] for i in train.tolist()})),
        "n_test_trials": float(len({dataset.trial_uids[int(i)] for i in test.tolist()})),
        "n_train_subjects": float(len({dataset.subject_ids[int(i)] for i in train.tolist()})),
        "n_test_subjects": float(len({dataset.subject_ids[int(i)] for i in test.tolist()})),
    }
    trial_ba, trial_n = _trial_aggregate(dataset, test, probabilities, classes)
    if np.isfinite(trial_ba):
        metrics["trial_aggregated_balanced_accuracy"] = _finite(trial_ba)
        metrics["trial_aggregated_n_trials"] = float(trial_n)
    per_subject: dict[str, float | None] = {}
    subject_rows: dict[str, list[int]] = defaultdict(list)
    for position, row in enumerate(test.tolist()):
        subject_rows[dataset.subject_ids[int(row)]].append(position)
    for subject, positions in sorted(subject_rows.items()):
        truth = y[test[positions]]
        predicted = prediction[positions]
        if len(set(truth.tolist())) < 2:
            per_subject[subject] = None
        else:
            per_subject[subject] = _finite(balanced_accuracy_score(truth, predicted))
    matrix = confusion_matrix(y[test], prediction, labels=[-1, 1]).tolist()
    return {
        "valid": True,
        "invalid_reason": None,
        "metrics": metrics,
        "details": {
            "confusion_matrix": matrix,
            "classes": [int(value) for value in classes.tolist()],
            "per_subject_balanced_accuracy": per_subject,
            "trial_aggregated_n_trials": trial_n,
        },
    }


def _config_hash(dataset: FeatureDataset, context: ExperimentContext) -> str:
    payload = {
        "data_hash": context.data_hash,
        "tool_version": context.tool_version,
        "classifier": context.classifier_config,
        "splits": {
            level: {"seed": indices.split_seed, "n_train": len(indices.train_indices), "n_test": len(indices.test_indices)}
            for level, indices in context.splits.items()
        },
        "random_label_seeds": context.random_label_seeds,
        "seed": context.seed,
        "case_id": dataset.case_id,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def compute_baselines(dataset: FeatureDataset, splits: dict[str, SplitIndices]) -> BaselineBundle:
    metrics: dict[str, float] = {}
    audits: dict[str, dict[str, object]] = {}
    details: dict[str, object] = {}
    for level in SPLIT_LEVELS:
        indices = splits[level]
        score = fit_and_score(dataset, indices)
        audits[level] = audit_split(dataset, indices)
        details[level] = score.get("details", {})
        if not score["valid"]:
            continue
        split_metrics = cast(dict[str, float], score["metrics"])
        for key, value in split_metrics.items():
            metrics[f"{level}_{key}"] = _finite(value)
    for left, right in (("window", "trial"), ("window", "subject"), ("trial", "subject")):
        left_key = f"{left}_balanced_accuracy"
        right_key = f"{right}_balanced_accuracy"
        if left_key in metrics and right_key in metrics:
            metrics[f"gap_{left}_minus_{right}"] = _finite(metrics[left_key] - metrics[right_key])
    data_hash = hash_dataset(dataset)
    context = ExperimentContext(
        splits=splits,
        random_label_seeds=[],
        tool_version="1.0",
        timeout_seconds=300,
        data_hash=data_hash,
        seed=0,
    )
    return BaselineBundle(
        metrics=metrics,
        audits={level: {**audits[level], "details": details[level]} for level in SPLIT_LEVELS},
        data_hash=data_hash,
        config_hash=_config_hash(dataset, context),
    )


def make_trial_random_labels(dataset: FeatureDataset, seed: int) -> dict[str, int]:
    rng = np.random.default_rng(seed)
    by_session: dict[str, list[str]] = defaultdict(list)
    trial_label: dict[str, int] = {}
    for trial_uid, session_uid, label in zip(dataset.trial_uids, dataset.session_uids, dataset.y.tolist(), strict=True):
        if trial_uid not in trial_label:
            trial_label[trial_uid] = int(label)
            by_session[session_uid].append(trial_uid)
    mapping: dict[str, int] = {}
    for session_uid in sorted(by_session):
        trials = sorted(by_session[session_uid])
        labels = [trial_label[trial] for trial in trials]
        rng.shuffle(labels)
        for trial, label in zip(trials, labels, strict=True):
            mapping[trial] = int(label)
    return mapping


def make_within_subject_permutation(dataset: FeatureDataset, seed: int) -> tuple[dict[str, int] | None, str | None]:
    rng = np.random.default_rng(seed)
    by_subject: dict[str, list[str]] = defaultdict(list)
    trial_label: dict[str, int] = {}
    for trial_uid, subject_id, label in zip(dataset.trial_uids, dataset.subject_ids, dataset.y.tolist(), strict=True):
        if trial_uid not in trial_label:
            trial_label[trial_uid] = int(label)
            by_subject[subject_id].append(trial_uid)
    mapping: dict[str, int] = {}
    for subject_id in sorted(by_subject):
        trials = sorted(by_subject[subject_id])
        labels = [trial_label[trial] for trial in trials]
        if len(set(labels)) < 2:
            return None, f"subject {subject_id} has a single class and cannot be permuted"
        rng.shuffle(labels)
        for trial, label in zip(trials, labels, strict=True):
            mapping[trial] = int(label)
    return mapping, None


def make_window_random_labels(dataset: FeatureDataset, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    labels = dataset.y.copy()
    rng.shuffle(labels)
    return labels


def labels_for_windows(dataset: FeatureDataset, mapping: dict[str, int]) -> np.ndarray:
    return np.asarray([mapping[trial] for trial in dataset.trial_uids], dtype=np.int64)


def _mapping_changed(dataset: FeatureDataset, mapping: dict[str, int]) -> bool:
    return any(mapping[trial] != int(label) for trial, label in zip(dataset.trial_uids, dataset.y.tolist(), strict=True))


def _distribution(values: list[float], prefix: str) -> dict[str, float]:
    finite = np.asarray([value for value in values if np.isfinite(value)], dtype=np.float64)
    if len(finite) == 0:
        return {}
    return {
        f"{prefix}_mean": float(np.mean(finite)),
        f"{prefix}_std": float(np.std(finite)),
        f"{prefix}_min": float(np.min(finite)),
        f"{prefix}_max": float(np.max(finite)),
    }


def _randomization_result(
    dataset: FeatureDataset,
    context: ExperimentContext,
    *,
    tool_id: str,
    mapping_factory: str,
) -> tuple[dict[str, float], dict[str, object], dict[str, object], bool, str | None]:
    per_seed: list[dict[str, object]] = []
    window_values: list[float] = []
    trial_values: list[float] = []
    gap_values: list[float] = []
    invalid_reasons: list[str] = []
    for seed in context.random_label_seeds:
        mapping: dict[str, int] | None
        invalid_reason: str | None
        if mapping_factory == "trial":
            mapping = make_trial_random_labels(dataset, seed)
            invalid_reason = None
        elif mapping_factory == "subject":
            mapping, invalid_reason = make_within_subject_permutation(dataset, seed)
        else:
            raise ValueError(f"unknown mapping factory {mapping_factory}")
        if mapping is None or invalid_reason is not None:
            invalid_reasons.append(f"{seed}: {invalid_reason}")
            per_seed.append({"seed": seed, "valid": False, "invalid_reason": invalid_reason})
            continue
        random_y = labels_for_windows(dataset, mapping)
        window_score = fit_and_score(dataset, context.splits["window"], y_override=random_y)
        trial_score = fit_and_score(dataset, context.splits["trial"], y_override=random_y)
        window_ba = float(cast(dict[str, float], window_score["metrics"]).get("balanced_accuracy", float("nan")))
        trial_ba = float(cast(dict[str, float], trial_score["metrics"]).get("balanced_accuracy", float("nan")))
        gap = window_ba - trial_ba if np.isfinite(window_ba) and np.isfinite(trial_ba) else float("nan")
        if window_score["valid"]:
            window_values.append(window_ba)
        if trial_score["valid"]:
            trial_values.append(trial_ba)
        if np.isfinite(gap):
            gap_values.append(gap)
        per_seed.append(
            {
                "seed": seed,
                "valid": bool(window_score["valid"] and trial_score["valid"]),
                "mapping_changed": _mapping_changed(dataset, mapping),
                "window_ba": window_ba if np.isfinite(window_ba) else None,
                "trial_ba": trial_ba if np.isfinite(trial_ba) else None,
                "gap": gap if np.isfinite(gap) else None,
                "invalid_reason": None if window_score["valid"] and trial_score["valid"] else "score invalid",
            }
        )
    metrics: dict[str, float] = {}
    metrics.update(_distribution(window_values, f"{tool_id}_window_ba"))
    metrics.update(_distribution(trial_values, f"{tool_id}_trial_ba"))
    metrics.update(_distribution(gap_values, f"{tool_id}_gap"))
    valid = len(window_values) > 0 and len(trial_values) > 0
    randomization = {
        "tool_id": tool_id,
        "seeds": list(context.random_label_seeds),
        "per_seed": per_seed,
        "n_valid_seeds": len(window_values),
        "invalid_reasons": invalid_reasons,
    }
    details = {"n_seeds": len(context.random_label_seeds), "n_valid_seeds": len(window_values)}
    return metrics, randomization, details, valid, None if valid else "no valid randomization seed"


def _metadata_only(
    dataset: FeatureDataset,
    context: ExperimentContext,
) -> tuple[dict[str, float], dict[str, object], bool, str | None]:
    indices = context.splits["trial"]
    train = indices.train_indices
    test = indices.test_indices
    metadata = np.asarray(
        [[subject, session] for subject, session in zip(dataset.subject_ids, dataset.session_uids, strict=True)],
        dtype=object,
    )
    try:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # pragma: no cover - older scikit-learn compatibility
        encoder = OneHotEncoder(handle_unknown="ignore", sparse=False)  # type: ignore[call-arg]
    encoder.fit(metadata[train])
    x_metadata = encoder.transform(metadata)
    score = fit_and_score(dataset, indices, x_override=x_metadata)
    if not score["valid"]:
        return {}, {"confusion_matrix": []}, False, str(score["invalid_reason"])
    split_metrics = cast(dict[str, float], score["metrics"])
    metrics = {
        "metadata_only_balanced_accuracy": _finite(split_metrics["balanced_accuracy"]),
        "metadata_only_accuracy": _finite(split_metrics["accuracy"]),
        "metadata_only_ba_minus_chance": _finite(split_metrics["balanced_accuracy"] - 0.5),
    }
    details = {
        "n_metadata_columns": int(x_metadata.shape[1]),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "confusion_matrix": cast(dict[str, object], score["details"])["confusion_matrix"],
    }
    return metrics, details, True, None


def execute_experiment(
    dataset: FeatureDataset,
    request: ExperimentRequest,
    context: ExperimentContext,
) -> ExperimentResult:
    if request.tool_id not in ALLOWED_TOOLS:
        raise ExperimentError(f"unknown tool {request.tool_id}")
    if request.parameters:
        raise ExperimentError("tools accept no parameters")
    started = time.perf_counter()
    audit = audit_all_splits(dataset, context.splits)
    metrics: dict[str, float] = {}
    randomization: dict[str, object] = {}
    details: dict[str, object] = {}
    valid = True
    invalid_reason: str | None = None

    if request.tool_id == "split_audit":
        baseline = compute_baselines(dataset, context.splits)
        metrics = dict(baseline.metrics)
        audit = baseline.audits
        details = {
            "per_subject_balanced_accuracy": {
                level: cast(dict[str, object], audit[level].get("details", {})).get("per_subject_balanced_accuracy", {})
                for level in SPLIT_LEVELS
            },
            "estimand_note": "window split shares trials; its trial aggregation is diagnostic only",
        }
    elif request.tool_id == "trial_random_labels":
        metrics, randomization, details, valid, invalid_reason = _randomization_result(
            dataset, context, tool_id="trial_random", mapping_factory="trial"
        )
    elif request.tool_id == "trial_shuffle_within_subject":
        metrics, randomization, details, valid, invalid_reason = _randomization_result(
            dataset, context, tool_id="trial_shuffle", mapping_factory="subject"
        )
    elif request.tool_id == "window_random_labels":
        per_seed: list[dict[str, object]] = []
        values: list[float] = []
        for seed in context.random_label_seeds:
            random_y = make_window_random_labels(dataset, seed)
            score = fit_and_score(dataset, context.splits["window"], y_override=random_y)
            value = float(cast(dict[str, float], score["metrics"]).get("balanced_accuracy", float("nan")))
            if score["valid"]:
                values.append(value)
            per_seed.append(
                {
                    "seed": seed,
                    "valid": bool(score["valid"]),
                    "balanced_accuracy": value if np.isfinite(value) else None,
                }
            )
        metrics = _distribution(values, "window_random_ba")
        if "window_random_ba_mean" in metrics:
            metrics["window_random_ba_minus_chance"] = _finite(metrics["window_random_ba_mean"] - 0.5)
        randomization = {
            "tool_id": "window_random",
            "seeds": list(context.random_label_seeds),
            "per_seed": per_seed,
            "n_valid_seeds": len(values),
        }
        details = {"n_seeds": len(context.random_label_seeds), "trial_aggregation": "not applicable"}
        valid = len(values) > 0
        if not valid:
            invalid_reason = "no valid window randomization seed"
    elif request.tool_id == "metadata_only":
        metrics, details, valid, invalid_reason = _metadata_only(dataset, context)
    else:  # pragma: no cover - guarded above
        raise ExperimentError(f"unknown tool {request.tool_id}")

    elapsed = time.perf_counter() - started
    return ExperimentResult(
        request_id=request.request_id,
        tool_id=request.tool_id,
        valid=valid,
        invalid_reason=invalid_reason,
        metrics={key: _finite(value) for key, value in metrics.items()},
        randomization=randomization,
        audit=audit,
        data_hash=context.data_hash,
        config_hash=_config_hash(dataset, context),
        elapsed_seconds=float(elapsed),
        details=details,
    )


def run_sealed_experiment(
    dataset: FeatureDataset,
    sealed: object,
    context: ExperimentContext,
) -> ExperimentResult:
    """Execute only after verifying the sealed prediction exists on disk."""
    from .storage import verify_sealed

    if not verify_sealed(sealed):
        raise ExperimentError("sealed prediction is missing or does not match the event log")
    request = getattr(sealed, "request", None)
    if not isinstance(request, ExperimentRequest):
        raise ExperimentError("sealed request is malformed")
    return execute_experiment(dataset, request, context)


def metric_reference(metric_key: str) -> float:
    """Balanced-accuracy metrics are compared with chance (0.5); gaps with 0."""
    if metric_key.endswith("_ba_minus_chance") or "minus_chance" in metric_key:
        return 0.0
    if metric_key.endswith("_balanced_accuracy") or metric_key.endswith("_ba_mean"):
        return 0.5
    return 0.0


def observed_direction(value: float, threshold: float, reference: float = 0.0) -> str:
    delta = value - reference
    if delta > threshold:
        return "positive"
    if delta < -threshold:
        return "negative"
    return "near_zero"


def score_prediction(prediction: Prediction, result: ExperimentResult) -> dict[str, object]:
    if prediction.scoring_status == "not_applicable":
        return {"status": "not_applicable", "hit": None, "observed_direction": None, "metric_key": None, "value": None}
    if not result.valid or prediction.metric_key is None or prediction.primary_direction is None:
        return {"status": "invalid", "hit": None, "observed_direction": None, "metric_key": prediction.metric_key, "value": None}
    value = result.metrics.get(prediction.metric_key)
    if value is None:
        return {
            "status": "invalid",
            "hit": None,
            "observed_direction": None,
            "metric_key": prediction.metric_key,
            "value": None,
        }
    reference = metric_reference(prediction.metric_key)
    direction = observed_direction(float(value), prediction.threshold, reference)
    return {
        "status": "scored",
        "hit": direction == prediction.primary_direction,
        "observed_direction": direction,
        "metric_key": prediction.metric_key,
        "value": float(value),
        "reference": reference,
        "delta": float(value) - reference,
    }


def validate_request_against_tool(request: ExperimentRequest) -> None:
    if request.tool_id not in ALLOWED_TOOLS:
        raise ExperimentError(f"unknown tool {request.tool_id}")
    if request.parameters:
        raise ExperimentError("tools accept no parameters")
    if request.prediction.scoring_status == "numeric":
        allowed = SUPPORTED_METRIC_KEYS[request.tool_id]
        if request.prediction.metric_key not in allowed:
            raise ExperimentError(f"metric {request.prediction.metric_key} is not supported by {request.tool_id}")
