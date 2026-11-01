"""Fixed isolated candidate execution, private evidence, trusted result release.

Only the trusted bridge may call this evaluator. Its test reservation MUST be
committed before submit. No candidate module is imported into this process.
Runtime roots and aggregator are trusted enrollment configuration, never Actor
inputs. The aggregator validates true rows/labels privately and must not execute
submitted code. A passing local canary is not certification of a different server.
"""
from __future__ import annotations

import ast
from contextlib import closing
from dataclasses import dataclass
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import struct
import sys
from typing import Any, Callable, TYPE_CHECKING
import zipfile

from eegfm.agent.budget import run_bounded
from eegfm.agent.budget import write_atomic
from eegfm.evaluation.bundle import canonical_bytes
from eegfm.evaluation.bundle import digest_file
from eegfm.evaluation.bundle import safe_relative
from eegfm.evaluation.bundle import verify_public_bundle

# Match only the trusted validator's complete fixed messages. No exception text
# or candidate/private value is ever returned to the Actor.
_OUTPUT_DIAGNOSTICS = {
    "Control strength must match each individual window": "intervention_strength_mismatch",
    "Recorded shifts do not lie in the recorded direction spans": "direction_span_mismatch",
    "Controls must match actual numerical rank": "control_rank_mismatch",
    "Controls must have distinct subspaces": "control_subspace_mismatch",
    "Nonfinite numeric evidence": "nonfinite_evidence",
    "Nonfinite derived intervention evidence": "nonfinite_evidence",
    "R2 arithmetic overflow in candidate evidence": "nonfinite_evidence",
}
_CANDIDATE_OUTPUT_ERRORS = frozenset({
    "Unexpected prediction array schema", "Prediction archive too large",
    "Unsafe dtype header", "Invalid array shape/dtype", "Array byte length mismatch",
    "Prediction rows do not match trusted split", "Nonfinite predictions",
    "Scientific sample IDs must match exact trusted row order",
    "Negative target control must be a permutation of training rows",
    "Negative control must derange complete participant blocks",
    "Negative control retained within-participant row alignment",
    "Negative control does not bijectively map participant blocks",
    "An active target column is unchanged by the negative control",
    "Use analysis.npz for the fixed two-layer feature schema",
    "Frozen validation selection requires actual validation analysis",
    "Interventions require Q1 evidence",
    "Frozen validation predictions differ from actual validation evidence",
    "Intervention rows or validation-selected feature/layer mismatch",
    "Unused direction columns must be zero padding", "A positive actual rank is required",
    "Intervention has zero strength in every window",
})
_REQUIRED_OUTPUT_FILES = frozenset({"results.npz", "analysis.npz", "interventions.npz"})


def _output_failure_diagnostic(error: Exception, output: Path) -> str:
    """Only recognized candidate faults may relax the completion gate."""
    if type(error) is ValueError:
        message = str(error)
        if message in _OUTPUT_DIAGNOSTICS:
            return _OUTPUT_DIAGNOSTICS[message]
        if message in _CANDIDATE_OUTPUT_ERRORS:
            return "candidate_outputs_rejected"
    elif type(error) is FileNotFoundError and error.filename is not None:
        missing = Path(error.filename)
        if missing.is_absolute() and missing in {output / name for name in _REQUIRED_OUTPUT_FILES}:
            return "candidate_outputs_rejected"
    return "evaluation_integrity_failed"

if TYPE_CHECKING:
    from eegfm.agent.controller import EvaluationSpec


def _sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Invalid SHA256")
    return value


def _id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", value):
        raise ValueError("Invalid identity")
    return value


def _path(path: Path, *, directory: bool = False) -> Path:
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Data/artifact paths cannot contain links")
    info = path.stat()
    if directory:
        if not stat.S_ISDIR(info.st_mode): raise ValueError("Expected directory")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Expected single-link regular file")
    return path


def _tree(root: Path, *, maximum_bytes: int = 64 * 1024**2, maximum_files: int = 256,
          hidden: bool = False) -> list[dict[str, Any]]:
    _path(root, directory=True)
    entries: list[dict[str, Any]] = []
    total = 0
    for file in sorted(root.rglob("*")):
        relative = file.relative_to(root)
        if file.is_symlink() or (not hidden and any(part.startswith(".") for part in relative.parts)):
            raise ValueError("Unsafe tree entry")
        if file.is_dir(): continue
        _path(file)
        total += file.stat().st_size
        if total > maximum_bytes or len(entries) >= maximum_files: raise ValueError("Tree size limit")
        entries.append({"path": relative.as_posix(), "bytes": file.stat().st_size, "sha256": digest_file(file)})
    return entries


