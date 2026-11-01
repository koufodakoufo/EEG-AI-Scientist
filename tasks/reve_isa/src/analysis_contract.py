"""Immutable artifact-derived development summaries and final paired statistics."""
from __future__ import annotations

from pathlib import Path
import numpy as np

from artifact_io import fingerprint, read_json, sha256_file, verify_completion
from data_contract import TARGETS
from evaluation_contract import (EVALUATION_HASH, paired_bootstrap, sample_metrics,
                                 final_conditions, expected_test_calls, locked_round_limit)


def check_contained(path, artifacts):
    path = Path(path).resolve()
    if not path.is_relative_to(Path(artifacts).resolve()):
        raise ValueError("Scientific artifact escaped this run")
    return path


def check_condition(condition, artifacts, source_root):
    directory = check_contained(condition["directory"], artifacts)
    identity = condition["condition"]
    verify_completion(directory, identity)
    if identity["evaluation_hash"] != EVALUATION_HASH:
        raise ValueError("Different common downstream contract")
    split = read_json(Path(source_root) / "split_manifest.json")["targets"][condition["target"]]["folds"]
    units = {}
    classes = len(identity["release"]["label_semantics"]["id_to_name"])
    for mode in ("lp", "ft"):
        for fold in range(6):
            unit_dir = directory / f"{mode}/fold{fold}"
            marker = verify_completion(unit_dir)
            unit = read_json(unit_dir / "validation.json")
            predictions = read_json(unit_dir / "validation_predictions.json")
            if (unit["identity"] != marker["identity"] or unit["identity"]["condition"] != identity
                    or unit["identity"]["fold"] != split[fold] or unit["mode"] != mode
                    or unit["target"] != condition["target"] or unit["fold"] != fold
                    or unit["test_evaluations"] != 0 or not 1 <= unit["epochs_completed"] <= unit["config"][mode]["epochs"]
                    or unit["updates_completed"] < 1 or unit["checkpoint_sha256"] != sha256_file(unit_dir / "val_best.pt")):
                raise ValueError("Downstream execution/checkpoint/split provenance failed")
            metrics = sample_metrics(predictions["labels"], predictions["predictions"], classes)
            if metrics != unit["validation"] or metrics["samples"] != split[fold]["val_n"]:
                raise ValueError("Validation prediction-derived metrics disagree")
            units[(mode, fold)] = unit
    if len(units) != 12:
        raise ValueError("Target condition lacks twelve downstream units")
    return units


