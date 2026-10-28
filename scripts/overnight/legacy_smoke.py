"""Preserved wzf flow with a scripted Agent; explicitly NOT an LLM experiment."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

BASE=Path('/data/duandh/eegfm-stage-a-20261028')
WORK=BASE/'overnight-20261029'
CODE=WORK/'integration/framework'
sys.path.insert(0,str(CODE))
from eegfm.research_bench.budget import run_bounded,write_atomic


def main() -> None:
    root=WORK/'legacy-smoke'
    root.mkdir(exist_ok=False)
    shutil.copytree(CODE/'tasks/synthetic_demo',root/'tasks/synthetic_demo',ignore=shutil.ignore_patterns('RESEARCH_BRIEF.md','items','__pycache__'))
    for path in (root/'tasks/synthetic_demo/memory/items',root/'memory/items',root/'runs'):
        path.mkdir(parents=True,exist_ok=True)
    python=BASE/'venv/bin/python'
    env=dict(os.environ,EEGFM_ROOT=str(root),EEGFM_PYTHON=str(python),PYTHONPATH=str(CODE),PATH=str(BASE/'venv/bin')+':/usr/bin:/bin')
    run_id='night-scripted-smoke-20261029'
    command_log=[]
    state_chain=[]
    def command(*args: str) -> None:
        done=subprocess.run([str(CODE/'bin/eegfm'),*args],cwd=CODE,env=env,capture_output=True,text=True,timeout=15)
        command_log.append({'argv':list(args),'exit_code':done.returncode,'stdout':done.stdout,'stderr':done.stderr})
        if done.returncode: raise RuntimeError(done.stderr)
        state=root/'runs'/run_id/'STATE.json'
        if state.exists(): state_chain.append(json.loads(state.read_text()))
    command('run','init','--task','synthetic_demo','--run-id',run_id)
    base_args=[str(python),'-B','-m','eegfm.driver','run','--run',run_id,'--agent','script','--script',str(CODE/'tests/fake_agent.py'),
               '--poll','0.2','--session-timeout','30','--max-sessions','12','--stall-limit','2','--backoff','0.2']
    first=run_bounded(base_args+['--once'],cwd=CODE,output_dir=WORK/'evidence/legacy-smoke-brief',timeout_seconds=45,env=env)
    run=root/'runs'/run_id
    state_chain.append(json.loads((run/'STATE.json').read_text()))
    brief=(run/'RESEARCH_BRIEF.md').read_text()
    if first['status']!='completed' or state_chain[-1]['status']!='awaiting_review' or 'lower lr' not in brief:
        raise RuntimeError('Synthetic brief did not match the reviewed scope')
    approval='Builder reviewed this specific CPU-only synthetic smoke; authorized by user overnight taskbook A2. Scripted agent, no LLM, no real EEG, no GPU. This is not human review.'
    command('brief','approve',run_id,'--note',approval)
    full=run_bounded(base_args,cwd=CODE,output_dir=WORK/'evidence/legacy-smoke-full',timeout_seconds=120,env=env)
    state_chain.append(json.loads((run/'STATE.json').read_text()))
    attempts=[json.loads(p.read_text()) for p in sorted((run/'attempts').glob('A*/attempt.json'))]
    sessions=[json.loads(line) for line in (run/'sessions.jsonl').read_text().splitlines()]
    report={'classification':'scripted_non_LLM_engineering_smoke','run_id':run_id,'state_chain':state_chain,
            'brief_review':{'actor':'builder','authorization':'user overnight taskbook A2','actual_brief':brief,'approval_note':approval},
            'driver_exit':full,'attempt_ids':[a['id'] for a in attempts],'session_count':len(sessions),
            'final_test':json.loads((run/'final_test.json').read_text()) if (run/'final_test.json').exists() else None,
            'max_attempts_limit_observed':len(attempts)<=4,'max_attempts_hard_enforcement':'not implemented in legacy attempts.py; do not infer enforcement from this compliant script',
            'model_calls':0,'gpu_used':0,'scientific_evidence':False,'commands':command_log}
    write_atomic(WORK/'evidence/legacy-smoke-report.json',report)
    print(json.dumps({'status':state_chain[-1]['status'],'attempt_ids':report['attempt_ids'],'session_count':len(sessions),
                      'driver_exit_code':full['exit_code'],'classification':report['classification']},indent=2))
    if full['status']!='completed' or state_chain[-1]['status']!='done':
        raise RuntimeError('Legacy smoke incomplete; inspect owned run and job metadata')


if __name__=='__main__': main()
