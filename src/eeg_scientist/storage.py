"""Append-only audit log, sealed predictions, atomic state, and recovery."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import cast

from .schema import ExperimentRequest, ExperimentResult, RunEvent, SealedRequest


class CorruptEventLog(RuntimeError):
    """Raised when a middle event line is corrupt or the hash chain breaks."""


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: object) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False, default=str))


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _event_hash(event_without_hash: dict[str, object]) -> str:
    return sha256_text(canonical_json(event_without_hash))


def _quarantine_partial(run_dir: Path, line: bytes) -> None:
    target = run_dir / "events.corrupt.lastline"
    with target.open("ab") as handle:
        handle.write(line)
        handle.write(b"\n")


def _truncate_partial_tail(run_dir: Path) -> None:
    log_path = run_dir / "events.jsonl"
    if not log_path.exists():
        return
    raw = log_path.read_bytes()
    if not raw or raw.endswith(b"\n"):
        return
    last_newline = raw.rfind(b"\n")
    keep = 0 if last_newline < 0 else last_newline + 1
    log_path.write_bytes(raw[:keep])


def read_events(run_dir: Path) -> list[RunEvent]:
    log_path = run_dir / "events.jsonl"
    if not log_path.exists():
        return []
    raw = log_path.read_bytes()
    lines = raw.split(b"\n")
    if raw.endswith(b"\n"):
        lines = lines[:-1]
    events: list[RunEvent] = []
    previous_hash = ""
    for position, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            is_last = position == len(lines) - 1 and not raw.endswith(b"\n")
            if is_last:
                _quarantine_partial(run_dir, line)
                continue
            raise CorruptEventLog(f"corrupt middle event line at {position}: {error}") from error
        try:
            event = RunEvent.model_validate(payload)
        except Exception as error:  # noqa: BLE001 - boundary validation
            is_last = position == len(lines) - 1 and not raw.endswith(b"\n")
            if is_last:
                _quarantine_partial(run_dir, line)
                continue
            raise CorruptEventLog(f"invalid event at {position}: {error}") from error
        if event.sequence != len(events) + 1:
            raise CorruptEventLog(f"event sequence gap at {position}: {event.sequence}")
        if event.prev_hash != previous_hash:
            raise CorruptEventLog(f"event hash chain break at {position}")
        body = {
            "sequence": event.sequence,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "payload": event.payload,
            "prev_hash": event.prev_hash,
        }
        if _event_hash(body) != event.event_hash:
            raise CorruptEventLog(f"event hash mismatch at {position}")
        previous_hash = event.event_hash
        events.append(event)
    return events


def append_event(run_dir: Path, event_type: str, payload: dict[str, object]) -> RunEvent:
    ensure_dir(run_dir)
    read_events(run_dir)
    _truncate_partial_tail(run_dir)
    events = read_events(run_dir)
    previous_hash = events[-1].event_hash if events else ""
    sequence = len(events) + 1
    body = {
        "sequence": sequence,
        "event_type": event_type,
        "timestamp": utc_now(),
        "payload": payload,
        "prev_hash": previous_hash,
    }
    event = RunEvent(**body, event_hash=_event_hash(body))
    with (run_dir / "events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(event.model_dump_json() + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


def write_state(run_dir: Path, state: object) -> None:
    payload = state.model_dump(mode="json") if hasattr(state, "model_dump") else state
    atomic_write_json(run_dir / "state.json", payload)


def load_state(run_dir: Path) -> dict[str, object] | None:
    path = run_dir / "state.json"
    if not path.exists():
        return None
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def find_sealed(run_dir: Path, request_id: str) -> SealedRequest | None:
    for event in read_events(run_dir):
        if event.event_type != "prediction_sealed" or event.payload.get("request_id") != request_id:
            continue
        canonical = event.payload.get("canonical_json")
        digest = event.payload.get("sha256")
        if not isinstance(canonical, str) or not isinstance(digest, str):
            return None
        request = ExperimentRequest.model_validate(json.loads(canonical))
        return SealedRequest(
            request=request,
            canonical_json=canonical,
            sha256=digest,
            sealed_at=event.timestamp,
            event_sequence=event.sequence,
            run_dir=str(run_dir.resolve()),
        )
    return None


def load_result(run_dir: Path, request_id: str) -> ExperimentResult | None:
    for path in sorted(run_dir.glob("result_*.json")):
        try:
            result = ExperimentResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 - skip incomplete result files
            continue
        if result.request_id == request_id:
            return result
    return None


def seal_prediction(run_dir: Path, request: ExperimentRequest) -> SealedRequest:
    existing = find_sealed(run_dir, request.request_id)
    if existing is not None:
        return existing
    canonical = canonical_json(request.model_dump(mode="json"))
    digest = sha256_text(canonical)
    event = append_event(
        run_dir,
        "prediction_sealed",
        {"request_id": request.request_id, "sha256": digest, "canonical_json": canonical},
    )
    sealed = SealedRequest(
        request=request,
        canonical_json=canonical,
        sha256=digest,
        sealed_at=event.timestamp,
        event_sequence=event.sequence,
        run_dir=str(run_dir.resolve()),
    )
    atomic_write_json(run_dir / f"prediction_{event.sequence:03d}.json", sealed.model_dump(mode="json"))
    return sealed


def verify_sealed(sealed: object) -> bool:
    run_dir_value = getattr(sealed, "run_dir", None)
    sequence = getattr(sealed, "event_sequence", None)
    digest = getattr(sealed, "sha256", None)
    request = getattr(sealed, "request", None)
    if not isinstance(run_dir_value, str) or not isinstance(sequence, int) or not isinstance(digest, str):
        return False
    if not isinstance(request, ExperimentRequest):
        return False
    run_dir = Path(run_dir_value)
    events = read_events(run_dir)
    for event in events:
        if event.sequence == sequence:
            if event.event_type != "prediction_sealed":
                return False
            if event.payload.get("sha256") != digest:
                return False
            if event.payload.get("request_id") != request.request_id:
                return False
            return True
    return False


def has_result(run_dir: Path, request_id: str) -> bool:
    for event in read_events(run_dir):
        if event.event_type == "experiment_result" and event.payload.get("request_id") == request_id:
            return True
    return False


def cache_key(parts: dict[str, object]) -> str:
    return sha256_text(canonical_json(parts))


def read_cache(run_dir: Path, key: str) -> dict[str, object] | None:
    path = run_dir / "cache" / f"{key}.json"
    if not path.exists():
        return None
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def write_cache(run_dir: Path, key: str, value: dict[str, object]) -> None:
    atomic_write_json(run_dir / "cache" / f"{key}.json", value)


def redact(text: str, secrets: list[str]) -> str:
    cleaned = text
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned
