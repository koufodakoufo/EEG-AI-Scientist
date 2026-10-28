"""Immutable downstream and reporting rules shared by official R0 and candidates."""
from __future__ import annotations

import math
import numpy as np
import torch

from artifact_io import fingerprint

EVALUATION = {
    "version": "reve_isa_validation_only_v1",
    "input_policy": "released_uV_NoClip_no_zscore",
    "representation": "official_tokens_flatten_337920",
    "lp": {"epochs": 100, "lr": 0.001, "optimizer": "Adam", "feature_standardization": "train_only_ddof0_floor1e-6"},
    "ft": {"epochs": 60, "lr": 0.00001, "optimizer": "AdamW", "head": "LayerNorm_256_ReLU_dropout0.2_128_ReLU_dropout0.2_classes"},
    "batch_size": 128, "weight_decay": 0.0001,
    "optimizer_betas": [0.9, 0.999], "optimizer_eps": 1e-8,
    "scheduler": "none", "early_stop_patience": 10, "early_stop_min_delta": 0.01,
    "early_stop_metric": "relative_epoch_mean_training_CE_as_in_reference",
    "checkpoint_selection": "max_validation_sample_bAcc_first_epoch_on_tie",
    "auto_lr_shrink": False, "r0_calibration": "No automatic sweep; failed numerical gate requires one separately reviewed common repair",
    "lp_head_seed": "42+fold", "ft_head_encoder_seed": "42+fold",
    "ft_batch_order_seed": "42+fold*997", "rng_processes": "one independently seeded process per fold",
    "precision": "encoder_BF16_autocast_head_FP32_loss_FP32", "gradient_checkpointing": True,
    "ft_gradient_clip": 1.0, "gradient_accumulation": 1,
    "metric_unit": "sample_predictions_within_fold", "summary_std_ddof": 0,
    "test_policy": "defer_all_test_calls_until_common_method_lock_after_all_requested_rounds_validation",
    "bootstrap": {"resamples": 5000, "seed": 20260713, "confidence": 0.95, "interval": "paired_fold_difference_percentile"},
    "final_selection": "max_equal_dataset_mean_FT_validation_then_positive_gain_count_then_lower_posttrain_wall_time_then_lower_round",
}
EVALUATION_HASH = fingerprint(EVALUATION)


def sample_metrics(labels, predictions, classes):
    labels, predictions = np.asarray(labels), np.asarray(predictions)
    if labels.ndim != 1 or predictions.shape != labels.shape or len(labels) == 0:
        raise ValueError("Invalid metric inputs")
    if set(labels.tolist()) != set(range(classes)) or not set(predictions.tolist()) <= set(range(classes)):
        raise ValueError("Metric label/prediction vocabulary changed")
    recalls, f1s = [], []
    for label in range(classes):
        tp = int(np.count_nonzero((labels == label) & (predictions == label)))
        actual = int(np.count_nonzero(labels == label))
        predicted = int(np.count_nonzero(predictions == label))
        recalls.append(tp / actual)
        f1s.append(2 * tp / (actual + predicted) if actual + predicted else 0.0)
    return {"balanced_accuracy": float(np.mean(recalls)), "macro_f1": float(np.mean(f1s)),
            "accuracy": float(np.mean(labels == predictions)), "samples": len(labels)}


def training_statistics(features, rows, batch_size=128):
    """Float64 CPU accumulation, frozen across conditions; only train rows enter."""
    rows = np.asarray(rows, dtype=np.int64)
    if rows.ndim != 1 or len(rows) < 2 or len(np.unique(rows)) != len(rows):
        raise ValueError("Invalid standardization training rows")
    dimension = features.shape[1]
    total, squared = np.zeros(dimension, np.float64), np.zeros(dimension, np.float64)
    for offset in range(0, len(rows), batch_size):
        values = np.asarray(features[rows[offset:offset+batch_size]], dtype=np.float64)
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite LP training features")
        total += values.sum(axis=0)
        squared += np.square(values).sum(axis=0)
    mean = total / len(rows)
    variance = np.maximum(squared / len(rows) - np.square(mean), 0)
    return mean.astype(np.float32), np.maximum(np.sqrt(variance), 1e-6).astype(np.float32)


