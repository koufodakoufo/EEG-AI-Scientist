"""Fixed residual-recovery statistics and declarative candidate identities.

Passing numerical gates is not a source or replay audit. Neither method
declarations nor a preparation receipt prove the computations they describe.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path
import re
from typing import Any

import numpy as np

from eegfm.evaluation.bundle import canonical_bytes, safe_relative
from eegfm.evaluation.worker import _path

TASK_ID = "eegmat-residual-recovery-v1"
VIEWS = ("identity", "leace", "random_2301", "random_2302", "random_2303")
TARGET_COLUMNS = (12, 13, 14, 15, 16, 17)
FEATURE_COUNT = 200
BASELINE_MODELS = ("linear", "linear_shuffled")
MODELS = (*BASELINE_MODELS, "flexible", "flexible_shuffled")
METHOD_SCHEMA = "residual_recovery_method_v1"
IDENTITY_SCHEMA = "residual_baseline_identity_v1"
QUALIFICATION_SCHEMA = "residual_recovery_qualification_v1"
QUALIFICATION_ROLES = frozenset({
    "public_train", "public_validation", "inference_validation", "inference_test",
    "truth_train", "truth_validation", "truth_test", "split_manifest",
})
PROVENANCE_FIELDS = frozenset(name + "_sha256" for name in (
    "input_manifest", "pooling_source", "join_source", "feature_registry", "backbone_identity",
    "export_identity", "api_source", "preparer_source", "shuffle_permutation", "checks_receipt",
))
QUALIFICATION_CHECKS = frozenset({
    "source_versions_match", "joins_exact", "split_disjoint", "eraser_checks_passed", "pooling_parity_passed",
})
VARIANCE_FLOOR = 1e-12
SHUFFLE_SEED = 230418
BOOTSTRAP_SEED = 230419
BOOTSTRAP_RESAMPLES = 10000
QUANTILES = (.025, .975)
USEFUL_MARGIN = .05
MAX_METHOD_BYTES = 64 * 1024
MAX_PARAMETER_ARRAYS = 128
MAX_PARAMETER_ELEMENTS = 1_000_000
MAX_PARAMETER_RANK = 4
MAX_RECIPES = 4


def _require_fields(value: Any, expected: set[str] | frozenset[str], description: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"Invalid {description} fields")


def _check_sha(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid SHA256")
    return value


def validate_qualification(document: dict[str, Any], expected_roles: dict[str, str]) -> dict[str, Any]:
    """Check an exact trusted preparation attestation against all eight roles."""
    _require_fields(document, {"schema_version", "status", "task_id", "not_project_unseen_confirmation",
                               "bindings", "source_provenance", "checks"}, "qualification")
    _require_fields(expected_roles, QUALIFICATION_ROLES, "expected qualification roles")
    if (document["schema_version"] != QUALIFICATION_SCHEMA
            or document["status"] != "cached_residual_inputs_qualified_for_development"
            or document["task_id"] != TASK_ID or document["not_project_unseen_confirmation"] is not True):
        raise ValueError("Invalid qualification identity")
    records = document["bindings"]
    if not isinstance(records, list) or len(records) != len(QUALIFICATION_ROLES):
        raise ValueError("Invalid qualification bindings")
    roles = {}
    for record in records:
        _require_fields(record, {"role", "sha256"}, "qualification binding")
        role = record["role"]
        if not isinstance(role, str) or role not in QUALIFICATION_ROLES or role in roles:
            raise ValueError("Invalid or duplicate qualification binding")
        roles[role] = _check_sha(record["sha256"])
    if roles != {name: _check_sha(value) for name, value in expected_roles.items()}:
        raise ValueError("Residual qualification role binding mismatch")
    _require_fields(document["source_provenance"], PROVENANCE_FIELDS, "qualification source provenance")
    for digest in document["source_provenance"].values():
        _check_sha(digest)
    _require_fields(document["checks"], QUALIFICATION_CHECKS, "qualification checks")
    if any(value is not True for value in document["checks"].values()):
        raise ValueError("Qualification checks must all attest success")
    return document


def _source_relative(name: str) -> Path:
    if not isinstance(name, str) or any(ord(char) < 32 for char in name):
        raise ValueError("Invalid baseline source path")
    path = safe_relative(name)
    if (path.name.lower() == "parameters.npz"
            or any(part.startswith(".") or part.rstrip(" .") != part for part in path.parts)):
        raise ValueError("Invalid baseline source path")
    return path


def validate_method_manifest(document: dict[str, Any]) -> dict[str, Any]:
    """Validate candidate text declarations without evaluating their semantics."""
    _require_fields(document, {"schema_version", "phase", "baseline_sources", "families", "parameter_schema"},
                    "method")
    try:
        length = len(canonical_bytes(document))
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("Method manifest must be finite UTF-8 JSON") from error
    if length > MAX_METHOD_BYTES:
        raise ValueError("Method manifest exceeds byte cap")
    if document["schema_version"] != METHOD_SCHEMA or document["phase"] not in ("baseline", "final"):
        raise ValueError("Invalid method schema or phase")
    sources = document["baseline_sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("Baseline sources must be a nonempty list")
    for source in sources:
        _source_relative(source)
    if sorted(set(sources)) != sources:
        raise ValueError("Baseline source paths must be sorted and unique")
    families = {"linear"} if document["phase"] == "baseline" else {"linear", "flexible"}
    _require_fields(document["families"], families, "model families")
    for family in document["families"].values():
        _require_fields(family, {"description", "recipes"}, "family")
        if not isinstance(family["description"], str) or not family["description"].strip():
            raise ValueError("Family description must be nonempty text")
        _require_fields(family["recipes"], set(VIEWS), "recipe views")
        for recipes in family["recipes"].values():
            if not isinstance(recipes, list) or not 1 <= len(recipes) <= MAX_RECIPES:
                raise ValueError("Declare one to four recipes per family and view")
            for recipe in recipes:
                _require_fields(recipe, {"preprocessing", "hyperparameters"}, "recipe")
    schema = document["parameter_schema"]
    selected_keys = {family + "__selected" for family in families}
    models = BASELINE_MODELS if document["phase"] == "baseline" else MODELS
    if not isinstance(schema, dict) or not selected_keys <= set(schema) or len(schema) > MAX_PARAMETER_ARRAYS:
        raise ValueError("Invalid parameter schema or missing selected recipe declaration")
    for name, record in schema.items():
        if (not isinstance(name, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name) is None
                or not any(name.startswith(model + "__") and len(name) > len(model) + 2 for model in models)
                or name in {"linear_shuffled__selected", "flexible_shuffled__selected"}):
            raise ValueError("Invalid residual parameter namespace")
        _require_fields(record, {"dtype", "shape", "purpose"}, "parameter declaration")
        if not isinstance(record["dtype"], str) or not record["dtype"]:
            raise ValueError("Parameter dtype must be explicit")
        try:
            dtype = np.dtype(record["dtype"])
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid parameter dtype") from error
        shape = record["shape"]
        if (dtype.kind not in "biuf" or not isinstance(shape, list) or len(shape) > MAX_PARAMETER_RANK
                or any(type(size) is not int or not 0 <= size <= np.iinfo(np.intp).max for size in shape)
                or math.prod(shape) > MAX_PARAMETER_ELEMENTS
                or not isinstance(record["purpose"], str) or not record["purpose"].strip()):
            raise ValueError("Invalid bounded numeric parameter declaration")
        if name in selected_keys and (dtype != np.dtype("int64") or shape != [len(VIEWS)]):
            raise ValueError("Selected recipes must be int64[5]")
    return document


def validate_parameters(method: dict[str, Any], parameters: dict[str, np.ndarray]) -> None:
    """Check the numeric arrays against a previously validated declaration."""
    schema = method["parameter_schema"]
    if set(parameters) != set(schema):
        raise ValueError("Numeric parameters differ from the declared member set")
    for name, value in parameters.items():
        record = schema[name]
        if (not isinstance(value, np.ndarray) or value.dtype != np.dtype(record["dtype"])
                or list(value.shape) != record["shape"] or not np.isfinite(value).all()):
            raise ValueError("Numeric parameter disagrees with declared dtype, shape or finiteness")
    for family, declaration in method["families"].items():
        selected = parameters[family + "__selected"]
        if any(not 0 <= index < len(declaration["recipes"][view]) for view, index in zip(VIEWS, selected)):
            raise ValueError("Selected recipe index is outside its view's declared grid")


def _numeric_sha(array: np.ndarray) -> str:
    digest = hashlib.sha256(canonical_bytes({"dtype": array.dtype.str, "shape": list(array.shape)}))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _source_hashes(candidate: Path, names: list[str]) -> dict[str, str]:
    root = _path(candidate, directory=True)
    sources = {}
    for name in names:
        source = _path(root / _source_relative(name))
        source.resolve(strict=True).relative_to(root.resolve(strict=True))
        try:
            data = source.read_bytes()
            data.decode("utf-8")
        except UnicodeError as error:
            raise ValueError("Baseline sources must be UTF-8 text") from error
        if b"\0" in data:
            raise ValueError("Baseline sources must be UTF-8 text")
        sources[name] = hashlib.sha256(data).hexdigest()
    return sources


def baseline_identity(candidate: Path, method: dict[str, Any], parameters: dict[str, np.ndarray],
                      predictions: np.ndarray, *, public_manifest_sha256: str,
                      inference_sha256: str) -> dict[str, Any]:
    """Fingerprint the baseline contents only, independent of ZIP metadata and job identity."""
    validate_method_manifest(method)
    validate_parameters(method, parameters)
    _check_predictions(predictions, len(predictions) if isinstance(predictions, np.ndarray) and predictions.ndim else 0)
    models = BASELINE_MODELS if method["phase"] == "baseline" else MODELS
    if predictions.shape[2] != len(models):
        raise ValueError("Prediction model count differs from declared phase")
    names = sorted(name for name in parameters if name.startswith(("linear__", "linear_shuffled__")))
    return {
        "schema_version": IDENTITY_SCHEMA, "task_id": TASK_ID, "method_schema": METHOD_SCHEMA,
        "baseline_sources": _source_hashes(candidate, method["baseline_sources"]), "linear_family": deepcopy(method["families"]["linear"]),
        "baseline_parameter_schema": {name: deepcopy(method["parameter_schema"][name]) for name in names},
        "selected_indices": parameters["linear__selected"].tolist(),
        "baseline_parameters_sha256": {name: _numeric_sha(parameters[name]) for name in names},
        "validation_predictions_sha256": _numeric_sha(predictions[:, :, :len(BASELINE_MODELS), :]),
        "public_manifest_sha256": _check_sha(public_manifest_sha256),
        "inference_sha256": _check_sha(inference_sha256),
    }


def _check_targets(values: np.ndarray) -> None:
    if (not isinstance(values, np.ndarray) or values.dtype != np.dtype("float64")
            or values.ndim != 2 or values.shape[1] != len(TARGET_COLUMNS) or len(values) < 1):
        raise ValueError("Expected nonempty float64[N,6] targets")
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite targets")


def _check_predictions(predictions: np.ndarray, n: int) -> None:
    if (not isinstance(predictions, np.ndarray) or predictions.dtype != np.dtype("float64")
            or predictions.ndim != 4 or predictions.shape[:2] != (n, len(VIEWS)) or n < 1
            or predictions.shape[2] not in (len(BASELINE_MODELS), len(MODELS))
            or predictions.shape[3] != len(TARGET_COLUMNS)):
        raise ValueError("Expected float64[N,5,M,6] predictions with M=2 or 4")
    if not np.isfinite(predictions).all():
        raise ValueError("Nonfinite predictions")


def _active(values: np.ndarray) -> np.ndarray:
    centered = values - values.mean(axis=0)
    return np.mean(centered**2, axis=0) > VARIANCE_FLOOR * np.maximum(1., np.mean(values**2, axis=0))


def _target_masks(train_y: np.ndarray, evaluation_y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    _check_targets(train_y)
    _check_targets(evaluation_y)
    with np.errstate(over="raise", invalid="raise"):
        try:
            return _active(train_y), _active(evaluation_y)
        except FloatingPointError as error:
            raise ValueError("Nonfinite target moments") from error


def fixed_target_mask(train_y: np.ndarray, evaluation_y: np.ndarray) -> np.ndarray:
    active, estimable = _target_masks(train_y, evaluation_y)
    return active & estimable


def _sums(y: np.ndarray, losses: np.ndarray, subjects: np.ndarray) -> tuple[np.ndarray, ...]:
    """Participant sufficient statistics; keep centered sums of squares stable."""
    counts, means, centered_ss, y2, errors = [], [], [], [], []
    for index in range(int(subjects.max()) + 1):
        rows = subjects == index
        block = y[rows]
        mean = block.mean(axis=0)
        counts.append(len(block))
        means.append(mean)
        centered_ss.append(np.sum((block - mean)**2, axis=0))
        y2.append(np.sum(block**2, axis=0))
        errors.append(losses[rows].sum(axis=0))
    return tuple(np.asarray(item) for item in (counts, means, centered_ss, y2, errors))


def _sample_scores(draws: np.ndarray, sums: tuple[np.ndarray, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Pool repeated blocks, using within- and between-participant sums of squares."""
    counts, means, centered_ss, y2, losses = sums
    weights = counts[draws, None]
    block_means = means[draws]
    n = weights.sum(axis=1)
    average = (block_means * weights).sum(axis=1) / n
    ss = (centered_ss[draws] + weights * (block_means - average[:, None])**2).sum(axis=1)
    valid = (ss / n > VARIANCE_FLOOR * np.maximum(1., y2[draws].sum(axis=1) / n)).all(axis=1)
    scores = np.full((len(draws), *losses.shape[1:-1]), np.nan)
    if valid.any():
        per_column = 1. - losses[draws[valid]].sum(axis=1) / ss[valid, None, None, :]
        scores[valid] = per_column.mean(axis=-1)
    return scores, valid


