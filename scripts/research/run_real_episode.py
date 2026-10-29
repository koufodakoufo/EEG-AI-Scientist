"""Launch one frozen, isolated native EEGMAT episode from trusted JSON config."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "framework"))
from eegfm.research_bench.real_episode import read_json, run_episode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    arguments = parser.parse_args()
    result = run_episode(read_json(arguments.config))
    print(json.dumps(result, ensure_ascii=False))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
