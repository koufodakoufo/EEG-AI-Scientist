"""Collect visible Codex events while excluding reasoning and account metadata."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from eegfm.agent.budget import write_atomic
from eegfm.evaluation.bundle import digest_file


def cli_usage(stdout: str) -> dict[str, int] | None:
    """Retain reported terminal usage only; missing usage is not zero cost."""
    usage = None
    fields = {"input_tokens", "cached_input_tokens", "cache_write_input_tokens",
              "output_tokens", "reasoning_output_tokens"}
    for line in stdout.splitlines():
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(row, dict) or row.get("type") != "turn.completed":
            continue
        values = row.get("usage")
        if not isinstance(values, dict):
            continue
        selected = {key: value for key, value in values.items() if key in fields}
        if ({"input_tokens", "output_tokens"} <= selected.keys()
                and all(type(value) is int and value >= 0 for value in selected.values())):
            usage = selected
    return usage


def visible_payload(payload: dict[str,Any]) -> dict[str,Any] | None:
    kind=payload.get('type')
    if kind in {'function_call','custom_tool_call'}:
        return {key:payload[key] for key in ('type','call_id','name','arguments','input') if key in payload}
    if kind in {'function_call_output','custom_tool_call_output'}:
        return {key:payload[key] for key in ('type','call_id','output') if key in payload}
    if kind=='message' and payload.get('role') in {'user','assistant'} and payload.get('channel') not in {'analysis','justify','confidence'}:
        return {key:payload[key] for key in ('type','role','channel','content') if key in payload}
    return None


def declared_names(tools: list[dict[str,Any]], prefix: str='') -> list[str]:
    names=[]
    for tool in tools:
        name=prefix+str(tool.get('name',''))
        if tool.get('type')=='namespace': names.extend(declared_names(tool.get('tools',[]),name+'.'))
        elif tool.get('name'): names.append(name)
    return names


def collect_visible_trace(control_home: Path,destination: Path,*,sanitize_native: bool=True) -> dict[str,Any]:
    if destination.exists(): raise FileExistsError('Visible trace already collected')
    destination.mkdir(parents=True)
    visible=[]; metadata=[]; declarations=set(); sources=[]; excluded=0
    for path in sorted((control_home/'sessions').rglob('*.jsonl')):
        if path.is_symlink(): raise ValueError('Unexpected rollout symlink')
        sources.append({'path':str(path.relative_to(control_home)),'raw_sha256':digest_file(path)})
        sanitized=[]
        for line in path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line); payload=row.get('payload',{})
            if row.get('type')=='response_item':
                if payload.get('type')=='additional_tools': declarations.update(declared_names(payload.get('tools',[])))
                kept=visible_payload(payload)
                if kept is not None:
                    event={'timestamp':row.get('timestamp'),'type':'response_item','payload':kept}
                    visible.append(event); sanitized.append(event)
                else: excluded+=1
            elif row.get('type')=='turn_context':
                selected={key:payload.get(key) for key in ('cwd','model','effort','approval_policy','permission_profile','active_permission_profile','file_system_sandbox_policy','multi_agent_version')}
                metadata.append(selected)
                sanitized.append({'timestamp':row.get('timestamp'),'type':'turn_context','payload':selected})
            elif row.get('type')=='event_msg' and payload.get('type') in {'token_count','task_started','task_complete'}:
                # Raw token_count may contain model-limit/account fields. Keep
                # usage separately from the CLI's turn.completed event instead.
                excluded+=1
            else: excluded+=1
        if sanitize_native:
            # The dedicated process has ended. Keep visible native records only;
            # do not retain encrypted/private reasoning or account identifiers.
            temporary=path.with_suffix('.sanitizing')
            temporary.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in sanitized),encoding='utf-8')
            temporary.replace(path)
            sources[-1]['sanitized_sha256']=digest_file(path)
    if not sources: raise ValueError('No native rollout; actual nested tool provenance unavailable')
    out=destination/'visible_trace.jsonl'
    out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in visible),encoding='utf-8')
    report={'schema_version':'visible_trace_v1','sources':sources,'visible_events':len(visible),'excluded_records':excluded,
            'declared_tools':sorted(declarations),'turn_metadata':metadata,'trace_sha256':digest_file(out),
            'native_sanitized':sanitize_native,'hidden_reasoning_retained':False}
    write_atomic(destination/'trace-index.json',report)
    return report
