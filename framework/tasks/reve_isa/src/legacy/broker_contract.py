"""Immutable TiONE request construction and finite receipt/output verification.

No cloud SDK, credentials, shell command, resource purchase or pool selection.
Only later scheduler stages may publish these requests.
"""
from __future__ import annotations

import re
import math
from pathlib import Path

from artifact_io import atomic_json, read_json
from data_contract import TARGETS

MAX_WORKER_SECONDS = 43200
REQUEST_FIELDS = {"schema_version", "request_id", "job_dir", "script", "args", "gpus", "timeout_seconds"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def deployment_contract():
    """Read only the approved task snapshot; workers never open broker credentials/config."""
    import yaml
    from evaluation_contract import validate_round_limit
    task = yaml.safe_load((Path(__file__).resolve().parent / "task.yaml").read_text())
    protocol = task["research"]["protocol"]
    run_id = protocol["run_id"]
    deadline = protocol["resources"]["deadline"]
    if (not isinstance(run_id, str) or not ID_PATTERN.fullmatch(run_id)
            or isinstance(deadline, bool) or not isinstance(deadline, (int, float))
            or not math.isfinite(deadline) or deadline <= 0):
        raise ValueError("Frozen task requires a safe run ID and finite deployment deadline")
    return {"run_id": run_id, "deadline": float(deadline),
            "round_limit": validate_round_limit(protocol.get("valid_rounds", 2))}


def worker_request_id(job_id, phase, target):
    if not ID_PATTERN.fullmatch(job_id) or phase not in {"baseline", "development", "final_test"} or target not in TARGETS:
        raise ValueError("Invalid task-owned worker identity")
    return f"{job_id}.{phase}.{target}"


def build_request(*, job_dir, artifacts, phase, target, round_number, round_limit,
                  parameters, snapshot_hash, plan_hash):
    job_dir, artifacts = Path(job_dir), Path(artifacts)
    if (not job_dir.is_absolute() or not artifacts.is_absolute() or job_dir.parent.name != "experiments"
            or artifacts.name != "artifacts" or job_dir.parent.parent != artifacts.parent):
        raise ValueError("Broker job/artifact paths must belong to the same run")
    from evaluation_contract import validate_round_limit
    if type(round_number) is not int or round_number not in range(1, validate_round_limit(round_limit) + 1):
        raise ValueError("Round is outside the frozen research campaign")
    if phase == "final_test" and round_number != round_limit:
        raise ValueError("Final testing requires the last requested round")
    request_id = worker_request_id(job_dir.name, phase, target)
    output = artifacts / "tione/outputs" / request_id
    args = ["--phase", phase, "--target", target, "--research-round", str(round_number),
            "--research-round-limit", str(round_limit), "--output", str(output),
            "--artifacts", str(artifacts), "--snapshot-hash", snapshot_hash,
            "--plan-hash", plan_hash, "--deadline", str(deployment_contract()["deadline"])]
    for name in ("posttrain_lr", "temperature", "posttrain_weight_decay", "warmup_epochs", "gradient_clip"):
        args.extend(["--" + name.replace("_", "-"), str(parameters[name])])
    request = {"schema_version": "1.0", "request_id": request_id, "job_dir": str(job_dir),
               "script": "remote_worker.py", "args": args, "gpus": 6,
               "timeout_seconds": MAX_WORKER_SECONDS}
    validate_request(request, artifacts=artifacts)
    return request


def validate_request(request, *, artifacts):
    if set(request) != REQUEST_FIELDS or request["schema_version"] != "1.0":
        raise ValueError("Unknown broker request fields")
    if not ID_PATTERN.fullmatch(request["request_id"]):
        raise ValueError("Unsafe broker request identity")
    if request["script"] != "remote_worker.py" or not isinstance(request["args"], list):
        raise ValueError("Entrypoint is not the reviewed relative worker")
    if type(request["gpus"]) is not int or request["gpus"] != 6:
        raise ValueError("Worker GPU bound failed")
    if type(request["timeout_seconds"]) is not int or not 0 < request["timeout_seconds"] <= MAX_WORKER_SECONDS:
        raise ValueError("Worker timeout bound failed")
    expected = str(Path(artifacts) / "tione/outputs" / request["request_id"])
    if request["args"][request["args"].index("--output") + 1] != expected:
        raise ValueError("Output is not the broker-owned request output root")


def publish_request(request, artifacts):
    validate_request(request, artifacts=artifacts)
    path = Path(artifacts) / "tione/requests" / (request["request_id"] + ".json")
    if path.exists():
        if read_json(path) != request:
            raise ValueError("Existing broker request differs; no new identity retry")
        return path
    atomic_json(path, request)
    return path


def check_receipt(receipt, request, expected_snapshot):
    if receipt.get("status") in {"REJECTED", "SUBMISSION_UNRESOLVED"}:
        raise RuntimeError(f"Permanent or uncertain broker submission: {receipt['status']}; do not replace request")
    if receipt.get("status") in {"FAILED", "STOPPED"}:
        raise RuntimeError("Owned cloud worker failed; preserve output, no automatic resubmission")
    if receipt.get("snapshot_hash") != expected_snapshot or receipt.get("gpus") != request["gpus"]:
        raise ValueError("Broker mirror refers to a different source/GPU allocation")
    if receipt.get("status") in {"SUCCEED", "SUCCESS", "COMPLETED"}:
        if receipt.get("remote_result", {}).get("exit_code") != 0:
            raise RuntimeError("Cloud success without guarded exit zero")
        return True
    return False
