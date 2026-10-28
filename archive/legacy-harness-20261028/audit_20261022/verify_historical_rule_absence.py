r"""Read-only audit of archived emotion runs: was the saved rule text actually sent?

This script never writes to the archive and never calls a model.

    .\.venv\Scripts\python.exe audit_20261022\verify_historical_rule_absence.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "archive" / "experiments" / "emotion_20261021" / "runs" / "flash_emotion_20261021" / "runs"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    entries: list[dict[str, Any]] = []
    pairs: dict[tuple[str, str], list[str]] = {}
    for run in sorted(RUNS.glob("*/repeat_*")):
        messages_path = run / "messages.json"
        input_path = run / "scientist_input.md"
        rules = sorted((run / "rules").glob("*.md"))
        if not messages_path.exists() or not rules:
            continue
        messages = json.loads(messages_path.read_text(encoding="utf-8"))
        system_text = str(messages[0].get("content", ""))
        user_text = str(messages[1].get("content", ""))
        scientist_input = input_path.read_text(encoding="utf-8") if input_path.exists() else ""
        normalized_user = re.sub(r"Current local time: [^.]*\.", "Current local time: <TIME>.", user_text)
        key = (_sha(system_text), _sha(normalized_user))
        pairs.setdefault(key, []).append(run.relative_to(RUNS).as_posix())
        entries.append(
            {
                "run": run.relative_to(RUNS).as_posix(),
                "rule_snapshot": rules[0].name,
                "rule_chars": len(rules[0].read_text(encoding="utf-8").strip()),
                "rule_in_system": rules[0].read_text(encoding="utf-8").strip() in system_text,
                "rule_in_user": rules[0].read_text(encoding="utf-8").strip() in user_text,
                "rule_in_scientist_input": rules[0].read_text(encoding="utf-8").strip() in scientist_input,
                "system_sha256": key[0],
                "normalized_user_sha256": key[1],
            }
        )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runs_directory": str(RUNS.relative_to(ROOT)),
        "runs_checked": len(entries),
        "rule_in_system_count": sum(1 for item in entries if item["rule_in_system"]),
        "rule_in_user_count": sum(1 for item in entries if item["rule_in_user"]),
        "rule_in_scientist_input_count": sum(1 for item in entries if item["rule_in_scientist_input"]),
        "distinct_normalized_input_pairs": [
            {"system_sha256": key[0], "normalized_user_sha256": key[1], "runs": value}
            for key, value in pairs.items()
        ],
        "entries": entries,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
