"""Launch one frozen, isolated native EEGMAT episode from trusted JSON config."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from eegfm.eeg.episode import read_json
from eegfm.eeg.episode import run_episode


def main() -> int:
    from eegfm.arguments import task_parser
    parser = task_parser('episode', description=__doc__)
    arguments = parser.parse_args()
    result = run_episode(read_json(arguments.config))
    print(json.dumps(result, ensure_ascii=False))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
