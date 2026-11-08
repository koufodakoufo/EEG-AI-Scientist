"""Trusted, episode-local scientific research controller.

Security contract: this module and its SQLite journal live OUTSIDE the Actor's
filesystem grants. Actor output is ingested only after all session descendants
have stopped. `evaluator` is an injected TRUSTED submit/poll implementation: it
MUST launch candidate code in a separate, no-network sandbox with only the
specified split's permitted tensors, never import/exec it in this controller.
Test EEG/targets/caches and raw worker logs must never enter the Actor case.
`sandboxed=True` and a receipt are required declarations, not isolation proofs;
the integration must independently certify that implementation with live probes.

Requests are JSON {request_id, episode_id, operation, payload}. They cannot
specify commands, environment, host paths or reviewer identities. Canonical
requests and responses are insert-only; test reservations commit before submit.
Replays return the saved response and NEVER submit again, including after crash.
Unknown submitted jobs are queried by ID, never retried automatically.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
import time
from typing import Any, Callable, Iterator, Protocol

from eegfm.common import append_jsonl, now, write_json
from eegfm.agent.driver import Adapter
from eegfm.agent.driver import Driver
from eegfm.evaluation.bundle import canonical_bytes
from eegfm.evaluation.bundle import digest_file
from eegfm.evaluation.bundle import safe_relative


RECOVERY_POLICIES = frozenset({"strict-v1", "validation-recovery-v1"})
# Closed vocabulary: never derive public messages from exceptions or worker text.
FAILURE_MESSAGES = {
    "evaluation_failed": "Evaluation failed without a recognized candidate diagnostic; trusted review is required.",
    "evaluation_setup_failed": "Trusted evaluation setup failed; trusted review is required.",
    "evaluation_integrity_failed": "Evaluation integrity checks failed; trusted review is required.",
    "evaluation_interrupted": "Evaluation was interrupted; the consumed job cannot be resubmitted.",
    "evaluator_unavailable": "The evaluator did not return a valid response; trusted review is required.",
    "worker_result_rejected": "The worker response failed controller validation; trusted review is required.",
    "candidate_execution_failed": "Candidate execution did not finish cleanly; check the entrypoint and resource limits.",
    "candidate_outputs_rejected": "Candidate outputs failed validation; check the public schema and complete required artifacts.",
    "intervention_strength_mismatch": "Control strength must match the intervention strength in every window; check precision and per-window norms.",
    "direction_span_mismatch": "Recorded shifts must lie in their recorded direction spans; check numerical precision and reconstruction.",
    "control_rank_mismatch": "Controls must match actual numerical rank; check the recorded direction bases.",
    "control_subspace_mismatch": "Controls must use distinct subspaces; check the recorded direction bases.",
    "nonfinite_evidence": "Scientific evidence must contain finite numeric values; check derived arrays and overflow.",
    "final_test_failed": "The one-shot final test failed; its reservation is consumed and completion is blocked.",
}
RECOVERABLE_FAILURES = frozenset({"candidate_execution_failed", "candidate_outputs_rejected",
    "intervention_strength_mismatch", "direction_span_mismatch", "control_rank_mismatch",
    "control_subspace_mismatch", "nonfinite_evidence"})


class ControllerAlreadyRunning(RuntimeError):
    """Lease contention is a non-mutating refusal, not an episode failure."""


class SandboxedEvaluator(Protocol):
    """Trusted implementation; poll must have NO execution/submission side effect."""
    sandboxed: bool

    def submit(self, spec: EvaluationSpec) -> dict[str, Any]: ...
    def poll(self, job_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class EvaluationSpec:
    job_id: str
    episode_id: str
    run_id: str
    attempt_id: str
    split: str
    candidate_dir: Path
    candidate_digest: str
    split_manifest_sha256: str
    public_manifest_sha256: str


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", value):
        raise ValueError("Invalid identifier")
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Invalid SHA256")
    return value


def _fields(value: Any, expected: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("Unexpected or missing fields")


def _safe_path(root: Path, relative: str, *, directory: bool = False) -> Path:
    if not isinstance(relative, str) or not relative or len(relative) > 4096 or '\x00' in relative:
        raise ValueError('Path must be bounded nonempty text')
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError("Input root/ancestors cannot be links")
    path = root
    for component in safe_relative(relative).parts:
        path = path / component
        if path.is_symlink():
            raise ValueError("Links are forbidden")
    path.resolve(strict=True).relative_to(root.resolve(strict=True))
    if directory:
        if not path.is_dir():
            raise ValueError("Expected directory")
    elif not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Expected regular unlinked file")
    return path


def _manifest(root: Path) -> tuple[list[dict[str, Any]], str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Candidate root must be a regular directory")
    entries: list[dict[str, Any]] = []
    total = 0
    for path in sorted(root.rglob("*"), key=lambda path: path.relative_to(root).parts):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or any(part.startswith(".") for part in path.relative_to(root).parts):
            raise ValueError("Links and hidden candidate paths are forbidden")
        if path.is_dir():
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Candidate must contain regular single-link files")
        total += info.st_size
        if len(entries) >= 256 or total > 64 * 1024**2:
            raise ValueError("Candidate size limit exceeded")
        entries.append({"path": path.relative_to(root).as_posix(), "bytes": info.st_size,
                        "sha256": digest_file(path)})
    if not entries:
        raise ValueError("Empty candidate")
    return entries, hashlib.sha256(canonical_bytes(entries)).hexdigest()


class ResearchController:
    def __init__(self, *, trusted_root: Path, case_root: Path, episode_id: str, run_id: str,
                 public_manifest_sha256: str, split_manifest_sha256: str,
                 evaluator: SandboxedEvaluator, max_attempts: int = 4,
                 recovery_policy: str = "strict-v1") -> None:
        self.root = Path(trusted_root).resolve()
        self.case = Path(case_root).resolve(strict=True)
        if self.root == self.case or self.root in self.case.parents or self.case in self.root.parents:
            raise ValueError("Trusted control and Actor case must be disjoint")
        if getattr(evaluator, "sandboxed", False) is not True:
            raise ValueError("Evaluator must implement the separate-sandbox contract")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 32:
            raise ValueError("Invalid attempt budget")
        if not isinstance(recovery_policy, str) or recovery_policy not in RECOVERY_POLICIES:
            raise ValueError("Unknown recovery policy")
        self.recovery_policy = recovery_policy
        self.episode_id, self.run_id = _identifier(episode_id), _identifier(run_id)
        self.evaluator = evaluator
        self.run = self.root / "runs" / self.run_id
        self.run.mkdir(parents=True, exist_ok=True)
        for name in ("attempts", "jobs", "sessions", "sealed", "requests", "candidates"):
            (self.run / name).mkdir(exist_ok=True)
        self.database = self.run / "control.sqlite3"
        identity = {"episode_id": self.episode_id, "run_id": self.run_id,
                    "public_manifest_sha256": _digest(public_manifest_sha256),
                    "split_manifest_sha256": _digest(split_manifest_sha256),
                    "max_attempts": max_attempts, "research_mode": "analysis"}
        if recovery_policy != "strict-v1":
            identity["recovery_policy"] = recovery_policy
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, digest TEXT NOT NULL, request TEXT NOT NULL, response TEXT NOT NULL)")
            row = db.execute("SELECT value FROM state WHERE id=1").fetchone()
            if row is None:
                state = {"identity": identity, "status": "brief", "note": "episode initialized",
                         "jobs": {}, "attempts": [], "review": None, "contract": None,
                         "lock": None, "test_job": None, "sessions": [], "report": None,
                         "version": 0}
                db.execute("INSERT INTO state VALUES(1,?)", (json.dumps(state),))
            else:
                state = json.loads(row[0])
                if state["identity"] != identity:
                    raise ValueError("Existing episode identity/contract mismatch")
            self._save(db, state)

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.database, timeout=30)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _load(self, db: sqlite3.Connection) -> dict[str, Any]:
        return json.loads(db.execute("SELECT value FROM state WHERE id=1").fetchone()[0])

    def _save(self, db: sqlite3.Connection, state: dict[str, Any]) -> None:
        db.execute("UPDATE state SET value=? WHERE id=1", (json.dumps(state, allow_nan=False),))
        # Mirrors are inspectable lifecycle artifacts, never authority. Rebuilt on resume.
        write_json(self.run / "STATE.json", {"status": state["status"], "note": state["note"],
            "jobs": [key for key, job in state["jobs"].items() if job["status"] not in {"succeeded", "failed"}],
            "updated_by": "trusted_driver_bridge", "version": state["version"]})
        write_json(self.run / "run.json", state["identity"])
        if state["review"]:
            write_json(self.run / "review.json", state["review"])
        if state["contract"]:
            write_json(self.run / "freeze.json", state["contract"])
        if state["lock"]:
            write_json(self.run / "lock.json", state["lock"])
        for attempt in state["attempts"]:
            write_json(self.run / "attempts" / attempt["id"] / "attempt.json", attempt)
        for key, job in state["jobs"].items():
            write_json(self.run / "jobs" / f"{key}.json", job)
        lines = ["# Episode attempts", "", "| id | kind | status | retention | metrics |",
                 "|---|---|---|---|---|"]
        for attempt in state["attempts"]:
            lines.append(f"| {attempt['id']} | {attempt['kind']} | {attempt['status']} | {attempt.get('retention', '')} | {json.dumps(attempt.get('metrics', {}))} |")
        (self.run / "attempts" / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _event(self, event: str, **fields: Any) -> None:
        record = {"event": event, "episode_id": self.episode_id, "run_id": self.run_id, **fields}
        append_jsonl(self.run / "events.jsonl", record)
        append_jsonl(self.run / "audit.jsonl", record)

    def _snapshot(self, relative: str) -> tuple[Path, str]:
        source = _safe_path(self.case / "output", relative, directory=True)
        entries, digest = _manifest(source)
        destination = self.run / "candidates" / digest
        if destination.exists():
            if _manifest(destination)[1] != digest:
                raise ValueError("Existing candidate changed")
            return destination, digest
        temporary = Path(tempfile.mkdtemp(prefix="snapshot-", dir=self.run / "candidates"))
        try:
            for entry in entries:
                original = _safe_path(source, entry["path"])
                target = temporary / entry["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
            if _manifest(source)[1] != digest or _manifest(temporary)[1] != digest:
                raise ValueError("Candidate changed during snapshot")
            temporary.rename(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        write_json(self.run / "candidates" / f"{digest}.json", {"digest": digest, "files": entries})
        return destination, digest

    def _spec(self, state: dict[str, Any], job: dict[str, Any]) -> EvaluationSpec:
        identity = state["identity"]
        return EvaluationSpec(job_id=job["job_id"], episode_id=self.episode_id, run_id=self.run_id,
            attempt_id=job["attempt_id"], split=job["split"],
            candidate_dir=self.run / "candidates" / job["candidate_digest"],
            candidate_digest=job["candidate_digest"], split_manifest_sha256=identity["split_manifest_sha256"],
            public_manifest_sha256=identity["public_manifest_sha256"])

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        _fields(request, {"request_id", "episode_id", "operation", "payload"})
        identifier = _identifier(request["request_id"])
        _identifier(request['operation'])
        if request["episode_id"] != self.episode_id:
            raise ValueError("Cross-episode request")
        raw = canonical_bytes(request)
        if len(raw) > 64 * 1024:
            raise ValueError("Request too large")
        digest = hashlib.sha256(raw).hexdigest()
        request = json.loads(raw)  # caller cannot mutate the accepted payload concurrently
        pending: EvaluationSpec | None = None
        with self._transaction() as db:
            previous = db.execute("SELECT digest,response FROM requests WHERE id=?", (identifier,)).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ValueError("Request ID reused with different content")
                return json.loads(previous[1])
            state = self._load(db)
            response, job = self._dispatch(state, request["operation"], request["payload"])
            response = {"request_id": identifier, "request_sha256": digest, **response}
            state["version"] += 1
            db.execute("INSERT INTO requests VALUES(?,?,?,?)", (identifier, digest, raw.decode(), json.dumps(response)))
            self._save(db, state)
            if job:
                pending = self._spec(state, job)
            request_dir = self.run / "requests" / identifier
            request_dir.mkdir(exist_ok=False)
            (request_dir / "request.json").write_bytes(raw)
            write_json(request_dir / "response.json", response)
            self._event(request["operation"], request_id=identifier, request_sha256=digest,
                        candidate_digest=response.get("candidate_digest"), job_id=response.get("job_id"))
        # Reservation and immutable response are durable BEFORE any worker starts.
        if pending:
            diagnostic_code = "evaluator_unavailable"
            try:
                result = self.evaluator.submit(pending)
                diagnostic_code = "worker_result_rejected"
                self._accept_result(pending.job_id, result)
            except Exception as error:
                self._fail_job(pending.job_id, type(error).__name__, diagnostic_code)
        return response

    def _dispatch(self, state: dict[str, Any], operation: str, payload: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if state["status"] in {"done", "blocked"}:
            raise ValueError("Episode is terminal")
        if operation == "brief":
            _fields(payload, {"path"})
            if state["status"] != "brief":
                raise ValueError("Brief is already submitted")
            source = _safe_path(self.case / "output", payload["path"])
            content = source.read_bytes()
            if not 0 < len(content) <= 65536:
                raise ValueError("Invalid brief size")
            (self.run / "RESEARCH_BRIEF.md").write_bytes(content)
            state["brief_sha256"] = hashlib.sha256(content).hexdigest()
            state.update(status="awaiting_review", note="delegated protocol review pending")
            return {"status": "awaiting_review"}, None
        if operation == "contract":
            _fields(payload, {"protocol"})
            protocol = payload["protocol"]
            if not state["review"] or not state["review"]["approved"] or state["contract"]:
                raise ValueError("Review required; contract freezes once")
            if not isinstance(protocol, dict) or protocol.get("research_mode") != "analysis" or protocol.get("selection_split") != "validation":
                raise ValueError("Analysis/validation contract required")
            state["contract"] = {"protocol": protocol, "sha256": hashlib.sha256(canonical_bytes(protocol)).hexdigest(),
                                 "frozen_at": now()}
            return {"status": "frozen", "contract_sha256": state["contract"]["sha256"]}, None
        if operation in {"baseline", "attempt"}:
            _fields(payload, {"candidate_dir", "split", "title"})
            if not state["contract"] or state["lock"] or state["status"] != "working":
                raise ValueError("Contract and working pre-lock state required")
            if payload["split"] != "validation" or not isinstance(payload["title"], str) or not 0 < len(payload["title"]) <= 500:
                raise ValueError("Invalid validation proposal")
            baselines = [a for a in state["attempts"] if a["kind"] == "baseline"]
            if operation == "baseline" and baselines:
                raise ValueError("Baseline already allocated")
            if operation == "attempt" and (not baselines or baselines[0]["status"] != "evaluated"):
                raise ValueError("Successful baseline required")
            if operation == "attempt" and sum(a["kind"] == "iteration" for a in state["attempts"]) >= state["identity"]["max_attempts"]:
                raise ValueError("Attempt budget exhausted")
            _, digest = self._snapshot(payload["candidate_dir"])
            attempt_id = f"A{len(state['attempts']) + 1}"
            state["attempts"].append({"id": attempt_id, "kind": "baseline" if operation == "baseline" else "iteration",
                "title": payload["title"], "status": "submitted", "candidate_digest": digest, "metrics": {}, "jobs": []})
            job = self._new_job(state, attempt_id, digest, "validation")
            return {"status": "accepted", "attempt_id": attempt_id, "candidate_digest": digest, "job_id": job["job_id"]}, job
        if operation == "lock":
            _fields(payload, {"attempt_id", "candidate_digest"})
            if state["lock"] or state["status"] != "working":
                raise ValueError("One lock per episode in working state")
            matches = [a for a in state["attempts"] if a["id"] == payload["attempt_id"]]
            if not matches or not self._validated_attempt(state, matches[0]) or matches[0]["candidate_digest"] != payload["candidate_digest"]:
                raise ValueError("Lock must match an evaluated candidate")
            digest = _digest(payload["candidate_digest"])
            if _manifest(self.run / "candidates" / digest)[1] != digest:
                raise ValueError("Candidate changed")
            state["lock"] = {**payload, "contract_sha256": state["contract"]["sha256"],
                             "split_manifest_sha256": state["identity"]["split_manifest_sha256"], "locked_at": now()}
            append_jsonl(self.run / "locks.jsonl", state["lock"])
            return {"status": "locked", "candidate_digest": digest}, None
        if operation == "test":
            _fields(payload, {"candidate_digest", "split"})
            if not state["lock"] or state["test_job"] or state["status"] != "working":
                raise ValueError("Test requires lock and unused reservation")
            digest = _digest(payload["candidate_digest"])
            if payload["split"] != "test" or digest != state["lock"]["candidate_digest"]:
                raise ValueError("Test split/candidate mismatch")
            if _manifest(self.run / "candidates" / digest)[1] != digest:
                raise ValueError("Locked candidate changed")
            job = self._new_job(state, state["lock"]["attempt_id"], digest, "test")
            state["test_job"] = job["job_id"]
            return {"status": "accepted", "candidate_digest": digest, "job_id": job["job_id"]}, job
        if operation == "report":
            _fields(payload, {"path"})
            self._completion_ready(state)
            source = _safe_path(self.case / "output", payload["path"])
            content = source.read_bytes()
            if not 0 < len(content) <= 1024 * 1024 or not content.decode("utf-8").strip():
                raise ValueError("Report missing or too large")
            (self.run / "FINAL_REPORT.md").write_bytes(content)
            state["report"] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
            state.update(status="done", note="successful frozen analysis and report")
            return {"status": "done", "report_sha256": state["report"]["sha256"]}, None
        raise ValueError("Operation is not an Actor capability")

    def reject_request(self, request: Any, error_type: str) -> None:
        """Keep safe feedback without returning exceptions containing host paths."""
        self._event("request_rejected", reason=error_type)
        if not isinstance(request, dict) or request.get("episode_id") != self.episode_id:
            return
        try:
            identifier = _identifier(request.get("request_id"))
            raw = canonical_bytes(request)
        except (ValueError, TypeError):
            return
        if len(raw) > 64 * 1024:
            return
        digest = hashlib.sha256(raw).hexdigest()
        response = {"request_id": identifier, "request_sha256": digest,
                    "status": "rejected", "error_type": error_type}
        with self._transaction() as db:
            if db.execute("SELECT id FROM requests WHERE id=?", (identifier,)).fetchone():
                return  # An accepted or rejected ID can never be overwritten.
            db.execute("INSERT INTO requests VALUES(?,?,?,?)", (identifier, digest, raw.decode(), json.dumps(response)))
            directory = self.run / "requests" / identifier
            directory.mkdir(exist_ok=False)
            (directory / "request.json").write_bytes(raw)
            write_json(directory / "response.json", response)
            state = self._load(db)
            state["version"] += 1
            self._save(db, state)

    def _new_job(self, state: dict[str, Any], attempt_id: str, digest: str, split: str) -> dict[str, Any]:
        job_id = f"{self.run_id}-{attempt_id}-{split}"
        job = {"job_id": job_id, "attempt_id": attempt_id, "candidate_digest": digest,
               "split": split, "status": "dispatching", "reserved_at": now()}
        state["jobs"][job_id] = job
        next(a for a in state["attempts"] if a["id"] == attempt_id)["jobs"].append(job_id)
        state.update(status="waiting_job", note="trusted job reserved before execution")
        return job

    def review(self, *, approved: bool, reviewer_id: str, policy_sha256: str) -> None:
        with self._transaction() as db:
            state = self._load(db)
            if state["status"] != "awaiting_review" or type(approved) is not bool:
                raise ValueError("No brief awaiting review")
            state["review"] = {"approval_mode": "delegated_protocol_review", "reviewer_id": _identifier(reviewer_id),
                "policy_sha256": _digest(policy_sha256), "approved": approved,
                "brief_sha256": state["brief_sha256"], "reviewed_at": now()}
            state.update(status="working" if approved else "brief", note="delegated protocol review recorded")
            state["version"] += 1
            self._save(db, state)
            self._event("brief_review", **state["review"])

    def _accept_result(self, job_id: str, result: dict[str, Any]) -> None:
        fields = {"job_id", "candidate_digest", "split", "status", "metrics", "artifacts", "sandbox_receipt"}
        if isinstance(result, dict) and "diagnostic_code" in result:
            fields.add("diagnostic_code")
        _fields(result, fields)
        code = result.get("diagnostic_code", "evaluation_failed")
        if not isinstance(code, str) or code not in FAILURE_MESSAGES or ("diagnostic_code" in result and result["status"] != "failed"):
            raise ValueError("Invalid worker diagnostic")
        if result["status"] not in {"waiting", "succeeded", "failed"} or not isinstance(result["sandbox_receipt"], str) or not result["sandbox_receipt"]:
            raise ValueError("Invalid worker receipt/status")
        metrics = result["metrics"]
        if not isinstance(metrics, dict) or any(not isinstance(k, str) or type(v) not in {int, float} or not math.isfinite(v) for k, v in metrics.items()):
            raise ValueError("Metrics must be finite numbers")
        if result["status"] == "succeeded" and not metrics:
            raise ValueError("Successful evaluation requires metrics")
        if not isinstance(result["artifacts"], list):
            raise ValueError("Artifact manifest required")
        for artifact in result["artifacts"]:
            _fields(artifact, {"path", "sha256"})
            safe_relative(artifact["path"])
            _digest(artifact["sha256"])
        with self._transaction() as db:
            state = self._load(db)
            job = state["jobs"][job_id]
            if any(result[key] != job[key] for key in ("job_id", "candidate_digest", "split")):
                raise ValueError("Worker result identity mismatch")
            if job["status"] in {"succeeded", "failed"}:
                if result['status'] == 'waiting':
                    return  # A stale concurrent poll cannot regress a terminal job.
                if job.get("result") != result:
                    raise ValueError("Terminal result is immutable")
                return
            if _manifest(self.run / "candidates" / job["candidate_digest"])[1] != job["candidate_digest"]:
                raise ValueError("Candidate changed during evaluation")
            job.update(status=result["status"], result=result)
            if result["status"] == "failed":
                job["diagnostic_code"] = code
            if result["status"] != "waiting":
                if job["split"] == "validation":
                    attempt = next(a for a in state["attempts"] if a["id"] == job["attempt_id"])
                    attempt.update(status="evaluated" if result["status"] == "succeeded" else "failed",
                                   metrics=metrics if result["status"] == "succeeded" else {},
                                   retention="retained_valid" if result["status"] == "succeeded" else "execution_failed")
                else:
                    write_json(self.run / "sealed" / "final_test.json", result)
                state.update(status="working", note=f"job {job_id} {result['status']}")
            state["version"] += 1
            self._save(db, state)
            self._event("job_result", job_id=job_id, status=result["status"], split=job["split"])

    def _fail_job(self, job_id: str, error_type: str, diagnostic_code: str = "evaluation_failed") -> None:
        if diagnostic_code not in FAILURE_MESSAGES:
            raise ValueError("Unknown failure diagnostic")
        with self._transaction() as db:
            state = self._load(db)
            job = state["jobs"][job_id]
            if job['status'] in {'succeeded', 'failed'}:
                return
            job.update(status="failed", error_type=error_type, diagnostic_code=diagnostic_code)
            if job["split"] == "validation":
                next(a for a in state["attempts"] if a["id"] == job["attempt_id"]).update(status="failed", retention="execution_failed")
            state.update(status="working", note=f"job {job_id} failed; no automatic resubmission")
            state["version"] += 1
            self._save(db, state)

    def poll_jobs(self) -> list[dict[str, Any]]:
        with self._transaction() as db:
            state = self._load(db)
            pending = [key for key, job in state["jobs"].items() if job["status"] not in {"succeeded", "failed"}]
        for job_id in pending:
            diagnostic_code = "evaluator_unavailable"
            try:
                result = self.evaluator.poll(job_id)
                diagnostic_code = "worker_result_rejected"
                self._accept_result(job_id, result)
            except Exception as error:
                self._fail_job(job_id, type(error).__name__, diagnostic_code)
        with self._transaction() as db:
            return list(self._load(db)["jobs"].values())

    def _session_history(self, state: dict[str,Any]) -> None:
        fd, name = tempfile.mkstemp(prefix='.sessions-',dir=self.run)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                for record in state['sessions']:
                    stream.write(json.dumps(record,ensure_ascii=False)+'\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name,self.run/'sessions.jsonl')
        finally:
            Path(name).unlink(missing_ok=True)

    def reserve_session(self, maximum: int, *, provider: str | None = None, timeout_seconds: int = 900) -> str:
        if provider is not None:
            from eegfm.agent.provider import PROVIDER
            if provider != PROVIDER or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 240:
                raise ValueError('Invalid delegated provider/session allocation')
        with self._transaction() as db:
            state = self._load(db)
            if any(item.get('status') == 'reserved' for item in state['sessions']):
                raise ValueError('Unresolved prior launch: trusted process cleanup audit required')
            if len(state['sessions']) >= maximum:
                raise ValueError('Durable session budget exhausted')
            identifier = f"session-{len(state['sessions'])+1:02d}"
            state['sessions'].append({'reservation_id':identifier,'status':'reserved',
                'ok':False,'error':'interrupted','summary':{'reason':'reserved before model launch'},
                'started':time.time(),'progressed':False,'episode_id':self.episode_id,'run_id':self.run_id,
                'allocated_timeout_seconds':timeout_seconds if provider is not None else 900})
            if provider is not None:
                state['sessions'][-1]['provider'] = provider
            self._save(db,state)
            self._session_history(state)
            return identifier

    def guard_crash_resume(self) -> None:
        """A released flock does not prove a killed launcher's children stopped."""
        with self._transaction() as db:
            state = self._load(db)
            unresolved = [item.get('reservation_id') for item in state['sessions'] if item.get('status') == 'reserved']
            if unresolved:
                state.update(status='blocked',note='Unresolved model launch; independent owned-process cleanup audit required before any case reuse')
                state['version'] += 1
                self._save(db,state)
                self._event('crash_resume_blocked',unresolved_reservations=unresolved)

    def record_session(self, receipt: dict[str, Any], *, reservation_id: str | None = None) -> dict[str, Any]:
        delegated = None
        if receipt.get('provider') is not None:
            from eegfm.agent.provider import read_trusted_receipt
            if reservation_id is None:
                raise ValueError('Delegated receipt needs its existing reservation')
            delegated = read_trusted_receipt(receipt, controller_run=self.run, reservation_id=reservation_id,
                                            episode_id=self.episode_id, run_id=self.run_id)
            ok = delegated['status'] == 'completed'
            error = None if ok else 'transient' if delegated['status'] == 'timed_out' else 'failed'
            summary = {'provider': delegated['provider'], 'model': delegated['model'], 'effort': delegated['effort'],
                       'model_context_id': delegated.get('model_context_id'),
                       'trusted_audit_sha256': delegated.get('trusted_audit_sha256')}
        else:
            ok, error, summary = Adapter("codex").classify(receipt.get("exit_code", -1), receipt.get("stdout", ""),
                receipt.get("stderr", ""), receipt.get("status") == "timed_out")
            ok = bool(ok and receipt.get("status") == "completed" and receipt.get("process_cleanup", {}).get("surviving_owned_pids") == [])
        if not ok and error is None:
            error = "failed"
        record = {"ok": ok, "error": error, "summary": summary, "started": time.time(), "progressed": False,
                  "episode_id": self.episode_id, "run_id": self.run_id}
        if delegated is not None:
            record['provider'] = delegated['provider']
        with self._transaction() as db:
            state = self._load(db)
            if reservation_id is None:
                state['sessions'].append(record)
            else:
                index = next((i for i,item in enumerate(state['sessions']) if item.get('reservation_id') == reservation_id),None)
                if index is None or state['sessions'][index].get('status') != 'reserved':
                    raise ValueError('Session reservation missing or already completed')
                original = state['sessions'][index]
                if delegated is not None and (original.get('provider') != delegated['provider']
                        or original['allocated_timeout_seconds'] != delegated['allocated_timeout_seconds']):
                    raise ValueError('Delegated receipt changed its reserved provider/budget')
                if delegated is None and original.get('provider') is not None:
                    raise ValueError('Delegated reservation cannot use native receipt events')
                record.update(reservation_id=reservation_id,status='finished',started=original['started'],
                              allocated_timeout_seconds=original['allocated_timeout_seconds'])
                state['sessions'][index] = record
            self._save(db, state)
            self._session_history(state)
        return {**record, 'requests': delegated['requests']} if delegated is not None else record

    def _validated_attempt(self, state: dict[str, Any], attempt: dict[str, Any]) -> bool:
        jobs = [state["jobs"][key] for key in attempt["jobs"] if state["jobs"][key]["split"] == "validation"]
        return (attempt["status"] == "evaluated" and len(jobs) == 1
                and jobs[0]["status"] == "succeeded"
                and jobs[0]["candidate_digest"] == attempt["candidate_digest"]
                and jobs[0].get("result", {}).get("status") == "succeeded")

    def _recoverable_job(self, state: dict[str, Any], job: dict[str, Any]) -> bool:
        return (self.recovery_policy == "validation-recovery-v1"
                and job["split"] == "validation" and job["status"] == "failed"
                and job.get("diagnostic_code") in RECOVERABLE_FAILURES
                and any(a["id"] == job["attempt_id"] and a["kind"] == "iteration"
                        and a["status"] == "failed" for a in state["attempts"]))

    def _completion_ready(self, state: dict[str, Any]) -> None:
        if not state["sessions"] or not state["sessions"][-1]["ok"]:
            raise ValueError("Successful completed model session required")
        if not state["review"] or not state["contract"] or not state["lock"] or not state["test_job"]:
            raise ValueError("Lifecycle incomplete")
        if any(job["status"] != "succeeded" and not self._recoverable_job(state, job) for job in state["jobs"].values()):
            raise ValueError("All required jobs must succeed")
        baseline = [a for a in state["attempts"] if a["kind"] == "baseline"]
        selected = [a for a in state["attempts"] if a["id"] == state["lock"]["attempt_id"]]
        final = state["jobs"][state["test_job"]]
        if (len(baseline) != 1 or not self._validated_attempt(state, baseline[0])
                or len(selected) != 1 or not self._validated_attempt(state, selected[0])
                or final["status"] != "succeeded" or final["split"] != "test"
                or final["attempt_id"] != selected[0]["id"]
                or final["candidate_digest"] != state["lock"]["candidate_digest"]):
            raise ValueError("Successful baseline, locked validation and final test required")
        if not any(a["kind"] == "iteration" and self._validated_attempt(state, a) for a in state["attempts"]):
            raise ValueError("At least one successful scientific analysis required")

    def validate_done(self) -> None:
        with self._transaction() as db:
            state = self._load(db)
            self._completion_ready(state)
            if state["status"] != "done" or not state["report"] or digest_file(self.run / "FINAL_REPORT.md") != state["report"]["sha256"]:
                raise ValueError("Frozen report missing or changed")

    def block(self, note: str) -> None:
        with self._transaction() as db:
            state = self._load(db)
            if state["status"] == "done":
                raise ValueError("Completed episode is immutable")
            state.update(status="blocked", note=note)
            state["version"] += 1
            self._save(db, state)
            self._event("blocked", note=note, actor="driver")

    def projection(self) -> dict[str, Any]:
        """Only own-episode approved outputs; no host paths, raw worker logs or DB."""
        with self._transaction() as db:
            state = self._load(db)
            requests = [json.loads(row[0]) for row in db.execute("SELECT response FROM requests ORDER BY rowid")]
        jobs = []
        for job in state["jobs"].values():
            public = {key: job[key] for key in ("job_id", "attempt_id", "candidate_digest", "split", "status")}
            if job.get("result"):
                public["result"] = {key: value for key, value in job["result"].items()
                                    if key not in {"sandbox_receipt", "diagnostic_code"}}
                if job["status"] == "failed":
                    public["result"].update(metrics={}, artifacts=[])
            if self.recovery_policy == "validation-recovery-v1" and job["status"] == "failed":
                code = "final_test_failed" if job["split"] == "test" else job.get("diagnostic_code", "evaluation_failed")
                public["diagnostic"] = {"code": code, "message": FAILURE_MESSAGES[code],
                                        "eligible_for_new_iteration": self._recoverable_job(state, job)}
            jobs.append(public)
        projection = {"episode_id": self.episode_id, "run_id": self.run_id,
                "state": {"status": state["status"], "note": state["note"], "version": state["version"]},
                "review": state["review"], "contract": state["contract"], "attempts": state["attempts"],
                "jobs": jobs, "lock": state["lock"], "responses": requests}
        if self.recovery_policy == "validation-recovery-v1":
            used = sum(a["kind"] == "iteration" for a in state["attempts"])
            projection["recovery"] = {"policy": self.recovery_policy,
                "max_iterations": state["identity"]["max_attempts"], "used_iterations": used,
                "remaining_iterations": state["identity"]["max_attempts"] - used,
                "final_test_consumed": state["test_job"] is not None,
                "rule": "Eligible validation failures remain failed and consume an iteration. Submit a corrected candidate as a new attempt before lock, within the remaining iteration and session budgets. Baseline, integrity and final-test failures block completion."}
        return projection


