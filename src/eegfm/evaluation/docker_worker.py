"""Narrow rootless Docker execution; cgroup flags are never treated as enforcement.

This file is also installed in the immutable image as the trusted PID1. Candidates
are single processes with bounded threads. New processes and signalling other
processes are denied by an inherited seccomp filter; BLAS/Torch threads work.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

MEMORY_BYTES = 12 * 1024**3
OUTPUT_BYTES = 2 * 1024**3
SUPERVISOR = "/opt/eegfm/docker_worker.py"
LABEL = "eegfm.worker.owner"


@dataclass(frozen=True)
class DockerBackend:
    client: Path
    image: str
    host: str
    python: Path

    def __post_init__(self) -> None:
        if not self.client.is_absolute() or not self.python.is_absolute():
            raise ValueError("Docker client and image Python require absolute paths")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.image):
            raise ValueError("Docker requires an immutable image ID")
        if not re.fullmatch(r"unix:///[A-Za-z0-9_./-]+", self.host) or "/../" in self.host:
            raise ValueError("Only an explicit local Docker daemon is allowed")

    def command(self, *arguments: str) -> list[str]:
        return [str(self.client), "--host", self.host, *arguments]

    def inspect_image(self) -> dict[str, Any]:
        raw = subprocess.check_output(self.command("image", "inspect", self.image), timeout=20)
        value = json.loads(raw)[0]
        if value["Id"] != self.image:
            raise ValueError("Image identity mismatch")
        source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if value.get('Config', {}).get('Labels', {}).get('eegfm.worker.supervisor-sha256') != source_hash:
            raise ValueError('Image does not bind this trusted supervisor')
        if value.get('Architecture') != 'amd64':
            raise ValueError('Validated worker requires amd64 image')
        # A Docker image is a frozen runtime; never mount host environments.
        return {"image": value["Id"], "architecture": value["Architecture"],
                "supervisor_sha256": source_hash, "daemon": self.host, "python": str(self.python)}

    def create_command(self, job: Path, fingerprint: str, split: str, timeout: int) -> list[str]:
        if not job.is_absolute() or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("Invalid Docker job identity")
        if split not in {"validation", "test"} or type(timeout) is not int or not 0 < timeout <= 1800:
            raise ValueError("Invalid Docker split/deadline")
        if any(c in str(job) for c in (",", "\n", "\r")):
            raise ValueError("Unsupported mount path")
        command = self.command("create", "--pull=never", "--name", "eegfm-" + fingerprint[:32],
            "--label", LABEL + "=" + fingerprint, "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=67108864", "--workdir", "/candidate",
            "--entrypoint", str(self.python))
        for source, target, readonly in (("candidate", "/candidate", True), ("public", "/public", True),
                                        ("inputs", "/inputs", True),
                                        ("out", "/out", False)):
            command += ["--mount", f"type=bind,source={job / source},target={target}" + (",readonly" if readonly else "")]
        environment = {"HOME": "/tmp", "TMPDIR": "/tmp", "XDG_CACHE_HOME": "/tmp/cache",
            "HF_HOME": "/tmp/huggingface", "TORCH_HOME": "/tmp/torch", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1", "CUDA_VISIBLE_DEVICES": "", "LANG": "C.UTF-8",
            "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "MKL_NUM_THREADS": "4",
            "NUMEXPR_NUM_THREADS": "4", "VECLIB_MAXIMUM_THREADS": "4"}
        for key, value in environment.items():
            command += ["--env", key + "=" + value]
        return command + [self.image, "-B", SUPERVISOR, "--supervise", str(timeout), split]

    def remove_owned(self, container: str, fingerprint: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", container):
            raise ValueError("Invalid container ID")
        try:
            raw = subprocess.check_output(self.command("inspect", container), timeout=20, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as error:
            if b'No such' in (error.stderr or b''):
                return
            raise
        item = json.loads(raw)[0]
        if item["Id"] != container or item["Config"]["Labels"].get(LABEL) != fingerprint:
            raise ValueError("Refuse cleanup of unowned container")
        subprocess.run(self.command("rm", "--force", container), check=True, timeout=20, capture_output=True)
        check = subprocess.run(self.command("inspect", container), capture_output=True, timeout=20)
        if check.returncode == 0 or b"No such" not in check.stderr:
            raise RuntimeError("Container removal not confirmed")

    def execute(self, job: Path, fingerprint: str, split: str, timeout: int, free_floor: int) -> dict[str, Any]:
        from eegfm.agent.budget import run_bounded, write_atomic
        container = None
        status: dict[str, Any] = {}
        try:
            container = subprocess.check_output(self.create_command(job, fingerprint, split, timeout), timeout=30).decode().strip()
            if not re.fullmatch(r"[0-9a-f]{64}", container):
                raise RuntimeError("Docker returned invalid container identity")
            write_atomic(job / "container.json", {"id": container, "owner": fingerprint, "image": self.image})
            status = run_bounded(self.command("start", "--attach", container), cwd=job, output_dir=job / "execution",
                timeout_seconds=timeout + 15, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                threads=4, memory_limit_bytes=MEMORY_BYTES, storage_scope=job,
                storage_limit_bytes=OUTPUT_BYTES, stdout_limit_bytes=16 * 1024**2, minimum_free_bytes=free_floor)
            inspected = json.loads(subprocess.check_output(self.command("inspect", container), timeout=20))[0]
            if inspected["State"]["Running"]:
                status["status"] = "timed_out" if status["status"] == "timed_out" else "failed"
            elif inspected["State"]["ExitCode"] == 124:
                status["status"] = "timed_out"
            elif inspected["State"]["ExitCode"] != 0:
                status["status"] = "failed"
            status["container_exit_code"] = inspected["State"]["ExitCode"]
            status["resource_enforcement"] = {"cgroups": False, "candidate_processes": 1,
                "cpu_affinity_count": 4, "address_space_bytes": MEMORY_BYTES,
                "max_threads_per_uid": 128, "output_storage": "sampled", "tmpfs_bytes": 64 * 1024**2}
            return status
        finally:
            if container is not None:
                self.remove_owned(container, fingerprint)
                status["container_cleanup"] = "verified_removed"
            if status:
                write_atomic(job / "execution" / "status.json", status)


def _candidate_limits(timeout: int) -> None:
    """Apply immutable limits before any submitted code is loaded (x86_64 only)."""
    import ctypes
    import errno
    import resource
    if os.uname().machine != "x86_64":
        raise RuntimeError("Validated seccomp policy requires x86_64")
    available = sorted(os.sched_getaffinity(0))
    if len(available) < 4:
        raise RuntimeError("Four allocated logical CPUs required")
    os.sched_setaffinity(0, available[:4])
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (timeout * 4, timeout * 4))
    resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    libc = ctypes.CDLL(None, use_errno=True)
    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]
    class Program(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ushort), ("filters", ctypes.POINTER(Filter))]
    # Check architecture, reject x32 syscalls, deny clone3 so libc falls back
    # to inspectable clone flags, and permit clone only for CLONE_THREAD.
    instructions = [(0x20,0,0,4),(0x15,1,0,0xC000003E),(0x06,0,0,0x80000000),
                    (0x20,0,0,0),(0x35,0,1,0x40000000),(0x06,0,0,0x80000000),
                    (0x15,0,1,435),(0x06,0,0,0x00050000|errno.ENOSYS),
                    (0x15,0,4,56),(0x20,0,0,16),(0x45,1,0,0x10000),
                    (0x06,0,0,0x00050000|errno.EPERM),(0x06,0,0,0x7FFF0000)]
    # No sockets (including non-IP families), fork/vfork, signal variants,
    # ptrace/process-vm, namespace/affinity changes or priority escalation.
    # Limits cannot be raised without capabilities.
    for syscall in (41,53,57,58,62,129,200,234,297,424,101,310,311,272,308,203,140,141,142,144,145):
        instructions += [(0x15,0,1,syscall),(0x06,0,0,0x00050000|errno.EPERM)]
    instructions += [(0x06,0,0,0x7FFF0000)]
    filters = (Filter * len(instructions))(*(Filter(*item) for item in instructions))
    program = Program(len(filters), filters)
    if libc.prctl(38,1,0,0,0) != 0 or libc.prctl(22,2,ctypes.byref(program),0,0) != 0:
        raise OSError(ctypes.get_errno(), "Cannot install seccomp boundary")


def supervise(timeout: int, split: str) -> int:
    """PID1 survives candidate signals and kills the namespace at its deadline."""
    import ctypes
    os.umask(0o022)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(4,0,0,0,0) != 0:
        raise RuntimeError("Cannot protect supervisor from ptrace/proc access")
    child = os.fork()
    if child == 0:
        try:
            _candidate_limits(timeout)
            os.execv(sys.executable, [sys.executable, "-B", "/candidate/main.py", "--split", split,
                "--input", "/inputs/evaluation.npz", "--train", "/inputs/train.npz", "--public", "/public", "--output", "/out"])
        except BaseException:
            os._exit(125)
    deadline = time.monotonic() + timeout
    while True:
        ended, status = os.waitpid(child, os.WNOHANG)
        if ended:
            return os.waitstatus_to_exitcode(status) if os.WIFEXITED(status) else 128 + os.WTERMSIG(status)
        if time.monotonic() >= deadline:
            os.kill(child, 9)
            os.waitpid(child, 0)
            return 124
        time.sleep(0.05)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--supervise" or os.getpid() != 1:
        raise SystemExit("Trusted container PID1 invocation required")
    seconds = int(sys.argv[2])
    if not 0 < seconds <= 1800 or sys.argv[3] not in {"validation", "test"}:
        raise SystemExit("Invalid worker invocation")
    raise SystemExit(supervise(seconds, sys.argv[3]))
