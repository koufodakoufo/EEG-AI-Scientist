"""Bounded trusted residual regression scoring. Never imports candidate code."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
import io
from itertools import combinations
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, TYPE_CHECKING
import zipfile

import numpy as np

from eegfm.eeg.aggregation import MAX_ROWS, Schema, _bounded_npz, _write_new
from eegfm.eeg.residual_recovery import (
    BASELINE_MODELS, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, FEATURE_COUNT, IDENTITY_SCHEMA,
    MAX_METHOD_BYTES, MAX_PARAMETER_ARRAYS, MAX_PARAMETER_ELEMENTS, MAX_PARAMETER_RANK, MAX_RECIPES,
    METHOD_SCHEMA, MODELS, QUALIFICATION_SCHEMA, QUANTILES, SHUFFLE_SEED, TARGET_COLUMNS, TASK_ID,
    USEFUL_MARGIN, VARIANCE_FLOOR, VIEWS, _check_sha, _numeric_sha, _source_hashes, baseline_identity,
    score_recovery, validate_method_manifest, validate_parameters, validate_qualification,
)
from eegfm.evaluation.bundle import canonical_bytes, digest_file
from eegfm.evaluation.public_workbench import MAX_COMPRESSED, MAX_EXPANDED
from eegfm.evaluation.public_workbench import validate_parameters as validate_public_parameters
from eegfm.evaluation.worker import FileBinding, _path, candidate_digest

if TYPE_CHECKING:
    from eegfm.agent.controller import EvaluationSpec

POLICY_SCHEMA = "residual_recovery_metric_policy_v1"
SCORER_SCHEMA = "trusted_residual_recovery_analysis_v1"
SPLITS = ("train", "validation", "test")
PARTICIPANTS = {"train": 12, "validation": 6, "test": 6}
WINDOWS_PER_TRAIN_PARTICIPANT = 24
ROW_COUNTS = {"train": 288, "validation": 144, "test": 144}
MAX_ARCHIVE_BYTES = 40 * 1024**2
SOURCE_FILES = ("eeg/residual_recovery.py", "eeg/residual_recovery_aggregation.py", "eeg/aggregation.py",
                "eeg/data.py", "eeg/statistics.py", "evaluation/bundle.py", "evaluation/worker.py",
                "evaluation/public_workbench.py")
SCALARS = frozenset({
    "model_count", "view_count", "target_count", "numeric_scope_complete", "baseline_only",
    "included_target_count", "bootstrap_requested", "bootstrap_valid", "bootstrap_invalid", "intervals_valid",
    "primary_delta", "primary_ci95_low", "primary_ci95_high", "registered_useful_effect",
    "registered_linear_recovery", "identity_gate_passed",
})


def _read_bytes(path: Path, cap: int) -> bytes:
    with _path(path).open("rb") as stream:
        data = stream.read(cap + 1)
    if not 0 < len(data) <= cap:
        raise ValueError("File exceeds byte cap or is empty")
    return data


def _read_json(path: Path, cap: int) -> dict[str, Any]:
    def unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid(_: str) -> Any:
        raise ValueError("Nonfinite JSON literal")

    try:
        result = json.loads(_read_bytes(path, cap).decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("Invalid bounded UTF-8 JSON") from error
    if not isinstance(result, dict):
        raise ValueError("Expected JSON object")
    return result


def _read_npz(path: Path, schema: Schema) -> dict[str, np.ndarray]:
    path = _path(path)
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Residual archive exceeds byte cap")
    try:
        with zipfile.ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_ARCHIVE_BYTES:
                raise ValueError("Residual archive exceeds expanded byte cap")
        arrays = _bounded_npz(path, schema)
    except (zipfile.BadZipFile, EOFError, OSError, TypeError) as error:
        raise ValueError("Invalid residual array archive") from error
    if any(array.dtype != np.dtype("float64") for name, array in arrays.items() if schema[name][1] == "f"):
        raise ValueError("Residual numeric data must be exactly float64")
    return arrays


def _read_parameters(path: Path, method: dict[str, Any]) -> dict[str, np.ndarray]:
    data = _read_bytes(path, MAX_COMPRESSED)
    schema = method["parameter_schema"]
    expected = {name + ".npy" for name in schema}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if (len(entries) != len(expected) or {item.filename for item in entries} != expected
                    or sum(item.file_size for item in entries) > MAX_EXPANDED):
                raise ValueError("Unexpected numeric parameter members or expanded size")
            for entry in entries:
                if entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError("Unsupported numeric parameter compression")
                declared = schema[entry.filename[:-4]]
                with archive.open(entry) as stream:
                    version = np.lib.format.read_magic(stream)
                    if version == (1, 0):
                        shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
                    elif version == (2, 0):
                        shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
                    else:
                        raise ValueError("Unsupported numeric array format")
                    if (list(shape) != declared["shape"] or dtype != np.dtype(declared["dtype"])
                            or stream.tell() + math.prod(shape) * dtype.itemsize != entry.file_size):
                        raise ValueError("Numeric parameter header differs from declared schema or byte length")
        validate_public_parameters(data)
        with np.load(io.BytesIO(data), allow_pickle=False) as archive:
            parameters = {name: archive[name] for name in schema}
    except (zipfile.BadZipFile, EOFError, OSError, TypeError) as error:
        raise ValueError("Invalid numeric parameter archive") from error
    validate_parameters(method, parameters)
    return parameters


def _policy(roles: dict[str, str], qualification: FileBinding, receipt: dict[str, Any],
            source_bindings: tuple[FileBinding, ...], runtime_identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": POLICY_SCHEMA, "task_id": TASK_ID, "scorer_schema": SCORER_SCHEMA,
        "method_schema": METHOD_SCHEMA, "baseline_identity_schema": IDENTITY_SCHEMA,
        "validation_identity_release": "residual_baseline_identity_hash_v1",
        "qualification": {"schema_version": QUALIFICATION_SCHEMA, "file_sha256": qualification.sha256,
                          "canonical_sha256": hashlib.sha256(canonical_bytes(receipt)).hexdigest(), "receipt": receipt},
        "role_sha256": roles, "source_sha256": {name: item.sha256 for name, item in zip(SOURCE_FILES, source_bindings)},
        "aggregate_runtime": runtime_identity, "view_order": list(VIEWS), "target_columns": list(TARGET_COLUMNS),
        "pooled_feature_count": FEATURE_COUNT, "model_order": {"baseline": list(BASELINE_MODELS), "final": list(MODELS)},
        "npz": {
            "public": {"x": "float64[N,5,200]", "y": "float64[N,6]", "sample_ids": "Unicode[N]",
                       "subject_ids": "Unicode[N]"},
            "inference": {"x": "float64[N,5,200]", "sample_ids": "Unicode[N]", "subject_ids": "Unicode[N]"},
            "truth": {"y": "float64[N,6]", "sample_ids": "Unicode[N]", "subject_ids": "Unicode[N]"},
            "result": {"predictions": "float64[N,5,M,6]", "sample_ids": "Unicode[N]"},
            "row_counts": ROW_COUNTS.copy(), "participants": PARTICIPANTS.copy(), "max_rows": MAX_ROWS,
            "max_compressed_and_expanded_bytes": MAX_ARCHIVE_BYTES, "allow_pickle": False,
            "row_binding": "exact ordered sample/participant joins; disjoint splits; exact public arrays",
        },
        "parameters": {"max_compressed_bytes": MAX_COMPRESSED, "max_expanded_bytes": MAX_EXPANDED,
                       "max_arrays": MAX_PARAMETER_ARRAYS, "max_rank": MAX_PARAMETER_RANK,
                       "max_elements_per_array": MAX_PARAMETER_ELEMENTS,
                       "identity": "baseline source bytes, linear declaration, selected indices, dtype/shape/C bytes "
                                   "of baseline parameters and baseline predictions, and ordered validation binding"},
        "fit_protocol": {
            "max_method_bytes": MAX_METHOD_BYTES, "max_recipes_per_view_family": MAX_RECIPES,
            "selection": "equal-weight fixed-mask validation R2; first declared recipe breaks exact ties",
            "fitting": "B only, including scaling; linear affine; no evaluation fitting, IDs, or cross-view features",
            "shuffle": {"seed": SHUFFLE_SEED, "rng": "PCG64", "participants": PARTICIPANTS["train"],
                        "windows_per_participant": WINDOWS_PER_TRAIN_PARTICIPANT,
                        "algorithm": "nonzero sorted-participant cyclic offset, then one nonzero within-block offset; "
                                     "canonical sample order; common permutation and unchanged selected recipes"},
            "fit_slots": 2, "baseline_validation_slots": 1, "iteration_validation_slots": 1, "locked_test_slots": 1,
            "independent_replay_slots": 2, "max_attempts": 1,
            "staging": "text only; omit parameters.npz at all depths",
        },
        "statistics": {
            "r2": "1-SSE/evaluation-centered-SST; equal weight across retained columns; unclipped",
            "variance_floor": VARIANCE_FLOOR, "mask": "B-training-active AND evaluation-estimable using centered "
                                                    "second moment > variance_floor * max(1, mean(y**2))",
            "train_mean": "fixed B means, separate from cohort mean R2 zero",
            "bootstrap": {"seed": BOOTSTRAP_SEED, "resamples": BOOTSTRAP_RESAMPLES, "rng": "PCG64",
                          "unit": "paired sorted participant blocks, including all repeated windows",
                          "quantiles": list(QUANTILES), "quantile_method": "linear",
                          "undefined": "fixed mask; any retained column failing the estimability floor invalidates "
                                       "the common draw; any invalid draw nulls all intervals and gates are inconclusive"},
            "leave_one_participant_out": "same fixed mask, report undefined omissions by zero-based ordinal in sorted participant order",
            "gates": {
                "strict_useful_margin": USEFUL_MARGIN, "primary": "LEACE flexible minus linear",
                "useful": "LEACE flexible R2 > 0; own shuffle CI lower > 0; primary point and CI lower > margin; "
                          "identity gate passes",
                "linear": "LEACE linear R2 > 0 and own shuffle CI lower > 0",
                "identity": "identity flexible R2 > 0 and own shuffle CI lower > 0",
            },
        },
        "scientific_validity": "separate source, fit and independent replay audit; prior project test exposure",
        "released_metrics": sorted(ResidualRecoveryAggregator.released_metrics),
    }


def _scalar_metrics(scored: dict[str, Any]) -> dict[str, float]:
    models = scored["model_order"]
    bootstrap = scored["bootstrap"]
    metrics = {
        "model_count": len(models), "view_count": len(VIEWS), "target_count": len(TARGET_COLUMNS),
        "numeric_scope_complete": len(models) == len(MODELS), "baseline_only": len(models) == len(BASELINE_MODELS),
        "included_target_count": sum(scored["target_mask"]), "bootstrap_requested": bootstrap["requested"],
        "bootstrap_valid": bootstrap["valid"], "bootstrap_invalid": bootstrap["invalid"],
        "intervals_valid": bootstrap["intervals_valid"],
        **{name: status == "passed" for name, status in scored["gates"].items()},
    }
    for view, scores in scored["views"].items():
        for model, summary in scores.items():
            metrics[f"{view}__{model}__r2"] = summary["r2"]
            if model == "train_mean" and view != "identity":
                continue
            prefix = "train_mean" if model == "train_mean" else f"{view}__{model}"
            for i, value in enumerate(summary["per_column_r2"]):
                if value is not None:
                    metrics[f"{prefix}__column{i}_r2"] = value
    metrics.update({f"target_column{i}_included": value for i, value in enumerate(scored["target_mask"])})
    for view, contrast in RELEASED_CONTRASTS:
        summary = scored["contrasts"][view].get(contrast)
        if summary is not None:
            prefix = f"{view}__{contrast}"
            metrics[f"{prefix}__delta"] = summary["delta"]
            if summary["ci95"] is not None:
                metrics[f"{prefix}__ci95_low"], metrics[f"{prefix}__ci95_high"] = summary["ci95"]
    for item in scored["leave_one_participant_out"]:
        prefix = f"loo_p{item['omission_index']}"
        valid = item["status"] == "defined"
        metrics[f"{prefix}__valid"] = valid
        if valid:
            metrics[f"{prefix}__leace_linear_r2"] = item["views"]["leace"]["linear"]
            if "flexible" in models:
                metrics[f"{prefix}__leace_flexible_r2"] = item["views"]["leace"]["flexible"]
                metrics[f"{prefix}__primary_delta"] = item["contrasts"]["leace"]["flexible_minus_linear"]
    primary = scored["primary"]
    if primary is not None:
        metrics["primary_delta"] = primary["delta"]
        if primary["ci95"] is not None:
            metrics["primary_ci95_low"], metrics["primary_ci95_high"] = primary["ci95"]
    return {name: float(value) for name, value in metrics.items()}


RELEASED_CONTRASTS = (("leace", "linear_minus_shuffled"), ("leace", "flexible_minus_shuffled"),
                      ("identity", "flexible_minus_shuffled"))


class ResidualRecoveryAggregator:
    """Stateless worker callable bound to enrolled runtime, source and input files."""

    released_metrics = SCALARS | frozenset(f"{view}__{model}__r2" for view in VIEWS for model in (*MODELS, "train_mean"))
    released_metrics |= frozenset(f"{view}__{model}__column{i}_r2" for view in VIEWS for model in MODELS for i in range(6))
    released_metrics |= frozenset(f"train_mean__column{i}_r2" for i in range(6))
    released_metrics |= frozenset(f"target_column{i}_included" for i in range(6))
    released_metrics |= frozenset(f"{view}__{contrast}__{suffix}" for view, contrast in RELEASED_CONTRASTS
                                  for suffix in ("delta", "ci95_low", "ci95_high"))
    released_metrics |= frozenset(f"loo_p{i}__{suffix}" for i in range(6)
                                  for suffix in ("valid", "leace_linear_r2", "leace_flexible_r2", "primary_delta"))

    def __init__(self, truth_by_split: Mapping[str, FileBinding], train_truth: FileBinding,
                 inference_by_split: Mapping[str, FileBinding], *, public_by_split: Mapping[str, FileBinding],
                 qualification: FileBinding, runtime_identity: dict[str, Any],
                 verify_runtime: Callable[[], None] | None = None) -> None:
        if set(truth_by_split) != {"validation", "test"} or set(inference_by_split) != {"validation", "test"}:
            raise ValueError("Residual truth and inference require exactly validation/test")
        if set(public_by_split) != {"train", "validation"}:
            raise ValueError("Residual public input requires exactly train/validation")
        if not isinstance(runtime_identity, dict):
            raise ValueError("Residual scoring requires a runtime identity object")
        self.train_truth = train_truth
        self.truth = MappingProxyType({name: truth_by_split[name] for name in ("validation", "test")})
        self.inference = MappingProxyType({name: inference_by_split[name] for name in ("validation", "test")})
        self.public = MappingProxyType({name: public_by_split[name] for name in ("train", "validation")})
        self.qualification = qualification
        self.verify_runtime = verify_runtime
        package = Path(__file__).resolve().parents[1]
        self.source_bindings = tuple(FileBinding(package / name, digest_file(package / name)) for name in SOURCE_FILES)
        self.input_bindings = (train_truth, *self.truth.values(), *self.inference.values(), *self.public.values(),
                               qualification)
        self.bindings = (*self.input_bindings, *self.source_bindings)
        self._verify_bindings()
        receipt = _read_json(qualification.verify(), MAX_METHOD_BYTES)
        records = receipt.get("bindings")
        split_hash = None
        if isinstance(records, list):
            split_hash = next((record.get("sha256") for record in records
                               if isinstance(record, dict) and record.get("role") == "split_manifest"), None)
        self._role_hashes = {
            "truth_train": train_truth.sha256,
            **{f"truth_{name}": item.sha256 for name, item in self.truth.items()},
            **{f"inference_{name}": item.sha256 for name, item in self.inference.items()},
            **{f"public_{name}": item.sha256 for name, item in self.public.items()},
        }
        roles = {**self._role_hashes, "split_manifest": split_hash}
        validate_qualification(receipt, roles)
        self._scoring_policy = _policy(roles, qualification, receipt, self.source_bindings,
                                       json.loads(canonical_bytes(runtime_identity)))
        self.policy_sha256 = hashlib.sha256(canonical_bytes(self._scoring_policy)).hexdigest()

    @property
    def scoring_policy(self) -> dict[str, Any]:
        return json.loads(canonical_bytes(self._scoring_policy))

    def _verify_bindings(self) -> None:
        for binding in self.bindings:
            binding.verify()

    def _inputs(self) -> dict[str, dict[str, np.ndarray]]:
        truths = {}
        for split, binding in {"train": self.train_truth, **self.truth}.items():
            rows = ROW_COUNTS[split]
            truth = _read_npz(binding.verify(), {"sample_ids": ((rows,), "U"), "subject_ids": ((rows,), "U"),
                                                  "y": ((rows, len(TARGET_COLUMNS)), "f")})
            n = len(truth["y"])
            subjects, counts = np.unique(truth["subject_ids"], return_counts=True)
            if (len(truth["sample_ids"]) != n or len(truth["subject_ids"]) != n
                    or len(np.unique(truth["sample_ids"])) != n or len(subjects) != PARTICIPANTS[split]
                    or any(np.any(truth[key] == "") for key in ("sample_ids", "subject_ids"))
                    or (split == "train" and np.any(counts != WINDOWS_PER_TRAIN_PARTICIPANT))):
                raise ValueError("Invalid trusted sample/participant alignment")
            inference_schema = {"sample_ids": ((n,), "U"), "subject_ids": ((n,), "U"),
                                "x": ((n, len(VIEWS), FEATURE_COUNT), "f")}
            inference = None
            if split in self.inference:
                inference = _read_npz(self.inference[split].verify(), inference_schema)
                if any(not np.array_equal(inference[key], truth[key]) for key in ("sample_ids", "subject_ids")):
                    raise ValueError("Trusted inference differs from ordered truth samples or participants")
            if split in self.public:
                public = _read_npz(self.public[split].verify(),
                                   {**inference_schema, "y": ((n, len(TARGET_COLUMNS)), "f")})
                if (any(not np.array_equal(public[key], truth[key]) for key in ("sample_ids", "subject_ids", "y"))
                        or (inference is not None and not np.array_equal(public["x"], inference["x"]))):
                    raise ValueError("Public arrays differ from ordered trusted inputs")
            truths[split] = truth
        for key in ("sample_ids", "subject_ids"):
            for left, right in combinations(SPLITS, 2):
                if np.intersect1d(truths[left][key], truths[right][key]).size:
                    raise ValueError("Train/validation/test samples or participants overlap")
        return truths

    def __call__(self, output: Path, spec: EvaluationSpec) -> dict[str, Any]:
        output = _path(output, directory=True)
        if {path.name for path in output.iterdir()} != {"results.npz"}:
            raise ValueError("Residual output must contain exactly results.npz")
        if spec.split not in self.truth:
            raise ValueError("Only residual validation/test scoring is supported")
        if self.verify_runtime is not None:
            self.verify_runtime()
        self._verify_bindings()
        validate_qualification(self._scoring_policy["qualification"]["receipt"],
                               {**self._role_hashes, "split_manifest": spec.split_manifest_sha256})
        public_manifest_sha = _check_sha(spec.public_manifest_sha256)
        candidate = _path(spec.candidate_dir, directory=True)
        if candidate_digest(candidate) != _check_sha(spec.candidate_digest):
            raise ValueError("Candidate differs from frozen identity")
        method_path = candidate / "method.json"
        method = validate_method_manifest(_read_json(method_path, MAX_METHOD_BYTES))
        if spec.split == "test" and method["phase"] != "final":
            raise ValueError("Residual test requires final models")
        models = BASELINE_MODELS if method["phase"] == "baseline" else MODELS
        parameter_path = candidate / "parameters.npz"
        parameters = _read_parameters(parameter_path, method)
        truths = self._inputs()
        truth = truths[spec.split]
        n = len(truth["y"])
        results_path = _path(output / "results.npz")
        if results_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("Residual archive exceeds byte cap")
        results_sha = digest_file(results_path)
        results = _read_npz(results_path, {"sample_ids": ((n,), "U"),
                                         "predictions": ((n, len(VIEWS), len(models), len(TARGET_COLUMNS)), "f")})
        if not np.array_equal(results["sample_ids"], truth["sample_ids"]):
            raise ValueError("Residual predictions differ from ordered inference samples")
        predictions = results["predictions"]
        scored = score_recovery(truths["train"]["y"], truth["y"], predictions, truth["subject_ids"])
        metrics = _scalar_metrics(scored)
        if not set(metrics) <= self.released_metrics or any(not math.isfinite(value) for value in metrics.values()):
            raise ValueError("Undeclared or nonfinite released residual metric")
        inference_sha = self.inference[spec.split].sha256
        identity_bytes = None
        if spec.split == "validation":
            identity = baseline_identity(candidate, method, parameters, predictions,
                                         public_manifest_sha256=public_manifest_sha, inference_sha256=inference_sha)
            identity_bytes = canonical_bytes(identity)
            source_hashes = identity["baseline_sources"]
        else:
            source_hashes = _source_hashes(candidate, method["baseline_sources"])
        report = {
            "schema_version": SCORER_SCHEMA, "task_id": TASK_ID, "split": spec.split,
            "identity": {"job_id": spec.job_id, "episode_id": spec.episode_id, "run_id": spec.run_id,
                         "attempt_id": spec.attempt_id, "public_manifest_sha256": public_manifest_sha,
                         "split_manifest_sha256": spec.split_manifest_sha256, "inference_sha256": inference_sha},
            "candidate_digest": spec.candidate_digest, "scoring_policy_sha256": self.policy_sha256,
            "qualification_sha256": self.qualification.sha256, "method": method,
            "method_sha256": digest_file(method_path), "parameters_sha256": digest_file(parameter_path),
            "baseline_source_sha256": source_hashes,
            "numeric_parameters_sha256": {name: _numeric_sha(array) for name, array in parameters.items()},
            "predictions_sha256": _numeric_sha(predictions), "results_sha256": results_sha,
            "baseline_identity_sha256": hashlib.sha256(identity_bytes).hexdigest() if identity_bytes else None,
            "scientific_validity": "pending_independent_source_fit_and_prediction_replay",
            "not_project_unseen_confirmation": True, "statistics": scored, "metrics": metrics,
            "limitations": [
                "The preparation receipt attests source qualification; the scorer does not reproduce those checks.",
                "Six test participants and prior project test exposure limit interpretation.",
                "Intervals condition on frozen fits. The fixed shuffle is diagnostic, not a permutation p-value.",
                "Additional recovery beyond this finite linear comparator does not establish intrinsic or exclusive "
                "nonlinearity, causal reliance, method gain or recursive self-improvement.",
            ],
        }
        self._verify_bindings()
        if candidate_digest(candidate) != spec.candidate_digest or digest_file(results_path) != results_sha:
            raise ValueError("Candidate or results changed during scoring")
        if self.verify_runtime is not None:
            self.verify_runtime()
        artifacts = [results_path]
        if identity_bytes is not None:
            identity_path = output / "baseline_identity.json"
            with identity_path.open("xb") as stream:
                stream.write(identity_bytes)
            artifacts.append(identity_path)
        report_path = output / "trusted_residual_recovery_analysis.json"
        _write_new(report_path, report)
        artifacts.append(report_path)
        return {"metrics": metrics, "artifacts": [{"path": path.name, "sha256": digest_file(path)} for path in artifacts]}
