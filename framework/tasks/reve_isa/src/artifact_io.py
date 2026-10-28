"""Task-owned hashing, atomic publication and verified completion markers."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def sha256_file(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f".{path.name}.{uuid.uuid4().hex}.pending")
    try:
        with pending.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def atomic_torch_save(path, value):
    import torch
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f".{path.name}.{uuid.uuid4().hex}.pending")
    try:
        torch.save(value, pending)
        with pending.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


@contextlib.contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def check_deadline(deadline):
    if time.time() >= float(deadline):
        raise TimeoutError("Task deadline reached; no replacement job is authorized")


def publish_completion(directory, identity, names):
    directory = Path(directory)
    entries = []
    for name in names:
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError("Completion requires actual contained artifacts")
        entries.append({"path": name, "sha256": sha256_file(path), "bytes": path.stat().st_size,
                        "mtime_ns": path.stat().st_mtime_ns})
    marker = {"identity": identity, "identity_hash": fingerprint(identity), "files": entries}
    atomic_json(directory / "COMPLETE.json", marker)
    return marker


def verify_completion(directory, identity=None):
    directory = Path(directory)
    marker = read_json(directory / "COMPLETE.json")
    if marker["identity_hash"] != fingerprint(marker["identity"]):
        raise ValueError("Completion identity checksum failed")
    if identity is not None and marker["identity"] != identity:
        raise ValueError("Completed artifact belongs to a different protocol or source")
    if not marker["files"]:
        raise ValueError("Empty completion marker")
    for entry in marker["files"]:
        path = (directory / entry["path"]).resolve()
        if (not path.is_relative_to(directory.resolve()) or not path.is_file()
                or path.stat().st_size != entry["bytes"] or sha256_file(path) != entry["sha256"]):
            raise ValueError("Completed artifact changed or is missing")
    return marker


def verify_completion_metadata(directory, identity=None):
    """Reuse a checksummed immutable cache only while size/mtime remain exact.

    Publication hashes every byte. Models/checkpoints still use full digest
    verification; this path avoids re-reading 116GB of LP caches for each fold.
    """
    directory = Path(directory)
    marker = read_json(directory / "COMPLETE.json")
    if marker["identity_hash"] != fingerprint(marker["identity"]) or (identity is not None and marker["identity"] != identity):
        raise ValueError("Cache identity checksum failed")
    if not marker["files"]:
        raise ValueError("Empty cache completion")
    for entry in marker["files"]:
        path = (directory / entry["path"]).resolve()
        if (not path.is_relative_to(directory.resolve()) or not path.is_file()
                or path.stat().st_size != entry["bytes"] or path.stat().st_mtime_ns != entry.get("mtime_ns")):
            raise ValueError("Completed cache changed; full repair/verification required")
    return marker


def verify_source_snapshot(source):
    """The Harness/Broker freezes snapshot.json one directory above source."""
    source = Path(source).resolve()
    manifest = read_json(source.parent / "snapshot.json")
    # Broker relocates an approved source; do not trust the recorded old root.
    expected = manifest["files"]
    if fingerprint(expected) != manifest["snapshot_hash"]:
        raise ValueError("Source snapshot identity mismatch")
    actual = {str(p.relative_to(source)) for p in source.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != {entry["path"] for entry in expected}:
        raise ValueError("Snapshot has extra or missing files")
    for entry in expected:
        path = source / entry["path"]
        if path.is_symlink() or not path.resolve().is_relative_to(source) or sha256_file(path) != entry["sha256"]:
            raise ValueError("Source snapshot file changed")
    return manifest
