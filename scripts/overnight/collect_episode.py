"""Freeze a stopped Actor's submission, validate interfaces and replay once."""
from __future__ import annotations
import json
from pathlib import Path
import sys

BASE=Path('/data/duandh/eegfm-stage-a-20261028'); WORK=BASE/'overnight-20261029'
sys.path.insert(0,str(WORK/'integration/framework'))
from eegfm.research_bench.replay import freeze_submission,replay_submission
from eegfm.research_bench.budget import write_atomic
from eegfm.research_bench.bundle import checked_file,digest_file,verify_public_bundle
from eegfm.research_bench.schema import AtomicClaim
from eegfm.research_bench.evidence import audit_evidence


def main() -> None:
    call_id=sys.argv[1]
    if not call_id.startswith('M') or not call_id[1:].isdigit(): raise ValueError('Invalid call ID')
    evidence=WORK/f'evidence/{call_id}'; status=json.loads((evidence/'status.json').read_text())
    if status['status'] not in {'completed','failed','timed_out','memory_exceeded','output_exceeded','storage_exceeded','disk_free_floor','launcher_failed'}:
        raise ValueError('Episode has no terminal launcher status')
    case=WORK/f'cases/{call_id}-actor'; verify_public_bundle(case/'public')
    frozen=WORK/f'submissions/{call_id}/output'
    manifest=freeze_submission(case/'output',frozen)
    errors=[]; parsed_claims=[]; report=''
    required=['REPORT.md','PLAN.md','LOCKED_ANALYSIS.json','claims.json','evidence.json','COMMANDS.json']
    for name in required:
        try: checked_file(frozen,name)
        except (OSError,ValueError): errors.append('missing_or_unsafe:'+name)
    try:
        report=(frozen/'REPORT.md').read_text()
        value=json.loads((frozen/'claims.json').read_text())
        if set(value)!={'schema_version','claims'} or value['schema_version']!='research_bench_v1' or not isinstance(value['claims'],list):
            raise ValueError('claims envelope mismatch')
        if len(value['claims'])>30: raise ValueError('claims exceed public cap')
        ids=set()
        for item in value['claims']:
            claim=AtomicClaim.from_dict(item); span=claim.source_span
            if claim.claim_id in ids: raise ValueError('duplicate claim ID')
            ids.add(claim.claim_id)
            if span['source']!='REPORT.md' or report[span['start']:span['end']]!=claim.text:
                raise ValueError('claim quote/span mismatch:'+claim.claim_id)
            parsed_claims.append(claim.to_dict())
    except (OSError,ValueError,TypeError,KeyError) as error:
        errors.append('claims_validation:'+str(error))
    try:
        replay=replay_submission(frozen_output=frozen,public=case/'public',replay_case=WORK/f'replays/{call_id}',
            control_home=WORK/f'control/replay-{call_id}',native_binary=WORK/'tools/runtime-review/bin/codex',
            bwrap_dir=WORK/'tools/bubblewrap/usr/bin',run_id=status['run_id'],evidence_dir=evidence/'replay')
    except (OSError,ValueError,RuntimeError) as error:
        replay={'status':'blocked','reason':str(error),'command_ledger':[],'model_calls':0}
        write_atomic(evidence/'replay-blocked.json',replay)
    try:
        records=json.loads((frozen/'evidence.json').read_text())
        if not isinstance(records,list): raise ValueError('evidence must be an array')
        audit=audit_evidence(records,frozen,replay.get('command_ledger',[]),expected_run_id=status['run_id'])
    except (OSError,ValueError,TypeError) as error:
        audit={'status':'invalid','reason':str(error),'valid':False}
    write_atomic(evidence/'evidence-audit.json',audit)
    commands=[]; usage=[]
    for line in (evidence/'stdout.jsonl').read_text().splitlines():
        try: row=json.loads(line)
        except ValueError: continue
        item=row.get('item',{})
        if item.get('type')=='command_execution':
            commands.append({'event_type':row.get('type'),'item_id':item.get('id'),'command':item.get('command'),
                             'status':item.get('status'),'exit_code':item.get('exit_code')})
        if row.get('type')=='turn.completed': usage.append(row.get('usage',{}))
    summary={'schema_version':'episode_collection_v1','call_id':call_id,'run_id':status['run_id'],
        'launcher_status':status['status'],'exit_code':status['exit_code'],'elapsed_seconds':status['elapsed_seconds'],
        'submission_manifest':manifest,'interface_errors':errors,'submitted_claims_parsed':len(parsed_claims),
        'report_present':bool(report),'report_sha256':digest_file(frozen/'REPORT.md') if report else None,
        'replay_status':replay['status'],'evidence_audit_status':audit['status'],
        'visible_command_events':commands,'usage':usage,
        'limitations':['Trusted replay validates reproducibility, not scientific truth.',
                       'Replay ledger labels validation metrics; training-only/code evidence may fail split binding.',
                       'Raw submitted claims retained; symmetric extraction is a separate evaluator stage.']}
    write_atomic(evidence/'collection.json',summary)
    print(json.dumps({k:summary[k] for k in ('call_id','launcher_status','interface_errors','submitted_claims_parsed','replay_status','evidence_audit_status','usage')},indent=2))


if __name__=='__main__': main()
