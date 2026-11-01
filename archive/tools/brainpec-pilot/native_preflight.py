"""One bounded authentication/control check; no research data or user history."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys

BASE=Path('/data/duandh/eegfm-stage-a-20261028')
RUNTIME=BASE/'overnight-20261029'
WORK=BASE/'brainpec-real-20261029'
sys.path.insert(0,str(RUNTIME/'integration/framework'))
from eegfm.research_bench.actor import prepare_control,launch_actor
from eegfm.research_bench.bundle import create_public_bundle


def main() -> None:
    call_id='R10'
    source=WORK/'builders/preflight-public'
    case=WORK/'cases/R10-preflight'
    source.mkdir(parents=True,exist_ok=False)
    case.mkdir(parents=True,exist_ok=False)
    (source/'TASK.md').write_text('Control preflight only. No scientific materials.\n')
    create_public_bundle(source,case/'public',['TASK.md'],task_id='real-preflight',tier='synthetic_mechanism')
    meta=prepare_control(case=case,public=case/'public',control_home=WORK/f'control/{call_id}',
        native_binary=RUNTIME/'tools/runtime-review/bin/codex',bwrap_dir=RUNTIME/'tools/bubblewrap/usr/bin',
        auth_source=BASE/'codex-home/auth.json',model='gpt-6.1-sol',read_only_roots=(WORK/'venv',))
    report=launch_actor(meta,'Reply exactly PREFLIGHT_OK. Use no tools.',output_dir=WORK/f'evidence/{call_id}',
        timeout_seconds=90,bwrap_dir=RUNTIME/'tools/bubblewrap/usr/bin',proxy_url=os.environ['HTTPS_PROXY'],role='preflight')
    print(json.dumps({key:report.get(key) for key in ('status','exit_code','elapsed_seconds','role')}))


if __name__=='__main__':
    main()