def _contrast_indices(models: tuple[str, ...]) -> dict[str, tuple[int, int]]:
    contrasts = {"linear_minus_shuffled": (0, 1), "linear_minus_train_mean": (0, len(models))}
    if models == MODELS:
        contrasts.update({"flexible_minus_shuffled": (2, 3), "flexible_minus_linear": (2, 0),
                          "flexible_minus_train_mean": (2, len(models))})
    return contrasts


def _score(train_y: np.ndarray, y: np.ndarray, predictions: np.ndarray, subjects: np.ndarray,
           active: np.ndarray, estimable: np.ndarray, resamples: int, seed: int) -> dict[str, Any]:
    mask = active & estimable
    models = MODELS if predictions.shape[2] == len(MODELS) else BASELINE_MODELS
    names = (*models, "train_mean")
    contrasts = _contrast_indices(models)
    evaluation = y[:, mask]
    train_mean = train_y.mean(axis=0)[mask]
    model_losses = (evaluation[:, None, None, :] - predictions[..., mask])**2
    mean_losses = np.broadcast_to((evaluation - train_mean)[:, None, None, :]**2,
                                  (len(y), len(VIEWS), 1, mask.sum()))
    losses = np.concatenate((model_losses, mean_losses), axis=2)
    denominator = ((evaluation - evaluation.mean(axis=0))**2).sum(axis=0)
    columns = 1. - losses.sum(axis=0) / denominator
    points = columns.mean(axis=-1)
    sums = _sums(evaluation, losses, subjects)
    participant_count = len(sums[0])
    rng = np.random.Generator(np.random.PCG64(seed))
    sampled = np.empty((resamples, len(VIEWS), len(names)))
    valid_count = 0
    # Bound advanced-index intermediates regardless of participant count.
    batch = min(256, max(1, 262144 // (participant_count * len(VIEWS) * len(names) * mask.sum())))
    for start in range(0, resamples, batch):
        stop = min(start + batch, resamples)
        draws = rng.integers(0, participant_count, size=(stop - start, participant_count))
        sampled[start:stop], valid = _sample_scores(draws, sums)
        valid_count += int(valid.sum())
    intervals_valid = valid_count == resamples

    def ci(values: np.ndarray) -> list[float] | None:
        return np.quantile(values, QUANTILES, method="linear").tolist() if intervals_valid else None

    def with_mask(values: np.ndarray) -> list[float | None]:
        results: list[float | None] = [None] * len(TARGET_COLUMNS)
        for index, value in zip(np.flatnonzero(mask), values):
            results[index] = float(value)
        return results

    views = {
        view: {name: {"r2": float(points[i, j]), "ci95": ci(sampled[:, i, j]),
                      "per_column_r2": with_mask(columns[i, j])}
               for j, name in enumerate(names)}
        for i, view in enumerate(VIEWS)
    }
    differences = {
        view: {name: {"delta": float(points[i, left] - points[i, right]),
                      "ci95": ci(sampled[:, i, left] - sampled[:, i, right]),
                      "per_column_delta": with_mask(columns[i, left] - columns[i, right])}
               for name, (left, right) in contrasts.items()}
        for i, view in enumerate(VIEWS)
    }
    loo = []
    indices = np.arange(participant_count)
    for omitted in indices:
        record: dict[str, Any] = {"omission_index": int(omitted), "status": "undefined", "views": None,
                                  "contrasts": None}
        if participant_count > 1:
            estimate, valid = _sample_scores(indices[indices != omitted][None, :], sums)
            if valid[0]:
                record.update(status="defined",
                              views={view: dict(zip(names, estimate[0, i].tolist()))
                                     for i, view in enumerate(VIEWS)},
                              contrasts={view: {name: float(estimate[0, i, left] - estimate[0, i, right])
                                                for name, (left, right) in contrasts.items()}
                                         for i, view in enumerate(VIEWS)})
        loo.append(record)

    def gate(points_pass: bool, intervals_pass: bool, *, diagnostic_points_positive: bool) -> str:
        # Diagnostic points distinguish an imprecise estimate from a descriptive result;
        # only the registered inequalities determine whether the gate passes.
        if not intervals_valid:
            return "inconclusive"
        if points_pass and intervals_pass:
            return "passed"
        return "inconclusive" if points_pass and diagnostic_points_positive else "descriptive"

    def lower_exceeds(record: dict[str, Any], threshold: float) -> bool:
        return record["ci95"] is not None and record["ci95"][0] > threshold

    linear_shuffle = differences["leace"]["linear_minus_shuffled"]
    linear = gate(views["leace"]["linear"]["r2"] > 0, lower_exceeds(linear_shuffle, 0),
                  diagnostic_points_positive=linear_shuffle["delta"] > 0)
    useful = identity = "not_applicable"
    primary = None
    if models == MODELS:
        contrast = differences["leace"]["flexible_minus_linear"]
        primary = {"delta": contrast["delta"], "ci95": contrast["ci95"]}
        identity_shuffle = differences["identity"]["flexible_minus_shuffled"]
        identity_positive = views["identity"]["flexible"]["r2"] > 0
        identity = gate(identity_positive, lower_exceeds(identity_shuffle, 0),
                        diagnostic_points_positive=identity_shuffle["delta"] > 0)
        leace_shuffle = differences["leace"]["flexible_minus_shuffled"]
        useful = gate(views["leace"]["flexible"]["r2"] > 0 and primary["delta"] > USEFUL_MARGIN,
                      lower_exceeds(leace_shuffle, 0) and lower_exceeds(primary, USEFUL_MARGIN)
                      and identity == "passed",
                      diagnostic_points_positive=leace_shuffle["delta"] > 0 and identity != "descriptive")

    return {
        "target_mask": mask.tolist(),
        "targets": [{"column": column, "included": bool(mask[i]),
                     "exclusions": [reason for reason, keep in (("B_train_inactive", active[i]),
                                                                ("evaluation_unestimable", estimable[i]))
                                    if not keep]}
                    for i, column in enumerate(TARGET_COLUMNS)],
        "rows": len(y), "participants": participant_count, "model_order": list(models), "view_order": list(VIEWS),
        "views": views, "contrasts": differences, "primary": primary, "leave_one_participant_out": loo,
        "bootstrap": {"requested": resamples, "valid": valid_count, "invalid": resamples - valid_count,
                      "intervals_valid": intervals_valid},
        "gates": {"registered_linear_recovery": linear, "identity_gate_passed": identity,
                  "registered_useful_effect": useful},
    }


def score_recovery(train_y: np.ndarray, y: np.ndarray, predictions: np.ndarray, subject_ids: np.ndarray,
                   *, bootstrap_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    """Calculate unclipped R? and shared paired subject-block intervals."""
    active, estimable = _target_masks(train_y, y)
    if not (active & estimable).any():
        raise ValueError("Empty fixed target mask")
    _check_predictions(predictions, len(y))
    if (not isinstance(subject_ids, np.ndarray) or subject_ids.dtype.kind != "U"
            or subject_ids.shape != (len(y),) or np.any(subject_ids == "")):
        raise ValueError("Expected nonempty Unicode participant IDs in row order")
    if type(bootstrap_resamples) is not int or not 1 <= bootstrap_resamples <= BOOTSTRAP_RESAMPLES:
        raise ValueError("Invalid bootstrap resample count")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Invalid bootstrap seed")
    _, subjects = np.unique(subject_ids, return_inverse=True)
    try:
        with np.errstate(over="raise", divide="raise", invalid="raise"):
            return _score(train_y, y, predictions, subjects, active, estimable, bootstrap_resamples, seed)
    except FloatingPointError as error:
        raise ValueError("Nonfinite derived residual recovery metric") from error