@dataclass(frozen=True)
class _AdapterIdentity:
    name: str = "isolated-codex"
    model: str | None = None


class ResearchDriver(Driver):
    """Uses inherited Driver.loop; never invokes the legacy Adapter.argv.

    launch(projection) MUST invoke eegfm.agent.actor.launch_actor with a
    fresh control home and live gate, then collect stdout/stderr and typed
    requests after owned descendants stop. It returns a bounded receipt with
    `requests: list[dict]`. Actor output request files are untrusted until handle.
    reviewer(projection) optionally returns approved/reviewer_id/policy_sha256.
    """
    def __init__(self, controller: ResearchController, *, launch: Callable[[dict[str, Any]], dict[str, Any]],
                 reviewer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                 max_sessions: int = 6, once: bool = False, poll: float = 1.0,
                 session_provider: str | None = None, provider_model: str | None = None,
                 provider_timeout_seconds: int = 240) -> None:
        self.controller, self.launch, self.reviewer = controller, launch, reviewer
        if type(max_sessions) is not int or not 1 <= max_sessions <= 6:
            raise ValueError('Blind episode permits one to six model sessions')
        if session_provider is not None:
            from eegfm.agent.provider import PROVIDER
            if session_provider != PROVIDER or provider_model != 'gpt-6.1-sol' or type(provider_timeout_seconds) is not int or not 1 <= provider_timeout_seconds <= 240:
                raise ValueError('Explicit audited provider and bounded model required')
        self.session_provider, self.provider_timeout_seconds = session_provider, provider_timeout_seconds
        adapter = _AdapterIdentity('delegated-audited', provider_model) if session_provider else _AdapterIdentity()
        super().__init__(controller.run_id, adapter, run_path=controller.run,
            task={"task_id": controller.episode_id, "compute": {"backend": "local"}},
            max_sessions=max_sessions, once=once, poll=poll, outage_max=600, session_timeout=900)

    def loop(self) -> int:
        """Hold a lifetime lease, then use the original Driver.loop scheduler."""
        import fcntl
        with (self.run/'bridge-driver.lock').open('a') as lease:
            try:
                fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ControllerAlreadyRunning('Another controller owns this episode') from error
            try:
                if self.session_provider is not None:
                    from eegfm.agent.provider import recover_completed_reservations
                    recover_completed_reservations(self.controller)
                self.controller.guard_crash_resume()
                return super().loop()
            finally:
                fcntl.flock(lease,fcntl.LOCK_UN)

    def session(self, state: dict[str, Any]) -> dict[str, Any]:
        before = self.controller.projection()["state"]["version"]
        reservation_id = self.controller.reserve_session(self.max_sessions, **(
            {'provider': self.session_provider, 'timeout_seconds': self.provider_timeout_seconds} if self.session_provider else {}))
        projection = self.controller.projection()
        if self.session_provider:
            projection['provider_session'] = {'reservation_id': reservation_id,
                'timeout_seconds': self.provider_timeout_seconds, 'provider': self.session_provider}
        receipt = self.launch(projection)
        record = self.controller.record_session(receipt,reservation_id=reservation_id)
        if record["ok"]:
            requests = record.get('requests', []) if self.session_provider else receipt.get("requests", [])
            if not isinstance(requests, list) or len(requests) > 16:
                raise ValueError("Invalid request batch")
            for request in requests:
                try:
                    self.controller.handle(request)
                except (ValueError, OSError) as error:
                    self.controller.reject_request(request, type(error).__name__)
        record["progressed"] = self.controller.projection()["state"]["version"] != before
        return record

    def review_ready(self, state: dict[str, Any]) -> bool:
        if self.reviewer is None:
            return False
        self.controller.review(**self.reviewer(self.controller.projection()))
        return True

    def refresh_jobs(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        return self.controller.poll_jobs()

    def jobs_finished(self, records: list[dict[str, Any]]) -> None:
        # poll_jobs already records controller-authoritative state and metrics.
        return None

    def validate_done(self) -> None:
        self.controller.validate_done()

    def transition(self, status: str, note: str, actor: str = "driver") -> None:
        if status != "blocked" or actor != "driver":
            raise ValueError("Unexpected trusted driver transition")
        self.controller.block(note)
