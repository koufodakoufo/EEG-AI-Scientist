r"""Compare current historical payload bytes with the pre-fix baseline.

Reads ``audit_20261022/before_hashes.json`` and re-hashes every recorded path.
New files (for example the correction note) are listed separately; any changed
or missing original is a failure.

    .\.venv\Scripts\python.exe audit_20261022\verify_payload_hashes.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "audit_20261022" / "before_hashes.json"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    recorded: list[dict[str, Any]] = list(baseline["archive"]) + list(baseline["meeting_originals"])
    changed: list[str] = []
    missing: list[str] = []
    unchanged = 0
    for entry in recorded:
        path = ROOT / str(entry["path"])
        if not path.is_file():
            missing.append(str(entry["path"]))
            continue
        if _sha(path) != entry["sha256"]:
            changed.append(str(entry["path"]))
            continue
        unchanged += 1
    recorded_paths = {str(entry["path"]) for entry in recorded}
    roots = [ROOT / "archive", ROOT / "meeting_20261022" / "originals"]
    added = sorted(
        path.relative_to(ROOT).as_posix()
        for root in roots
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(ROOT).as_posix() not in recorded_paths
    )
    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "baseline_aggregate_sha256": baseline["aggregate_sha256"],
        "files_checked": len(recorded),
        "unchanged": unchanged,
        "changed": changed,
        "missing": missing,
        "added_after_baseline": added,
        "ok": not changed and not missing,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