def summarize_validation(worker_results, *, artifacts, source_root, round_number, snapshot_hash, protocol_hash, plan_hash):
    if set(worker_results) != set(TARGETS):
        raise ValueError("A research round requires all six LODO targets")
    datasets, validation_units, posttrain_wall = {}, [], 0.0
    diagnostics, evidence = {}, {}
    for target in TARGETS:
        result = worker_results[target]
        if result["phase"] != "development" or result["target"] != target or result["snapshot_hash"] != snapshot_hash or result["test_evaluations"] != 0:
            raise ValueError("Worker completion refers to a different round/source/phase")
        baseline = check_condition(result["baseline"], artifacts, source_root)
        candidate = check_condition(result["candidate"], artifacts, source_root)
        training = result["posttrain"]
        if (training["target"] != target or set(training["sources"]) != set(TARGETS)-{target}
                or training["posttrain_split"] != "all" or training["epochs_completed"] != 40
                or training["updates_completed"] != training["updates_requested"]
                or training["negatives_per_anchor"] != 62 or training["contrastive_batch_per_source"] != 64
                or training["test_evaluations"] != 0 or not result["cuda_smoke"]["passed"]):
            raise ValueError("Candidate ISA/initialization/numerical gate failed")
        verify_completion(Path(result["candidate"]["directory"]) / "posttrain", result["candidate"]["condition"])
        diagnostics[target] = {"posttrain": training, "cuda_smoke": result["cuda_smoke"],
                               "throughput_plan": result["throughput_plan"]}
        candidate_dir = Path(result["candidate"]["directory"])
        baseline_dir = Path(result["baseline"]["directory"])
        evidence[target] = [{"path":str(path),"sha256":sha256_file(path)} for path in
                            (candidate_dir/"condition.json",candidate_dir/"posttrain/training.json",baseline_dir/"condition.json")]
        posttrain_wall += training["telemetry"]["wall_seconds"]
        dataset_metrics = {}
        for mode in ("lp", "ft"):
            before = [baseline[(mode, fold)]["validation"]["balanced_accuracy"] for fold in range(6)]
            after = [candidate[(mode, fold)]["validation"]["balanced_accuracy"] for fold in range(6)]
            f1_before = [baseline[(mode, fold)]["validation"]["macro_f1"] for fold in range(6)]
            f1_after = [candidate[(mode, fold)]["validation"]["macro_f1"] for fold in range(6)]
            dataset_metrics[mode] = {"baseline_bacc_mean": float(np.mean(before)), "candidate_bacc_mean": float(np.mean(after)),
                                     "candidate_bacc_std": float(np.std(after, ddof=0)), "paired_delta_mean": float(np.mean(np.subtract(after,before))),
                                     "baseline_macro_f1_mean": float(np.mean(f1_before)), "candidate_macro_f1_mean": float(np.mean(f1_after))}
            for fold in range(6):
                unit = candidate[(mode, fold)]
                validation_units.append({"target": target, "mode": mode, "fold": fold, "split_seed": 42+fold,
                                         "baseline": baseline[(mode, fold)]["validation"], "candidate": unit["validation"],
                                         "selected_epoch": unit["selected_epoch"], "epochs_completed": unit["epochs_completed"],
                                         "checkpoint_sha256": unit["checkpoint_sha256"], "checkpoint_path": unit["checkpoint_path"],
                                         "wall_seconds": unit["telemetry"]["wall_seconds"]})
        datasets[target] = dataset_metrics
    summary = {"datasets": datasets}
    for mode in ("lp", "ft"):
        summary[f"{mode}_macro_balanced_accuracy"] = float(np.mean([datasets[name][mode]["candidate_bacc_mean"] for name in TARGETS]))
        summary[f"{mode}_macro_paired_delta"] = float(np.mean([datasets[name][mode]["paired_delta_mean"] for name in TARGETS]))
        summary[f"{mode}_positive_gain_datasets"] = sum(datasets[name][mode]["paired_delta_mean"] > 0 for name in TARGETS)
    return {"schema_version": "1.0", "execution_valid": True,
            "protocol_gate": {"passed": True, "checked": ["six LODO targets", "five all-sample sources", "official initialization",
                               "SEED session mapping", "actual release hashes", "40 epoch updates", "real source batch64",
                               "72 val-best units", "frozen common split/evaluation", "no development test calls"]},
            "snapshot_hash": snapshot_hash, "protocol_hash": protocol_hash, "plan_hash": plan_hash,
            "research_round": round_number, "validation_evaluations": len(validation_units), "test_evaluations": 0,
            "baseline_evaluations": 72, "baseline_counts_as_round": False,
            "evidence_level": "E1_directional" if round_number == 1 else "E2_development",
            "validation_summary": summary, "per_fold_validation": validation_units,
            "training_and_throughput_diagnostics": diagnostics, "condition_evidence": evidence,
            "posttrain_wall_seconds": float(posttrain_wall), "evaluation_hash": EVALUATION_HASH,
            "scope": "Development transfer under reused historical subject splits; does not establish independent-population confirmation",
            "test_policy": "Deferred until every requested validation round and a common method lock",
            "performance_success": None, "process_success": False}


