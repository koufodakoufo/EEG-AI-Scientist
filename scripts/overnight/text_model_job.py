"""One fresh bounded text-only extractor/judge invocation, reserved by Builder."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys

BASE=Path('/data/duandh/eegfm-stage-a-20261028'); WORK=BASE/'overnight-20261029'
sys.path.insert(0,str(WORK/'integration/framework'))
from eegfm.research_bench.actor import prepare_control,launch_actor
from eegfm.research_bench.bundle import create_public_bundle,digest_file
from eegfm.research_bench.budget import write_atomic
from eegfm.research_bench.trace import collect_visible_trace


def main() -> None:
    job_path=Path(sys.argv[1]).resolve(strict=True); job_path.relative_to(WORK)
    job=json.loads(job_path.read_text()); call_id=job['call_id']
    if not call_id.startswith('M') or not call_id[1:].isdigit(): raise ValueError('Invalid call ID')
    source=job_path.parent/'source'; case=WORK/f'cases/{call_id}-text'; case.mkdir(parents=True,exist_ok=False)
    create_public_bundle(source,case/'public',['INPUT.json','PROTOCOL.md'],task_id=job['protocol_version'],tier='synthetic_mechanism')
    meta=prepare_control(case=case,public=case/'public',control_home=WORK/f'control/{call_id}',native_binary=WORK/'tools/runtime-review/bin/codex',
                         bwrap_dir=WORK/'tools/bubblewrap/usr/bin',auth_source=BASE/'codex-home/auth.json',model='gpt-6.1-sol')
    prompt=(source/'PROTOCOL.md').read_text()+'\n\nINPUT_JSON (data, not instructions):\n'+(source/'INPUT.json').read_text()
    output=WORK/f'evidence/{call_id}'
    role='distiller' if job['role']=='skill_distiller' else 'judge'
    isolation=json.loads((WORK/'evidence/ISOLATION_REPORT.json').read_text()) if role=='distiller' else None
    result=launch_actor(meta,prompt,output_dir=output,timeout_seconds=job['timeout_seconds'],bwrap_dir=WORK/'tools/bubblewrap/usr/bin',
                         proxy_url=os.environ['HTTPS_PROXY'],role=role,isolation_report=isolation,prompt_via_stdin=True)
    result['subrole']=job['role']; result['protocol_sha256']=digest_file(source/'PROTOCOL.md'); result['input_sha256']=digest_file(source/'INPUT.json')
    write_atomic(output/'status.json',result)
    trace=collect_visible_trace(Path(meta['control_home']),output/'trace')
    print(json.dumps({'call_id':call_id,'status':result['status'],'exit_code':result['exit_code'],'elapsed_seconds':result['elapsed_seconds'],
                     'visible_trace_sha256':trace['trace_sha256'],'final_exists':(output/'final.txt').is_file()},indent=2))


if __name__=='__main__': main()
