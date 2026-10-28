"""Delete only nightly workers' copied auth and raw native rollouts after trace export.

Never access or alter the base user's authentication. No recursive directory deletion.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

WORK=Path('/data/duandh/eegfm-stage-a-20261028/overnight-20261029').resolve(strict=True)
sys.path.insert(0,str(WORK/'integration/framework'))
from eegfm.research_bench.budget import write_atomic
from eegfm.research_bench.bundle import digest_file
from eegfm.research_bench.trace import collect_visible_trace


def main() -> None:
    report_path=WORK/'evidence/CONTROL_RETIREMENT.json'
    if report_path.exists():
        raise FileExistsError('Retirement already recorded')
    candidates=[]
    for folder in sorted((WORK/'control').glob('M*')):
        if not folder.is_dir() or folder.is_symlink() or not folder.name[1:].isdigit():
            continue
        identifier=folder.name; evidence=WORK/'evidence'/identifier
        status=json.loads((evidence/'status.json').read_text())
        if status['status'] not in {'completed','failed','timed_out','memory_exceeded','output_exceeded','storage_exceeded','disk_free_floor','launcher_failed'}:
            raise ValueError('Worker is not terminal: '+identifier)
        if status.get('process_cleanup',{}).get('surviving_owned_pids',[]) != []:
            raise ValueError('Worker has surviving descendants: '+identifier)
        rollouts=list((folder/'sessions').rglob('*.jsonl')) if (folder/'sessions').is_dir() else []
        if rollouts and not (evidence/'trace/trace-index.json').is_file():
            collect_visible_trace(folder,evidence/'trace')
        for path in [folder/'auth.json',*rollouts]:
            if not path.exists(): continue
            if path.is_symlink() or path.resolve().parent==WORK or not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Unsafe control path')
            if path.stat().st_nlink!=1:
                raise ValueError('Refuse to remove linked control file')
            candidates.append((identifier,path))
    removed=[]
    for identifier,path in candidates:
        item={'worker':identifier,'relative_path':str(path.relative_to(WORK)),
              'kind':'copied_auth' if path.name=='auth.json' else 'raw_native_rollout'}
        if path.name!='auth.json': item['sha256_before_removal']=digest_file(path)
        # Authentication contents are not read, printed or hashed.
        path.unlink(); removed.append(item)
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'removed':removed,
        'base_auth_untouched':True,'visible_sanitized_traces_preserved':True,
        'reason':'No workers remain. Remove temporary credential copies and raw rollouts; retain visible-only trace evidence.'}
    write_atomic(report_path,report)
    print(json.dumps({'removed_files':len(removed),'copied_auth_files':sum(v['kind']=='copied_auth' for v in removed),
                      'base_auth_untouched':True}))


if __name__=='__main__': main()
