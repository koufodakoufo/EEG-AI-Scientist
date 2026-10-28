"""Compute backends behind one interface: submit / status / stop.

Every job has a ledger file runs/<run>/jobs/<job_id>.json written *before*
the backend is called, so a crash between submit and record never causes a
silent duplicate: TiONE submission first looks the exact task name up.
"""
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import time

from .common import append_jsonl, now, read_json, write_json

TERMINAL = {"succeeded", "failed", "stopped"}
TIONE_HELPER = Path("/mnt/cfs-omni/wzf/iclr2027/experiments/3stage/scripts/tione/submit_full_npd_70gpu.py")
RECORD_JOB = Path("/mnt/cfs-omni/wzf/.volcengine/record_job.py")
TIONE_STATES = {"SUCCEED": "succeeded", "SUCCESS": "succeeded", "COMPLETED": "succeeded",
                "FAILED": "failed", "STOPPED": "stopped", "CANCELLED": "stopped", "CANCELED": "stopped"}


def ledger(run, job_id):
    return run / "jobs" / f"{job_id}.json"


class LocalBackend:
    name = "local"

    def submit(self, run, job_id, cwd, command, log, gpus=0, **_):
        exit_file = run / "jobs" / f"{job_id}.exit"
        wrapped = f"cd {shlex.quote(str(cwd))} && ({command}); echo $? > {shlex.quote(str(exit_file))}"
        with open(log, "ab") as handle:
            process = subprocess.Popen(["bash", "-c", wrapped], stdin=subprocess.DEVNULL, stdout=handle,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        return {"pid": process.pid, "exit_file": str(exit_file)}

    def status(self, record):
        exit_file = Path(record["backend_info"]["exit_file"])
        if exit_file.exists():
            code = exit_file.read_text().strip()
            return ("succeeded" if code == "0" else "failed"), {"exit_code": code}
        try:
            os.kill(record["backend_info"]["pid"], 0)
            return "running", {}
        except ProcessLookupError:
            return "failed", {"reason": "process exited without an exit code"}
        except PermissionError:
            return "running", {}

    def stop(self, record):
        try:
            os.killpg(record["backend_info"]["pid"], 15)
        except ProcessLookupError:
            pass


class TioneBackend:
    """Tencent TiONE via the workspace's existing trusted helper (STS from the notebook)."""
    name = "tione"

    def __init__(self, compute, client_factory=None):
        self.compute = compute
        self._factory = client_factory

    def helper(self):
        spec = importlib.util.spec_from_file_location("_eegfm_tione_helper", TIONE_HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def client(self):
        if self._factory:
            return self._factory()
        h = self.helper()
        return h, h._new_client()

    def submit(self, run, job_id, cwd, command, log, gpus=1, **_):
        h, client = self.client()
        existing = h._find_exact_task(client, job_id)
        if existing is not None:  # resubmission after a crash: adopt, never duplicate
            return {"task_id": str(existing.Id), "adopted": True}
        from tikit.models import FrameworkInfo, ResourceConfigInfo, TrainingDataConfig

        c = self.compute
        framework = FrameworkInfo.new_custom(training_mode="DDP", image_type="TCR",
                                             image_url=c.get("image_url", h.IMAGE_URL),
                                             registry_region=h.TCR_REGISTRY_REGION,
                                             registry_id=h.TCR_REGISTRY_ID)
        resource = ResourceConfigInfo.new_prepaid(
            gpu_type=c.get("gpu_type", h.GPU_TYPE), cpu=c.get("cpu_per_gpu", 4) * gpus,
            memory=c.get("memory_gb_per_gpu", 112) * gpus, gpu=gpus, instance_num=1)
        mounts = [TrainingDataConfig.new_mount_cfs(h.CFS_ID, "/", "/mnt/cfs-omni"),
                  *[TrainingDataConfig.new_mount_cosfs(a, b) for a, b in h.COSFS_MOUNTS],
                  *[TrainingDataConfig.new_mount_cosfs(a, b) for a, b in c.get("extra_cosfs_mounts", [])]]
        start = f"cd {shlex.quote(str(cwd))} && ({command}) > {shlex.quote(str(log))} 2>&1"
        result = client.create_training_task(
            name=job_id, framework=framework, worker_resource=resource, input_data_config=mounts,
            worker_start_cmd=start, tags=[], tuning_parameters_dict={},
            resource_group_id=c.get("resource_group_id", h.RESOURCE_GROUP_ID),
            remark=f"eegfm {run.name}", vpc_id=h.VPC_ID, sub_net_id=h.SUBNET_ID,
            enable_rdma=False, restart_limit=0)
        task_id = str(result.Id)
        self.register(run, job_id, task_id, cwd, gpus)
        return {"task_id": task_id, "adopted": False}

    def register(self, run, job_id, task_id, cwd, gpus):
        """Workspace rule: record every new TiONE task with record_job.py."""
        meta = read_json(run / "run.json", {})
        argv = ["python3", str(RECORD_JOB), "create", "--task-id", task_id, "--project", "eeg-fm-research",
                "--job-name", job_id, "--output-path", str(cwd), "--receipt-path", str(ledger(run, job_id)),
                "--config-path", str(run / "run.json"), "--code-ref", meta.get("task_id", "unknown"),
                "--gpu-count", str(gpus)]
        if self.compute.get("gpu_type"):
            argv += ["--gpu-type", self.compute["gpu_type"]]
        if RECORD_JOB.exists():
            subprocess.run(argv, check=False, capture_output=True)

    def status(self, record):
        h, client = self.client()
        task = client.describe_training_task(record["backend_info"]["task_id"]).TrainingTaskDetail
        raw = str(task.Status).upper()
        status = TIONE_STATES.get(raw, "running")
        if RECORD_JOB.exists() and status != record.get("status"):
            mapped = {"running": "running", "succeeded": "succeeded", "failed": "failed", "stopped": "stopped"}[status]
            subprocess.run(["python3", str(RECORD_JOB), "status", "--task-id", record["backend_info"]["task_id"],
                            "--state", mapped], check=False, capture_output=True)
        return status, {"tione_status": raw}

    def stop(self, record):
        h, client = self.client()
        client.stop_training_task(record["backend_info"]["task_id"])


def backend(compute, **kwargs):
    if compute["backend"] == "local":
        return LocalBackend()
    return TioneBackend(compute, **kwargs)


def submit(run, compute, attempt_id, phase, cwd, command, gpus=None, **kwargs):
    earlier = [r for r in (read_json(p) for p in (run / "jobs").glob("*.json"))
               if r and r.get("attempt") == attempt_id and r.get("phase") == phase]
    job_id = f"{run.name}-{attempt_id}-{phase}-{len(earlier) + 1}".replace("_", "-").lower()
    gpus = gpus if gpus is not None else compute.get("gpus_per_job", 0 if compute["backend"] == "local" else 1)
    log = run / "jobs" / f"{job_id}.log"
    record = {"job_id": job_id, "attempt": attempt_id, "phase": phase, "backend": compute["backend"],
              "cwd": str(cwd), "command": command, "gpus": gpus, "log": str(log), "status": "submitting",
              "submitted_at": now(), "backend_info": None}
    write_json(ledger(run, job_id), record)  # intent first
    info = backend(compute, **kwargs).submit(run, job_id, cwd, command, log, gpus=gpus)
    record.update(status="running", backend_info=info, started_at=time.time())
    write_json(ledger(run, job_id), record)
    append_jsonl(run / "events.jsonl", {"event": "job_submitted", "job": job_id, "attempt": attempt_id,
                                         "phase": phase, "backend": compute["backend"]})
    return record


def refresh(run, compute, job_id, **kwargs):
    record = read_json(ledger(run, job_id))
    if not record:
        raise SystemExit(f"Unknown job {job_id}")
    if record["status"] in TERMINAL:
        return record
    if record["status"] == "submitting":
        return record  # an interrupted submit; `eegfm job submit` again adopts it
    status, extra = backend(compute, **kwargs).status(record)
    if status != record["status"]:
        record.update(status=status, **extra)
        if status in TERMINAL:
            record["finished_at"] = time.time()
            record["gpu_hours"] = record["gpus"] * (record["finished_at"] - record["started_at"]) / 3600
        write_json(ledger(run, job_id), record)
        append_jsonl(run / "events.jsonl", {"event": "job_status", "job": job_id, "status": status})
    return record
