"""Public-only fitting artifacts, using the existing isolated worker/job store.

Submitted Python is copied as text and runs only in the scientific sandbox.
The host validates bounded numeric NPZs; it never imports submitted modules.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile
from typing import Any

import numpy as np

from eegfm.agent.budget import write_atomic
from eegfm.agent.controller import EvaluationSpec
from eegfm.evaluation.bundle import canonical_bytes, digest_file, safe_relative, verify_public_bundle
from eegfm.evaluation.worker import FileBinding, candidate_digest, require_public_fit_window, _path, _id

MODE = "public-finite-npz-v1"
MAX_COMPRESSED = 1024**2
MAX_EXPANDED = 8 * 1024**2
FIT_ENTRY = '''from pathlib import Path
import runpy, sys
source = Path(__file__).parent / "authored"
sys.path.insert(0, str(source))
sys.argv = [str(source / "fit.py"), "--public", "/public", "--output", "/out"]
runpy.run_path(str(source / "fit.py"), run_name="__main__")
'''


def validate_parameters(data: bytes) -> None:
    if not data or len(data) > MAX_COMPRESSED:
        raise ValueError("Public parameter byte cap exceeded")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= 128 or sum(item.file_size for item in entries) > MAX_EXPANDED:
                raise ValueError("Public parameter expanded cap exceeded")
            if len({item.filename for item in entries}) != len(entries):
                raise ValueError("Duplicate numeric parameter")
            for entry in entries:
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}\.npy", entry.filename) is None:
                    raise ValueError("Invalid parameter name")
                with archive.open(entry) as stream:
                    version = np.lib.format.read_magic(stream)
                    if version == (1, 0):
                        shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
                    elif version == (2, 0):
                        shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
                    else:
                        raise ValueError("Unsupported numeric array format")
                    count = 1
                    for size in shape:
                        count *= size
                    if dtype.kind not in "biuf" or len(shape) > 4 or count > 1000000:
                        raise ValueError("Only bounded real numeric arrays are public artifacts")
        with np.load(io.BytesIO(data), allow_pickle=False) as arrays:
            if any(not np.isfinite(arrays[name]).all() for name in arrays.files):
                raise ValueError("Nonfinite numeric parameters")
    except (OSError, EOFError, zipfile.BadZipFile, TypeError) as exc:
        raise ValueError("Invalid numeric parameter archive") from exc


def encode_parameters(path: Path) -> dict[str, Any]:
    data = _path(path).read_bytes()
    validate_parameters(data)
    return {"name": "parameters.npz", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "data_base64": base64.b64encode(data).decode("ascii")}


def decode_parameters(record: dict[str, Any]) -> bytes:
    if (not isinstance(record, dict) or set(record) != {"name", "bytes", "sha256", "data_base64"}
            or record["name"] != "parameters.npz" or type(record["bytes"]) is not int
            or not 0 < record["bytes"] <= MAX_COMPRESSED or not isinstance(record["data_base64"], str)
            or len(record["data_base64"]) > 4 * ((MAX_COMPRESSED + 2) // 3)):
        raise ValueError("Invalid typed public artifact")
    try:
        data = base64.b64decode(record["data_base64"], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid artifact encoding") from exc
    if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError("Public artifact binding mismatch")
    validate_parameters(data)
    return data


class PublicFitAggregator:
    """No truth/scoring inputs: only frozen public train/validation resources."""
    released_metrics = frozenset({"public_fit_artifacts"})

    def __init__(self, public_root: Path, public_manifest_sha256: str) -> None:
        self.public = _path(public_root, directory=True)
        verify_public_bundle(self.public)
        self.public_hash = public_manifest_sha256
        if digest_file(self.public / "PUBLIC_MANIFEST.json") != public_manifest_sha256:
            raise ValueError("Public fit manifest mismatch")
        self.bindings = tuple(FileBinding(self.public / name, digest_file(self.public / name))
                              for name in ("PUBLIC_MANIFEST.json", "train.npz", "validation.npz"))
        self.policy_sha256 = hashlib.sha256(canonical_bytes({"mode": MODE, "public": self.public_hash,
            "compressed": MAX_COMPRESSED, "expanded": MAX_EXPANDED})).hexdigest()

    def __call__(self, output: Path, spec: EvaluationSpec) -> dict[str, Any]:
        if spec.split != "validation" or spec.public_manifest_sha256 != self.public_hash:
            raise ValueError("Public fitting cannot evaluate a test split")
        verify_public_bundle(self.public)
        for binding in self.bindings:
            binding.verify()
        if {path.name for path in output.iterdir()} != {"parameters.npz"}:
            raise ValueError("Public fitting emits only parameters.npz")
        encode_parameters(output / "parameters.npz")
        return {"metrics": {"public_fit_artifacts": 1}, "artifacts": [
            {"path": "parameters.npz", "sha256": digest_file(output / "parameters.npz")} ]}


def load_public_worker(config: dict[str, Any]):
    """Trusted fixed SSH config admission; no truth/test/reference fields exist."""
    from eegfm.evaluation.worker import SandboxedWorkerEvaluator, SplitInputs, RuntimeConfig
    required = {"schema_version", "episode_id", "run_id", "staging_root", "private_root", "public_root",
                "public_manifest_sha256", "split_manifest", "runtime"}
    if not required <= set(config) or set(config) - required - {"timeout_seconds", "minimum_free_bytes", "episode_deadline_epoch"}:
        raise ValueError("Unexpected public-fit configuration fields")
    if config["schema_version"] != "ssh_public_fit_worker_v1":
        raise ValueError("Unknown public-fit configuration")
    for name in ("episode_id", "run_id"):
        _id(config[name])
    for name in ("staging_root", "private_root", "public_root"):
        if not Path(config[name]).is_absolute():
            raise ValueError("Absolute public-fit roots required")
    public = Path(config["public_root"])
    aggregate = PublicFitAggregator(public, config["public_manifest_sha256"])
    split = config["split_manifest"]
    if set(split) != {"path", "sha256"} or not Path(split["path"]).is_absolute():
        raise ValueError("Public split binding required")
    binding = FileBinding(Path(split["path"]), split["sha256"])
    binding.verify()
    runtime = config["runtime"]
    if set(runtime) != {"python", "docker", "image", "host"}:
        raise ValueError("Fixed Docker runtime required")
    return SandboxedWorkerEvaluator(private_root=Path(config["private_root"]), public_root=public,
        public_manifest_sha256=config["public_manifest_sha256"], split_manifest_path=binding.path,
        split_manifest_sha256=binding.sha256,
        inputs_by_split={"validation": SplitInputs(aggregate.bindings[1], aggregate.bindings[2])},
        runtime=RuntimeConfig(None, Path(runtime["python"]), backend="docker", docker=Path(runtime["docker"]),
                              docker_image=runtime["image"], docker_host=runtime["host"]),
        aggregate=aggregate, released_metrics=aggregate.released_metrics, aggregate_bindings=aggregate.bindings,
        aggregate_policy_sha256=aggregate.policy_sha256, allowed_splits=frozenset({"validation"}),
        public_artifact_mode=MODE, timeout_seconds=config.get("timeout_seconds", 120),
        public_fit_deadline_epoch=config.get("episode_deadline_epoch"),
        minimum_free_bytes=config.get("minimum_free_bytes", 20 * 1024**3))


def _case_path(case: Path, relative: str) -> Path:
    relative_path = safe_relative(relative)
    if any(part.startswith(".") for part in relative_path.parts):
        raise ValueError("Hidden workbench paths forbidden")
    path = case / "output"
    for part in relative_path.parts:
        path /= part
        if path.is_symlink():
            raise ValueError("Workbench links forbidden")
    path.resolve().relative_to((case / "output").resolve())
    return path


def source_manifest(root: Path) -> list[dict[str, Any]]:
    _path(root, directory=True)
    result, size = [], 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Authored source links forbidden")
        if path.is_dir() or path.name == "parameters.npz":
            continue
        _path(path)
        relative = path.relative_to(root).as_posix()
        if (any(part.startswith(".") for part in path.relative_to(root).parts)
                or path.suffix not in {".py", ".json", ".md", ".txt", ".yaml"}):
            raise ValueError("Public fitting receives text sources only")
        path.read_text(encoding="utf-8")
        size += path.stat().st_size
        if size > 1024**2 or len(result) >= 256:
            raise ValueError("Authored source cap exceeded")
        result.append({"path": relative, "sha256": digest_file(path)})
    if not any(row["path"] == "fit.py" for row in result):
        raise ValueError("Authored fit.py required")
    return result


class PublicWorkbench:
    """Episode-bound promotion around the existing worker's durable submit/poll."""
    def __init__(self, *, evaluator: Any, private_root: Path, case_root: Path,
                 episode_id: str, run_id: str, public_manifest_sha256: str,
                 split_manifest_sha256: str) -> None:
        self.worker, self.private, self.case = evaluator, Path(private_root).absolute(), Path(case_root).resolve()
        if self.private == self.case or self.private in self.case.parents or self.case in self.private.parents:
            raise ValueError("Workbench evidence must be outside the case")
        remote_identity = evaluator.identity if hasattr(evaluator, "identity") else None
        identity = remote_identity["worker"] if remote_identity is not None else evaluator._enrollment()
        if (identity.get("public_artifact_mode") != MODE or identity.get("allowed_splits") != ["validation"]
                or identity.get("public_artifact_manifest_sha256") != public_manifest_sha256):
            raise ValueError("Only enrolled public-only workers can export fitted parameters")
        self.episode, self.run = _id(episode_id), _id(run_id)
        self.public_hash, self.split_hash = public_manifest_sha256, split_manifest_sha256
        if remote_identity is not None:
            for key, expected in (("episode_id", self.episode), ("run_id", self.run),
                                  ("public_manifest_sha256", self.public_hash), ("split_manifest_sha256", self.split_hash)):
                if key in remote_identity and remote_identity[key] != expected:
                    raise ValueError('Remote public workbench identity mismatch')
        else:
            if getattr(evaluator, 'public_hash', self.public_hash) != self.public_hash or getattr(evaluator, 'split_hash', self.split_hash) != self.split_hash:
                raise ValueError('Local public workbench binding mismatch')
        self.worker_identity = json.loads(canonical_bytes(remote_identity if remote_identity is not None else identity))
        self.private.mkdir(parents=True, exist_ok=True)
        _path(self.private, directory=True)
        self.identity = {"case_root": str(self.case), "episode_id": self.episode, "run_id": self.run,
                         "public_manifest_sha256": self.public_hash, "split_manifest_sha256": self.split_hash,
                         "worker_enrollment_sha256": hashlib.sha256(canonical_bytes(self.worker_identity)).hexdigest()}
        enrollment = self.private / 'ENROLLMENT.json'
        if enrollment.exists():
            if json.loads(_path(enrollment).read_text()) != self.identity:
                raise ValueError('Public workbench case/worker enrollment changed')
        else:
            with enrollment.open('xb') as stream:
                stream.write(canonical_bytes(self.identity))

    def require_submit_time(self) -> None:
        deadline = getattr(self.worker, 'deadline_epoch', None)
        remote_deadline = self.worker_identity.get('episode_deadline_epoch')
        if remote_deadline is not None:
            deadline = remote_deadline if deadline is None else min(deadline, remote_deadline)
        if deadline is not None:
            require_public_fit_window(deadline, self.worker.operation_timeout_seconds)
        elif hasattr(self.worker, 'require_public_fit_time'):
            self.worker.require_public_fit_time()

    def submit(self, job_id: str, candidate_relative: str) -> dict[str, Any]:
        _id(job_id)
        source = _case_path(self.case, candidate_relative)
        manifest = source_manifest(source)
        record_path = self.private / f"{job_id}.json"
        identity = {**self.identity, "job_id": job_id,
                    "target": candidate_relative, "source_manifest": manifest,
                    "public_manifest_sha256": self.public_hash, "split_manifest_sha256": self.split_hash}
        if record_path.exists():
            retained = json.loads(record_path.read_text())
            if retained["identity"] != identity:
                raise ValueError("Public fit ID reused with changed source/case")
            return self.poll(job_id)
        self.require_submit_time()
        staged = self.private / job_id
        staged.mkdir(exist_ok=False)
        (staged / "authored").mkdir()
        for entry in manifest:
            target = staged / "authored" / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / entry["path"], target)
            if digest_file(target) != entry["sha256"]:
                raise ValueError("Authored source changed during staging")
        (staged / "main.py").write_text(FIT_ENTRY, encoding="utf-8")
        digest = candidate_digest(staged)
        # The existing evaluator independently reserves before submission. This
        # immutable record ensures this wrapper also polls rather than resubmits.
        record = {"identity": identity, "candidate_digest": digest}
        with record_path.open("xb") as stream:
            stream.write(canonical_bytes(record))
        spec = EvaluationSpec(job_id, self.episode, self.run, "public-fit", "validation", staged,
                              digest, self.split_hash, self.public_hash)
        result = self.worker.submit(spec)
        return self._accept(record, result)

    def poll(self, job_id: str) -> dict[str, Any]:
        record = json.loads(_path(self.private / f"{_id(job_id)}.json").read_text())
        try:
            result = self.worker.poll(job_id)
        except ValueError as exc:
            if str(exc) not in {'Unknown local SSH worker job', 'Unknown worker job'}:
                raise
            result = {'job_id': job_id, 'candidate_digest': record['candidate_digest'],
                      'split': 'validation', 'status': 'waiting'}
        return self._accept(record, result)

    def _accept(self, record: dict, result: dict) -> dict[str, Any]:
        expected = record["identity"]
        current_identity = self.worker.identity if hasattr(self.worker, 'identity') else self.worker._enrollment()
        if current_identity != self.worker_identity:
            raise ValueError('Public workbench worker enrollment changed')
        if any(expected.get(key) != value for key, value in self.identity.items()):
            raise ValueError('Public fit journal belongs to another case or worker')
        if (result.get("job_id") != expected["job_id"] or result.get("candidate_digest") != record["candidate_digest"]
                or result.get("split") != "validation" or result.get("status") not in {"waiting", "failed", "succeeded"}):
            raise ValueError("Public fit result belongs to another source/job/case")
        public = {key: result[key] for key in ("job_id", "status")}
        if result["status"] != "succeeded":
            return public
        artifacts = result.get("public_artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != 1:
            raise ValueError("Typed fitted parameter artifact missing")
        data = decode_parameters(artifacts[0])
        target = _case_path(self.case, expected["target"])
        if source_manifest(target) != expected["source_manifest"]:
            raise ValueError("Authored source changed before parameter promotion")
        destination = target / "parameters.npz"
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError("Frozen numeric artifact changed; use a fresh candidate")
        if not destination.exists():
            with destination.open("xb") as stream:
                stream.write(data)
        public["artifact"] = {key: artifacts[0][key] for key in ("name", "sha256", "bytes")}
        return public
