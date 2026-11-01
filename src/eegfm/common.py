"""Shared helpers: project paths, atomic files, task contracts, hashes."""
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import tempfile

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parent


def checkout_root() -> Path | None:
    """Locate an editable checkout without depending on the current directory."""
    for parent in PACKAGE_ROOT.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "tasks").is_dir():
            return parent
    return None


def resolve_workspace(explicit: str | Path | None = None) -> Path:
    """Use the selected research workspace, or this package's source checkout."""
    selected = explicit or os.environ.get("EEGFM_ROOT")
    if selected:
        path = Path(selected).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"EEGFM_ROOT must be an existing directory: {path}")
        return path
    checkout = checkout_root()
    if checkout is None:
        raise RuntimeError("Set EEGFM_ROOT to an existing research workspace")
    return checkout


ROOT = resolve_workspace()
CODE = checkout_root() or ROOT


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": now(), **record}, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                break  # torn final line after a crash
    return out


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_dir(run_id):
    path = ROOT / "runs" / run_id
    if not (path / "run.json").exists():
        raise SystemExit(f"Unknown run {run_id!r}: {path} has no run.json")
    return path


def task_dir(task_id):
    return ROOT / "tasks" / task_id


REQUIRED_TASK_KEYS = {"task_id", "title", "source", "evaluation", "compute", "search"}


def load_task(task_id):
    path = task_dir(task_id) / "task.yaml"
    task = yaml.safe_load(path.read_text(encoding="utf-8"))
    missing = REQUIRED_TASK_KEYS - set(task)
    if missing:
        raise SystemExit(f"{path}: missing {sorted(missing)}")
    ev = task["evaluation"]
    for key in ("val_command", "metric", "direction"):
        if key not in ev:
            raise SystemExit(f"{path}: evaluation.{key} is required")
    if ev["direction"] not in {"maximize", "minimize"}:
        raise SystemExit(f"{path}: evaluation.direction must be maximize or minimize")
    if task["compute"].get("backend") not in {"local", "tione"}:
        raise SystemExit(f"{path}: compute.backend must be local or tione")
    task["_path"] = str(path)
    return task


def matches(name, patterns):
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns or [])


def source_files(root, include=None, exclude=None):
    """Relative paths of the task's code base that are copied into a run."""
    root = Path(root)
    out = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = str(path.relative_to(root))
        if any(part in {".git", "__pycache__"} for part in path.relative_to(root).parts):
            continue
        if include and not matches(rel, include):
            continue
        if exclude and matches(rel, exclude):
            continue
        out.append(rel)
    return out