class EpochSelection:
    def __init__(self):
        self.best_val = None
        self.best_epoch = None
        self.best_loss = math.inf
        self.no_improvement = 0

    def observe(self, epoch, *, training_loss, validation_bacc):
        if not math.isfinite(training_loss) or not math.isfinite(validation_bacc) or not 0 <= validation_bacc <= 1:
            raise ValueError("Invalid epoch observation")
        selected = self.best_val is None or validation_bacc > self.best_val
        if selected:
            self.best_val, self.best_epoch = validation_bacc, epoch
        if not math.isfinite(self.best_loss) or training_loss < self.best_loss - 0.01 * max(abs(self.best_loss), 1e-12):
            self.best_loss, self.no_improvement = training_loss, 0
        else:
            self.no_improvement += 1
        return selected, self.no_improvement >= 10


def validate_round_limit(round_limit=2):
    if type(round_limit) is not int or round_limit not in (1, 2):
        raise ValueError("The frozen campaign must request one or two complete rounds")
    return round_limit


def final_conditions(round_limit=2):
    return tuple(f"R{number}" for number in range(validate_round_limit(round_limit) + 1))


def expected_test_calls(round_limit=2):
    return 72 * len(final_conditions(round_limit))


def locked_round_limit(method_lock, *, expected=None):
    limit = validate_round_limit(method_lock.get("round_limit", 2))
    if (expected is not None and limit != validate_round_limit(expected)):
        raise ValueError("Method lock differs from the frozen round limit")
    if (method_lock.get("complete_validation_rounds") != list(range(1, limit + 1))
            or type(method_lock.get("selected_round")) is not int
            or method_lock["selected_round"] not in range(1, limit + 1)
            or method_lock.get("selection_data") != "validation_only"
            or method_lock.get("test_started_before_lock", False) is not False):
        raise ValueError("Test blocked until every requested round and a validation-only common method lock")
    return limit


def select_method(reports, *, round_limit=2):
    """One whole-round method, frozen before any final test output exists."""
    if set(reports) != set(range(1, validate_round_limit(round_limit) + 1)):
        raise ValueError("Method selection requires every requested completed round")
    keys = {}
    for ordinal, report in reports.items():
        if report["test_evaluations"] != 0 or report["validation_evaluations"] != 72 or not report["execution_valid"]:
            raise ValueError("Cannot select using incomplete or test-exposed development reports")
        metrics = report["validation_summary"]
        macro = metrics["ft_macro_balanced_accuracy"]
        cost = report["posttrain_wall_seconds"]
        if not math.isfinite(macro) or not math.isfinite(cost):
            raise ValueError("Nonfinite method selection values")
        keys[ordinal] = (macro, metrics["ft_positive_gain_datasets"], -cost, -ordinal)
    return max(keys, key=keys.get)


def paired_bootstrap(candidate, baseline):
    candidate, baseline = np.asarray(candidate, np.float64), np.asarray(baseline, np.float64)
    if candidate.shape != (6,) or baseline.shape != (6,) or not np.isfinite(candidate).all() or not np.isfinite(baseline).all():
        raise ValueError("Require six matched valid fold scores")
    delta = candidate - baseline
    indices = np.random.default_rng(20260713).integers(0, 6, (5000, 6))
    lower, upper = np.quantile(delta[indices].mean(axis=1), [0.025, 0.975])
    return {"mean_delta": float(delta.mean()), "lower": float(lower), "upper": float(upper),
            "resamples": 5000, "seed": 20260713, "unit": "paired repeated-split difference",
            "limitation": "Overlapping subject splits are dependent; interval describes split stability, not six independent replications"}
