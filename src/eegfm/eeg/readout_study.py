"""Fixed, auditable Builder analysis for the cached readout-bottleneck study.

Inputs have 325 columns: embedding [0:200], handcrafted [200:262], frozen
old-head logit [262], and independent Gaussian control [263:325]. This module
does not load EEG, models, files, or held-out labels during fitting. Callers
freeze the JSON-serializable fit before calling the separate evaluator.
"""
from __future__ import annotations

import warnings
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
C_GRID = (0.01, 0.1, 1.0, 10.0)
READOUT_ORDER = ("A", "B", "C", "D", "E")
POSITIVE_SLOPE_MINIMUM = 1e-8


def _finite_array(value: Any, *, name: str) -> FloatArray:
    array = np.asarray(value)
    if array.dtype.kind not in "biuf" or not np.isfinite(array).all():
        raise ValueError(f"{name} must contain finite real numbers")
    return array.astype(np.float64, copy=False)


def _matrix(value: Any, columns: int, *, name: str) -> FloatArray:
    array = _finite_array(value, name=name)
    if array.ndim != 2 or array.shape[1] != columns or not len(array):
        raise ValueError(f"{name} must be a nonempty matrix with {columns} columns")
    return array


def _labels(value: Any, rows: int) -> FloatArray:
    labels = _finite_array(value, name="y")
    if labels.shape != (rows,) or set(np.unique(labels)) != {0, 1}:
        raise ValueError("y must align with rows and contain exactly classes 0 and 1")
    return labels


def _ids(value: Any, rows: int, *, name: str) -> NDArray[np.str_]:
    identifiers = np.asarray(value)
    if identifiers.shape != (rows,) or identifiers.dtype.kind not in "USiu":
        raise ValueError(f"{name} must be an aligned vector of string or integer IDs")
    identifiers = identifiers.astype(str)
    if np.any(np.char.strip(identifiers) == ""):
        raise ValueError(f"{name} cannot contain empty IDs")
    return identifiers


def _partition(data: dict[str, np.ndarray]) -> tuple[FloatArray, FloatArray, NDArray[np.str_], NDArray[np.str_]]:
    if not isinstance(data, dict) or set(data) != {"x", "y", "sample_ids", "subject_ids"}:
        raise ValueError("Partition requires exactly x, y, sample_ids, subject_ids")
    x = _matrix(data["x"], 325, name="x")
    y = _labels(data["y"], len(x))
    samples = _ids(data["sample_ids"], len(x), name="sample_ids")
    subjects = _ids(data["subject_ids"], len(x), name="subject_ids")
    if len(np.unique(samples)) != len(samples):
        raise ValueError("sample_ids must be unique")
    return x, y, samples, subjects


def _balanced_accuracy(y: FloatArray, logits: FloatArray) -> float:
    predicted = logits >= 0
    return float(np.mean([np.mean(predicted[y == label] == label) for label in (0, 1)]))


def _calibration(z: FloatArray, y: FloatArray, c: float) -> dict[str, Any]:
    from scipy.optimize import minimize
    from scipy.special import expit

    def objective(parameters: FloatArray) -> tuple[float, FloatArray]:
        slope, intercept = parameters
        logits = z[:, 0] * slope + intercept
        residual = expit(logits) - y
        # Same L2 objective as unweighted sklearn logistic regression: the
        # summed logistic loss plus ||coefficient||^2/(2*C), intercept excluded.
        loss = np.logaddexp(0, (1 - 2 * y) * logits).sum() + slope * slope / (2 * c)
        gradient = np.array([z[:, 0] @ residual + slope / c, residual.sum()])
        return float(loss), gradient

    prevalence = float(y.mean())
    initial = np.array([1.0, np.log(prevalence / (1 - prevalence))])
    fitted = minimize(objective, initial, jac=True, method="L-BFGS-B",
                      bounds=[(POSITIVE_SLOPE_MINIMUM, None), (None, None)],
                      options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-8})
    if not fitted.success or not np.isfinite(fitted.x).all():
        raise RuntimeError(f"Positive calibration did not converge: {fitted.message}")
    return {"coefficient": [float(fitted.x[0])], "intercept": float(fitted.x[1]),
            "iterations": int(fitted.nit)}


