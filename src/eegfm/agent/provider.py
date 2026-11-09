"""Opt-in delegated coding sessions: durable mailbox, staging and audited receipts.

This does not launch models or execute authored Python. A trusted root launches
the declared fresh context and passively qualifies its complete native record.
The model boundary is audited tool use, not OS isolation or memory-free input.
"""
from __future__ import annotations

from contextlib import contextmanager, closing
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import time
from typing import Any, Iterator

from eegfm.agent.budget import write_atomic
from eegfm.evaluation.bundle import canonical_bytes, digest_file, safe_relative, verify_public_bundle

PROVIDER = "delegated_audited_v1"
MAX_CHUNK = 4096


def _id(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", value) is None:
        raise ValueError("Invalid provider identifier")
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _regular(path: Path, *, directory: bool = False) -> Path:
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError("Provider links forbidden")
    if directory:
        if not path.is_dir():
            raise ValueError("Expected provider directory")
    elif not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Expected regular single-link provider file")
    return path


def _relative(root: Path, relative: str) -> Path:
    parts = safe_relative(relative).parts
    if any(part.startswith(".") for part in parts):
        raise ValueError("Hidden provider paths forbidden")
    path = root
    for part in parts:
        path /= part
        if path.is_symlink():
            raise ValueError("Provider links forbidden")
    path.resolve().relative_to(root.resolve())
    return path


def tree_manifest(root: Path) -> list[dict[str, Any]]:
    _regular(root, directory=True)
    entries, total = [], 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Provider source links forbidden")
        if path.is_dir():
            continue
        _regular(path)
        name = path.relative_to(root).as_posix()
        _relative(root, name)
        total += path.stat().st_size
        if len(entries) >= 256 or total > 64 * 1024**2:
            raise ValueError("Provider source tree exceeds candidate cap")
        entries.append({"path": name, "bytes": path.stat().st_size, "sha256": digest_file(path)})
    return entries


class ProviderMailbox:
    """Trusted root operations are separate methods, never public capabilities."""
    def __init__(self, *, root: Path, case_root: Path, public_root: Path,
                 enrollment: dict[str, Any], workbench_factory: Any = None) -> None:
        self.root, self.case, self.public = Path(root).absolute(), Path(case_root).absolute(), Path(public_root).absolute()
        if self.root == self.case or self.root in self.case.parents or self.case in self.root.parents:
            raise ValueError("Provider control must be outside the case")
        _regular(self.case, directory=True)
        _regular(self.public, directory=True)
        manifest = verify_public_bundle(self.public)
        required = {"episode_id", "run_id", "model", "effort", "parent_thread", "agent_prefix", "session_limit",
                    "session_timeout_seconds", "gateway", "inherited_context"}
        if not required <= set(enrollment) or set(enrollment) - required - {'study_disclosure', 'trace_export'}:
            raise ValueError("Explicit provider enrollment fields required")
        for name in ("episode_id", "run_id"):
            _id(enrollment[name])
        if (enrollment["model"] != "gpt-6.1-sol" or enrollment["effort"] not in {"medium", "high"}
                or type(enrollment["session_limit"]) is not int or not 1 <= enrollment["session_limit"] <= 6
                or type(enrollment["session_timeout_seconds"]) is not int or not 1 <= enrollment["session_timeout_seconds"] <= 240
                or not re.fullmatch(r"/root/[A-Za-z0-9_-]+", enrollment["agent_prefix"])):
            raise ValueError("Invalid frozen provider model/budget/context")
        inherited = enrollment["inherited_context"]
        if (not isinstance(inherited, dict) or set(inherited) != {"memory_summary_sha256", "disclosure", "initial_messages"}
                or re.fullmatch(r"[0-9a-f]{64}", inherited.get("memory_summary_sha256", "")) is None
                or not isinstance(inherited["disclosure"], str) or not inherited["disclosure"].strip()):
            raise ValueError("Common inherited context must be bound and disclosed")
        if not isinstance(inherited['initial_messages'], list) or not inherited['initial_messages']:
            raise ValueError('Prospective complete initial-input profile required')
        for row in inherited['initial_messages']:
            if (not isinstance(row, dict) or set(row) != {'role', 'kinds', 'content_sha256'}
                    or row['role'] not in {'system', 'developer', 'user'} or not isinstance(row['kinds'], list)
                    or re.fullmatch(r'[0-9a-f]{64}', row['content_sha256']) is None):
                raise ValueError('Invalid prospective initial-input profile')
        gateway = enrollment["gateway"]
        if (not isinstance(gateway, dict) or set(gateway) != {"script", "workdir"}
                or any(not isinstance(value, str) or re.fullmatch(r"[A-Za-z]:/[A-Za-z0-9_./-]+", value) is None for value in gateway.values())):
            raise ValueError("Fixed Windows gateway paths required")
        if 'trace_export' in enrollment:
            from eegfm.agent.provider_export import validate_binding
            validate_binding(enrollment)
        self.identity = {**enrollment, "case_root": str(self.case.resolve()), "public_manifest_sha256": digest_file(self.public / "PUBLIC_MANIFEST.json"),
                         "provider_source_sha256": digest_file(Path(__file__)),
                         "trace_verifier_source_sha256": digest_file(Path(__file__).with_name('provider_trace.py')),
                         "resource_tier": manifest["resource_tier"]}
        self.workbench_factory = workbench_factory
        self.root.mkdir(parents=True, exist_ok=True)
        _regular(self.root, directory=True)
        for name in ("sessions", "receipts", "audits"):
            (self.root / name).mkdir(exist_ok=True)
        binding = self.root / "ENROLLMENT.json"
        if binding.exists():
            if json.loads(_regular(binding).read_text()) != self.identity:
                raise ValueError("Provider enrollment drift")
        else:
            with binding.open("xb") as stream:
                stream.write(canonical_bytes(self.identity))
        self.database = self.root / "mailbox.sqlite3"
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS requests(session TEXT,id TEXT,digest TEXT,request TEXT,response TEXT,PRIMARY KEY(session,id))")
            db.execute("CREATE TABLE IF NOT EXISTS deliveries(sequence INTEGER PRIMARY KEY,session TEXT,request TEXT,response TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS fits(session TEXT,id TEXT,identity TEXT,status TEXT,PRIMARY KEY(session,id))")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.database, timeout=30)) as db, db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db

    def verify(self) -> None:
        if (json.loads(_regular(self.root / "ENROLLMENT.json").read_text()) != self.identity
                or digest_file(Path(__file__)) != self.identity["provider_source_sha256"]
                or digest_file(Path(__file__).with_name('provider_trace.py')) != self.identity['trace_verifier_source_sha256']
                or digest_file(self.public / "PUBLIC_MANIFEST.json") != self.identity["public_manifest_sha256"]):
            raise ValueError("Frozen provider source/public binding changed")
        verify_public_bundle(self.public)
        if 'trace_export' in self.identity:
            from eegfm.agent.provider_export import validate_binding
            validate_binding(self.identity)

    def _session(self, db: sqlite3.Connection, identifier: str) -> dict:
        row = db.execute("SELECT value FROM sessions WHERE id=?", (_id(identifier),)).fetchone()
        if row is None:
            raise ValueError("Unknown provider session")
        return json.loads(row[0])

    def _save_session(self, db: sqlite3.Connection, value: dict) -> None:
        db.execute("UPDATE sessions SET value=? WHERE id=?", (json.dumps(value, allow_nan=False), value["session_id"]))

    def session(self, identifier: str) -> dict:
        self.verify()
        with self.transaction() as db:
            return self._session(db, identifier)

    def publish(self, identifier: str, projection: dict, *, timeout_seconds: int) -> dict:
        self.verify()
        _id(identifier)
        if (type(timeout_seconds) is not int or not 1 <= timeout_seconds <= self.identity["session_timeout_seconds"]
                or projection.get("episode_id") != self.identity["episode_id"] or projection.get("run_id") != self.identity["run_id"]):
            raise ValueError("Provider reservation/projection mismatch")
        bound = {"session_id": identifier, "projection": projection, "timeout_seconds": timeout_seconds,
                 "agent_path": self.identity["agent_prefix"] + "_" + identifier.replace("-", "_")}
        with self.transaction() as db:
            row = db.execute("SELECT value FROM sessions WHERE id=?", (identifier,)).fetchone()
            if row:
                retained = json.loads(row[0])
                if any(retained.get(key) != value for key, value in bound.items()):
                    raise ValueError("Provider reservation reused with changed identity")
                return retained["published"]
            if db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] >= self.identity["session_limit"]:
                raise ValueError("Provider session budget exhausted")
            directory = self.root / "sessions" / identifier
            pending = directory / "case" / "output"
            pending.mkdir(parents=True, exist_ok=False)
            original = tree_manifest(self.case / "output")
            for entry in original:
                target = _relative(pending, entry["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.case / "output" / entry["path"], target)
                if digest_file(target) != entry["sha256"]:
                    raise ValueError("Own output changed during provider snapshot")
            published = {"session_id": identifier, "agent_path": bound["agent_path"], "timeout_seconds": timeout_seconds,
                         "bootstrap": bootstrap(self.identity, identifier)}
            state = {**bound, "published": published, "original_manifest": original, "started_epoch": time.time(),
                     "status": "open", "task_read": False, "uploads": {}, "written_bytes": 0,
                     "fit_jobs": {}, "sealed": None, "registered_context": None, "receipt_sha256": None}
            db.execute("INSERT INTO sessions VALUES(?,?)", (identifier, json.dumps(state)))
            write_atomic(directory / "PUBLIC_RESERVATION.json", published)
            return published

    def register_context(self, identifier: str, *, context_id: str, trace_path: Path,
                         trusted_admin_initial: dict | None = None, export_source: dict | None = None) -> None:
        """Root-only mapping, not an operation accepted by handle()."""
        self.verify()
        session = self.session(identifier)
        sanitized = 'trace_export' in self.identity
        if (trusted_admin_initial is not None) != sanitized or (export_source is not None) != sanitized:
            raise ValueError('Initial audit transport differs from enrollment')
        audit = trusted_admin_initial if trusted_admin_initial is not None else audit_initial_context(
            trace_path, identity=self.identity, agent_path=session['agent_path'], context_id=context_id, session_id=identifier)
        if not audit['valid']:
            raise ValueError('Native initial context differs from prospective enrollment')
        audit_path = self.root / 'audits' / f'{identifier}-initial.json'
        value = {"context_id": context_id, "trace_path": str(Path(trace_path).resolve())}
        if export_source is not None:
            value['export_source'] = export_source
        with self.transaction() as db:
            session = self._session(db, identifier)
            if session["registered_context"] is not None:
                previous = session['registered_context']
                if (previous != {**value, 'initial_audit_sha256': digest_file(_regular(audit_path))}
                        or json.loads(audit_path.read_text(encoding='utf-8')) != audit):
                    raise ValueError("Context reservation cannot be replaced")
                return
            write_atomic(audit_path, audit)
            value['initial_audit_sha256'] = digest_file(audit_path)
            session["registered_context"] = value
            pending = list(db.execute('SELECT id,digest,request FROM requests WHERE session=? AND response IS NULL', (identifier,)))
            for request_id, digest, raw in pending:
                request = json.loads(raw)
                if request['operation'] != 'task' or request['payload']:
                    raise ValueError('Only the deferred public task may await context admission')
                result = self._action(session, 'task', {})
                response = {'request_id': request_id, 'request_sha256': digest, 'status': 'ok', 'result': result}
                db.execute('UPDATE requests SET response=? WHERE session=? AND id=?', (json.dumps(response), identifier, request_id))
            self._save_session(db, session)

    def _pending_root(self, identifier: str) -> Path:
        return self.root / "sessions" / _id(identifier) / "case" / "output"

    def handle(self, identifier: str, request: dict) -> dict:
        self.verify()
        if not isinstance(request, dict) or set(request) != {"request_id", "operation", "payload"}:
            raise ValueError("Provider requests have fixed fields")
        request_id = _id(request["request_id"])
        raw = canonical_bytes(request)
        if len(raw) > 8192:
            raise ValueError("Provider request exceeds byte cap")
        request = json.loads(raw)
        digest = hashlib.sha256(raw).hexdigest()
        with self.transaction() as db:
            session = self._session(db, identifier)
            previous = db.execute("SELECT digest,response FROM requests WHERE session=? AND id=?", (identifier, request_id)).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ValueError("Gateway request ID reused with changed body")
                response = json.loads(previous[1]) if previous[1] else {"request_id": request_id, "request_sha256": digest,
                    "status": "uncertain" if session['registered_context'] else 'awaiting_context_admission'}
                db.execute("INSERT INTO deliveries(session,request,response) VALUES(?,?,?)", (identifier, raw.decode(), json.dumps(response)))
                return response
            if db.execute("SELECT COUNT(*) FROM requests WHERE session=?", (identifier,)).fetchone()[0] >= 96:
                raise ValueError("Gateway operation budget exhausted")
            db.execute("INSERT INTO requests VALUES(?,?,?,?,NULL)", (identifier, request_id, digest, raw.decode()))
            if session['registered_context'] is None:
                if request['operation'] == 'task' and request['payload'] == {}:
                    response = {'request_id': request_id, 'request_sha256': digest, 'status': 'awaiting_context_admission'}
                else:
                    response = {'request_id': request_id, 'request_sha256': digest, 'status': 'rejected', 'error_type': 'ContextNotAdmitted'}
                    db.execute('UPDATE requests SET response=? WHERE session=? AND id=?', (json.dumps(response), identifier, request_id))
                db.execute('INSERT INTO deliveries(session,request,response) VALUES(?,?,?)', (identifier, raw.decode(), json.dumps(response)))
                return response
        try:
            if time.time() > session["started_epoch"] + session["timeout_seconds"]:
                raise ValueError("Provider session deadline reached")
            result = self._action(session, request["operation"], request["payload"])
            response = {"request_id": request_id, "request_sha256": digest, "status": "ok", "result": result}
        except (ValueError, OSError, KeyError, TypeError) as error:
            response = {"request_id": request_id, "request_sha256": digest, "status": "rejected", "error_type": type(error).__name__}
        with self.transaction() as db:
            self._save_session(db, session)
            db.execute("UPDATE requests SET response=? WHERE session=? AND id=?", (json.dumps(response), identifier, request_id))
            db.execute("INSERT INTO deliveries(session,request,response) VALUES(?,?,?)", (identifier, raw.decode(), json.dumps(response)))
        return response

    def _action(self, session: dict, operation: str, payload: Any) -> Any:
        if not isinstance(payload, dict):
            raise ValueError("Gateway payload must be object")
        pending = self._pending_root(session["session_id"])
        if operation == "request_status" and set(payload) == {"request_id"}:
            with self.transaction() as db:
                row = db.execute("SELECT response FROM requests WHERE session=? AND id=?", (session["session_id"], _id(payload["request_id"]))).fetchone()
            return {"response": json.loads(row[0]) if row and row[0] else None, "state": "complete" if row and row[0] else "uncertain"}
        if session["status"] != "open":
            raise ValueError("Provider session is sealed")
        if operation == "task" and not payload:
            if session["task_read"]:
                raise ValueError("Task is read once")
            session["task_read"] = True
            manifest = verify_public_bundle(self.public)
            return {"session_id": session["session_id"], "projection": session["projection"], "files": manifest["files"],
                    "own_files": tree_manifest(pending), "inherited_context": {key:self.identity['inherited_context'][key] for key in ('memory_summary_sha256', 'disclosure')},
                    'boundary_override': 'The native OS-isolation/global-memory-unavailable/process-cleanup descriptions in copied TASK/INTERFACE are superseded for this opted-in provider. Common inherited platform/project history is prospectively enrolled; requests are ingested only after a complete delegated-context/gateway audit. A typed receipt is not native-process isolation. Candidate fitting/inference still execute only in the separate restricted scientific Docker worker.',
                    'study_disclosure': self.identity.get('study_disclosure', self.identity['inherited_context']['disclosure']),
                    "instructions": "Use only the exact gateway and poll templates. Read declared public TASK/INTERFACE/API/schema and optional skill. Author source with UTF-8 chunks <=4096 bytes. Each write_chunk returns cumulative bytes and SHA256; seal_file uses that final returned hash, so no other hashing tool is needed. Upload the JSON array of <=16 existing controller requests as requests.json, seal that file, then seal_session with its path and returned SHA256 after public fitting finishes. Return exactly SESSION_SEALED. Every gateway envelope has request_id/operation/payload and is <=8192 encoded JSON bytes. This is an audited tool context with common inherited platform history, not OS isolation or a memory-free blind evaluation.",
                    "call_template": call_template(self.identity, session["session_id"], "<STRICT_JSON_LITERAL>"),
                    "operations": {"task": {}, "read_public": {"path": "declared path", "offset": 0},
                        "read_own": {"path": "own relative path", "offset": 0},
                        "write_chunk": {"path": "candidate/fit.py", "offset": 0, "text": "UTF-8 text <=4096 bytes"},
                        "seal_file": {"path": "candidate/fit.py", "sha256": "whole-file SHA256"},
                        "fit_submit": {"job_id": "fit-1", "candidate_dir": "candidate"}, "fit_poll": {"job_id": "fit-1"},
                        "request_status": {"request_id": "the original gateway request ID"},
                        "seal_session": {"requests_path": "requests.json", "sha256": "sealed request-file SHA256"}},
                    "poll_template": poll_template(123456)}
        if not session["task_read"]:
            raise ValueError("Read task before coding")
        if operation in {"read_public", "read_own"} and set(payload) == {"path", "offset"}:
            path = _relative(self.public if operation == "read_public" else pending, payload["path"])
            _regular(path)
            if operation == "read_public" and payload["path"] not in {entry["path"] for entry in verify_public_bundle(self.public)["files"]}:
                raise ValueError("Undeclared public resource")
            if type(payload["offset"]) is not int or payload["offset"] < 0:
                raise ValueError("Invalid source offset")
            if path.suffix == ".npz":
                import numpy as np
                if path.stat().st_size > 64 * 1024**2:
                    raise ValueError("Public numeric descriptor cap")
                with np.load(path, allow_pickle=False) as arrays:
                    return {"path": payload["path"], "sha256": digest_file(path),
                            "arrays": {name: {"shape": list(arrays[name].shape), "dtype": str(arrays[name].dtype)} for name in arrays.files}}
            text = path.read_text(encoding="utf-8")
            return {"path": payload["path"], "sha256": digest_file(path), "offset": payload["offset"],
                    "text": text[payload["offset"]:payload["offset"] + 6000], "characters": len(text)}
        if operation == "write_chunk" and set(payload) == {"path", "offset", "text"}:
            path = _relative(pending, payload["path"])
            if path.suffix not in {".py", ".json", ".md", ".txt", ".yaml"}:
                raise ValueError("Gateway authors text sources only")
            if session["projection"].get("lock") and not (payload['path'] == 'requests.json' or '/' not in payload['path'] and path.suffix == '.md'):
                raise ValueError("Only root-level reports/notes/request transport are writable after lock")
            if not isinstance(payload["text"], str) or type(payload["offset"]) is not int:
                raise ValueError("UTF-8 chunk and offset required")
            data = payload["text"].encode("utf-8")
            if any(ord(char) < 32 and char not in '\t\r\n' for char in payload['text']):
                raise ValueError('Source contains unsupported control characters')
            if len(data) > MAX_CHUNK or session["written_bytes"] + len(data) > 1024**2:
                raise ValueError("Source upload byte cap")
            upload = session["uploads"].setdefault(payload["path"], "")
            if len(upload.encode("utf-8")) != payload["offset"]:
                raise ValueError("Source chunk offset mismatch")
            session["uploads"][payload["path"]] += payload["text"]
            session["written_bytes"] += len(data)
            return {"path": payload["path"], "bytes": payload["offset"] + len(data),
                    'sha256': hashlib.sha256(session['uploads'][payload['path']].encode('utf-8')).hexdigest()}
        if operation == "seal_file" and set(payload) == {"path", "sha256"}:
            path = _relative(pending, payload["path"])
            data = session["uploads"][payload["path"]].encode("utf-8")
            if hashlib.sha256(data).hexdigest() != payload["sha256"]:
                raise ValueError("Source file hash mismatch")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".provider-tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
            del session["uploads"][payload["path"]]
            return {"path": payload["path"], "sha256": digest_file(path), "bytes": len(data)}
        if operation in {"fit_submit", "fit_poll"}:
            if self.workbench_factory is None or session["projection"].get("lock"):
                raise ValueError("Public fitting unavailable after lock or without enrollment")
            bench = self.workbench_factory(pending.parent)
            job_id = _id(payload["job_id"])
            full_id = _id(self.identity["run_id"] + "-" + session["session_id"] + "-" + job_id)
            if operation == "fit_submit" and set(payload) == {"job_id", "candidate_dir"}:
                from eegfm.evaluation.public_workbench import source_manifest
                source = _relative(pending, payload['candidate_dir'])
                fit_identity = {'candidate_dir': payload['candidate_dir'], 'source_manifest_sha256': _hash(source_manifest(source))}
                with self.transaction() as db:
                    row = db.execute('SELECT identity FROM fits WHERE session=? AND id=?', (session['session_id'], job_id)).fetchone()
                    if row and json.loads(row[0]) != fit_identity:
                        raise ValueError('Public fit reservation changed source')
                    if not row:
                        require_time = getattr(bench, 'require_submit_time', None)
                        if require_time is not None:
                            require_time()
                        if db.execute('SELECT COUNT(*) FROM fits').fetchone()[0] >= 2:
                            raise ValueError('Episode-wide public fit budget exhausted')
                        db.execute('INSERT INTO fits VALUES(?,?,?,?)', (session['session_id'], job_id, json.dumps(fit_identity), 'waiting'))
                    session['fit_jobs'][job_id] = 'waiting'
                    self._save_session(db, session)
                if not row:
                    result = bench.submit(full_id, payload["candidate_dir"])
                else:
                    try:
                        result = bench.poll(full_id)
                    except ValueError:
                        if (bench.private / f'{full_id}.json').exists():
                            raise
                        result = {'job_id': full_id, 'status': 'waiting'}
            elif operation == "fit_poll" and set(payload) == {"job_id"} and job_id in session["fit_jobs"]:
                try:
                    result = bench.poll(full_id)
                except ValueError:
                    if (bench.private / f'{full_id}.json').exists():
                        raise
                    result = {'job_id': full_id, 'status': 'waiting'}
            else:
                raise ValueError("Invalid public fitting request")
            session["fit_jobs"][job_id] = result["status"]
            with self.transaction() as db:
                db.execute('UPDATE fits SET status=? WHERE session=? AND id=?', (result['status'], session['session_id'], job_id))
            return result
        if operation == "seal_session" and set(payload) in ({"requests"}, {'requests_path', 'sha256'}):
            if 'requests_path' in payload:
                request_file = _regular(_relative(pending, payload['requests_path']))
                if request_file.stat().st_size > 1024**2 or digest_file(request_file) != payload['sha256']:
                    raise ValueError('Sealed request-file binding mismatch')
                requests = json.loads(request_file.read_text(encoding='utf-8'))
            else:
                requests = payload["requests"]
            if (session["uploads"] or any(value == "waiting" for value in session["fit_jobs"].values())
                    or not isinstance(requests, list) or len(requests) > 16 or len(canonical_bytes(requests)) > 1024**2):
                raise ValueError("Unfinished source/fitting or oversized batch")
            ids = set()
            for request in requests:
                if (not isinstance(request, dict) or set(request) != {"request_id", "episode_id", "operation", "payload"}
                        or request["episode_id"] != self.identity["episode_id"] or len(canonical_bytes(request)) > 65536
                        or _id(request["request_id"]) in ids):
                    raise ValueError("Invalid controller request batch")
                ids.add(request["request_id"])
            sealed = {"requests": requests, "source_manifest": tree_manifest(pending)}
            session["sealed"] = sealed
            session["status"] = "sealed"
            return {"sealed_batch_sha256": _hash(sealed), "request_count": len(requests),
                    "authored_manifest_sha256": _hash(sealed["source_manifest"])}
        raise ValueError("Not a gateway capability")

    def deliveries(self, identifier: str) -> list[dict]:
        with self.transaction() as db:
            return [{"request": json.loads(row[0]), "response": json.loads(row[1])} for row in db.execute(
                "SELECT request,response FROM deliveries WHERE session=? ORDER BY sequence", (_id(identifier),))]

    def accept_trace(self, identifier: str, trace_path: Path, *, trusted_admin_initial: dict | None = None,
                     export_source: dict | None = None) -> dict:
        """Root-only passive verification; no arbitrary successful audit injection."""
        from eegfm.agent.provider_trace import audit_native_context
        self.verify()
        session = self.session(identifier)
        sanitized = 'trace_export' in self.identity
        if (trusted_admin_initial is not None) != sanitized or (export_source is not None) != sanitized:
            raise ValueError('Complete audit transport differs from enrollment')
        if session['receipt_sha256']:
            return {'provider': PROVIDER, 'receipt_path': str(self.root / 'receipts' / f'{identifier}.json'),
                    'receipt_sha256': session['receipt_sha256']}
        if session['status'] != 'sealed' or not session['registered_context']:
            raise ValueError('Completed sealed source/context required')
        initial_path = self.root / 'audits' / f'{identifier}-initial.json'
        if digest_file(_regular(initial_path)) != session['registered_context']['initial_audit_sha256']:
            raise ValueError('Initial context admission changed')
        audit = audit_native_context(trace_path, self.identity, session, self.deliveries(identifier), trusted_admin_initial=trusted_admin_initial)
        if audit['initial_context'] != json.loads(initial_path.read_text()):
            raise ValueError('Native initial inputs changed after admission')
        audit_path = self.root / 'audits' / f'{identifier}.json'
        if export_source is not None:
            audit['trace_export'] = {'binding': self.identity['trace_export'], 'source': export_source,
                                     'admitted_source': session['registered_context']['export_source']}
        write_atomic(audit_path, audit)
        if not audit['valid']:
            raise ValueError('Complete native provider trace failed qualification; reservation remains unresolved')
        pending = self._pending_root(identifier)
        sealed = session['sealed']
        if tree_manifest(pending) != sealed['source_manifest'] or tree_manifest(self.case / 'output') != session['original_manifest']:
            raise ValueError('Staged or current case changed before audited promotion')
        for entry in sealed['source_manifest']:
            source = _regular(_relative(pending, entry['path']))
            destination = _relative(self.case / 'output', entry['path'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + '.provider-tmp')
            shutil.copyfile(source, temporary)
            if digest_file(temporary) != entry['sha256']:
                raise ValueError('Audited source changed during case promotion')
            temporary.replace(destination)
        receipt = {'provider': PROVIDER, 'reservation_id': identifier, 'episode_id': self.identity['episode_id'],
                   'run_id': self.identity['run_id'], 'model': self.identity['model'], 'effort': self.identity['effort'],
                   'status': 'completed', 'allocated_timeout_seconds': session['timeout_seconds'],
                   'model_context_id': session['registered_context']['context_id'],
                   'trusted_audit_sha256': digest_file(audit_path), 'trace_sha256': audit['trace_sha256'],
                   'authored_manifest_sha256': _hash(sealed['source_manifest']), 'sealed_batch_sha256': _hash(sealed),
                   'gateway_transports_terminal': True, 'requests': sealed['requests']}
        receipt_path = self.root / 'receipts' / f'{identifier}.json'
        with receipt_path.open('xb') as stream:
            stream.write(canonical_bytes(receipt))
        with self.transaction() as db:
            current = self._session(db, identifier)
            if current['sealed'] != sealed or current['receipt_sha256'] is not None:
                raise ValueError('Provider session changed during audit')
            current['receipt_sha256'] = digest_file(receipt_path)
            current['status'] = 'accepted'
            self._save_session(db, current)
        return {'provider': PROVIDER, 'receipt_path': str(receipt_path), 'receipt_sha256': digest_file(receipt_path)}


class ProviderLaunch:
    """ResearchDriver callable. Root passively services the durable model outbox."""
    def __init__(self, mailbox: ProviderMailbox, *, poll_seconds: float = .5,
                 budget_path: Path | None = None, call_ids: list[str] | None = None) -> None:
        self.mailbox, self.poll_seconds = mailbox, poll_seconds
        self.budget_path, self.call_ids = budget_path, call_ids

    def __call__(self, projection: dict) -> dict:
        reservation = projection.get('provider_session', {})
        if reservation.get('provider') != PROVIDER:
            raise ValueError('Audited provider reservation required')
        identifier = reservation['reservation_id']
        timeout = reservation['timeout_seconds']
        call_id, running = None, False
        if self.budget_path is not None:
            from eegfm.agent.budget import reserve_call
            number = int(identifier.removeprefix('session-')) - 1
            if self.call_ids is None or not 0 <= number < len(self.call_ids):
                raise ValueError('Declared model call allocation missing')
            call_id = self.call_ids[number]
            reserve_call(self.budget_path, call_id, 'actor', timeout)
        self.mailbox.publish(identifier, projection, timeout_seconds=timeout)
        while True:
            state = self.mailbox.session(identifier)
            if call_id is not None and state['registered_context'] and not running:
                from eegfm.agent.budget import mark_call
                mark_call(self.budget_path, call_id, 'running', provider=PROVIDER,
                          model_context_id=state['registered_context']['context_id'])
                running = True
            if state['receipt_sha256']:
                if call_id is not None:
                    from eegfm.agent.budget import mark_call
                    if not running:
                        raise ValueError('Completed model receipt lacks registered context')
                    mark_call(self.budget_path, call_id, 'completed', provider=PROVIDER,
                              receipt_sha256=state['receipt_sha256'])
                return {'provider': PROVIDER, 'receipt_path': str(self.mailbox.root / 'receipts' / f'{identifier}.json'),
                        'receipt_sha256': state['receipt_sha256']}
            if time.time() >= state['started_epoch'] + timeout:
                # Never fabricate process cleanup or free an unresolved model
                # slot. Existing controller crash-resume guard quarantines it.
                raise RuntimeError('Delegated model/transport outcome unresolved; trusted context cleanup required')
            time.sleep(min(self.poll_seconds, max(0., state['started_epoch'] + timeout - time.time())))


def command(identity: dict, session: str) -> str:
    return f"python -X utf8 {identity['gateway']['script']} call --session {_id(session)} --payload "


def call_template(identity: dict, session: str, literal: str) -> str:
    return ("const request = " + literal + "; const payload = encodeURIComponent(JSON.stringify(request)).replace(/[!'()*]/g,c=>'%'"
            "+c.charCodeAt(0).toString(16).toUpperCase()); const result = await tools.exec_command({cmd:'"
            + command(identity, session) + "'+payload,workdir:'" + identity["gateway"]["workdir"]
            + "',max_output_tokens:9000,yield_time_ms:1000}); text(result);")


def poll_template(session_id: int) -> str:
    if type(session_id) is not int or session_id <= 0:
        raise ValueError("Positive native transport session ID required")
    return ("const result = await tools.write_stdin({session_id:" + str(session_id)
            + ",chars:'',max_output_tokens:9000,yield_time_ms:1000}); text(result);")


def bootstrap(identity: dict, identifier: str) -> str:
    request = {"request_id": "task", "operation": "task", "payload": {}}
    return ("Use only this episode's exact audited gateway. Do not use any other tool/command, read files or memory directly, browse, or delegate. "
            "Platform history is automatically inherited and prospectively disclosed; this is workflow development, not memory-free or OS-isolated evaluation. "
            "If the native result returns session_id, poll only that ID with the shown empty-input poll template; never resubmit an uncertain mutation. "
            "If task returns awaiting_context_admission, wait and query request_status for request_id task; root passively verifies initial inherited context before releasing it. "
            "After sealing the authored source/request batch, return exactly SESSION_SEALED.\n"
            + call_template(identity, identifier, canonical_bytes(request).decode().strip()) + "\nPOLL TEMPLATE (replace only observed positive session_id):\n" + poll_template(123456))


def _trace_records(path: Path, *, allow_partial: bool = True) -> list[dict]:
    return _trace_records_from_bytes(_regular(Path(path)).read_bytes(), allow_partial=allow_partial)


def _trace_records_from_bytes(raw: bytes, *, allow_partial: bool) -> list[dict]:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('Duplicate native trace key')
            result[key] = value
        return result
    records = []
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        try:
            record = json.loads(line, object_pairs_hook=pairs)
            if not isinstance(record, dict):
                raise ValueError('Native trace object required')
            records.append(record)
        except ValueError:
            if allow_partial and index == len(lines) - 1 and not line.endswith(b'\n'):
                break
            raise
    return records


def audit_initial_context(path: Path, *, identity: dict, agent_path: str, context_id: str, session_id: str | None = None) -> dict:
    """Private hashes only. This audit runs before public task/fitting admission."""
    return _audit_initial_records(_trace_records(path), identity=identity, agent_path=agent_path, context_id=context_id, session_id=session_id)


def _audit_initial_records(records: list[dict], *, identity: dict, agent_path: str, context_id: str, session_id: str | None) -> dict:
    issues, messages, summaries, contexts = [], [], [], []
    user_inputs, bootstrap_inputs = 0, 0
    meta = records[0].get('payload', {}) if records and records[0].get('type') == 'session_meta' else {}
    if meta.get('id') != context_id or meta.get('agent_path') != agent_path or meta.get('parent_thread_id') != identity['parent_thread']:
        issues.append('native initial context identity mismatch')
    known = {'model.base_instructions', 'memories.instructions', 'host_skills.instructions', 'permissions.instructions',
             'collaboration_mode.instructions', 'tools.deferred_namespaces', 'multi_agent.role_instructions', 'multi_agent.mode_instructions'}
    known_developer = known | {'generic.developer_instructions', 'plugins.recommendations'}
    variant_mode = 'context_variants' in identity.get('trace_export', {})
    metadata = []
    if variant_mode:
        from eegfm.agent.provider_export import initial_metadata_sha256, matches_context_bundle, validate_binding
        validate_binding(identity)
    for record in records:
        item = record.get('payload', {})
        if record.get('type') == 'response_item' and item.get('type') in {'function_call', 'custom_tool_call'}:
            break
        if variant_mode:
            kind = record.get('type')
            if kind == 'world_state' or kind == 'response_item' and item.get('type') == 'additional_tools':
                metadata_kind = 'world_state' if kind == 'world_state' else 'additional_tools'
                try:
                    metadata.append({'kind': metadata_kind, 'payload_sha256': initial_metadata_sha256(metadata_kind, item)})
                except ValueError:
                    issues.append('Invalid initial instruction-bearing metadata')
        if record.get('type') == 'turn_context':
            effort = item.get('effort') or item.get('collaboration_mode', {}).get('settings', {}).get('reasoning_effort')
            contexts.append({'model': item.get('model'), 'effort': effort})
        if record.get('type') == 'response_item' and item.get('type') == 'message' and item.get('role') == 'user':
            user_inputs += 1
            content = item.get('content', [])
            kinds = item.get('internal_chat_message_metadata_passthrough', {}).get('content_item_kinds', [])
            if (user_inputs > 1 or kinds != ['environments.environment_context'] or len(content) != 1
                    or content[0].get('type') != 'input_text' or not content[0].get('text', '').strip().startswith('<environment_context>')
                    or not content[0].get('text', '').strip().endswith('</environment_context>')):
                issues.append('undeclared initial user input')
            messages.append({'role': 'user', 'kinds': kinds, 'text_sha256': _hash(content), 'content_sha256': _hash(content)})
        if record.get('type') == 'response_item' and item.get('type') == 'agent_message':
            bootstrap_inputs += 1
            content = item.get('content', [])
            header = f'Message Type: NEW_TASK\nTask name: {agent_path}\nSender: /root\nPayload:\n'
            expected_bootstrap = bootstrap(identity, session_id or 'session-01')
            if (bootstrap_inputs > 1 or item.get('author') != '/root' or item.get('recipient') != agent_path
                    or len(content) != 2 or content[0].get('text') != header
                    or not (content[1].get('type') == 'encrypted_content' and isinstance(content[1].get('encrypted_content'), str)
                            or content[1].get('type') == 'input_text' and content[1].get('text') == expected_bootstrap)):
                issues.append('undeclared initial bootstrap input')
            messages.append({'role': 'agent_message', 'kinds': ['declared_bootstrap'], 'text_sha256': _hash(content), 'content_sha256': _hash(content)})
        if record.get('type') == 'response_item' and item.get('type') == 'message' and item.get('role') in {'developer', 'system'}:
            kinds = item.get('internal_chat_message_metadata_passthrough', {}).get('content_item_kinds', [])
            allowed_kinds = known_developer if item['role'] == 'developer' else known
            if not kinds or any(kind not in allowed_kinds for kind in kinds):
                issues.append('unexpected initial platform input kind')
            text = ''.join(part.get('text', '') for part in item.get('content', []) if part.get('type') == 'input_text')
            messages.append({'role': item['role'], 'kinds': kinds, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                             'content_sha256': _hash(item.get('content', []))})
            if '========= MEMORY_SUMMARY BEGINS =========' in text:
                try:
                    body = text.split('========= MEMORY_SUMMARY BEGINS =========', 1)[1].split('========= MEMORY_SUMMARY ENDS =========', 1)[0]
                    summaries.append(hashlib.sha256(body.encode()).hexdigest())
                except IndexError:
                    issues.append('incomplete inherited context disclosure')
    if summaries != [identity['inherited_context']['memory_summary_sha256']]:
        issues.append('inherited memory summary mismatch or missing')
    actual_profile = [{key:row[key] for key in ('role', 'kinds', 'content_sha256')} for row in messages if row['role'] != 'agent_message']
    memory_hash = summaries[0] if len(summaries) == 1 else None
    profile_matches = (matches_context_bundle(identity, actual_profile, metadata, memory_hash) if variant_mode
                       else actual_profile == identity['inherited_context']['initial_messages'])
    if not profile_matches or user_inputs != 1 or bootstrap_inputs != 1:
        issues.append('complete initial context profile or required environment/bootstrap mismatch')
    if not contexts or any(row != {'model': identity['model'], 'effort': identity['effort']} for row in contexts):
        issues.append('initial model/effort mismatch')
    return {'valid': not issues, 'issues': issues, 'context_id': context_id, 'agent_path': agent_path,
            'initial_messages': messages, 'memory_summary_sha256': memory_hash,
            'disclosure': identity['inherited_context']['disclosure']}


def read_trusted_receipt(pointer: dict, *, controller_run: Path, reservation_id: str,
                         episode_id: str, run_id: str) -> dict:
    if not isinstance(pointer, dict) or set(pointer) != {"provider", "receipt_path", "receipt_sha256"} or pointer["provider"] != PROVIDER:
        raise ValueError("Typed delegated receipt pointer required")
    root = Path(controller_run) / "provider"
    expected = root / "receipts" / f"{_id(reservation_id)}.json"
    if Path(pointer["receipt_path"]).absolute() != expected.absolute():
        raise ValueError("Delegated receipt must be in the trusted run root")
    path = _regular(expected)
    if digest_file(path) != pointer["receipt_sha256"]:
        raise ValueError("Delegated receipt hash mismatch")
    with closing(sqlite3.connect(_regular(root / "mailbox.sqlite3"))) as db:
        row = db.execute("SELECT value FROM sessions WHERE id=?", (reservation_id,)).fetchone()
    state = json.loads(row[0]) if row else {}
    if state.get("receipt_sha256") != pointer["receipt_sha256"]:
        raise ValueError("Delegated receipt is not authoritative in the mailbox")
    receipt = json.loads(path.read_text())
    if (receipt.get("provider") != PROVIDER or receipt.get("reservation_id") != reservation_id
            or receipt.get("episode_id") != episode_id or receipt.get("run_id") != run_id):
        raise ValueError("Delegated receipt identity mismatch")
    if receipt.get("status") == "completed":
        audit = _regular(root / "audits" / f"{reservation_id}.json")
        if digest_file(audit) != receipt.get("trusted_audit_sha256") or json.loads(audit.read_text()).get("valid") is not True:
            raise ValueError("Successful delegated receipt requires its trusted audit")
    return receipt


def recover_completed_reservations(controller: Any) -> int:
    """Called only inside the existing driver's lifetime lease; never relaunch."""
    with controller._transaction() as db:
        rows = [dict(row) for row in controller._load(db)['sessions']
                if (row.get('provider') == PROVIDER or row.get('summary', {}).get('provider') == PROVIDER)
                and (row.get('status') == 'reserved' or row.get('status') == 'finished' and row.get('ok'))]
    restored = 0
    for row in rows:
        path = controller.run / 'provider/receipts' / f"{row['reservation_id']}.json"
        if not path.exists():
            continue
        pointer = {'provider': PROVIDER, 'receipt_path': str(path), 'receipt_sha256': digest_file(_regular(path))}
        if row.get('status') == 'reserved':
            requests = controller.record_session(pointer, reservation_id=row['reservation_id'])['requests']
        else:
            requests = read_trusted_receipt(pointer, controller_run=controller.run, reservation_id=row['reservation_id'],
                                            episode_id=controller.episode_id, run_id=controller.run_id)['requests']
        for request in requests:
            try:
                controller.handle(request)
            except (ValueError, OSError) as error:
                controller.reject_request(request, type(error).__name__)
        restored += 1
    return restored


def load_service(config_path: Path, config_sha256: str) -> ProviderMailbox:
    """Fixed trusted service config, loaded by the existing-account SSH channel."""
    from eegfm.evaluation.worker import FileBinding
    binding = FileBinding(config_path, config_sha256)
    config = json.loads(_regular(binding.verify()).read_text(encoding='utf-8'))
    required = {'schema_version', 'mailbox_root', 'case_root', 'public_root', 'enrollment'}
    if (not required <= set(config) or set(config) - required - {'public_fit_worker', 'public_fit_journal', 'episode_deadline_epoch'}
            or config['schema_version'] != 'audited_provider_service_v1'):
        raise ValueError('Unknown audited provider service configuration')
    for name in ('mailbox_root', 'case_root', 'public_root'):
        if not Path(config[name]).is_absolute():
            raise ValueError('Absolute provider service roots required')
    factory = None
    if 'public_fit_worker' in config:
        def factory(pending_case: Path):
            from eegfm.evaluation.ssh_worker import SshWorkerEvaluator
            from eegfm.evaluation.public_workbench import PublicWorkbench
            cloud = config['public_fit_worker']
            worker = SshWorkerEvaluator(host=cloud['host'], port=cloud['port'], user=cloud['user'],
                known_hosts=FileBinding(Path(cloud['known_hosts']['path']), cloud['known_hosts']['sha256']),
                remote_python=Path(cloud['python']), remote_code=Path(cloud['code']),
                remote_config=FileBinding(Path(cloud['config']['path']), cloud['config']['sha256']),
                journal_root=Path(config['public_fit_journal']))
            worker.deadline_epoch = config.get('episode_deadline_epoch')
            if 'trace_export' in config['enrollment']:
                remote_deadline = worker.identity.get('episode_deadline_epoch')
                if (type(remote_deadline) not in (int, float) or type(worker.deadline_epoch) not in (int, float)
                        or not 0 < remote_deadline <= worker.deadline_epoch < float('inf')):
                    raise ValueError('Sanitized provider requires a bound remote public fit deadline')
            relative = pending_case.resolve().relative_to((Path(config['mailbox_root']) / 'sessions').resolve())
            if len(relative.parts) != 2 or relative.parts[-1] != 'case':
                raise ValueError('Fit case does not belong to this provider')
            return PublicWorkbench(evaluator=worker, private_root=Path(config['mailbox_root']) / 'fit-journals' / relative.parts[0],
                case_root=pending_case, episode_id=config['enrollment']['episode_id'], run_id=config['enrollment']['run_id'],
                public_manifest_sha256=digest_file(Path(config['public_root']) / 'PUBLIC_MANIFEST.json'),
                split_manifest_sha256=worker.identity['split_manifest_sha256'])
    return ProviderMailbox(root=Path(config['mailbox_root']), case_root=Path(config['case_root']),
                           public_root=Path(config['public_root']), enrollment=config['enrollment'], workbench_factory=factory)


def service_request(mailbox: ProviderMailbox, request: dict) -> dict:
    """Public envelope cannot select an administrative method. Root is trusted."""
    if set(request) == {'session', 'request'}:
        return mailbox.handle(request['session'], request['request'])
    if request.get('admin') == 'outbox' and set(request) == {'admin'}:
        with mailbox.transaction() as db:
            return {'sessions': [json.loads(row[0])['published'] for row in db.execute('SELECT value FROM sessions ORDER BY id')]}
    if request.get('admin') == 'status' and set(request) == {'admin', 'session'}:
        state = mailbox.session(request['session'])
        keys = ('session_id', 'status', 'registered_context', 'receipt_sha256', 'fit_jobs')
        if 'trace_export' in mailbox.identity:
            keys += ('agent_path', 'started_epoch', 'timeout_seconds')
        return {key: state[key] for key in keys}
    if request.get('admin') in {'admit_sanitized', 'accept_sanitized'} and set(request) == {'admin', 'session', 'context_id', 'export'}:
        return _admin_export(mailbox, request)
    if request.get('admin') in {'admit', 'accept'} and set(request) == {'admin', 'session', 'context_id', 'trace_base64'}:
        if 'trace_export' in mailbox.identity:
            raise ValueError('Raw trace upload forbidden for sanitized enrollment')
        import base64
        encoded = request['trace_base64']
        if not isinstance(encoded, str) or len(encoded) > 24 * 1024**2:
            raise ValueError('Native trace byte cap exceeded')
        data = base64.b64decode(encoded, validate=True)
        if len(data) > 16 * 1024**2:
            raise ValueError('Native trace byte cap exceeded')
        identifier = _id(request['session'])
        mailbox.session(identifier)
        path = mailbox.root / 'sessions' / identifier / 'native.jsonl'
        temporary = path.with_suffix('.upload')
        temporary.write_bytes(data)
        temporary.replace(path)
        if request['admin'] == 'admit':
            mailbox.register_context(identifier, context_id=request['context_id'], trace_path=path)
            return {'status': 'initial_context_admitted', 'context_id': request['context_id']}
        if mailbox.session(identifier)['registered_context']['context_id'] != request['context_id']:
            raise ValueError('Root context identity changed before final audit')
        return mailbox.accept_trace(identifier, path)
    raise ValueError('Unknown provider service envelope')


def _admin_export(mailbox: ProviderMailbox, request: dict) -> dict:
    """Explicit trusted-root route for private projected native evidence."""
    from eegfm.agent.provider_export import validate_admin_export

    mailbox.verify()
    identifier = _id(request['session'])
    context_id, exported = _id(request['context_id']), request['export']
    session = mailbox.session(identifier)
    registered = session['registered_context']
    complete = request['admin'] == 'accept_sanitized'
    if complete and (not registered or registered['context_id'] != context_id or session['status'] not in {'sealed', 'accepted'}):
        raise ValueError('Sealed previously admitted context required')
    prior = registered['export_source'] if complete else None
    records, initial = validate_admin_export(exported, mailbox.identity, session, context_id=context_id, prior_source=prior)
    source = exported['source']
    directory = mailbox.root / 'sessions' / identifier
    admit_proof = directory / 'admitted-export.json'
    proof = directory / 'complete-export.json' if complete else admit_proof
    if complete:
        admitted = json.loads(_regular(admit_proof).read_text(encoding='utf-8'))
        if (source['raw_bytes'] != source['prefix_bytes'] or source['raw_sha256'] != source['prefix_sha256']
                or admitted['source'] != prior or admitted['initial_audit'] != initial
                or records[:len(admitted['records'])] != admitted['records']):
            raise ValueError('Complete projected trace does not extend the exact admitted prefix')
    raw = canonical_bytes(exported)
    if len(raw) > 16 * 1024**2:
        raise ValueError('Projected trace byte cap exceeded')
    if proof.exists():
        if _regular(proof).read_bytes() != raw:
            raise ValueError('Trusted native projection cannot be replaced')
    else:
        with proof.open('xb') as stream:
            stream.write(raw)
    path = directory / 'native.jsonl'
    if complete or registered is None:
        temporary = path.with_suffix('.upload')
        temporary.write_bytes(b''.join(canonical_bytes(row) for row in records))
        temporary.replace(path)
    if complete:
        return mailbox.accept_trace(identifier, path, trusted_admin_initial=initial, export_source=source)
    mailbox.register_context(identifier, context_id=context_id, trace_path=path, trusted_admin_initial=initial, export_source=source)
    return {'status': 'initial_context_admitted', 'context_id': context_id}


def main() -> None:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    args = parser.parse_args()
    raw = sys.stdin.buffer.read(32 * 1024**2 + 1)
    if len(raw) > 32 * 1024**2:
        raise ValueError('Provider service request too large')
    envelope = json.loads(raw)
    mailbox = load_service(args.config, args.config_sha256)
    if (not isinstance(envelope, dict) or set(envelope) != {'episode_id', 'run_id', 'body'}
            or envelope['episode_id'] != mailbox.identity['episode_id'] or envelope['run_id'] != mailbox.identity['run_id']):
        raise ValueError('Provider transport routed to another enrolled episode')
    response = service_request(mailbox, envelope['body'])
    sys.stdout.buffer.write(canonical_bytes(response) + b'\n')


if __name__ == '__main__':
    main()
