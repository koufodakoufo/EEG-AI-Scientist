"""Literal-only auditing of delegated coding gateway/poll native records.

No JavaScript evaluation or model reasoning export. The existing controller is
the authority after this transport audit, not a model's self-reported success.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
import re
from urllib.parse import quote, unquote_to_bytes

from eegfm.agent.provider import WAIT_STATUS_PREFIX, _trace_records, audit_initial_context, call_template, poll_template, command
from eegfm.evaluation.bundle import canonical_bytes

SHELL_PREFIX = [r"C:\Users\14090\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe", "-Command"]


def _json(text: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate tool JSON key')
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=pairs)
    canonical_bytes(value)
    return value


def percent_encode(value: dict) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    text = ''.join(('\\u%04x' % ord(char)) if 0xD800 <= ord(char) <= 0xDFFF else char for char in text)
    return quote(text, safe='-_.~')


def parse_tool(code: str, identity: dict, session: str):
    if not isinstance(code, str):
        raise ValueError('Plaintext gateway tool source required')
    code = code.strip(' \t\r\n\v\f')
    poll = re.fullmatch(r"const result = await tools\.write_stdin\(\{session_id:([1-9][0-9]*),chars:'',max_output_tokens:9000,yield_time_ms:1000\}\); text\(result\);", code)
    if poll:
        return 'poll', int(poll[1])
    waited = code.startswith(WAIT_STATUS_PREFIX)
    if waited:
        code = code.removeprefix(WAIT_STATUS_PREFIX)
    prefix = 'const request = '
    if not code.startswith(prefix):
        raise ValueError('Not an exact coding gateway/poll template')
    body = code[len(prefix):]
    _, end = json.JSONDecoder().raw_decode(body)
    request = _json(body[:end])
    if code != call_template(identity, session, body[:end]):
        raise ValueError('Coding gateway template altered')
    if not isinstance(request, dict):
        raise ValueError('Gateway request object required')
    if waited and request.get('operation') != 'request_status':
        raise ValueError('The fixed wait prefix is only for request_status')
    return 'call', request


def _envelope(output):
    if (not isinstance(output, list) or len(output) != 2 or any(not isinstance(part, dict) or part.get('type') != 'input_text' for part in output)
            or re.fullmatch(r'Script completed\n(?:Wall time [0-9.]+ seconds\n)?Output:\n', output[0].get('text', '')) is None):
        raise ValueError('Unexpected or extra native gateway output chunks')
    result = _json(output[1].get('text', ''))
    allowed = {'chunk_id', 'exit_code', 'output', 'session_id', 'wall_time_seconds', 'original_token_count'}
    if not isinstance(result, dict) or set(result) - allowed or not isinstance(result.get('output'), str):
        raise ValueError('Complete native result envelope required')
    if 'session_id' in result and result['session_id'] is not None and (type(result['session_id']) is not int or result['session_id'] <= 0):
        raise ValueError('Invalid native transport session ID')
    if 'exit_code' in result and result['exit_code'] is not None and type(result['exit_code']) is not int:
        raise ValueError('Invalid native process exit code')
    return result


def _timing(records: list[dict], session: dict) -> dict:
    """Prove execution against its original reservation, not ingestion time."""
    start, duration = session.get('started_epoch'), session.get('timeout_seconds')
    if (type(start) not in (int, float) or not math.isfinite(start)
            or type(duration) is not int or not 1 <= duration <= 240):
        raise ValueError('Original finite native session reservation required')
    deadline, previous, completion = start + duration, start, None
    for record in records:
        item, kind = record.get('payload', {}), record.get('type')
        ptype = item.get('type')
        critical = (kind == 'turn_context' or kind == 'event_msg' and ptype in {'task_started', 'task_complete', 'item_completed'}
                    or kind == 'response_item' and (ptype in {'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'}
                        or ptype == 'message' and item.get('role') == 'assistant' and item.get('phase') == 'final_answer'))
        if not critical:
            continue
        try:
            stamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('Native timestamp must include its UTC offset')
            epoch = stamp.timestamp()
        except (KeyError, TypeError, AttributeError, ValueError, OverflowError) as error:
            raise ValueError('Qualified native execution timestamps required') from error
        if not math.isfinite(epoch) or not previous <= epoch <= deadline:
            raise ValueError('Native execution outside original reservation or timestamp order')
        previous = epoch
        if kind == 'event_msg' and ptype == 'task_complete':
            completion = epoch
    if completion is None:
        raise ValueError('Timestamped native completion required')
    return {'started_epoch': start, 'deadline_epoch': deadline, 'completion_epoch': completion,
            'execution_wall_seconds': completion - start}


def audit_native_context(path: Path, identity: dict, session: dict, deliveries: list[dict], *,
                         trusted_admin_initial: dict | None = None) -> dict:
    registered = session.get('registered_context') or {}
    initial = trusted_admin_initial if trusted_admin_initial is not None else audit_initial_context(
        path, identity=identity, agent_path=session['agent_path'], context_id=registered.get('context_id'), session_id=session['session_id'])
    result = _audit_native_records(_trace_records(path, allow_partial=False), identity, session, deliveries,
                                   initial, sanitized=trusted_admin_initial is not None)
    if str(Path(path).resolve()) != registered.get('trace_path'):
        result['issues'].append('Native trace is not the registered context source')
        result['valid'] = False
    result['trace_sha256'] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return result


def _audit_native_records(records: list[dict], identity: dict, session: dict, deliveries: list[dict] | None,
                          initial: dict, *, sanitized: bool) -> dict:
    issues = list(initial['issues'])
    timing = None
    try:
        timing = _timing(records, session)
    except ValueError as error:
        issues.append(str(error))
    calls, outputs, shells, contexts, finals, complete = [], {}, [], [], [], []
    first_tool = None
    for position, record in enumerate(records):
        item, kind = record.get('payload', {}), record.get('type')
        ptype = item.get('type')
        if kind == 'turn_context':
            effort = item.get('effort') or item.get('collaboration_mode', {}).get('settings', {}).get('reasoning_effort')
            contexts.append((item.get('turn_id'), item.get('model'), effort))
        elif kind == 'response_item':
            if ptype in {'function_call', 'custom_tool_call'}:
                calls.append((position, item))
                first_tool = position if first_tool is None else first_tool
            elif ptype in {'function_call_output', 'custom_tool_call_output'}:
                outputs.setdefault(item.get('call_id'), []).append((position, item))
            elif ptype == 'message' and item.get('role') == 'assistant' and item.get('phase') == 'final_answer':
                finals.append((position, ''.join(part.get('text', '') for part in item.get('content', []) if part.get('type') == 'output_text'),
                               item.get('internal_chat_message_metadata_passthrough', {}).get('turn_id')))
            elif sanitized and ptype == 'initial_context_hash' and first_tool is None:
                pass
            elif ptype not in {'reasoning', 'message', 'agent_message', 'configuration_update', 'additional_tools'}:
                issues.append('Unexpected or opaque native tool/input record')
            if first_tool is not None and (ptype == 'agent_message' or ptype == 'message' and item.get('role') in {'user', 'developer', 'system'}):
                issues.append('Unexpected late scientific/platform input')
            if ptype == 'configuration_update' and (first_tool is not None or set(item) != {'type', 'reasoning'} or item.get('reasoning') != {'effort': identity['effort']}):
                issues.append('Unexpected native configuration change')
            if ptype == 'additional_tools' and first_tool is not None:
                issues.append('Late native tool interface change')
        elif kind == 'event_msg' and ptype == 'task_complete':
            complete.append((position, item.get('turn_id')))
        elif kind == 'event_msg' and ptype == 'item_completed':
            native = item.get('item', {})
            if native.get('type') == 'CommandExecution':
                shells.append((position, native))
            elif native.get('type') not in {'Reasoning', 'AgentMessage'}:
                issues.append('Unexpected native execution event')
        elif kind == 'event_msg':
            if ptype not in {'task_started', 'thread_settings_applied', 'token_count'}:
                issues.append('Unexpected native event type')
            elif ptype in {'task_started', 'thread_settings_applied'} and first_tool is not None:
                issues.append('Unexpected late native task/settings event')
        elif kind == 'compacted':
            issues.append('Compacted native context is not a fresh-session record')
        elif sanitized and kind == 'sanitized_metadata':
            if first_tool is not None and item.get('kind') in {'additional_tools', 'world_state', 'inter_agent_communication_metadata'}:
                issues.append('Unexpected late native context metadata')
        elif kind != 'session_meta':
            issues.append('Unexpected native top-level record')
    if (len(contexts) != 1 or contexts[0][1:] != (identity['model'], identity['effort'])
            or len(finals) != 1 or finals[0][1] != 'SESSION_SEALED' or len(complete) != 1
            or finals[0][2] != complete[0][1] or contexts[0][0] != complete[0][1] or finals[0][0] >= complete[0][0]):
        issues.append('One completed declared context and SESSION_SEALED required')
    pending, logical, polls, verified, seen = None, [], 0, [], set()
    for index, (position, item) in enumerate(calls):
        try:
            if item.get('type') != 'custom_tool_call' or item.get('name') != 'exec' or not item.get('call_id') or item['call_id'] in seen:
                raise ValueError('Only unique exact functions.exec calls are allowed')
            seen.add(item['call_id'])
            retained = outputs.get(item['call_id'], [])
            if len(retained) != 1 or retained[0][1].get('type') != 'custom_tool_call_output' or retained[0][0] <= position:
                raise ValueError('Exactly one later native tool output required')
            if not finals or retained[0][0] >= finals[0][0]:
                raise ValueError('Every native tool output must precede SESSION_SEALED')
            if index + 1 < len(calls) and retained[0][0] >= calls[index + 1][0]:
                raise ValueError('Native calls cannot overlap or precede previous output')
            operation, value = parse_tool(item.get('input'), identity, session['session_id'])
            envelope = _envelope(retained[0][1].get('output'))
            if operation == 'call':
                if pending is not None:
                    raise ValueError('Poll the existing native transport instead of resubmitting')
                pending = {'request': value, 'stdout': '', 'native_session': None, 'position': position,
                           'last_running_output': position}
            else:
                polls += 1
                if pending is None or pending['native_session'] != value:
                    raise ValueError('Native poll session was not returned by this gateway call')
            pending['stdout'] += envelope['output']
            native_session = envelope.get('session_id')
            if native_session is not None:
                if envelope.get('exit_code') is not None:
                    raise ValueError('Native transport cannot be running and completed')
                if pending['native_session'] not in (None, native_session):
                    raise ValueError('Native transport session identity changed')
                pending['native_session'] = native_session
                pending['last_running_output'] = retained[0][0]
            else:
                if envelope.get('exit_code') != 0:
                    raise ValueError('Gateway transport did not complete successfully')
                pending['terminal_output_position'] = retained[0][0]
                logical.append(pending)
                verified.append({'request_id': pending['request'].get('request_id'),
                                 'stdout_sha256': hashlib.sha256(pending['stdout'].encode()).hexdigest()})
                pending = None
        except (ValueError, TypeError, KeyError) as error:
            issues.append(str(error))
    if pending is not None:
        issues.append('Unresolved native transport session remains')
    if set(outputs) != seen:
        issues.append('Orphan, encrypted or missing native outputs')
    if not calls or len(calls) > 192 or len(shells) != len(logical) or (deliveries is not None and len(logical) != len(deliveries)):
        issues.append('Native gateway/delivery/command count mismatch')
    for index, actual in enumerate(logical):
        try:
            expected_stdout = actual['stdout']
            if deliveries is not None:
                delivered = deliveries[index]
                if canonical_bytes(actual['request']) != canonical_bytes(delivered['request']):
                    raise ValueError('Native request differs from durable gateway delivery')
                if expected_stdout != canonical_bytes(delivered['response']).decode() + '\n':
                    raise ValueError('Actual native stdout differs from durable gateway response')
            native_position, native = shells[index]
            if native.get('status') != 'completed' or type(native.get('exit_code')) is not int or native['exit_code'] != 0:
                raise ValueError('Native command must complete successfully with matching exit code zero')
            prefix = command(identity, session['session_id'])
            argv = native.get('command')
            if not isinstance(argv, list) or argv[:-1] != SHELL_PREFIX or not isinstance(argv[-1], str) or not argv[-1].startswith(prefix):
                raise ValueError('Native gateway shell command changed')
            encoded = argv[-1][len(prefix):]
            if re.fullmatch(r'[A-Za-z0-9_.~%\-]+', encoded) is None or re.search(r'%(?![0-9A-Fa-f]{2})', encoded):
                raise ValueError('Native URL payload is not shell-safe ASCII')
            if canonical_bytes(_json(unquote_to_bytes(encoded).decode('utf-8'))) != canonical_bytes(actual['request']):
                raise ValueError('Native command payload differs from its literal request')
            if (native.get('aggregated_output') != expected_stdout
                    or not actual['last_running_output'] < native_position < actual['terminal_output_position']):
                raise ValueError('Native command/output/chronology mismatch')
        except (ValueError, TypeError, KeyError, IndexError, UnicodeError) as error:
            issues.append(str(error))
    return {'valid': not issues, 'issues': sorted(set(issues)), 'context_id': initial['context_id'],
            'gateway_calls': len(logical), 'native_poll_calls': polls, 'actual_tool_calls': len(calls),
            'initial_context': initial, 'deliveries': verified,
            'timing': timing,
            'boundary': 'Audited tool context with disclosed inherited history; not OS isolation or blind capability measurement.'}
