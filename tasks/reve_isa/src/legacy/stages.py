"""Immutable local CPU scheduler gates, broker handoff, bounded wait and analysis."""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import time

from artifact_io import (atomic_json, check_deadline, fingerprint, read_json, sha256_file,
                         verify_completion, verify_source_snapshot)
from broker_contract import deployment_contract, build_request, check_receipt, publish_request
from evaluation_contract import final_conditions, expected_test_calls, locked_round_limit, validate_round_limit
from data_contract import TARGETS
from hparam_contract import validate_h2_parameters, verify_scientist_plan
from hparam_reporting import enrich_report

ROOT = Path(__file__).resolve().parent


def task_contract():
    import yaml
    return yaml.safe_load((ROOT / "task.yaml").read_text())


def check_plan(round_number, artifacts):
    plan = read_json(ROOT / "candidate_plan.json")
    if plan.get("research_round") != round_number or not plan.get("hypothesis") or not plan.get("change") or not plan.get("opposite_result"):
        raise ValueError("Candidate plan lacks the current round hypothesis/change/opposite-result explanation")
    if round_number == 2:
        prior_path = Path(artifacts) / "development/round1_report.json"
        prior = read_json(prior_path)
        expected = {"path": str(prior_path), "sha256": sha256_file(prior_path)}
        if expected not in plan.get("evidence", []) or prior["test_evaluations"] != 0 or not prior["execution_valid"] or prior["validation_evaluations"] != 72:
            raise ValueError("R2 must explicitly cite the actual complete validation-only R1 report hash")
        if not plan.get("r1_diagnosis") or not plan.get("decision_value"):
            raise ValueError("R2 lacks its R1 diagnosis and discriminating decision value")
        if plan.get("change_type") == "stability_repeat" and not plan.get("stability_uncertainty"):
            raise ValueError("A stability repeat must answer a concrete R1 uncertainty")
    if round_number == 1:
        verify_scientist_plan(plan, ROOT)
    return plan


def check_r1(parameters):
    # Local R1 is cross-run H2; temperature is tunable within the frozen bounds.
    validate_h2_parameters(parameters)


def receipt_path(artifacts, request):
    return Path(artifacts) / "tione/receipts" / (request["request_id"] + ".json")


def check_worker_output(request, receipt, artifacts, source_manifest, *, round_number, plan_hash):
    if not check_receipt(receipt, request, source_manifest["snapshot_hash"]):
        return None
    directory = Path(artifacts) / "tione/outputs" / request["request_id"]
    marker = verify_completion(directory)
    value = read_json(directory / "worker_result.json")
    phase = request["args"][request["args"].index("--phase") + 1]
    target = request["args"][request["args"].index("--target") + 1]
    expected = {"phase": phase, "target": target, "snapshot_hash": source_manifest["snapshot_hash"],
                "plan_hash": plan_hash, "research_round": round_number}
    if marker["identity"] != expected or any(value[key] != expected[key] for key in expected):
        raise ValueError("Scientific worker output differs from frozen request identity")
    if value["source_files"] != source_manifest["files"] or value["actual_gpu_count"] != 6:
        raise ValueError("Actual worker source/GPU provenance failed")
    hashes = {entry["path"]: entry["sha256"] for entry in source_manifest["files"]}
    for entry in value["loaded_modules"].values():
        if hashes.get(entry["path"]) != entry["sha256"]:
            raise ValueError("Remote loaded module differs from frozen candidate source")
    if phase == "final_test":
        from analysis_contract import summarize_final
        from evaluation_contract import sample_metrics
        plan = read_json(directory / "test_plan.json")
        limit = int(request["args"][request["args"].index("--research-round-limit") + 1])
        locked_round_limit(plan["method_lock"], expected=limit)
        for condition in final_conditions(limit):
            for mode in ("lp", "ft"):
                for fold in range(6):
                    unit = directory / f"{condition}/{mode}/fold{fold}"
                    verified = verify_completion(unit)
                    record = read_json(unit / "test.json")
                    prediction = read_json(unit / "predictions.json")
                    classes = len(record["identity"]["validation_unit"]["release"]["label_semantics"]["id_to_name"])
                    if (record["identity"] != verified["identity"] or record["metrics"] != sample_metrics(prediction["labels"], prediction["predictions"], classes)
                            or record["method_lock_hash"] != fingerprint(plan["method_lock"]) or record["test_evaluations"] != 1
                            or record not in value["tests"]):
                        raise ValueError("Final test predictions/call identity failed")
    return value


