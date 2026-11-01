"""Read a legacy report without dropping it because its optional annex is broken."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from eegfm.evaluation.bundle import digest_file

def read(path: Path) -> Any: return json.loads(path.read_text(encoding='utf-8'))


def read_submission(frozen: Path) -> tuple[str,list,dict]:
    """A broken optional annex cannot discard an otherwise usable report."""
    error=None
    try:
        proposed=read(frozen/'claims.json') if (frozen/'claims.json').is_file() else {'claims':[]}
        if not isinstance(proposed,dict) or not isinstance(proposed.get('claims'),list):
            raise ValueError('Invalid proposed-claims annex')
    except (OSError,ValueError,TypeError) as exc:
        proposed={'claims':[]}; error=str(exc)
    path=frozen/'REPORT.md'
    return (path.read_text(encoding='utf-8') if path.is_file() else '',proposed['claims'],
            {'report_sha256':digest_file(path) if path.is_file() else None,'report_missing':not path.is_file(),'annex_error':error})
