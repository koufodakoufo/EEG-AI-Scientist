"""Offline artifact/command provenance audit, separate from claim agreement.

The command ledger MUST come from the trusted launcher, never the submission.
It binds command_id, run_id, status='completed', exit_code=0, data_split and an
artifacts list of {'artifact_path': relative POSIX path, 'sha256': digest}.
Hash agreement is integrity evidence, not proof of scientific correctness.
Audit only a frozen artifact tree not writable by an active Actor. This portable
implementation detects links/reparse points but cannot prevent hostile races
on every OS; process/filesystem isolation remains the launcher's responsibility.
"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping

from .schema import EvidenceRecord, SCHEMA_VERSION, ValidationError

DEFAULT_SPLITS = frozenset({"train", "validation", "synthetic", "not_applicable"})
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024


def _portable_path(value: str) -> tuple[str, ...]:
    if "\\" in value or ":" in value or "\x00" in value or PureWindowsPath(value).drive or PurePosixPath(value).is_absolute():
        raise ValidationError("unsafe_artifact_path")
    parts = value.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if any(part in {"", ".", ".."} or part.rstrip(" .") != part or part.split(".")[0].upper() in reserved for part in parts):
        raise ValidationError("unsafe_artifact_path")
    return tuple(parts)


def _is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _safe_artifact(root: Path, relative: str) -> Path:
    parts = _portable_path(relative)
    current = root
    for part in parts:
        current = current / part
        info = current.lstat()
        if _is_link(info):
            raise ValidationError("symlink_or_reparse_point")
    if not current.is_file():
        raise ValidationError("artifact_not_regular_file")
    if not current.resolve().is_relative_to(root):
        raise ValidationError("artifact_outside_root")
    return current


def _hash_artifact(path: Path, max_bytes: int) -> str:
    before = path.lstat()
    if _is_link(before) or not stat.S_ISREG(before.st_mode):
        raise ValidationError("artifact_not_regular_file")
    if before.st_nlink != 1:
        raise ValidationError("artifact_hardlink")
    if before.st_size > max_bytes:
        raise ValidationError("artifact_size_limit")
    digest = hashlib.sha256()
    count = 0
    # No executable loaders, pickle, eval, imports or subprocesses touch artifacts.
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValidationError("artifact_changed_during_audit")
        for chunk in iter(lambda: stream.read(65536), b""):
            count += len(chunk)
            if count > max_bytes:
                raise ValidationError("artifact_size_limit")
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    fingerprints = {(item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns) for item in (before, opened, after, final)}
    if len(fingerprints) != 1 or _is_link(final):
        raise ValidationError("artifact_changed_during_audit")
    return digest.hexdigest()


def audit_evidence(
    records: Iterable[EvidenceRecord | Mapping[str, Any]],
    artifact_root: str | os.PathLike[str],
    command_records: Iterable[Mapping[str, Any]] | Mapping[str, Mapping[str, Any]] | None = None,
    *, expected_run_id: str | None = None, expected_data_split: str | None = None,
    allowed_data_splits: Iterable[str] = DEFAULT_SPLITS, max_artifact_bytes: int = MAX_ARTIFACT_BYTES,
) -> dict[str, Any]:
    """Return per-evidence failures, valid IDs and aggregate integrity status.

    Missing command records fail closed. An evidence record is valid only when
    a successful trusted command declares its exact run, split, path AND hash.
    Test data are denied by default; deliberate authorization requires the
    evaluator to include 'test' in allowed_data_splits. Unknown splits fail.
    A supplied expected_run_id/expected_data_split additionally pins the case.
    Duplicate evidence or command IDs invalidate every affected record.
    """
    if type(max_artifact_bytes) is not int or max_artifact_bytes <= 0:
        raise ValidationError("max_artifact_bytes must be a positive integer")
    allowed = set(allowed_data_splits)
    root = Path(artifact_root).absolute()
    root_error: str | None = None
    try:
        # Reject links in the supplied root chain as well as below it.
        for ancestor in (root, *root.parents):
            if _is_link(ancestor.lstat()):
                raise ValidationError("artifact_root_link")
        root = root.resolve(strict=True)
        if not root.is_dir():
            raise ValidationError("artifact_root_not_directory")
    except (OSError, ValidationError) as error:
        root_error = str(error)

    commands: dict[str, Mapping[str, Any]] = {}
    duplicate_commands: set[str] = set()
    ledger_errors: list[str] = []
    if isinstance(command_records, Mapping):
        entries: Iterable[Mapping[str, Any]] = command_records.values()
        for key, entry in command_records.items():
            if not isinstance(entry, Mapping) or entry.get("command_id") != key:
                ledger_errors.append("command_mapping_key_mismatch")
    else:
        entries = () if command_records is None else command_records
    for entry in entries:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("command_id"), str):
            ledger_errors.append("invalid_command_record")
            continue
        command_id = entry["command_id"]
        if command_id in commands:
            duplicate_commands.add(command_id)
        commands[command_id] = entry

    values = list(records)
    seen: set[str] = set()
    duplicate_evidence: set[str] = set()
    for value in values:
        evidence_id = value.evidence_id if isinstance(value, EvidenceRecord) else value.get("evidence_id") if isinstance(value, Mapping) else None
        if isinstance(evidence_id, str):
            if evidence_id in seen:
                duplicate_evidence.add(evidence_id)
            seen.add(evidence_id)
    results: list[dict[str, Any]] = []
    for value in values:
        errors: list[str] = []
        try:
            record = EvidenceRecord.from_dict(value.to_dict() if isinstance(value, EvidenceRecord) else value)
        except (TypeError, ValueError) as error:
            results.append({"evidence_id": None, "valid": False, "errors": [f"invalid_record: {error}"]})
            continue
        if root_error:
            errors.append(f"invalid_artifact_root: {root_error}")
        if ledger_errors:
            errors.append("invalid_command_ledger")
        if record.evidence_id in duplicate_evidence:
            errors.append("duplicate_evidence_id")
        if record.command_id in duplicate_commands:
            errors.append("duplicate_command_id")
        if record.status != "completed":
            errors.append("evidence_not_completed")
        if record.data_split not in allowed:
            errors.append("disallowed_data_split")
        if expected_run_id is not None and record.run_id != expected_run_id:
            errors.append("unexpected_run_id")
        if expected_data_split is not None and record.data_split != expected_data_split:
            errors.append("unexpected_data_split")
        command = commands.get(record.command_id)
        if command is None:
            errors.append("missing_command_record")
        else:
            if command.get("run_id") != record.run_id:
                errors.append("run_id_mismatch")
            if command.get("status") != "completed" or type(command.get("exit_code")) is not int or command.get("exit_code") != 0:
                errors.append("command_not_successful")
            artifact_splits=command.get('artifact_data_splits',{})
            if not isinstance(artifact_splits,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in artifact_splits.items()):
                errors.append('invalid_artifact_split_ledger')
                artifact_splits={}
            if artifact_splits.get(record.artifact_path,command.get("data_split")) != record.data_split:
                errors.append("data_split_mismatch")
            artifacts = command.get("artifacts")
            if not isinstance(artifacts, list) or not all(isinstance(item, dict) and set(item) == {"artifact_path", "sha256"} for item in artifacts):
                errors.append("missing_or_invalid_command_artifacts")
            else:
                linked = [item for item in artifacts if item["artifact_path"] == record.artifact_path]
                if len(linked) != 1 or linked[0]["sha256"] != record.sha256:
                    errors.append("artifact_not_bound_to_command")
        actual_hash: str | None = None
        # Audit unauthorized/malformed paths without reading arbitrary files.
        try:
            _portable_path(record.artifact_path)
            if not errors:
                artifact = _safe_artifact(root, record.artifact_path)
                actual_hash = _hash_artifact(artifact, max_artifact_bytes)
                if actual_hash != record.sha256:
                    errors.append("sha256_mismatch")
        except ValidationError as error:
            errors.append(str(error))
        except FileNotFoundError:
            errors.append("missing_artifact")
        except OSError:
            errors.append("artifact_unreadable")
        results.append({**record.to_dict(), "valid": not errors, "errors": errors, "observed_sha256": actual_hash})
    valid_ids = [entry["evidence_id"] for entry in results if entry["valid"]]
    return {"schema_version": SCHEMA_VERSION, "status": "no_evidence" if not results else "valid" if len(valid_ids) == len(results) else "invalid",
            "valid": bool(results) and len(valid_ids) == len(results), "records": results,
            "counts": {"total": len(results), "valid": len(valid_ids), "invalid": len(results) - len(valid_ids)},
            "valid_evidence_ids": valid_ids, "ledger_errors": ledger_errors,
            "limitations": ["Caller must supply a trusted launcher ledger and a frozen, isolated artifact tree.",
                            "Integrity and command provenance do not establish scientific validity or claim support.",
                            "No submission-supplied evaluator or artifact code is executed."]}