def wait_phase(requests, *, artifacts, manifest, round_number, plan_hash):
    results = {}
    while len(results) != len(requests):
        check_deadline(deployment_contract()["deadline"])
        for request in requests:
            target = request["args"][request["args"].index("--target") + 1]
            if target in results:
                continue
            path = receipt_path(artifacts, request)
            if not path.is_file():
                continue
            value = check_worker_output(request, read_json(path), artifacts, manifest,
                                        round_number=round_number, plan_hash=plan_hash)
            if value is not None:
                results[target] = value
        if len(results) != len(requests):
            time.sleep(15)
    return results


def phase_requests(phase, *, job_dir, artifacts, round_number, parameters, manifest, plan_hash, round_limit=2):
    return [build_request(job_dir=job_dir, artifacts=artifacts, phase=phase, target=target,
                          round_number=round_number, round_limit=round_limit, parameters=parameters,
                          snapshot_hash=manifest["snapshot_hash"], plan_hash=plan_hash) for target in TARGETS]


def publish_phase(requests, artifacts):
    check_deadline(deployment_contract()["deadline"])
    for request in requests:
        publish_request(request, artifacts)


def reusable_baseline(artifacts):
    """Reuse completed R0 only under the same complete downstream contract.

    Source changes to posttraining or smoke do not invalidate the independently
    identified R0. Its original provenance stays intact; no worker receipt or
    completion marker is rewritten to claim it ran under the new snapshot.
    """
    from analysis_contract import check_condition
    from evaluation_contract import EVALUATION_HASH
    from official_model import BASE_WEIGHT_SHA256, POSITION_WEIGHT_SHA256
    from remote_worker import TRUSTED_EVALUATION_FILES
    path = Path(artifacts) / "development/baseline_campaign.json"
    if not path.exists():
        return None
    before_hash = sha256_file(path)
    campaign = read_json(path)
    if (set(campaign["targets"]) != set(TARGETS) or campaign["rounds_counted"] != 0
            or campaign["evaluation_units"] != 72 or campaign["test_evaluations"] != 0):
        raise ValueError("Existing R0 campaign is incomplete or has a different evaluation scope")
    expected_source = [{"path": name, "sha256": sha256_file(ROOT / name)}
                       for name in TRUSTED_EVALUATION_FILES]
    for target in TARGETS:
        condition = campaign["targets"][target]
        identity = condition["condition"]
        if (condition["target"] != target or condition["validation_evaluations"] != 12
                or condition["test_evaluations"] != 0 or identity["release"]["target"] != target
                or identity["condition"] != "R0_official_REVE"
                or identity["evaluation_hash"] != EVALUATION_HASH
                or identity["base_weight_sha256"] != BASE_WEIGHT_SHA256
                or identity["position_weight_sha256"] != POSITION_WEIGHT_SHA256
                or identity["trusted_source"] != expected_source):
            raise ValueError("Existing R0 identity differs from the current common evaluation contract")
        if len(check_condition(condition, artifacts, ROOT)) != 12:
            raise ValueError("Existing R0 lacks twelve verified downstream units")
    if sha256_file(path) != before_hash:
        raise ValueError("R0 campaign changed during verification")
    return {"path": str(path), "sha256": before_hash}


def prepare(args, review=False):
    manifest = verify_source_snapshot(ROOT)
    task = task_contract()
    contract = task["research"]
    if (contract["adapter"] != "scheduler" or args.research_round_limit != deployment_contract()["round_limit"]
            or args.research_round not in range(1, validate_round_limit(args.research_round_limit) + 1)):
        raise ValueError("Invalid frozen scheduler/round contract")
    plan = check_plan(args.research_round, args.artifacts)
    result = subprocess.run([sys.executable, "-B", str(ROOT / "validate.py")], cwd=ROOT,
                            text=True, capture_output=True, timeout=contract["validation_timeout_seconds"])
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "validation.stdout").write_text(result.stdout)
    (output / "validation.stderr").write_text(result.stderr)
    if result.returncode != 0:
        raise ValueError("Controlled CPU contract validation failed")
    value = {"passed": result.returncode == 0, "stage": "review" if review else "prepare",
             "snapshot_hash": manifest["snapshot_hash"], "protocol_hash": fingerprint(contract["protocol"]),
             "plan_hash": sha256_file(ROOT / "candidate_plan.json"), "research_round": args.research_round,
             "research_round_limit": args.research_round_limit, "validation_exit_code": result.returncode,
             "local_gpu_training": False, "scope": "deterministic CPU contracts; cloud worker must verify actual data/weights/CUDA",
             "plan": plan}
    atomic_json(output / "gate.json", value)


