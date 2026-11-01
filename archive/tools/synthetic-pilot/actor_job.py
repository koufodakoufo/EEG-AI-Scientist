"""Fresh isolated Actor episode. Job reservation is performed by trusted Builder."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

BASE=Path('/data/duandh/eegfm-stage-a-20261028'); WORK=BASE/'overnight-20261029'
sys.path.insert(0,str(WORK/'integration/framework'))
from eegfm.research_bench.actor import prepare_control,launch_actor
from eegfm.research_bench.bundle import verify_public_bundle,digest_file
from eegfm.research_bench.budget import write_atomic
from eegfm.research_bench.trace import collect_visible_trace


def main() -> None:
    job_path=Path(sys.argv[1]).resolve(strict=True); job_path.relative_to(WORK)
    job=json.loads(job_path.read_text()); call_id=job['call_id']
    if not call_id.startswith('M') or not call_id[1:].isdigit(): raise ValueError('Invalid call ID')
    if job['timeout_seconds']!=900: raise ValueError('Frozen episode budget is 900 seconds')
    source=job_path.parent/'public'; verify_public_bundle(source)
    if digest_file(source/'PUBLIC_MANIFEST.json')!=job['public_manifest_sha256']:
        raise ValueError('Public bundle differs from sealed job')
    case=WORK/f'cases/{call_id}-actor'; case.mkdir(parents=True,exist_ok=False)
    shutil.copytree(source,case/'public'); verify_public_bundle(case/'public')
    meta=prepare_control(case=case,public=case/'public',control_home=WORK/f'control/{call_id}',native_binary=WORK/'tools/runtime-review/bin/codex',
                         bwrap_dir=WORK/'tools/bubblewrap/usr/bin',auth_source=BASE/'codex-home/auth.json',model='gpt-6.1-sol')
    # Identical task prompt for matched runs apart from run_id and explicit skill bytes.
    prompt=('Conduct the supplied research task autonomously. Your run_id is '+job['run_id']+'. '
            'Start by reading public/TASK_PUBLIC.md and the other public interface documents. '
            'All task resources are in public/. Write deliverables only under output/. '
            'You have 900 seconds total; each analysis command must finish in 60 seconds. '
            'Use Python standard library only, up to 4 CPU threads, 12 GiB RAM, 64 MiB new output. '
            'No network, installations, GPU, other model calls, or attempts to access private material. '
            'Write output/PLAN.md and output/LOCKED_ANALYSIS.json before executing analysis. '
            'Complete the report, structured claims/evidence and reproducible COMMANDS.json even if findings are negative. '
            'Do not claim a command succeeded unless you observed its output. Return a short completion summary.')
    skill_path=job_path.parent/'SKILL.md'
    if job.get('skill_sha256'):
        if digest_file(skill_path)!=job['skill_sha256']: raise ValueError('Frozen skill differs')
        prompt+='\n\nEXPLICIT SCIENTIFIC WORKFLOW SKILL (version frozen before this episode):\n'+skill_path.read_text()
    elif skill_path.exists():
        raise ValueError('Unexpected skill in baseline job')
    output=WORK/f'evidence/{call_id}'
    report=json.loads((WORK/'evidence/ISOLATION_REPORT.json').read_text())
    result=launch_actor(meta,prompt,output_dir=output,timeout_seconds=900,bwrap_dir=WORK/'tools/bubblewrap/usr/bin',
                         proxy_url=os.environ['HTTPS_PROXY'],role='actor',isolation_report=report)
    result.update(call_id=call_id,run_id=job['run_id'],public_manifest_sha256=job['public_manifest_sha256'],
                  skill_sha256=job.get('skill_sha256'),prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                  experiment_seal_sha256=job['experiment_seal_sha256'])
    (output/'PROMPT.txt').write_text(prompt)
    write_atomic(output/'status.json',result)
    trace=collect_visible_trace(Path(meta['control_home']),output/'trace')
    print(json.dumps({'call_id':call_id,'status':result['status'],'exit_code':result['exit_code'],
                     'elapsed_seconds':result['elapsed_seconds'],'visible_trace_sha256':trace['trace_sha256']},indent=2))


if __name__=='__main__': main()
