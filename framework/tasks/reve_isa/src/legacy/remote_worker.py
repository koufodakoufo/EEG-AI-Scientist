"""Frozen TiONE entrypoint. Invoked only by the trusted broker after approval."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

from artifact_io import (atomic_json, check_deadline, file_lock, fingerprint, publish_completion,
                         read_json, sha256_file, verify_completion, verify_source_snapshot)

ROOT = Path(__file__).resolve().parent
TRUSTED_EVALUATION_FILES = ["official_model.py", "evaluation_contract.py", "downstream.py", "release_io.py",
                            "data_contract.py", "split_manifest.json", "release_reference.json",
                            "vendor/reve/modeling_reve.py", "vendor/reve/configuration_reve.py",
                            "vendor/reve/position_bank.py", "vendor/reve/configuration_bank.py",
                            "vendor/reve/config.json", "vendor/reve/position_config.json", "gpu_diagnostics.py"]


def set_scratch(output, artifacts):
    from broker_contract import deployment_contract
    own_scratch = Path("/omni-eeg-00/home/wzf/scratch/reve_isa_rsi") / deployment_contract()["run_id"] / Path(output).name
    own_scratch.mkdir(parents=True, exist_ok=True)
    temporary = own_scratch / "tmp"
    temporary.mkdir(exist_ok=True)
    # Fail before spawning any process when the run-scoped scratch is not writable.
    probe = temporary / ("write-check-" + str(os.getpid()))
    with probe.open("x") as stream:
        stream.write("scratch writable\n")
    probe.unlink()
    for name in ("TMPDIR", "TMP", "TEMP"):
        os.environ[name] = str(temporary)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    return own_scratch


def baseline_identity(release):
    from evaluation_contract import EVALUATION_HASH
    from official_model import BASE_WEIGHT_SHA256, POSITION_WEIGHT_SHA256
    return {"condition": "R0_official_REVE", "release": release.identity,
            "evaluation_hash": EVALUATION_HASH, "base_weight_sha256": BASE_WEIGHT_SHA256,
            "position_weight_sha256": POSITION_WEIGHT_SHA256,
            "trusted_source": [{"path": name, "sha256": sha256_file(ROOT / name)} for name in TRUSTED_EVALUATION_FILES]}


def condition_identity(release, args, parameters):
    from evaluation_contract import EVALUATION_HASH
    return {"condition": f"R{args.research_round}", "release": release.identity,
            "evaluation_hash": EVALUATION_HASH, "snapshot_hash": args.snapshot_hash,
            "plan_hash": args.plan_hash, "parameters": parameters,
            "baseline_identity_hash": fingerprint(baseline_identity(release))}


def run_fold_processes(directory, *, target, artifacts, device_count, deadline, encoder_checkpoint, feature_path, phase):
    """Six independent fold RNGs using the six allocated GPUs."""
    import torch
    workers, streams = [], []
    if device_count < 6:
        raise RuntimeError("Broker GPU allocation is incomplete: require six fold devices")
    try:
        for fold in range(6):
            log = (Path(directory) / f"fold{fold}.log").open("a")
            streams.append(log)
            command = [sys.executable, "-B", str(ROOT / "fold_worker.py"), "--phase", phase,
                       "--target", target, "--fold", str(fold), "--directory", str(directory),
                       "--artifacts", str(artifacts), "--device", f"cuda:{fold}",
                       "--deadline", str(deadline)]
            if encoder_checkpoint:
                command.extend(["--encoder-checkpoint", str(encoder_checkpoint)])
            if feature_path:
                command.extend(["--feature-path", str(feature_path)])
            workers.append(subprocess.Popen(command, cwd=ROOT, env=os.environ.copy(), stdout=log, stderr=subprocess.STDOUT))
        while any(process.poll() is None for process in workers):
            check_deadline(deadline)
            if any(process.poll() not in (None, 0) for process in workers):
                raise RuntimeError("Fold process failed; preserve logs and val-best states")
            time.sleep(5)
        if any(process.returncode != 0 for process in workers):
            raise RuntimeError("Fold campaign incomplete")
    finally:
        for process in workers:
            if process.poll() is None:
                process.terminate()
        for process in workers:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        for stream in streams:
            stream.close()


def validate_unit_set(directory, target, condition):
    from evaluation_contract import EVALUATION_HASH
    units = []
    for mode in ("lp", "ft"):
        for fold in range(6):
            unit_directory = Path(directory) / f"{mode}/fold{fold}"
            marker = verify_completion(unit_directory)
            report = read_json(unit_directory / "validation.json")
            if (report["identity"]["condition"] != condition or marker["identity"] != report["identity"]
                    or report["target"] != target or report["mode"] != mode or report["fold"] != fold
                    or report["identity"]["evaluation_hash"] != EVALUATION_HASH or report["test_evaluations"] != 0):
                raise ValueError("Validation unit identity or test isolation failed")
            report["directory"] = str(unit_directory)
            units.append(report)
    return units


def complete_condition(release, condition, directory, artifacts, *, encoder_checkpoint, deadline):
    import torch
    from downstream import build_validation_features
    directory = Path(directory)
    if (directory / "COMPLETE.json").is_file():
        verify_completion(directory, condition)
        validate_unit_set(directory, release.target, condition)
        return read_json(directory / "condition.json")
    directory.mkdir(parents=True, exist_ok=True)
    atomic_json(directory / "identity.json", condition)
    folds = read_json(ROOT / "split_manifest.json")["targets"][release.target]["folds"]
    feature_path = build_validation_features(release, folds, directory / "lp_features", device="cuda:0",
                                             encoder_checkpoint=encoder_checkpoint, deadline=deadline)
    torch.cuda.empty_cache()
    run_fold_processes(directory, target=release.target, artifacts=artifacts, device_count=torch.cuda.device_count(),
                       deadline=deadline, encoder_checkpoint=encoder_checkpoint, feature_path=feature_path, phase="validation")
    units = validate_unit_set(directory, release.target, condition)
    summary = {"condition": condition, "target": release.target, "directory": str(directory),
               "units": units, "validation_evaluations": len(units), "test_evaluations": 0}
    atomic_json(directory / "condition.json", summary)
    publish_completion(directory, condition, ["identity.json", "condition.json"])
    return summary


def probe_workload(args, parameters, output, artifacts, local_deadline):
    from data_contract import TARGETS
    from release_io import Release, overlap_audit
    releases = {target: Release.open(target) for target in TARGETS}
    atomic_json(output / "data_preflight.json", {"releases": {target: release.identity for target, release in releases.items()},
                                                 "overlap": overlap_audit(releases)})
    signal_caches={}
    for release in releases.values():
        signal_caches[release.target]=release.preload_signals(artifacts, deadline=local_deadline)
    atomic_json(output/"signal_cache_provenance.json",signal_caches)
    from cloud_smoke import smoke
    smoke_report = smoke(args.target, releases, parameters, output, device="cuda:0", deadline=local_deadline)
    # Forecast only after a complete, discarded formal-path throughput probe.
    # Numerical/serial diagnostics in cloud_smoke are not the update ETA.
    from posttrain import (run_posttrain, release_source_signals,
                           PROBE_WARMUP_STEPS, PROBE_MEASURED_STEPS)
    training_probe = run_posttrain(args.target, releases, parameters, output / "preflight-posttrain",
                                  device="cuda:0", identity={"kind": "discarded_preflight"},
                                  deadline=local_deadline,
                                  smoke_steps=PROBE_WARMUP_STEPS + PROBE_MEASURED_STEPS)
    smoke_report['training_path_smoke'] = training_probe
    from throughput_plan import forecast
    folds = read_json(ROOT / "split_manifest.json")["targets"][args.target]["folds"]
    estimate = forecast(smoke_report,releases,args.target,folds,args.phase,deadline=local_deadline,output=output/"throughput_plan.json",
                        round_limit=args.research_round_limit, training_probe=training_probe)
    if args.phase == 'baseline':
        release_source_signals(releases)
    return releases, smoke_report, estimate


def parser():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["baseline", "development", "final_test"], required=True)
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--preflight-contract")
    p.add_argument("--full-worker-seconds", type=int, default=43200)
    p.add_argument("--target", required=True)
    p.add_argument("--research-round", type=int, required=True)
    p.add_argument("--research-round-limit", type=int, required=True)
    for name in ("output", "artifacts", "snapshot-hash", "plan-hash"):
        p.add_argument("--" + name, required=True)
    for name in ("posttrain-lr", "temperature", "posttrain-weight-decay", "warmup-epochs", "gradient-clip", "deadline"):
        p.add_argument("--" + name, type=float, required=True)
    return p


def main():
    args = parser().parse_args()
    output, artifacts = Path(args.output), Path(args.artifacts)
    own_scratch = set_scratch(output, artifacts)
    from broker_contract import deployment_contract
    from data_contract import TARGETS
    from evaluation_contract import EVALUATION_HASH
    from gpu_diagnostics import require_cuda
    from posttrain import run_posttrain, validate_parameters
    from release_io import Release, overlap_audit
    import torch
    deployment = deployment_contract()
    if (args.deadline != deployment["deadline"] or args.research_round not in range(1, deployment["round_limit"] + 1)
            or args.research_round_limit != deployment["round_limit"] or args.target not in TARGETS
            or artifacts.parent.name != deployment["run_id"]):
        raise ValueError("Remote execution outside the immutable contract")
    if not output.is_relative_to(artifacts / "tione/outputs") or not output.is_dir():
        raise ValueError("Broker must create the exact writable output root before worker entry")
    manifest = verify_source_snapshot(ROOT)
    if manifest["snapshot_hash"] != args.snapshot_hash or sha256_file(ROOT / "candidate_plan.json") != args.plan_hash:
        raise ValueError("Remote execution snapshot or plan differs from scheduler request")
    parameters = {name: getattr(args, name) for name in ("posttrain_lr", "temperature", "posttrain_weight_decay", "warmup_epochs", "gradient_clip")}
    validate_parameters(parameters)
    from hparam_contract import verify_scientist_plan
    verify_scientist_plan(read_json(ROOT / "candidate_plan.json"), ROOT, parameters)
    require_cuda("cuda:0")
    if torch.cuda.device_count() != 6:
        raise RuntimeError("Worker must expose exactly its six broker-allocated GPUs")
    if not 60 <= args.full_worker_seconds <= 43200:
        raise ValueError("Invalid full worker time bound")
    local_deadline = min(args.deadline, time.time() + args.full_worker_seconds - min(100, args.full_worker_seconds * 0.01))
    check_deadline(local_deadline)
    if args.preflight_only:
        if not args.preflight_contract or len(args.preflight_contract) != 64:
            raise ValueError("Broker preflight contract required")
        releases, smoke_report, estimate = probe_workload(args, parameters, output, artifacts, local_deadline)
        atomic_json(output / "preflight.json", {
            "kind": "preflight", "passed": True, "contract_hash": args.preflight_contract,
            "snapshot_hash": args.snapshot_hash, "phase": args.phase, "target": args.target,
            "cuda_smoke": smoke_report, "throughput_plan": estimate,
            "training_path_smoke": smoke_report['training_path_smoke'],
            "research_rounds": 0, "test_evaluations": 0,
            "scope": "Discarded short smoke states; no formal posttrain or downstream campaign",
        })
        return
    if args.phase == "final_test":
        from evaluation_contract import final_conditions, expected_test_calls, locked_round_limit
        if args.research_round != args.research_round_limit:
            raise ValueError("Premature final test")
        lock = read_json(artifacts / "final/method_lock.json")
        locked_round_limit(lock, expected=args.research_round_limit)
        conditions = read_json(artifacts / "final/evaluation_plan.json")["conditions"][args.target]
        atomic_json(output / "test_plan.json", {"method_lock": lock, "conditions": conditions})
        run_fold_processes(output, target=args.target, artifacts=artifacts, device_count=torch.cuda.device_count(),
                           deadline=local_deadline, encoder_checkpoint=None, feature_path=None, phase="final_test")
        tests = []
        for condition in final_conditions(args.research_round_limit):
            for mode in ("lp", "ft"):
                for fold in range(6):
                    directory = output / f"{condition}/{mode}/fold{fold}"
                    verify_completion(directory)
                    tests.append(read_json(directory / "test.json"))
        target_calls = expected_test_calls(args.research_round_limit) // len(TARGETS)
        if len(tests) != target_calls or sum(test["test_evaluations"] for test in tests) != target_calls:
            raise ValueError("Incomplete actual final test call accounting")
        result = {"phase": args.phase, "target": args.target, "snapshot_hash": args.snapshot_hash,
                  "evaluation_hash": EVALUATION_HASH, "method_lock_hash": fingerprint(lock),
                  "tests": tests, "test_evaluations": target_calls}
    else:
        releases, smoke_report, estimate = probe_workload(args, parameters, output, artifacts, local_deadline)
        release = releases[args.target]
        baseline = baseline_identity(release)
        baseline_dir = artifacts / "baseline" / fingerprint(baseline) / args.target
        if args.phase == "baseline":
            with file_lock(baseline_dir.parent / (args.target + ".lock")):
                condition = complete_condition(release, baseline, baseline_dir, artifacts,
                                               encoder_checkpoint=None, deadline=local_deadline)
            result = {"phase": "baseline", "target": args.target, "snapshot_hash": args.snapshot_hash,
                      "evaluation_hash": EVALUATION_HASH, "baseline": condition,
                      "cuda_smoke": smoke_report, "test_evaluations": 0}
        else:
            # All six baseline workers must already be complete at the local run-stage gate.
            baseline_campaign = read_json(artifacts / "development/baseline_campaign.json")
            if set(baseline_campaign["targets"]) != set(TARGETS):
                raise ValueError("Incomplete six-target R0 campaign")
            verify_completion(baseline_dir, baseline)
            identity = condition_identity(release, args, parameters)
            directory = artifacts / "conditions" / f"R{args.research_round}" / fingerprint(identity) / args.target
            training = run_posttrain(args.target, releases, parameters, directory / "posttrain", device="cuda:0",
                                     identity=identity, deadline=local_deadline)
            from posttrain import release_source_signals
            release_source_signals(releases)
            torch.cuda.empty_cache()
            condition = complete_condition(release, identity, directory, artifacts,
                                           encoder_checkpoint=directory / "posttrain/encoder.pt", deadline=local_deadline)
            result = {"phase": "development", "target": args.target, "snapshot_hash": args.snapshot_hash,
                      "evaluation_hash": EVALUATION_HASH, "baseline": read_json(baseline_dir / "condition.json"),
                      "candidate": condition, "posttrain": training,
                      "cuda_smoke": smoke_report, "test_evaluations": 0}
    loaded = {}
    for name in ("official_model", "downstream", "posttrain", "isa_loss", "isa_builder", "isa_representation", "release_io"):
        module = sys.modules.get(name)
        if module is not None:
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(ROOT):
                raise ValueError("Remote import escaped the frozen execution source")
            loaded[name] = {"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)}
    result["loaded_modules"] = loaded
    result["source_files"] = manifest["files"]
    result["actual_gpu_count"] = torch.cuda.device_count()
    if args.phase != "final_test":
        result["throughput_plan"] = estimate
    result["plan_hash"] = args.plan_hash
    result["research_round"] = args.research_round
    atomic_json(output / "worker_result.json", result)
    publish_completion(output, {"phase": args.phase, "target": args.target, "snapshot_hash": args.snapshot_hash,
                                "plan_hash": args.plan_hash, "research_round": args.research_round}, ["worker_result.json"])
    # Leave scratch cleanup to the broker's guarded successful-completion path.


if __name__ == "__main__":
    main()