def submit(args):
    from posttrain import validate_parameters
    manifest = verify_source_snapshot(ROOT)
    plan = check_plan(args.research_round, args.artifacts)
    parameters = {name: getattr(args, name) for name in ("posttrain_lr", "temperature", "posttrain_weight_decay", "warmup_epochs", "gradient_clip")}
    validate_parameters(parameters)
    if args.research_round == 1:
        check_r1(parameters)
        verify_scientist_plan(plan, ROOT, parameters)
    output, artifacts = Path(args.output), Path(args.artifacts)
    job_dir = output.parents[1]
    plan_hash = sha256_file(ROOT / "candidate_plan.json")
    baseline_reuse = reusable_baseline(artifacts) if args.research_round == 1 else None
    first_phase = "baseline" if args.research_round == 1 and baseline_reuse is None else "development"
    requests = phase_requests(first_phase, job_dir=job_dir, artifacts=artifacts,
                              round_number=args.research_round, parameters=parameters, manifest=manifest, plan_hash=plan_hash,
                              round_limit=args.research_round_limit)
    # This stage only writes bounded requests. The separate trusted broker owns cloud submission.
    publish_phase(requests, artifacts)
    atomic_json(output / "submission.json", {"requests": requests, "job_dir": str(job_dir),
                                             "artifacts": str(artifacts), "parameters": parameters,
                                             "snapshot_hash": manifest["snapshot_hash"], "plan_hash": plan_hash,
                                             "research_round": args.research_round, "first_phase": first_phase,
                                             "baseline_reuse": baseline_reuse})


def run(args):
    from analysis_contract import check_condition, summarize_final, summarize_validation
    from evaluation_contract import select_method
    manifest = verify_source_snapshot(ROOT)
    contract = task_contract()["research"]
    submitted = read_json(Path(args.submit_output) / "submission.json")
    artifacts = Path(args.artifacts)
    if submitted["snapshot_hash"] != manifest["snapshot_hash"] or submitted["research_round"] != args.research_round or submitted["artifacts"] != str(artifacts):
        raise ValueError("Submit handoff differs from current frozen execution")
    parameters, plan_hash, job_dir = submitted["parameters"], submitted["plan_hash"], Path(submitted["job_dir"])
    check_plan(args.research_round, artifacts)
    reuse = submitted.get("baseline_reuse")
    if reuse is not None:
        if (args.research_round != 1 or submitted["first_phase"] != "development"
                or reuse != reusable_baseline(artifacts)):
            raise ValueError("Reused R0 evidence differs from the submission gate")
    elif args.research_round == 1 and submitted["first_phase"] != "baseline":
        raise ValueError("R1 development requires verified R0 provenance")
    first = wait_phase(submitted["requests"], artifacts=artifacts, manifest=manifest,
                       round_number=args.research_round, plan_hash=plan_hash)
    if args.research_round == 1 and reuse is None:
        if set(first) != set(TARGETS):
            raise ValueError("R0 campaign incomplete")
        for target in TARGETS:
            check_condition(first[target]["baseline"], artifacts, ROOT)
        atomic_json(artifacts / "development/baseline_campaign.json",
                    {"targets": {target: first[target]["baseline"] for target in TARGETS}, "rounds_counted": 0,
                     "evaluation_units": 72, "test_evaluations": 0, "source_snapshot_hash": manifest["snapshot_hash"]})
        requests = phase_requests("development", job_dir=job_dir, artifacts=artifacts, round_number=1,
                                  parameters=parameters, manifest=manifest, plan_hash=plan_hash, round_limit=args.research_round_limit)
        publish_phase(requests, artifacts)
        candidates = wait_phase(requests, artifacts=artifacts, manifest=manifest, round_number=1, plan_hash=plan_hash)
    else:
        candidates = first
    report = summarize_validation(candidates, artifacts=artifacts, source_root=ROOT, round_number=args.research_round,
                                  snapshot_hash=manifest["snapshot_hash"], protocol_hash=fingerprint(contract["protocol"]), plan_hash=plan_hash)
    report_path = artifacts / f"development/round{args.research_round}_report.json"
    atomic_json(report_path, report)
    # Development history contains validation only, including at final evaluation.
    development_manifest = {"research_round": args.research_round, "snapshot_hash": manifest["snapshot_hash"],
                            "report": {"path": str(report_path), "sha256": sha256_file(report_path)},
                            "conditions": {target: candidates[target]["candidate"]["directory"] for target in TARGETS},
                            "baselines": {target: candidates[target]["baseline"]["directory"] for target in TARGETS},
                            "worker_evidence": candidates}
    atomic_json(artifacts / f"development/round{args.research_round}_manifest.json", development_manifest)
    final = None
    if args.research_round == args.research_round_limit:
        rounds = list(range(1, args.research_round_limit + 1))
        reports = {number: read_json(artifacts / f"development/round{number}_report.json") for number in rounds}
        manifests = {number: read_json(artifacts / f"development/round{number}_manifest.json") for number in rounds}
        selected = select_method(reports, round_limit=args.research_round_limit)
        lock = {"round_limit": args.research_round_limit, "complete_validation_rounds": rounds,
                "selected_round": selected, "selection_data": "validation_only",
                "selected_snapshot_hash": reports[selected]["snapshot_hash"],
                "reports": [{"path": str(artifacts / f"development/round{number}_report.json"),
                             "sha256": sha256_file(artifacts / f"development/round{number}_report.json")} for number in rounds],
                "scope": "one common candidate across all six targets", "test_started_before_lock": False}
        lock_path = artifacts / "final/method_lock.json"
        if lock_path.exists() and read_json(lock_path) != lock:
            raise ValueError("Previously locked method differs; cannot reselect after test")
        atomic_json(lock_path, lock)
        test_plan = {"method_lock_hash": fingerprint(lock), "conditions": {
            target: {"R0": development_manifest["baselines"][target],
                     **{f"R{number}": manifests[number]["conditions"][target] for number in rounds}} for target in TARGETS}}
        atomic_json(artifacts / "final/evaluation_plan.json", test_plan)
        requests = phase_requests("final_test", job_dir=job_dir, artifacts=artifacts, round_number=args.research_round,
                                  parameters=parameters, manifest=manifest, plan_hash=plan_hash,
                                  round_limit=args.research_round_limit)
        publish_phase(requests, artifacts)
        tests = wait_phase(requests, artifacts=artifacts, manifest=manifest, round_number=args.research_round, plan_hash=plan_hash)
        final = summarize_final(tests, lock, artifacts)
        atomic_json(artifacts / "final/final_test_report.json", final)
    atomic_json(Path(args.run_dir) / "campaign.json", {"development_report": {"path": str(report_path), "sha256": sha256_file(report_path)},
                                                      "manifest": development_manifest, "final": final,
                                                      "snapshot_hash": manifest["snapshot_hash"], "protocol_hash": fingerprint(contract["protocol"]),
                                                      "research_round": args.research_round})


