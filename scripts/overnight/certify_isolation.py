"""Build a versioned live-boundary record from native events, never self-report."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

BASE=Path('/data/duandh/eegfm-stage-a-20261028')
WORK=BASE/'overnight-20261029'
sys.path.insert(0,str(WORK/'integration/framework'))
from eegfm.research_bench.actor import build_profile,profile_template_sha256,validate_isolation_gate
from eegfm.research_bench.bundle import digest_file,verify_public_bundle
from eegfm.research_bench.budget import write_atomic
from eegfm.research_bench.trace import collect_visible_trace


def main() -> None:
    call_id='M10'; home=WORK/f'control/{call_id}'; evidence=WORK/f'evidence/{call_id}'
    meta=json.loads((home/'launcher-metadata.json').read_text())
    status=json.loads((evidence/'status.json').read_text())
    if status['status']!='completed' or status['exit_code']!=0 or status['process_cleanup']['surviving_owned_pids']:
        raise RuntimeError('Canary control did not finish cleanly')
    public=Path(meta['public']); verify_public_bundle(public)
    native=Path(meta['native_binary']); bwrap=WORK/'tools/bubblewrap/usr/bin'
    rebuilt=build_profile(case=Path(meta['case']),public=public,control_home=home,runtime=Path(meta['runtime']),native_binary=native,bwrap_dir=bwrap,model=meta['model_requested'])
    if hashlib.sha256(rebuilt.encode()).hexdigest()!=meta['profile_sha256'] or digest_file(home/'actor.config.toml')!=meta['profile_sha256']:
        raise RuntimeError('Canary used a different profile; do not backfill a pass')
    events=[json.loads(line) for line in (evidence/'stdout.jsonl').read_text().splitlines()]
    commands=[event['item'] for event in events if event.get('type')=='item.completed' and event.get('item',{}).get('type')=='command_execution']
    if len(commands)!=1 or commands[0]['exit_code']!=0 or '/usr/bin/python3 public/probe.py' not in commands[0]['command']:
        raise RuntimeError('Exactly one real successful probe command is required')
    probes=json.loads(commands[0]['aggregated_output'])
    listings={}
    for event in events:
        item=event.get('item',{})
        if event.get('type')=='item.completed' and item.get('type')=='mcp_tool_call':
            result=item.get('result') or {}
            for content in result.get('content',[]):
                if content.get('type')=='text': listings[item['tool']]=json.loads(content['text'])
    if listings.get('list_mcp_resources')!={'resources':[]} or listings.get('list_mcp_resource_templates')!={'resourceTemplates':[]}:
        raise RuntimeError('MCP resources are not empty')
    if "unknown MCP server 'isolation-canary-nonexistent'" not in (evidence/'stderr.log').read_text():
        raise RuntimeError('Unconfigured MCP read did not fail closed')
    raw_tools=[]; instruction_text=[]
    for path in (home/'sessions').rglob('*.jsonl'):
        for line in path.read_text().splitlines():
            row=json.loads(line); payload=row.get('payload',{})
            if row.get('type')=='response_item' and payload.get('type')=='additional_tools': raw_tools.append(json.dumps(payload))
            if row.get('type')=='response_item' and payload.get('type')=='message' and payload.get('role')=='developer': instruction_text.append(json.dumps(payload))
    declaration='\n'.join(raw_tools)
    if not declaration or any(name in declaration for name in ('web__run','image_gen__imagegen','"collaboration"','"spawn_agent"')):
        raise RuntimeError('Forbidden hosted/model tools remain declared')
    if any('<skills_instructions>' in text for text in instruction_text):
        raise RuntimeError('Automatic skill instructions unexpectedly loaded')
    trace=collect_visible_trace(home,evidence/'trace')
    contexts=trace['turn_metadata']
    if not contexts or any(context['model']!='gpt-6.1-sol' or context['effort']!='medium' or context['approval_policy']!='never' for context in contexts):
        raise RuntimeError('Actual model or approval settings differ')
    fingerprints={'native_binary_sha256':digest_file(native),'code_mode_host_sha256':digest_file(native.parent/'codex-code-mode-host'),
                  'bwrap_sha256':digest_file(bwrap/'bwrap'),'profile_template_sha256':profile_template_sha256('gpt-6.1-sol')}
    report={'schema_version':'isolation_report_v2','status':'passed','call_id':call_id,'cli_version':'0.165.0',**fingerprints,
            'profile_sha256':meta['profile_sha256'],'probes':probes,'tool_surface_verified':True,'model_control_succeeded':True,
            'actual_model':'gpt-6.1-sol','reasoning_effort':'medium','declared_top_level_tools':trace['declared_tools'],
            'mcp_status':'generic resource helper APIs remain; configured resource/template lists empty and unknown server fails closed',
            'evidence':{'events_sha256':digest_file(evidence/'stdout.jsonl'),'visible_trace_sha256':trace['trace_sha256'],
                        'probe_sha256':digest_file(public/'probe.py'),'native_status_sha256':digest_file(evidence/'status.json')},
            'limits':['Empirical boundary for this exact binary/profile, not a kernel vulnerability proof.',
                      'RAM is enforced by sampled descendant RSS (100ms), not a delegated kernel cgroup; virtual address space is intentionally not capped.',
                      'Hosted model control traffic is permitted; tool network traffic is denied.',
                      'No claim of absence of pretraining knowledge or absolute paper contamination.']}
    validate_isolation_gate(fingerprints,report)
    write_atomic(WORK/'evidence/ISOLATION_REPORT.json',report)
    print(json.dumps({'status':'passed','model':report['actual_model'],'probe_count':len(probes),'profile_template_sha256':report['profile_template_sha256']},indent=2))


if __name__=='__main__': main()
