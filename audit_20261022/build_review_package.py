r"""Build the 2026-10-22 review package (source/tests/configs/docs/audit).

Excluded: credentials, archive payload (except the one synthetic prompt fixture
needed by a legacy test), private study data, personal notes, the input meeting
package, the old input zip, virtualenvs, caches, and git metadata.

    .\.venv\Scripts\python.exe audit_20261022\build_review_package.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "EEG_AI_Scientist_Review_20261022"
OUTPUT = ROOT / f"{PACKAGE_NAME}.zip"

INCLUDE_DIRS = ["src", "tests", "configs", "docs", "audit_20261022"]
INCLUDE_FILES = [
    "README.md",
    "HANDOFF.md",
    "ENVIRONMENT.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "studies/README.md",
]
# One legacy test reads this prompt; it is synthetic and contains no private data.
INCLUDE_EXTRA_DIRS = ["archive/experiments/synthetic_20261019/prompts"]
# Legacy lock/provenance test needs these two small config records (no answers).
INCLUDE_EXTRA_FILES = [
    "archive/experiments/emotion_20261021/configs/study.json",
    "archive/experiments/emotion_20261021/runs/flash_emotion_20261021/study_lock.json",
]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git"}
EXCLUDED_DESCRIPTION = [
    "credentials/ and any secret material",
    "archive/ experiment payloads (answers, messages, ledgers, reviews, events)",
    "studies/<id>/ run data and private material",
    "meeting_20261022/ input package and the old input zip",
    "group-meeting/, ref/, .venv/, git metadata, caches, personal notes",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _collect() -> list[tuple[str, bytes]]:
    entries: list[tuple[str, bytes]] = []

    def add(path: Path) -> None:
        relative = path.relative_to(ROOT).as_posix()
        if any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts):
            return
        if path.suffix in {".pyc", ".pyo"}:
            return
        entries.append((relative, path.read_bytes()))

    for directory in INCLUDE_DIRS:
        base = ROOT / directory
        if base.exists():
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    add(path)
    for directory in INCLUDE_EXTRA_DIRS:
        base = ROOT / directory
        if base.exists():
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    add(path)
    for name in INCLUDE_FILES + INCLUDE_EXTRA_FILES:
        path = ROOT / name
        if path.is_file():
            add(path)
    entries.sort(key=lambda item: item[0])
    return entries


def _package_readme(payload_count: int, total_bytes: int) -> bytes:
    text = f"""# EEG-AI-Scientist review package — 2026-10-22

This package covers **task A** of `DSH_NEXT_TASK.md` (input provenance, review
roundtrip, Claude/Gemini protocol, boundary tightening). Task B (archive
directory migration) is not included.

- Files: {payload_count}
- Uncompressed bytes: {total_bytes}
- Tests: run `.venv\\Scripts\\python.exe -m pytest` (or `uv run python -m pytest`).
  Expected result at packaging time: **114 passed**.
- No paid model call was made; Claude/Gemini remain `unverified`.
- Start with `docs/VERIFICATION_20261022.md`, `README.md`, `HANDOFF.md`, and
  `audit_20261022/probe_findings_after.json`.
- Correction for the old Meta-rule study: `docs/CORRECTION_20261022_META_INJECTION.md`.

## Included

`src/`, `tests/`, `configs/` (no secrets), `docs/`, `audit_20261022/`,
`pyproject.toml`, `uv.lock`, `.python-version`, `README.md`, `HANDOFF.md`,
`ENVIRONMENT.md`, `studies/README.md`, the synthetic prompt fixture
`archive/experiments/synthetic_20261019/prompts/`, and two small legacy
provenance records (`emotion_20261021` study config and study lock) needed by
one existing provenance test. No answers, messages, ledgers, reviews, or events
from the archive are included.

## Excluded

See `REVIEW_PACKAGE_MANIFEST.json` for the exact exclusion list. In particular:
credentials, experiment payloads, private study data, the input meeting package,
the old input zip, virtualenvs, caches, and git metadata.

## Reproduce the main evidence

```powershell
.\\.venv\\Scripts\\python.exe -m pytest
.\\.venv\\Scripts\\python.exe audit_20261022\\probe_fixed_code.py --source-root src
.\\.venv\\Scripts\\python.exe audit_20261022\\verify_historical_rule_absence.py
```

The historical audit reads `archive/experiments/emotion_20261021/...`; that
payload is intentionally absent from this package. Its recorded result is in
`audit_20261022/historical_rule_absence.json`, and the full byte-identity
baseline/comparison is in `audit_20261022/`.
"""
    return text.encode("utf-8")


def main() -> int:
    entries = _collect()
    total_bytes = sum(len(data) for _name, data in entries)
    readme = _package_readme(len(entries), total_bytes)
    manifest_payload: dict[str, Any] = {
        "schema_version": "1",
        "package": PACKAGE_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "DSH_NEXT_TASK.md task A only",
        "files": [
            {"path": name, "bytes": len(data), "sha256": _sha(data)} for name, data in entries
        ],
        "aggregate_sha256": _sha(
            "\n".join(f"{name}:{_sha(data)}" for name, data in entries).encode("utf-8")
        ),
        "excluded": EXCLUDED_DESCRIPTION,
        "note": "Payload hashes exclude REVIEW_PACKAGE_README.md and this manifest.",
    }
    manifest = (json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in entries:
            archive.writestr(f"{PACKAGE_NAME}/{name}", data)
        archive.writestr(f"{PACKAGE_NAME}/REVIEW_PACKAGE_README.md", readme)
        archive.writestr(f"{PACKAGE_NAME}/REVIEW_PACKAGE_MANIFEST.json", manifest)
    digest = _sha(OUTPUT.read_bytes())
    print(
        json.dumps(
            {
                "path": str(OUTPUT),
                "files": len(entries) + 2,
                "payload_files": len(entries),
                "uncompressed_bytes": total_bytes,
                "zip_bytes": OUTPUT.stat().st_size,
                "sha256": digest,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