def _fit_linear(train_x: FloatArray, y: FloatArray, val_x: FloatArray,
                val_y: FloatArray, *, calibration: bool) -> dict[str, Any]:
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression

    mean, scale = train_x.mean(axis=0), train_x.std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    z, val_z = (train_x - mean) / scale, (val_x - mean) / scale
    if not all(np.isfinite(array).all() for array in (mean, scale, z, val_z)):
        raise ValueError("Nonfinite training transform or standardized inputs")
    candidates: list[dict[str, Any]] = []
    for c in C_GRID:
        if calibration:
            parameters = _calibration(z, y, c)
        else:
            model = LogisticRegression(C=c, penalty="l2", solver="lbfgs", max_iter=2000,
                                       tol=1e-9, fit_intercept=True, class_weight=None)
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                try:
                    model.fit(z, y)
                except ConvergenceWarning as error:
                    raise RuntimeError("Logistic readout did not converge") from error
            parameters = {"coefficient": model.coef_[0].tolist(),
                          "intercept": float(model.intercept_[0]),
                          "iterations": int(model.n_iter_[0])}
        logits = val_z @ parameters["coefficient"] + parameters["intercept"]
        if not np.isfinite(logits).all():
            raise ValueError("Nonfinite validation logits")
        candidates.append({"C": c, "validation_balanced_accuracy": _balanced_accuracy(val_y, logits),
                           **parameters})
    # Ascending C and first maximum implement the prespecified tie break.
    selected = max(candidates, key=lambda candidate: candidate["validation_balanced_accuracy"])
    return {**selected, "mean": mean.tolist(), "scale": scale.tolist(), "selection_grid": candidates}


def fit_readouts(train: dict[str, np.ndarray], validation: dict[str, np.ndarray]) -> dict[str, Any]:
    """Fit B-E on train only; choose C per arm using validation BA at logit 0.

    Both dictionaries require x/y/sample_ids/subject_ids and disjoint IDs.
    The returned JSON-safe record includes all candidate parameters and scores.
    B's strictly positive numerical floor is recorded explicitly; its intercept
    is unpenalized. No refit on validation or choice of seed/threshold occurs.
    """
    x, y, samples, subjects = _partition(train)
    vx, vy, vsamples, vsubjects = _partition(validation)
    if set(samples) & set(vsamples) or set(subjects) & set(vsubjects):
        raise ValueError("Training/validation sample or subject overlap")
    models: dict[str, Any] = {"A": {"kind": "frozen_old_logit", "column": 262}}
    for name, start, stop in (("B", 262, 263), ("C", 0, 200), ("D", 200, 262), ("E", 263, 325)):
        model = _fit_linear(x[:, start:stop], y, vx[:, start:stop], vy, calibration=name == "B")
        models[name] = {"kind": "positive_affine" if name == "B" else "logistic",
                        "columns": [start, stop], **model}
    models["B"]["slope_minimum"] = POSITIVE_SLOPE_MINIMUM
    return {"schema_version": 1, "input_columns": 325, "readout_order": list(READOUT_ORDER),
            "training_samples": len(x), "validation_samples": len(vx),
            "training_subjects": len(np.unique(subjects)), "validation_subjects": len(np.unique(vsubjects)),
            "selection": {"C_grid": list(C_GRID), "metric": "balanced_accuracy", "threshold": 0.0,
                          "tie_break": "smaller_C", "max_iter": 2000, "class_weight": None,
                          "objective": "sum_logistic_loss + squared_coefficient_norm/(2*C)",
                          "intercept_penalized": False, "standardization": "train_mean_population_std"},
            "models": models}


