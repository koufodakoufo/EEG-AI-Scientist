"""Trusted post-completion replay; never call the Actor or its one-shot ledger.

Runs a locked candidate in a fresh owned directory using the original worker,
inputs, runtime and aggregator. This is independent execution of identical code,
not an independently implemented scientific method. Original failures survive.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def snapshot(paths: list[Path]) -> dict[str, str]:
    return {str(path): sha256(path) for path in sorted(set(paths))}


def compare_npz(original: Path, replay: Path, rtol: float, atol: float) -> dict[str, Any]:
    import numpy as np

    records: dict[str, Any] = {}
    with np.load(original, allow_pickle=False) as first, np.load(replay, allow_pickle=False) as second:
        if set(first.files) != set(second.files):
            raise ValueError("Prediction archive member sets differ")
        for name in sorted(first.files):
            left, right = first[name], second[name]
            same_structure = left.shape == right.shape and left.dtype == right.dtype
            is_scientific = left.dtype.kind in "fc" and "ids" not in name
            equal = bool(np.array_equal(left, right)) if same_structure else False
            close = bool(np.allclose(left, right, rtol=rtol, atol=atol, equal_nan=False)) if same_structure and is_scientific else equal
            records[name] = {"shape": list(left.shape), "dtype": str(left.dtype),
                             "same_structure": same_structure, "exact": equal, "accepted": close,
                             "max_abs_difference": float(np.max(np.abs(left - right))) if same_structure and is_scientific else None}
    return {"accepted": all(row["accepted"] for row in records.values()), "arrays": records}


def audit_saved_q1(candidate: Path, public: Path) -> dict[str, Any]:
    """Check saved normal equations and metadata. Never fit or select a model."""
    import numpy as np

    metadata = read_json(candidate / "fit_metadata.json")
    with np.load(candidate / "probes.npz", allow_pickle=False) as archive:
        fit = {key: archive[key] for key in archive.files}
    with np.load(public / "train.npz", allow_pickle=False) as archive:
        features = archive["features"].astype(np.float64)
        subjects = archive["subject_ids"]
        train_ids = archive["sample_ids"]
        pooled = np.stack([archive[f"layer_{layer}"].mean(axis=(1, 2), dtype=np.float64) for layer in (6, 12)], axis=1)
    with np.load(public / "validation.npz", allow_pickle=False) as archive:
        validation_features = archive["features"].astype(np.float64)
        validation_subjects = archive["subject_ids"]
        validation_ids = archive["sample_ids"]
        validation_pooled = np.stack([archive[f"layer_{layer}"].mean(axis=(1, 2), dtype=np.float64) for layer in (6, 12)], axis=1)
    means = {"x_mean": pooled.mean(axis=0), "y_mean": features.mean(axis=0)}
    x_scale, y_scale = pooled.std(axis=0), features.std(axis=0)
    x_scale[x_scale == 0] = 1
    active = np.ptp(features, axis=0) > 0
    y_scale[~active] = 1
    expected = {**means, "x_scale": x_scale, "y_scale": y_scale, "active_columns": active}
    transforms = {key: bool(np.array_equal(value, fit[key])) for key, value in expected.items()}
    blocks = [np.flatnonzero(subjects == subject) for subject in np.unique(subjects)]
    permutation = fit["negative_train_permutation"]
    rng = np.random.default_rng(20261030)
    offset = int(rng.integers(1, len(blocks)))
    expected_permutation = np.empty(len(subjects), dtype=np.int64)
    offsets = []
    positions = np.empty(len(subjects), dtype=np.int64)
    for index, block in enumerate(blocks):
        row_offset = int(rng.integers(1, len(block)))
        offsets.append(row_offset)
        expected_permutation[block] = np.roll(blocks[(index + offset) % len(blocks)], row_offset)
        positions[block] = np.arange(len(block))
    permutation_checks = {
        "saved_seed_reproduces_permutation": bool(np.array_equal(permutation, expected_permutation)),
        "metadata_offsets_match": offset == metadata["source_participant_offset"] and offsets == metadata["within_block_offsets"],
        "bijection": bool(np.array_equal(np.sort(permutation), np.arange(len(subjects)))),
        "participants_deranged": bool(np.all(subjects[permutation] != subjects)),
        "within_block_positions_deranged": bool(np.all(positions[permutation] != positions)),
        "every_active_target_column_changed": bool(np.all(np.any(features[permutation] != features, axis=0)[active])),
    }
    groups = [list(range(6 * group, 6 * group + 6)) for group in range(10)] + [[60], [61]]
    standardized = (features - means["y_mean"]) / y_scale
    standardized[:, ~active] = 0
    selections = []
    for item in metadata["selections"]:
        layer, kind = item["layer"], item["kind"]
        index = (6, 12).index(layer)
        alpha = item["selected"]["alpha"]
        z = (pooled[:, index] - means["x_mean"][index]) / x_scale[index]
        target = standardized if kind == "positive" else standardized[permutation]
        coefficients = fit[kind + "_coef"][index]
        lhs = (z.T @ z + alpha * np.eye(200)) @ coefficients
        rhs = z.T @ target
        relative_residual = float(np.linalg.norm(lhs - rhs) / max(np.linalg.norm(rhs), 1e-30))
        validation_z = (validation_pooled[:, index] - means["x_mean"][index]) / x_scale[index]
        prediction = (validation_z @ coefficients) * y_scale + means["y_mean"]
        sst = np.square(validation_features - validation_features.mean(axis=0)).sum(axis=0)
        valid = active & (sst > 0)
        r2 = np.full(62, np.nan)
        r2[valid] = 1 - np.square(validation_features - prediction).sum(axis=0)[valid] / sst[valid]
        scores = [float(np.mean(r2[[column for column in group if valid[column]]])) for group in groups]
        saved = item["selected"]
        # Verify the recorded choice, without calculating alternative fits or changing it.
        recorded_best = max(item["grid"], key=lambda row: (row["mean_group_r2"] if row["mean_group_r2"] is not None else -np.inf, row["alpha"]))
        selections.append({"layer": layer, "kind": kind, "saved_alpha": alpha,
            "normal_equation_relative_residual": relative_residual,
            "normal_equation_accepted": relative_residual < 1e-10,
            "saved_choice_matches_recorded_grid_rule": saved == recorded_best,
            "selected_score_matches_saved_coefficients": bool(np.allclose(scores, saved["group_r2"], rtol=1e-6, atol=1e-8)),
            "selected_mean_matches": bool(np.isclose(np.mean(scores), saved["mean_group_r2"], rtol=1e-6, atol=1e-8))})
    disjoint = not bool(set(subjects.tolist()) & set(validation_subjects.tolist()) or set(train_ids.tolist()) & set(validation_ids.tolist()))
    accepted = all(transforms.values()) and all(permutation_checks.values()) and disjoint and all(
        row["normal_equation_accepted"] and row["saved_choice_matches_recorded_grid_rule"] and row["selected_score_matches_saved_coefficients"] and row["selected_mean_matches"] for row in selections)
    return {"accepted": accepted, "method": "saved-parameter algebraic validation; no refitting or new scientific selection",
            "training_transform_exact_checks": transforms, "permutation_checks": permutation_checks,
            "train_validation_disjoint": disjoint, "training_rows": len(features), "validation_rows": len(validation_features),
            "training_participants": len(blocks), "active_columns": int(active.sum()), "saved_fits": selections}


def audit_transcription(case: Path, original_jobs: Path, run_id: str, attempt: str) -> dict[str, Any]:
    import numpy as np

    path = case / "output/released-q1-transcription.csv"
    if not path.exists():
        return {"available": False}
    metrics = {split: read_json(original_jobs / f"{run_id}-{attempt}-{split}/released_metrics.json") for split in ("validation", "test")}
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    checked = 0
    mismatches = []
    positive_pairs: dict[str, list[list[int]]] = {"validation": [], "test": []}
    for row in rows:
        split, layer, group = row["split"], int(row["layer"]), int(row["group"])
        prefix = f"q1_l{layer}_g{group:02d}_"
        for key, value in row.items():
            if prefix + key in metrics[split]:
                checked += 1
                if not np.isclose(float(value), metrics[split][prefix + key], rtol=1e-6, atol=1e-8):
                    mismatches.append([split, layer, group, key])
        positive = all(metrics[split][prefix + key] > 0 for key in ("r2", "r2_minus_negative", "r2_family_ci_low"))
        if positive != (row["positive_rule_met"].lower() == "true"):
            mismatches.append([split, layer, group, "positive_rule_met"])
        if positive:
            positive_pairs[split].append([layer, group])
    complete = {(row["split"], int(row["layer"]), int(row["group"])) for row in rows} == {(split, layer, group) for split in metrics for layer in (6, 12) for group in range(12)} and len(rows) == 48
    return {"available": True, "accepted": complete and not mismatches, "rows": len(rows), "complete_fixed_panel": complete,
            "numeric_cells_checked": checked, "mismatches": mismatches, "positive_rule_pairs": positive_pairs}


def main() -> int:
    from eegfm.arguments import task_parser
    parser = task_parser('replay', description=__doc__)
    args = parser.parse_args()
    requested = {int(value) for value in args.cpus.split(",")}
    if len(requested) != 4 or requested & {0, 1, 2, 3} or not requested <= os.sched_getaffinity(0):
        raise ValueError("Require four available replay CPUs disjoint from Actor CPUs 0-3")
    os.sched_setaffinity(0, requested)
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[key] = "4"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import numpy as np
    from eegfm.agent.controller import EvaluationSpec
    from eegfm.eeg.aggregation import ScientificAggregator
    from eegfm.evaluation.worker import FileBinding
    from eegfm.evaluation.worker import RuntimeConfig
    from eegfm.evaluation.worker import SandboxedWorkerEvaluator
    from eegfm.evaluation.worker import SplitInputs
    from eegfm.evaluation.worker import candidate_digest

    config = read_json(args.config)
    case, original_root = Path(config["case_root"]), Path(config["trusted_root"])
    original_jobs, public = original_root / "worker-evidence", case / "public"
    if read_json(original_root / "EPISODE_RESULT.json")["state"]["status"] != "done" or not (case / "output/REPORT.md").is_file():
        raise ValueError("Replay requires an already completed original episode and report")
    destination = args.replay_root.absolute()
    if destination == original_root or original_root in destination.parents or case in destination.parents:
        raise ValueError("Replay must be disjoint from original case and episode")
    destination.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {"schema": "locked_candidate_clean_replay_v1", "status": "running",
        "episode_id": config["episode_id"], "started_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": "independent clean execution of the same locked code, inputs, runtime and aggregator; not independent method implementation",
        "candidate_digest": candidate_digest(args.candidate), "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "rtol": 1e-6, "atol": 1e-8, "model_calls": 0, "new_scientific_fits": 0,
        "original_actor_ledger_invoked": False, "candidate_feedback": False, "jobs": {}}
    protected = [args.config, original_root / "EPISODE_RESULT.json", original_jobs / "worker.sqlite3", case / "output/REPORT.md"]
    protected.extend(path for path in args.candidate.rglob("*") if path.is_file())
    protected.extend(path for path in Path(__file__).resolve().parents[1].rglob("*.py"))
    protected.extend(path for name in ("fit_probes.py", "contract-protocol.json", "released-q1-transcription.csv") if (path := case / "output" / name).is_file())
    for split in ("validation", "test"):
        job = original_jobs / f"{config['run_id']}-{args.attempt}-{split}"
        protected.extend(path for path in job.rglob("*") if path.is_file())
    before = snapshot(protected)
    write_new(destination / "SOURCE_HASHES_BEFORE.json", before)
    try:
        def binding(value: dict[str, str]) -> FileBinding:
            result = FileBinding(Path(value["path"]), value["sha256"])
            result.verify()
            return result

        truth = {name: binding(value) for name, value in config["truth_by_split"].items()}
        aggregate = ScientificAggregator(truth, binding(config["train_truth"]), bootstrap_resamples=config.get("bootstrap_resamples", 2000))
        runtime = RuntimeConfig(bwrap=Path(config["bwrap"]), python=Path(config["scientific_python"]),
            environment_roots=tuple(Path(path) for path in config["scientific_roots"]), manifest=binding(config["runtime_manifest"]))
        split_manifest, train = binding(config["split_manifest"]), binding(config["train_input"])
        public_hash = sha256(public / "PUBLIC_MANIFEST.json")
        worker = SandboxedWorkerEvaluator(private_root=destination / "worker-evidence", public_root=public,
            public_manifest_sha256=public_hash, split_manifest_path=split_manifest.path, split_manifest_sha256=split_manifest.sha256,
            inputs_by_split={name: SplitInputs(train, binding(config[name + "_input"])) for name in ("validation", "test")},
            runtime=runtime, aggregate=aggregate, released_metrics=aggregate.released_metrics, aggregate_bindings=aggregate.bindings,
            aggregate_policy_sha256=aggregate.policy_sha256, timeout_seconds=config.get("worker_timeout_seconds", 900))
        enrollment = worker._enrollment()
        for split in ("validation", "test"):
            original = original_jobs / f"{config['run_id']}-{args.attempt}-{split}"
            request = read_json(original / "request.json")
            if request["enrollment"] != enrollment or request["candidate_digest"] != report["candidate_digest"]:
                raise ValueError("Replay enrollment or locked candidate differs from original")
        report["original_enrollment_exact_match"] = True
        if args.audit_e05_q1:
            report["saved_parameter_audit"] = audit_saved_q1(args.candidate, public)
            report["report_transcription_audit"] = audit_transcription(case, original_jobs, config["run_id"], args.attempt)
        write_new(destination / "PREEXECUTION_AUDIT.json", report)
        for split in ("validation", "test"):
            job_id = f"replay-{config['episode_id']}-{args.attempt}-{split}"
            spec = EvaluationSpec(job_id=job_id, episode_id=config["episode_id"], run_id="independent-clean-replay",
                attempt_id=args.attempt, split=split, candidate_dir=args.candidate, candidate_digest=report["candidate_digest"],
                split_manifest_sha256=split_manifest.sha256, public_manifest_sha256=public_hash)
            result = worker.submit(spec)
            row: dict[str, Any] = {"job_id": job_id, "status": result["status"]}
            report["jobs"][split] = row
            write_new(destination / f"RESULT-{split}.json", result)
            if result["status"] != "succeeded":
                raise RuntimeError("Replay worker failure retained; no retry")
            original, replay = original_jobs / f"{config['run_id']}-{args.attempt}-{split}", worker.job_directory(job_id)
            row["arrays"] = {path.name: compare_npz(path, replay / "out" / path.name, report["rtol"], report["atol"])
                             for path in sorted((original / "out").glob("*.npz"))}
            first, second = read_json(original / "released_metrics.json"), result["metrics"]
            row["metric_count"] = len(first)
            row["metrics_exact"] = first == second
            row["metrics_accepted"] = first.keys() == second.keys() and all(np.isclose(first[key], second[key], rtol=report["rtol"], atol=report["atol"]) for key in first)
            row["maximum_metric_abs_difference"] = max(abs(first[key] - second[key]) for key in first)
            row["trusted_analysis_exact"] = read_json(original / "out/trusted_analysis.json") == read_json(replay / "out/trusted_analysis.json")
            row["execution"] = read_json(replay / "execution/status.json")
            row["accepted"] = row["metrics_accepted"] and row["trusted_analysis_exact"] and all(item["accepted"] for item in row["arrays"].values())
            print(json.dumps({"split": split, "accepted": row["accepted"], "metrics_exact": row["metrics_exact"]}), flush=True)
        baseline = original_jobs / f"{config['run_id']}-A1-validation/out/results.npz"
        if baseline.is_file():
            report["a1_a2_validation_predictions"] = compare_npz(baseline, original_jobs / f"{config['run_id']}-{args.attempt}-validation/out/results.npz", report["rtol"], report["atol"])
        report["status"] = "accepted" if all(row["accepted"] for row in report["jobs"].values()) and all(report.get(key, {"accepted": True}).get("accepted", True) for key in ("saved_parameter_audit", "report_transcription_audit")) else "comparison_failed"
    except BaseException as error:
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        report["error"] = str(error)
        (destination / "FAILURE.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        after = snapshot(protected)
        write_new(destination / "SOURCE_HASHES_AFTER.json", after)
        report["protected_files_unchanged"] = before == after
        report["protected_file_count"] = len(before)
        report["changed_paths"] = [path for path in before if before[path] != after.get(path)]
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        report["runner_sha256"] = sha256(Path(__file__))
        if not report["protected_files_unchanged"]:
            report["status"] = "integrity_failed"
        write_new(destination / "REPLAY_AUDIT.json", report)
        print(json.dumps({key: report[key] for key in ("status", "protected_files_unchanged", "protected_file_count", "candidate_digest")}), flush=True)
    return 0 if report["status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
