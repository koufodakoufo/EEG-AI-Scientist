"""Publish selected operational metadata, never prompts, auth or reasoning."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/overnight/2026-10-29'
NIGHT=ROOT/'.local/overnight-20261029'


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> None:
    ledger=[]
    for call in read(DOC/'BUDGET.json')['calls']:
        path=NIGHT/f"evidence/server/{call['id']}"
        row={'call_id':call['id'],'role':call['role'],'budget_status':call['status'],
             'reserved_at':call.get('reserved_at','unknown'),'timeout_seconds':call.get('timeout_seconds','unknown'),
             'elapsed_seconds':call.get('elapsed_seconds','unknown'),'cost_usd':'unknown',
             'evidence':call.get('evidence','unknown'),'outcome':call.get('outcome','unknown'),
             'model_observed':'unknown','usage':'unknown'}
        if (path/'status.json').is_file():
            status=read(path/'status.json')
            for key in ('status','started_at','finished_at','exit_code','elapsed_seconds','timeout_seconds',
                        'memory_limit_bytes','peak_tree_rss_bytes','affinity_cpus','threads','storage_limit_bytes',
                        'last_scope_bytes','profile_sha256','context','process_cleanup','run_id','public_manifest_sha256',
                        'skill_sha256','prompt_sha256','experiment_seal_sha256','protocol_sha256','input_sha256'):
                if key in status: row[key]=status[key]
            usage=[]
            if (path/'stdout.jsonl').is_file():
                for line in (path/'stdout.jsonl').read_text(encoding='utf-8').splitlines():
                    try: event=json.loads(line)
                    except ValueError: continue
                    if event.get('type')=='turn.completed' and isinstance(event.get('usage'),dict): usage.append(event['usage'])
            if usage:
                keys=('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens')
                row['usage']={key:(sum(v[key] for v in usage) if all(key in v for v in usage) else 'unknown') for key in keys}
                row['usage_note']='Provider-reported totals, including repeated/cached context; not unique prompt size or monetary cost.'
            if (path/'trace/trace-index.json').is_file():
                trace=read(path/'trace/trace-index.json')
                row['model_observed']=sorted({v['model'] for v in trace['turn_metadata'] if v.get('model')}) or 'unknown'
                row['reasoning_effort_observed']=sorted({v['effort'] for v in trace['turn_metadata'] if v.get('effort')})
                row['visible_trace_sha256']=trace['trace_sha256']
                row['hidden_reasoning_retained']=trace['hidden_reasoning_retained']
            if (path/'launcher-metadata.json').is_file():
                metadata=read(path/'launcher-metadata.json')
                for key in ('native_binary_sha256','code_mode_host_sha256','bwrap_sha256','profile_template_sha256','model_requested'):
                    row[key]=metadata.get(key,'unknown')
        ledger.append(row)
    (DOC/'RUN_LEDGER.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in ledger),encoding='utf-8')
    usage=[r['usage'] for r in ledger if isinstance(r['usage'],dict)]
    print(json.dumps({'records':len(ledger),'calls_with_observable_usage':len(usage),
        'reported_input_tokens':sum(u['input_tokens'] for u in usage if isinstance(u['input_tokens'],int)),
        'reported_output_tokens':sum(u['output_tokens'] for u in usage if isinstance(u['output_tokens'],int)),'cost_usd':'unknown'}))


if __name__=='__main__': main()