def predict_readouts(fits: dict[str, Any], x: np.ndarray) -> np.ndarray:
    """Apply frozen parameters and return finite raw logits in columns A-E."""
    matrix = _matrix(x, 325, name="x")
    try:
        if fits["schema_version"] != 1 or fits["input_columns"] != 325 or fits["readout_order"] != list(READOUT_ORDER):
            raise ValueError("Unsupported fit schema or readout order")
        for partition in ("training", "validation"):
            rows, subjects = fits[f"{partition}_samples"], fits[f"{partition}_subjects"]
            if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer))
                   for value in (rows, subjects)) or not 1 <= subjects <= rows or rows < 2:
                raise ValueError("Invalid saved fitting sample/subject counts")
        models = fits["models"]
        if set(models) != set(READOUT_ORDER) or models["A"] != {"kind": "frozen_old_logit", "column": 262}:
            raise ValueError("Invalid frozen old-head specification")
        logits = np.empty((len(matrix), 5), dtype=np.float64)
        logits[:, 0] = matrix[:, 262]
        for column, (name, start, stop) in enumerate((("B", 262, 263), ("C", 0, 200), ("D", 200, 262), ("E", 263, 325)), 1):
            model = models[name]
            expected_kind = "positive_affine" if name == "B" else "logistic"
            if model["columns"] != [start, stop] or model["kind"] != expected_kind:
                raise ValueError("Readout input columns/kind changed")
            mean, scale, coefficient = [_finite_array(model[key], name=key) for key in ("mean", "scale", "coefficient")]
            intercept = _finite_array(model["intercept"], name="intercept")
            if any(value.shape != (stop - start,) for value in (mean, scale, coefficient)) or intercept.ndim != 0:
                raise ValueError("Readout parameter shape mismatch")
            if np.any(scale <= 0) or (name == "B" and coefficient[0] <= 0):
                raise ValueError("Scales and calibration slope must be positive")
            logits[:, column] = ((matrix[:, start:stop] - mean) / scale) @ coefficient + intercept
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed readout fit") from error
    if not np.isfinite(logits).all():
        raise ValueError("Nonfinite prediction logits")
    return logits


def _interval(values: FloatArray, confidence: float = 0.95) -> list[float]:
    # Never filter undefined draws: the caller must explicitly make an interval
    # unavailable instead of silently changing its bootstrap distribution.
    if not np.isfinite(values).all():
        raise ValueError("Cannot form an interval with nonfinite bootstrap draws")
    tail = (1 - confidence) / 2
    return np.quantile(values, [tail, 1 - tail]).tolist()


def _closure(numerator: float, denominator: float, bootstrap_numerator: FloatArray,
             bootstrap_denominator: FloatArray) -> dict[str, Any]:
    denominator_interval = _interval(bootstrap_denominator)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        ratios = bootstrap_numerator / bootstrap_denominator
        point = numerator / denominator if denominator != 0 else None
    undefined = int(np.count_nonzero(~np.isfinite(ratios)))
    return {"numerator": numerator, "numerator_ci95": _interval(bootstrap_numerator),
            "denominator": denominator, "denominator_ci95": denominator_interval,
            "ratio": point, "ci95": None if undefined else _interval(ratios),
            "undefined_bootstrap_ratios": undefined,
            "status": "unstable" if denominator_interval[0] <= 0.03 else "stable",
            "stability_threshold": 0.03}