def analysis(args):
    manifest = verify_source_snapshot(ROOT)
    campaign = read_json(Path(args.run_dir) / "campaign.json")
    source = campaign["development_report"]
    if source["sha256"] != sha256_file(source["path"]) or campaign["snapshot_hash"] != manifest["snapshot_hash"]:
        raise ValueError("Actual campaign/report identity changed")
    report = read_json(source["path"])
    report["decision_evidence"] = source
    report["candidate_plan"] = read_json(ROOT / "candidate_plan.json")
    if args.research_round == args.research_round_limit:
        final = campaign["final"]
        if final is None or final["test_evaluations"] != expected_test_calls(args.research_round_limit):
            raise ValueError("Last round incomplete without actual post-lock test campaign")
        report["test_evaluations"] = final["test_evaluations"]
        report["final"] = final
        report["performance_success"] = final["performance_success"]
        report["process_success"] = final["process_success"]
        report["final_method_lock"] = read_json(Path(args.artifacts) / "final/method_lock.json")
    report["protocol_gate"]["test_accounting_matches"] = report["test_evaluations"] == (expected_test_calls(args.research_round_limit) if args.research_round == args.research_round_limit else 0)
    if not report["protocol_gate"]["test_accounting_matches"]:
        raise ValueError("Scientific test count failed")
    cumulative = {"reports": [read_json(Path(args.artifacts) / f"development/round{number}_report.json")
                              for number in range(1, args.research_round+1)],
                  "test_evaluations": 0, "test_metrics_included": False}
    atomic_json(Path(args.artifacts) / "development/cumulative_validation.json", cumulative)
    report = enrich_report(report, root=ROOT, artifacts=args.artifacts)
    atomic_json(Path(args.output) / "report.json", report)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["prepare", "review", "submit", "run", "analysis"])
    p.add_argument("--output")
    p.add_argument("--run-dir")
    p.add_argument("--submit-output")
    p.add_argument("--artifacts", required=True)
    p.add_argument("--research-round", type=int, required=True)
    p.add_argument("--research-round-limit", type=int, required=True)
    for name in ("posttrain-lr", "temperature", "posttrain-weight-decay", "warmup-epochs", "gradient-clip"):
        p.add_argument("--"+name, type=float)
    args = p.parse_args()
    check_deadline(deployment_contract()["deadline"])
    deployment = deployment_contract()
    if (args.research_round_limit != deployment["round_limit"]
            or args.research_round not in range(1, deployment["round_limit"] + 1)
            or Path(args.artifacts).parent.name != deployment["run_id"]):
        raise ValueError("Scheduler arguments differ from the frozen run/round contract")
    if args.mode == "prepare":
        prepare(args)
    elif args.mode == "review":
        prepare(args, review=True)
    elif args.mode == "submit":
        submit(args)
    elif args.mode == "run":
        run(args)
    else:
        analysis(args)


if __name__ == "__main__":
    main()