def summarize_final(results, method_lock, artifacts):
    if set(results) != set(TARGETS):
        raise ValueError("Incomplete final target coverage")
    limit = locked_round_limit(method_lock)
    conditions = final_conditions(limit)
    target_calls = expected_test_calls(limit) // len(TARGETS)
    observations, count = {}, 0
    for target in TARGETS:
        result = results[target]
        if result["phase"] != "final_test" or result["method_lock_hash"] != fingerprint(method_lock) or result["test_evaluations"] != target_calls:
            raise ValueError("Final worker differs from the locked method")
        rows = result["tests"]
        seen = set()
        for row in rows:
            identity = row["identity"]["validation_unit"]
            raw_condition = identity["condition"]["condition"]
            condition = "R0" if raw_condition == "R0_official_REVE" else raw_condition
            key = (condition, row["mode"], row["fold"])
            if key in seen or condition not in conditions or row["mode"] not in {"lp", "ft"} or type(row["fold"]) is not int or row["fold"] not in range(6) or row["target"] != target:
                raise ValueError("Repeated or invalid final evaluation unit")
            seen.add(key)
            if row["method_lock_hash"] != fingerprint(method_lock) or row["test_evaluations"] != 1:
                raise ValueError("Test call counter/lock provenance failed")
            observations[(target, *key)] = row
            count += row["test_evaluations"]
        if len(seen) != target_calls:
            raise ValueError("Final worker lacks all condition x mode x fold test calls")
    if count != expected_test_calls(limit):
        raise ValueError("Actual test call count differs from the frozen campaign")
    chosen = f"R{method_lock['selected_round']}"
    tables = {}
    for target in TARGETS:
        tables[target] = {}
        for mode in ("lp", "ft"):
            table = {}
            for condition in conditions:
                metrics = [observations[(target, condition, mode, fold)]["metrics"] for fold in range(6)]
                table[condition] = {name+"_mean": float(np.mean([value[name] for value in metrics])) for name in ("balanced_accuracy", "macro_f1", "accuracy")}
                table[condition]["balanced_accuracy_std"] = float(np.std([value["balanced_accuracy"] for value in metrics], ddof=0))
                if condition != "R0":
                    table[condition]["paired_difference_vs_R0"] = paired_bootstrap(
                        [value["balanced_accuracy"] for value in metrics],
                        [observations[(target,"R0",mode,fold)]["metrics"]["balanced_accuracy"] for fold in range(6)])
            before = [observations[(target,"R0",mode,fold)]["metrics"]["balanced_accuracy"] for fold in range(6)]
            after = [observations[(target,chosen,mode,fold)]["metrics"]["balanced_accuracy"] for fold in range(6)]
            table["locked_candidate_paired_difference"] = paired_bootstrap(after, before)
            tables[target][mode] = table
    ft_deltas = [tables[target]["ft"]["locked_candidate_paired_difference"]["mean_delta"] for target in TARGETS]
    macro = {}
    for mode in ("lp","ft"):
        macro[mode] = {condition:{metric:float(np.mean([tables[target][mode][condition][metric] for target in TARGETS]))
                                 for metric in ("balanced_accuracy_mean","macro_f1_mean","accuracy_mean")}
                       for condition in conditions}
        macro[mode]["locked_candidate_mean_delta"] = float(np.mean([
            tables[target][mode]["locked_candidate_paired_difference"]["mean_delta"] for target in TARGETS]))
        macro[mode]["locked_candidate_positive_gain_datasets"] = sum(
            tables[target][mode]["locked_candidate_paired_difference"]["mean_delta"]>0 for target in TARGETS)
    # Equal dataset weights, with paired resampling within each dependent split set.
    generator = np.random.default_rng(20260713)
    resamples = np.zeros(5000)
    for target in TARGETS:
        delta = np.array([observations[(target, chosen, "ft", fold)]["metrics"]["balanced_accuracy"]-
                          observations[(target, "R0", "ft", fold)]["metrics"]["balanced_accuracy"] for fold in range(6)])
        resamples += delta[generator.integers(0,6,(5000,6))].mean(axis=1) / 6
    lower, upper = np.quantile(resamples,[0.025,0.975])
    return {"selected_common_condition": chosen, "test_evaluations": count, "tables": tables,
            "equal_dataset_macro_summary": macro,
            "per_fold": list(observations.values()), "ft_positive_gain_datasets": sum(delta > 0 for delta in ft_deltas),
            "ft_macro_paired_delta": float(np.mean(ft_deltas)),
            "ft_macro_paired_interval": {"lower": float(lower), "upper": float(upper), "resamples":5000,"seed":20260713},
            "performance_success": all(delta > 0 for delta in ft_deltas), "process_success": True,
            "evidence_level": "E2_development", "test_used_for_selection": False,
            "limitations": ["Historical repeated random splits reuse subjects", "Target validation guided method development",
                            "LODO does not prove cross-SEED-family physical person/stimulus independence",
                            "Paired fold bootstrap describes split stability; six folds are dependent",
                            "No independent confirmatory population was added"]}