def candidate_digest(root: Path) -> str:
    entries = _tree(root)
    if not entries: raise ValueError("Empty candidate")
    return hashlib.sha256(canonical_bytes(entries)).hexdigest()


@dataclass(frozen=True)
class FileBinding:
    path: Path
    sha256: str

    def verify(self) -> Path:
        path = _path(self.path)
        if digest_file(path) != _sha(self.sha256): raise ValueError("Bound input changed")
        return path


@dataclass(frozen=True)
class SplitInputs:
    train: FileBinding
    evaluation: FileBinding


@dataclass(frozen=True)
class RuntimeConfig:
    bwrap: Path
    python: Path
    environment_roots: tuple[Path, ...] = ()
    manifest: FileBinding | None = None

    def __post_init__(self) -> None:
        forbidden = {"/", "/data", "/mnt", "/mnt/dataset4", "/home", "/root", "/tmp", "/etc", "/proc", "/run", "/var", "/dev"}
        for root in self.environment_roots:
            if not root.is_absolute() or root.as_posix().rstrip("/") in forbidden or root == Path("/"):
                raise ValueError("Runtime must name an explicit environment, not a host root")
        if self.environment_roots and self.manifest is None:
            raise ValueError('Additional scientific runtimes require a frozen dependency manifest')


class SandboxedWorkerEvaluator:
    sandboxed = True

    def __init__(self, *, private_root: Path, public_root: Path, public_manifest_sha256: str,
                 split_manifest_path: Path, split_manifest_sha256: str,
                 inputs_by_split: dict[str, SplitInputs], runtime: RuntimeConfig,
                 aggregate: Callable[[Path, EvaluationSpec], dict[str, Any]],
                 released_metrics: frozenset[str], timeout_seconds: int = 900,
                 minimum_free_bytes: int = 20 * 1024**3,
                 aggregate_bindings: tuple[FileBinding, ...] = (),
                 aggregate_policy_sha256: str | None = None) -> None:
        if sys.platform != "linux": raise RuntimeError("Worker execution requires Linux")
        if set(inputs_by_split) != {"validation", "test"}: raise ValueError("Explicit validation/test bindings required")
        if type(timeout_seconds) is not int or not 0 < timeout_seconds <= 1800: raise ValueError("Invalid timeout")
        if not released_metrics or any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,119}", name) for name in released_metrics):
            raise ValueError("Finite public metric names must be predeclared")
        self.private = Path(private_root).absolute()
        self.public = _path(public_root, directory=True)
        if self.private == self.public or self.private in self.public.parents or self.public in self.private.parents:
            raise ValueError("Private evidence and public files must be disjoint")
        self.private.mkdir(parents=True, exist_ok=True)
        _path(self.private, directory=True)
        self.public_hash = _sha(public_manifest_sha256)
        self.split_path, self.split_hash = Path(split_manifest_path), _sha(split_manifest_sha256)
        self.inputs, self.runtime, self.aggregate = dict(inputs_by_split), runtime, aggregate
        self.released_metrics = frozenset(released_metrics)
        self.timeout, self.free_floor = timeout_seconds, minimum_free_bytes
        self.aggregate_bindings = aggregate_bindings
        callback = aggregate if inspect.isfunction(aggregate) else type(aggregate).__call__
        source_file = inspect.getsourcefile(callback)
        if source_file is None:
            raise ValueError('Aggregator must have inspectable trusted implementation')
        self.aggregate_source_path = Path(source_file)
        self.aggregate_source_sha256 = digest_file(self.aggregate_source_path)
        callback_source = inspect.getsource(callback)
        self.aggregate_policy_sha256 = _sha(aggregate_policy_sha256) if aggregate_policy_sha256 else hashlib.sha256(callback_source.encode()).hexdigest()
        self.runtime_hashes = {"bwrap": digest_file(runtime.bwrap.resolve(strict=True)),
                               "python": digest_file(runtime.python.resolve(strict=True))}
        allowed = [Path("/usr").resolve(), Path("/lib").resolve(), Path("/lib64").resolve()]
        for root in runtime.environment_roots:
            _path(root, directory=True)
            for protected in (self.private, self.public, self.split_path, *(binding.path for pair in self.inputs.values() for binding in (pair.train, pair.evaluation))):
                if root == protected or root in protected.parents or protected in root.parents:
                    raise ValueError("Environment mount overlaps protected material")
            allowed.append(root.resolve())
        binary = runtime.python.resolve(strict=True)
        if not any(binary == root or root in binary.parents for root in allowed):
            raise ValueError("Python is outside explicit runtime mounts")
        self.db_path = self.private / "worker.sqlite3"
        with closing(sqlite3.connect(self.db_path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, spec TEXT NOT NULL, result TEXT, owner_pid INTEGER, owner_start INTEGER)")

    def job_directory(self, job_id: str) -> Path:
        return self.private / _id(job_id)

    def _spec_record(self, spec: EvaluationSpec) -> dict[str, Any]:
        return {"job_id": _id(spec.job_id), "episode_id": _id(spec.episode_id), "run_id": _id(spec.run_id),
                "attempt_id": _id(spec.attempt_id), "split": spec.split,
                "candidate_dir": str(spec.candidate_dir), "candidate_digest": _sha(spec.candidate_digest),
                "public_manifest_sha256": _sha(spec.public_manifest_sha256),
                "split_manifest_sha256": _sha(spec.split_manifest_sha256),
                "enrollment": self._enrollment()}

    def _enrollment(self) -> dict[str,Any]:
        """Frozen trusted configuration is part of identity, including cache hits."""
        def file_identity(binding: FileBinding) -> dict[str,str]:
            path = binding.verify()
            return {'path':str(path),'sha256':binding.sha256}
        if digest_file(self.aggregate_source_path) != self.aggregate_source_sha256:
            raise ValueError('Aggregator source changed after enrollment')
        for name,path in (('python',self.runtime.python),('bwrap',self.runtime.bwrap)):
            if digest_file(path.resolve(strict=True)) != self.runtime_hashes[name]:
                raise ValueError('Runtime binary changed after enrollment')
        return {'inputs':{split:{'train':file_identity(pair.train),'evaluation':file_identity(pair.evaluation)}
                          for split,pair in sorted(self.inputs.items())},
                'aggregate_bindings':[file_identity(binding) for binding in self.aggregate_bindings],
                'aggregate_source_sha256':self.aggregate_source_sha256,
                'aggregate_policy_sha256':self.aggregate_policy_sha256,
                'worker_source_sha256':digest_file(Path(__file__)),
                'released_metrics':sorted(self.released_metrics),
                'runtime_binary_hashes':self.runtime_hashes,
                'runtime_roots':[str(path) for path in self.runtime.environment_roots],
                'runtime_manifest':file_identity(self.runtime.manifest) if self.runtime.manifest else None,
                'timeout_seconds':self.timeout,'minimum_free_bytes':self.free_floor,
                'threads':4,'memory_limit_bytes':12*1024**3,'output_limit_bytes':16*1024**2}

    def _verify(self, spec: EvaluationSpec) -> SplitInputs:
        self._spec_record(spec)
        if spec.split not in {"validation", "test"}: raise ValueError("Unauthorized split")
        if spec.public_manifest_sha256 != self.public_hash or spec.split_manifest_sha256 != self.split_hash:
            raise ValueError("Episode manifest identity mismatch")
        verify_public_bundle(self.public)
        _tree(self.public, maximum_bytes=10 * 1024**3, maximum_files=4096)
        if digest_file(self.public / "PUBLIC_MANIFEST.json") != self.public_hash: raise ValueError("Public manifest changed")
        if digest_file(_path(self.split_path)) != self.split_hash: raise ValueError("Split manifest changed")
        if candidate_digest(spec.candidate_dir) != spec.candidate_digest: raise ValueError("Candidate changed")
        _path(spec.candidate_dir / "main.py")
        for key, path in (("python", self.runtime.python), ("bwrap", self.runtime.bwrap)):
            if digest_file(path.resolve(strict=True)) != self.runtime_hashes[key]: raise ValueError("Runtime binary changed")
        selected = self.inputs[spec.split]
        train, evaluation = selected.train.verify(), selected.evaluation.verify()
        if train == evaluation: raise ValueError("Train and evaluation must be distinct")
        # Exact prepared-view schema prevents hidden targets or renamed label
        # arrays from entering the candidate mount through trusted misconfiguration.
        expected = {"x.npy", "sample_ids.npy", "subject_ids.npy"}
        with zipfile.ZipFile(evaluation) as archive:
            names = archive.namelist()
            if len(names) != len(expected) or set(names) != expected:
                raise ValueError("Evaluation inputs require only x, sample_ids, and subject_ids")
        return selected

    def build_command(self, spec: EvaluationSpec, candidate: Path, output: Path) -> list[str]:
        selected = self.inputs.get(spec.split)
        if selected is None: raise ValueError("Unauthorized split")
        command = [str(self.runtime.bwrap), "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--clearenv"]
        for root in (Path("/usr"), Path("/lib"), Path("/lib64"), *self.runtime.environment_roots):
            if root.exists(): command += ["--ro-bind", str(root.resolve()), str(root)]
        cache = Path("/etc/ld.so.cache")
        if cache.is_file(): command += ["--ro-bind", str(cache), str(cache)]
        command += ["--proc", "/proc", "--remount-ro", "/proc", "--dev", "/dev", "--remount-ro", "/dev",
                    "--bind", str(output.parent / "tmp"), "/tmp", "--dir", "/inputs",
                    "--ro-bind", str(candidate), "/candidate", "--ro-bind", str(self.public), "/public",
                    "--ro-bind", str(selected.train.path), "/inputs/train.npz",
                    "--ro-bind", str(selected.evaluation.path), "/inputs/evaluation.npz",
                    "--bind", str(output), "/out", "--remount-ro", "/", "--chdir", "/candidate"]
        environment = {"PATH": f"{self.runtime.python.parent}:/usr/bin", "HOME": "/tmp", "TMPDIR": "/tmp",
            "XDG_CACHE_HOME": "/tmp/cache", "HF_HOME": "/tmp/huggingface", "TORCH_HOME": "/tmp/torch",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "CUDA_VISIBLE_DEVICES": "",
            "LANG": "C.UTF-8", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4",
            "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "VECLIB_MAXIMUM_THREADS": "4"}
        for key, value in environment.items(): command += ["--setenv", key, value]
        return command + ["--", str(self.runtime.python), "-B", "/candidate/main.py", "--split", spec.split,
                          "--input", "/inputs/evaluation.npz", "--train", "/inputs/train.npz",
                          "--public", "/public", "--output", "/out"]

    def _base_result(self, record: dict[str, Any], status: str) -> dict[str, Any]:
        return {"job_id": record["job_id"], "candidate_digest": record["candidate_digest"], "split": record["split"],
                "status": status, "metrics": {}, "artifacts": [],
                "sandbox_receipt": str(self.job_directory(record["job_id"]) / "receipt.json")}

    def _finish(self, job_id: str, result: dict[str, Any]) -> None:
        with closing(sqlite3.connect(self.db_path, timeout=30)) as db, db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT result FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row[0] is not None and json.loads(row[0]) != result: raise ValueError("Terminal worker response immutable")
            db.execute("UPDATE jobs SET result=? WHERE id=?", (json.dumps(result, allow_nan=False), job_id))

    def submit(self, spec: EvaluationSpec) -> dict[str, Any]:
        self._verify(spec)
        record = self._spec_record(spec)
        fingerprint = hashlib.sha256(canonical_bytes(record)).hexdigest()
        from eegfm.agent.processes import process_info
        owner = process_info(os.getpid())
        if owner is None: raise RuntimeError("Cannot establish controller process identity")
        with closing(sqlite3.connect(self.db_path, timeout=30)) as db, db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT fingerprint FROM jobs WHERE id=?", (spec.job_id,)).fetchone()
            if previous:
                if previous[0] != fingerprint: raise ValueError("Job ID reused for a different request")
            else:
                directory = self.job_directory(spec.job_id)
                if directory.exists() or directory.is_symlink():
                    raise FileExistsError("Unregistered evidence directory exists; preserve it")
                db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?)", (spec.job_id, fingerprint, json.dumps(record), None, os.getpid(), owner["start"]))
        if previous: return self.poll(spec.job_id)
        job = self.job_directory(spec.job_id)
        diagnostic_code = "evaluation_setup_failed"
        try:
            job.mkdir(exist_ok=False)
            write_atomic(job / "request.json", {**record, "fingerprint": fingerprint, "runtime_binary_hashes": self.runtime_hashes})
            candidate = job / "candidate"
            shutil.copytree(spec.candidate_dir, candidate, symlinks=True)
            if candidate_digest(candidate) != spec.candidate_digest: raise ValueError("Snapshot changed")
            output = job / "out"
            output.mkdir()
            # Bubblewrap 0.6.1 lacks --size. Keep private scratch on the owned
            # data volume and inside the same monitored 2 GiB job allocation.
            (job / "tmp").mkdir(mode=0o700)
            command = self.build_command(spec, candidate, output)
            status = run_bounded(command, cwd=job, output_dir=job / "execution", timeout_seconds=self.timeout,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1"},
                threads=4, memory_limit_bytes=12 * 1024**3, storage_scope=job, storage_limit_bytes=2 * 1024**3,
                stdout_limit_bytes=16 * 1024**2, minimum_free_bytes=self.free_floor)
            diagnostic_code = "evaluation_integrity_failed"
            if status.get("process_cleanup", {}).get("surviving_owned_pids") != []:
                raise RuntimeError("Worker process cleanup was not confirmed")
            diagnostic_code = "candidate_execution_failed"
            if status["status"] != "completed" or status["exit_code"] != 0:
                raise RuntimeError("Worker did not complete cleanly")
            diagnostic_code = "evaluation_integrity_failed"
            self._verify(spec)
            if candidate_digest(candidate) != spec.candidate_digest: raise ValueError("Worker modified candidate")
            diagnostic_code = "candidate_outputs_rejected"
            _tree(output, maximum_bytes=512 * 1024**2, maximum_files=512, hidden=True)
            aggregated = self.aggregate(output, spec)
            diagnostic_code = "evaluation_integrity_failed"
            aggregated = self.validate_aggregate(output, aggregated)
            diagnostic_code = "evaluation_setup_failed"
            write_atomic(job / "aggregation-private.json", aggregated)
            metrics_file = job / "released_metrics.json"
            write_atomic(metrics_file, aggregated["metrics"])
            result = self._base_result(record, "succeeded")
            result.update(metrics=aggregated["metrics"], artifacts=[{"path": "released_metrics.json", "sha256": digest_file(metrics_file)}])
            write_atomic(job / "receipt.json", {"status": "succeeded", "request_fingerprint": fingerprint,
                "execution": str(job / "execution"), "aggregate_manifest_sha256": digest_file(job / "aggregation-private.json"),
                "result": result, "isolation": "bwrap-unshare-all", "raw_outputs_public": False})
            self._finish(spec.job_id, result)
            return result
        except BaseException as error:
            result = self._base_result(record, "failed")
            if not isinstance(error, Exception):
                diagnostic_code = "evaluation_interrupted"
            elif diagnostic_code == "candidate_outputs_rejected":
                diagnostic_code = _output_failure_diagnostic(error, output)
            result["diagnostic_code"] = diagnostic_code
            job.mkdir(exist_ok=True)
            write_atomic(job / "receipt.json", {"status": "failed", "error_type": type(error).__name__, "result": result})
            self._finish(spec.job_id, result)
            if not isinstance(error, Exception): raise
            return result

    def poll(self, job_id: str) -> dict[str, Any]:
        _id(job_id)
        with closing(sqlite3.connect(self.db_path)) as db, db:
            row = db.execute("SELECT spec,result,owner_pid,owner_start FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None: raise ValueError("Unknown worker job")
        record = json.loads(row[0])
        if record.get('enrollment') != self._enrollment():
            raise ValueError('Worker enrollment changed; consumed jobs cannot be reinterpreted or rerun')
        if row[1] is not None: return json.loads(row[1])
        from eegfm.agent.processes import process_info
        owner = process_info(row[2])
        if owner and owner["start"] == row[3] and owner["state"] != "Z":
            return self._base_result(record, "waiting")
        result = self._base_result(record, "failed")
        result["diagnostic_code"] = "evaluation_interrupted"
        self._finish(job_id, result)
        return result

    def validate_aggregate(self, output: Path, result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(result, dict) or set(result) != {"metrics", "artifacts"}: raise ValueError("Invalid aggregation schema")
        metrics = result["metrics"]
        if not isinstance(metrics, dict) or not metrics or not set(metrics) <= self.released_metrics:
            raise ValueError("Only predeclared metrics may be released")
        if any(type(value) not in {int, float} or not math.isfinite(value) for value in metrics.values()):
            raise ValueError("Metrics must be finite numeric scalars")
        artifacts = result["artifacts"]
        if not isinstance(artifacts, list) or len(artifacts) > 128: raise ValueError("Invalid private artifact manifest")
        seen: set[str] = set()
        for artifact in artifacts:
            if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}: raise ValueError("Invalid artifact")
            name = artifact["path"]
            if name in seen: raise ValueError("Duplicate artifact")
            seen.add(name)
            path = _path(output / safe_relative(name))
            path.resolve().relative_to(output.resolve())
            if digest_file(path) != _sha(artifact["sha256"]): raise ValueError("Artifact hash mismatch")
        return json.loads(canonical_bytes(result))


def validate_prediction_npz(path: Path, truth_path: Path, *, feature_count: int = 62) -> dict[str, Any]:
    """Strict arrays only; aligned IDs and labels come from trusted truth.

    Header/shape/byte caps are checked before untrusted arrays are allocated.
    No pickle, structured dtype, candidate labels or scalar-metric substitution.
    """
    import numpy as np
    _path(path)
    _path(truth_path)
    with np.load(truth_path, allow_pickle=False, max_header_size=10000) as truth:
        ids, labels = truth["sample_ids"], truth["y"]
    if ids.ndim != 1 or labels.shape != ids.shape or len(ids) == 0 or len(set(ids.tolist())) != len(ids):
        raise ValueError("Invalid trusted rows")
    if not np.isin(labels, [0, 1]).all() or set(labels.tolist()) != {0, 1}:
        raise ValueError("Both trusted binary classes required")
    rows = len(ids)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or not {"logits.npy", "sample_ids.npy"} <= set(names) or not set(names) <= {"logits.npy", "sample_ids.npy", "target_predictions.npy"}:
            raise ValueError("Unexpected prediction array schema")
        if sum(item.file_size for item in archive.infolist()) > 512 * 1024**2: raise ValueError("Prediction archive too large")
        for name in names:
            with archive.open(name) as handle:
                prefix = handle.read(8)
                if prefix[:6] != b"\x93NUMPY" or prefix[6:] not in {b"\x01\x00", b"\x02\x00", b"\x03\x00"}: raise ValueError("Invalid NPY header")
                length_width = 2 if prefix[6] == 1 else 4
                length_bytes = handle.read(length_width)
                if len(length_bytes) != length_width: raise ValueError("Truncated header")
                length = struct.unpack("<H" if length_width == 2 else "<I", length_bytes)[0]
                if length > 10000: raise ValueError("Oversized array header")
                header = ast.literal_eval(handle.read(length).decode("utf-8" if prefix[6] == 3 else "latin1"))
                if not isinstance(header, dict) or set(header) != {"descr", "fortran_order", "shape"} or not isinstance(header["descr"], str): raise ValueError("Unsafe dtype header")
                dtype = np.dtype(header["descr"])
                shape = (rows, feature_count) if name == "target_predictions.npy" else (rows,)
                kinds = "USiu" if name == "sample_ids.npy" else "fiu"
                if header["shape"] != shape or dtype.kind not in kinds or dtype.hasobject or dtype.itemsize > 4096:
                    raise ValueError("Invalid array shape/dtype")
                count = math.prod(shape)
                if 8 + length_width + length + count * dtype.itemsize != archive.getinfo(name).file_size:
                    raise ValueError("Array byte length mismatch")
    with np.load(path, allow_pickle=False, max_header_size=10000) as archive:
        arrays = {name: archive[name] for name in archive.files}
    if not np.array_equal(arrays["sample_ids"], ids): raise ValueError("Prediction rows do not match trusted split")
    if not np.isfinite(arrays["logits"]).all() or ("target_predictions" in arrays and not np.isfinite(arrays["target_predictions"]).all()):
        raise ValueError("Nonfinite predictions")
    return {**arrays, "trusted_y": labels}


class NpzClassificationAggregator:
    """Minimal classification check; grouped inference remains in real_science."""
    def __init__(self, truth_by_split: dict[str, FileBinding]) -> None:
        self.truth = dict(truth_by_split)

    def __call__(self, output: Path, spec: EvaluationSpec) -> dict[str, Any]:
        import numpy as np
        if spec.split not in self.truth: raise ValueError("No trusted truth for split")
        truth = self.truth[spec.split].verify()
        path = _path(output / "results.npz")
        arrays = validate_prediction_npz(path, truth)
        labels, predicted = arrays["trusted_y"], arrays["logits"] >= 0
        metrics = {"accuracy": float(np.mean(predicted == labels)),
                   "balanced_accuracy": float(sum(np.mean(predicted[labels == value] == value) for value in (0, 1)) / 2)}
        return {"metrics": metrics, "artifacts": [{"path": "results.npz", "sha256": digest_file(path)}]}
