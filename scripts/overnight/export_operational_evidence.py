"""Export only safe launcher metadata and bounded resource summaries on the server."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

BASE=Path('/data/duandh/eegfm-stage-a-20261028')
WORK=BASE/'overnight-20261029'
sys.path.insert(0,str(WORK/'integration/framework'))
from eegfm.research_bench.budget import tree_bytes,write_atomic


def main() -> None:
    copied=[]
    for source in (WORK/'control').glob('M*/launcher-metadata.json'):
        identifier=source.parent.name
        if not identifier[1:].isdigit() or not (WORK/'evidence'/identifier).is_dir():
            continue
        # This builder-generated metadata contains hashes and paths, not auth bytes.
        shutil.copyfile(source,WORK/'evidence'/identifier/'launcher-metadata.json')
        copied.append(identifier)
    def git(path: Path,*args: str) -> str:
        return subprocess.check_output(['git','-C',str(path),*args],text=True,timeout=10).strip()
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'copied_metadata':sorted(copied),
        'owned_nightly_bytes':tree_bytes(WORK),'data_free_bytes':shutil.disk_usage(WORK).free,
        'home_free_bytes':shutil.disk_usage('/home/duandh').free,'gpu_allocated':0,
        'dataset_copy_or_mutation_performed':False,'resource_probe_scope':'Earlier targeted stat only; no recursive dataset inventory.',
        'original_source_head':git(BASE/'source/eeg-fm-research','rev-parse','HEAD'),
        'original_source_status':git(BASE/'source/eeg-fm-research','status','--porcelain'),
        'integration_head':git(WORK/'integration','rev-parse','HEAD'),
        'integration_status':git(WORK/'integration','status','--porcelain'),
        'cost_usd':'unknown','private_credentials_exported':False}
    write_atomic(WORK/'evidence/RESOURCE_SNAPSHOT.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
