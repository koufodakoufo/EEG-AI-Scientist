"""Post-hoc M20 core-only diagnostic, never replacement of frozen primary audit."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys

WORK=Path('/data/duandh/eegfm-stage-a-20261028/overnight-20261029')
sys.path.insert(0,str(WORK/'integration/framework'))
from eegfm.research_bench.bundle import digest_file
from eegfm.research_bench.budget import write_atomic
from eegfm.research_bench.replay import replay_submission
from eegfm.research_bench.evidence import audit_evidence


def main() -> None:
    original=WORK/'submissions/M20/output'
    copied=WORK/'builders/M20-core-diagnostic-input'
    if copied.exists():
        raise FileExistsError('No overwrite or silent retry of diagnostic')
    shutil.copytree(original,copied)
    commands=json.loads((original/'COMMANDS.json').read_text())
    core=[]
    for name in ('fit','null','uncertainty','edits','followup'):
        command=next(c for c in commands if c['command_id']==name)
        if command['argv'][:2]!=['python3','-B']:
            raise ValueError('Unexpected frozen command; no general shell normalization')
        core.append({**command,'argv':[command['argv'][0],*command['argv'][2:]]})
    write_atomic(copied/'COMMANDS.json',core)
    target=WORK/'evidence/M20/supplemental-core'
    result=replay_submission(frozen_output=copied,public=WORK/'cases/M20-actor/public',
        replay_case=WORK/'replays/M20-core',control_home=WORK/'control/replay-M20-core',
        native_binary=WORK/'tools/runtime-review/bin/codex',bwrap_dir=WORK/'tools/bubblewrap/usr/bin',
        run_id='case_84',evidence_dir=target)
    evidence=json.loads((original/'evidence.json').read_text())
    audit=audit_evidence(evidence,original,result['command_ledger'],expected_run_id='case_84')
    write_atomic(target/'evidence-audit.json',audit)
    note={'status':result['status'],'model_calls':0,'post_hoc':True,'primary_audit_replaced':False,
        'reason':'Primary evaluator accepts only 1-8 commands and no Python -B prefix; these restrictions were not in the public contract. M20 supplied 12 commands.',
        'scope':'Only first five scientific analysis stages; report, self-replays and final verifier excluded, not certified.',
        'normalization':'Remove only -B from declared argv because trusted replay itself supplies -B. All scientific artifacts start absent.',
        'original_commands_sha256':digest_file(original/'COMMANDS.json'),
        'diagnostic_commands_sha256':digest_file(copied/'COMMANDS.json'),
        'original_submission_unchanged':True,'all_commands_completed':result['all_commands_completed'],
        'matching_artifacts':sum(c['matches'] for c in result['comparisons']),
        'total_artifacts':len(result['comparisons']),'evidence_audit_status':audit['status']}
    write_atomic(target/'DIAGNOSTIC.json',note)
    print(json.dumps(note,indent=2))


if __name__=='__main__': main()