def evaluate_readouts(y: np.ndarray, scores: np.ndarray, subjects: np.ndarray, *,
                      resamples: int = 10000, seed: int = 161803) -> dict[str, Any]:
    """Evaluate frozen A-E logits with a paired participant bootstrap of BA.

    All windows from each sampled participant are repeated together. BA pools
    windows within each class, including unequal participant sizes. Require two
    participants and both labels in each so every draw has defined BA. Primary
    C-A has a marginal 95% CI; the four secondary contrasts additionally receive
    Bonferroni 98.75% CIs. AUROC and stable logistic loss are absolute metrics.
    Call separately on diagnostic, confirmation and combined held-out cohorts.
    """
    from sklearn.metrics import roc_auc_score

    logits = _matrix(scores, 5, name="scores")
    labels = _labels(y, len(logits))
    identifiers = _ids(subjects, len(logits), name="subjects")
    if isinstance(resamples, (bool, np.bool_)) or not isinstance(resamples, (int, np.integer)) or not 1 <= resamples <= 10000:
        raise ValueError("resamples must be an integer from 1 to 10000")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    unique, inverse = np.unique(identifiers, return_inverse=True)
    if len(unique) < 2:
        raise ValueError("Participant bootstrap requires at least two subjects")
    class_counts = np.zeros((len(unique), 2), dtype=np.int64)
    correct_counts = np.zeros((len(unique), 2, 5), dtype=np.int64)
    predicted = logits >= 0
    for subject in range(len(unique)):
        for label in (0, 1):
            mask = (inverse == subject) & (labels == label)
            class_counts[subject, label] = np.count_nonzero(mask)
            correct_counts[subject, label] = np.sum(predicted[mask] == label, axis=0)
    if np.any(class_counts == 0):
        raise ValueError("Each participant must contain both classes for defined bootstrap metrics")
    draws = np.random.default_rng(seed).integers(0, len(unique), size=(resamples, len(unique)))
    offsets = np.arange(resamples)[:, None] * len(unique)
    weights = np.bincount((draws + offsets).ravel(), minlength=resamples * len(unique)).reshape(resamples, len(unique))
    sampled_counts = weights @ class_counts
    sampled_correct = (weights @ correct_counts.reshape(len(unique), 10)).reshape(resamples, 2, 5)
    bootstrap = np.mean(sampled_correct / sampled_counts[:, :, None], axis=1)
    absolute = np.mean(correct_counts.sum(axis=0) / class_counts.sum(axis=0)[:, None], axis=0)
    metrics: dict[str, Any] = {}
    for column, name in enumerate(READOUT_ORDER):
        # This logit-domain loss remains finite for strongly wrong predictions,
        # without clipping the raw scores or replacing them with probabilities.
        losses = np.logaddexp(0, (1 - 2 * labels) * logits[:, column])
        metrics[name] = {"balanced_accuracy": float(absolute[column]),
                         "balanced_accuracy_ci95": _interval(bootstrap[:, column]),
                         "auroc": float(roc_auc_score(labels, logits[:, column])),
                         "log_loss": float(np.sum(losses / len(labels)))}
    contrasts: dict[str, Any] = {}
    for name, left, right in (("C-A", 2, 0), ("B-A", 1, 0), ("D-A", 3, 0), ("D-C", 3, 2), ("D-E", 3, 4)):
        difference = bootstrap[:, left] - bootstrap[:, right]
        contrasts[name] = {"difference": float(absolute[left] - absolute[right]),
                           "ci95": _interval(difference), "primary": name == "C-A"}
        if name != "C-A":
            contrasts[name]["ci98_75"] = _interval(difference, 0.9875)
    numerator = float(absolute[3] - absolute[4])
    boot_numerator = bootstrap[:, 3] - bootstrap[:, 4]
    closure = {name: _closure(numerator, float(absolute[index] - absolute[4]),
                             boot_numerator, bootstrap[:, index] - bootstrap[:, 4])
               for name, index in (("old", 0), ("new", 2))}
    return {"schema_version": 1, "readout_order": list(READOUT_ORDER), "samples": len(labels),
            "subjects": len(unique), "threshold": 0.0, "useful_difference": 0.03,
            "bootstrap": {"unit": "participant", "paired": True, "resamples": int(resamples), "seed": int(seed),
                          "metric": "balanced_accuracy", "secondary_family_size": 4,
                          "secondary_adjustment": "Bonferroni", "quantile_method": "linear"},
            "metrics": metrics, "contrasts": contrasts, "closure": closure}
