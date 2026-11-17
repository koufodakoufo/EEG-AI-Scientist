"""Versioned, trusted-admin native-log privacy projection; never a model API.

The local root is the attestation authority. This is neither a signature nor
general DLP over authorized scientific payloads. Raw audit APIs stay separate.
"""
from __future__ import annotations

import hashlib
import copy
from datetime import datetime
import math
from pathlib import Path
import re
from urllib.parse import unquote_to_bytes

from eegfm.agent.provider import _audit_initial_records, _hash, _regular, _trace_records_from_bytes
from eegfm.agent.provider_trace import _audit_native_records, _envelope, _json, command, parse_tool, supported_shell_argv, local_rejections_enabled, local_payload_limit_rejection
from eegfm.evaluation.bundle import canonical_bytes

SCHEMA = 'trusted_admin_trace_v2'
PROFILE_KEYS = ('episode_id', 'run_id', 'model', 'effort', 'parent_thread', 'agent_prefix', 'inherited_context')
METADATA = {'world_state', 'inter_agent_communication_metadata', 'token_usage_record', 'token_count',
            'reasoning', 'Reasoning', 'assistant_commentary', 'additional_tools'}
INITIAL_METADATA = {'world_state', 'additional_tools'}
SESSION_CONTEXT_POLICY = 'trusted_root_pre_task_v1'
CONTEXT_ENROLLMENT_SCHEMA = 'trusted_root_pre_task_context_v1'


def source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def audit_profile(identity: dict) -> dict:
    keys = PROFILE_KEYS + tuple(key for key in ('native_timing', 'public_resource_delivery') if key in identity)
    return {key: identity[key] for key in keys}


def initial_metadata_sha256(kind: str, payload: dict) -> str:
    """Hash instruction-bearing data, omitting only the native tool-catalog nonce."""
    if kind == 'world_state':
        return _hash(payload)
    if (kind != 'additional_tools' or set(payload) != {'type', 'id', 'role', 'tools'}
            or payload['type'] != kind or payload['role'] != 'developer' or not isinstance(payload['tools'], list)
            or not isinstance(payload['id'], str)
            or re.fullmatch(r'at_[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', payload['id']) is None):
        raise ValueError('Unexpected native additional_tools payload')
    return _hash({key: payload[key] for key in ('type', 'role', 'tools')})


def _metadata_profile(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(row, dict) and set(row) == {'kind', 'payload_sha256'}
        and isinstance(row['kind'], str) and row['kind'] in INITIAL_METADATA and _sha(row['payload_sha256'])
        for row in value)


def _message_shape(value: object) -> list:
    if not isinstance(value, list) or not value or any(
            not isinstance(row, dict) or set(row) != {'role', 'kinds', 'content_sha256'}
            or row['role'] not in ('system', 'developer', 'user') or not isinstance(row['kinds'], list)
            or not row['kinds'] or any(not isinstance(kind, str) for kind in row['kinds']) or not _sha(row['content_sha256'])
            for row in value):
        raise ValueError('Invalid complete context variant message profile')
    return [(row['role'], row['kinds']) for row in value]


def _primary_context(identity: dict) -> dict:
    inherited = identity['inherited_context']
    return {'initial_messages': inherited['initial_messages'], 'memory_summary_sha256': inherited['memory_summary_sha256'],
            'initial_metadata': identity['trace_export']['initial_metadata']}


def _validate_compatible_context(identity: dict, bundle: dict) -> None:
    """Keep fixed structure, memory and environment across reviewed platform text."""
    primary = _primary_context(identity)
    shape = _message_shape(primary['initial_messages'])
    if (not isinstance(bundle, dict) or set(bundle) != set(primary)
            or not _sha(primary['memory_summary_sha256']) or sum(role == 'user' for role, _ in shape) != 1
            or not any('memories.instructions' in kinds for _, kinds in shape)
            or _message_shape(bundle['initial_messages']) != shape
            or not _metadata_profile(bundle['initial_metadata'])
            or [row['kind'] for row in bundle['initial_metadata']] != [row['kind'] for row in primary['initial_metadata']]
            or bundle['memory_summary_sha256'] != primary['memory_summary_sha256']
            or any(actual != expected for actual, expected in zip(bundle['initial_messages'], primary['initial_messages'])
                   if not (expected['role'] == 'developer' and ('generic.developer_instructions' in expected['kinds']
                       or set(expected['kinds']) <= {'host_skills.instructions', 'tools.deferred_namespaces', 'plugins.recommendations'})))):
        raise ValueError('Context enrollment requires common ordered structure, memory and environment')


def base_profile_sha256(identity: dict) -> str:
    """Bind the immutable base identity, sanitizer, gateway and opt-in policy."""
    return _hash({'audit_profile': audit_profile(identity), 'trace_export': identity['trace_export'], 'gateway': identity['gateway']})


def derive_session_context_identity(identity: dict, session: dict, *, context_id: str, context_enrollment: dict) -> dict:
    """Root review is trusted provenance, not a server-side semantic proof.

    The raw encrypted bootstrap cannot prove the root's plaintext spawn request;
    its published bytes and separate root-owned spawn evidence are hash-bound.
    """
    from eegfm.agent.provider import bootstrap
    validate_binding(identity)
    required = {'schema_version', 'base_profile_sha256', 'episode_id', 'run_id', 'session_id', 'context_id', 'agent_path',
                'context_bundle', 'reviewed_source', 'bootstrap_sha256', 'spawn_evidence_sha256', 'review_sha256'}
    value = context_enrollment
    if (identity['trace_export'].get('session_context_policy') != SESSION_CONTEXT_POLICY
            or not isinstance(value, dict) or set(value) != required or value['schema_version'] != CONTEXT_ENROLLMENT_SCHEMA
            or value['base_profile_sha256'] != base_profile_sha256(identity)
            or any(value[key] != identity[key] for key in ('episode_id', 'run_id'))
            or value['session_id'] != session['session_id'] or value['agent_path'] != session['agent_path']
            or not _identifier(context_id) or value['context_id'] != context_id
            or value['bootstrap_sha256'] != hashlib.sha256(bootstrap(identity, session['session_id']).encode()).hexdigest()
            or not _sha(value['spawn_evidence_sha256']) or not _sha(value['review_sha256'])):
        raise ValueError('Explicit bound trusted-root pre-task context enrollment required')
    source = value['reviewed_source']
    if (not isinstance(source, dict) or set(source) != {'path_sha256', 'prefix_bytes', 'prefix_sha256'}
            or type(source['prefix_bytes']) is not int or not 0 < source['prefix_bytes'] <= 64 * 1024**2
            or not _sha(source['path_sha256']) or not _sha(source['prefix_sha256'])):
        raise ValueError('Exact reviewed raw prefix provenance required')
    _validate_compatible_context(identity, value['context_bundle'])
    result = copy.deepcopy(identity)
    result['inherited_context']['initial_messages'] = copy.deepcopy(value['context_bundle']['initial_messages'])
    result['trace_export']['initial_metadata'] = copy.deepcopy(value['context_bundle']['initial_metadata'])
    result['trace_export']['audit_profile_sha256'] = _hash(audit_profile(result))
    return result


def _validate_context_variants(identity: dict) -> None:
    binding = identity['trace_export']
    if 'context_variants' not in binding:
        return
    variants = binding['context_variants']
    primary = _primary_context(identity)
    if (not isinstance(variants, list) or len(variants) != 2 or variants[0] == variants[1]
            or primary not in variants or any(not isinstance(bundle, dict) or set(bundle) != set(primary) for bundle in variants)):
        raise ValueError('Two distinct complete context variants must include the primary bundle')
    message_shape = _message_shape(primary['initial_messages'])
    if (not _sha(primary['memory_summary_sha256']) or sum(role == 'user' for role, _ in message_shape) != 1
            or not any('memories.instructions' in kinds for _, kinds in message_shape)):
        raise ValueError('Context variants require one environment and a bound memory profile')
    metadata_shape = [row['kind'] for row in primary['initial_metadata']]
    for bundle in variants:
        messages = bundle['initial_messages']
        metadata = bundle['initial_metadata']
        if (_message_shape(messages) != message_shape or not _metadata_profile(metadata)
                or [row['kind'] for row in metadata] != metadata_shape
                or bundle['memory_summary_sha256'] != primary['memory_summary_sha256']
                # Platforms may bundle generic instructions with memory in one
                # developer message. Its full hash must still match one exact
                # enrolled bundle; the summary and standalone memory stay fixed.
                or any(actual != expected for actual, expected in zip(messages, primary['initial_messages'])
                       if expected['role'] == 'user' or ('memories.instructions' in expected['kinds']
                           and not (expected['role'] == 'developer'
                                    and 'generic.developer_instructions' in expected['kinds'])))):
            raise ValueError('Context variants require common ordered structure, memory and environment')


def matches_context_bundle(identity: dict, messages: list, metadata: list, memory_sha256: str | None) -> bool:
    """Compare a complete observed bundle, never its fields independently."""
    binding = identity['trace_export']
    observed = {'initial_messages': messages, 'initial_metadata': metadata, 'memory_summary_sha256': memory_sha256}
    if 'context_variants' in binding:
        return observed in binding['context_variants']
    return observed == _primary_context(identity)


def validate_binding(identity: dict) -> None:
    binding = identity.get('trace_export')
    required = {'schema_version', 'client_source_sha256', 'sanitizer_source_sha256', 'audit_profile_sha256', 'initial_metadata'}
    if (not isinstance(binding, dict) or not required <= set(binding) or set(binding) - required - {'context_variants', 'session_context_policy', 'local_validation_rejections'}
            or binding['schema_version'] != SCHEMA
            or any(not isinstance(binding[key], str) or re.fullmatch('[0-9a-f]{64}', binding[key]) is None
                   for key in ('client_source_sha256', 'sanitizer_source_sha256', 'audit_profile_sha256'))
            or binding['sanitizer_source_sha256'] != source_sha256()
            or binding['audit_profile_sha256'] != _hash(audit_profile(identity))
            or not _metadata_profile(binding['initial_metadata'])):
        raise ValueError('Prospective trusted-admin sanitizer/profile binding required')
    if 'local_validation_rejections' in binding and not local_rejections_enabled(identity):
        raise ValueError('Local rejection policy requires the exact reviewed fixed client')
    if 'session_context_policy' in binding:
        if binding['session_context_policy'] != SESSION_CONTEXT_POLICY or 'context_variants' in binding:
            raise ValueError('Session context policy must be explicit and excludes context variants')
        _validate_compatible_context(identity, _primary_context(identity))
    _validate_context_variants(identity)


def _sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _identifier(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch('[A-Za-z0-9_-]{1,100}', value) is not None


def _timestamp(value: object) -> None:
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)', value):
        raise ValueError('Native timestamp must be a typed time value')
    datetime.fromisoformat(value.replace('Z', '+00:00'))


def _output(value: list) -> list:
    result = _envelope(value)
    for key in ('chunk_id', 'wall_time_seconds', 'original_token_count'):
        if key not in result or result[key] is None:
            continue
        item = result[key]
        valid = (isinstance(item, str) and re.fullmatch('[0-9a-f]{1,32}', item) is not None if key == 'chunk_id'
                 else type(item) is int and 0 <= item <= 10**8 if key == 'original_token_count'
                 else type(item) in (int, float) and 0 <= item <= 3600 and math.isfinite(item))
        if not valid:
            raise ValueError('Invalid safe scalar in native result envelope')
    return [{'type': 'input_text', 'text': part['text']} for part in value]


def _shell(native: dict, identity: dict, session: dict, requests: list) -> dict:
    argv = native.get('command')
    prefix = command(identity, session['session_id'])
    if (native.get('type') != 'CommandExecution'
            or not isinstance(native.get('aggregated_output'), str)
            or not supported_shell_argv(argv) or not isinstance(argv[-1], str)
            or not argv[-1].startswith(prefix)):
        raise ValueError('Unauthorized native shell cannot be exported')
    encoded = argv[-1][len(prefix):]
    if (re.fullmatch(r'[A-Za-z0-9_.~%\-]+', encoded) is None or re.search(r'%(?![A-Fa-f0-9]{2})', encoded)
            or canonical_bytes(_json(unquote_to_bytes(encoded).decode('utf-8'))) not in requests):
        raise ValueError('Native shell does not bind an approved request')
    if not (native.get('status') == 'completed' and type(native.get('exit_code')) is int and native['exit_code'] == 0
            or local_payload_limit_rejection(identity, encoded, native)):
        raise ValueError('Unauthorized native shell cannot be exported')
    return {key: native.get(key) for key in ('type', 'command', 'aggregated_output', 'status', 'exit_code')}


def sanitize_admin_trace(path: Path, identity: dict, session: dict, *, context_id: str,
                         prior_source: dict | None = None, complete: bool = False,
                         context_enrollment: dict | None = None) -> dict:
    """Local admin only: verify raw initial content and grammar before export."""
    validate_binding(identity)
    opted_in = 'session_context_policy' in identity['trace_export']
    if opted_in != (context_enrollment is not None):
        raise ValueError('Context enrollment differs from immutable session context policy')
    if opted_in:
        identity = derive_session_context_identity(identity, session, context_id=context_id, context_enrollment=context_enrollment)
    raw = _regular(Path(path)).read_bytes()
    if len(raw) > 64 * 1024**2:
        raise ValueError('Local native trace byte cap')
    records = _trace_records_from_bytes(raw, allow_partial=not complete)
    prefix_bytes = sum(map(len, raw.splitlines(keepends=True)[:len(records)]))
    source = {'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
              'prefix_sha256': hashlib.sha256(raw[:prefix_bytes]).hexdigest(), 'prefix_bytes': prefix_bytes,
              'path_sha256': _hash(str(Path(path).resolve()))}
    if opted_in:
        reviewed = context_enrollment['reviewed_source']
        if (reviewed['path_sha256'] != source['path_sha256'] or reviewed['prefix_bytes'] > source['prefix_bytes']
                or hashlib.sha256(raw[:reviewed['prefix_bytes']]).hexdigest() != reviewed['prefix_sha256']
                or not raw[:reviewed['prefix_bytes']].endswith(b'\n')):
            raise ValueError('Local raw source differs from the reviewed prefix')
    if prior_source is not None and (source['path_sha256'] != prior_source['path_sha256']
            or len(raw) < prior_source['raw_bytes']
            or hashlib.sha256(raw[:prior_source['raw_bytes']]).hexdigest() != prior_source['raw_sha256']
            or hashlib.sha256(raw[:prior_source['prefix_bytes']]).hexdigest() != prior_source['prefix_sha256']):
        raise ValueError('Local admitted raw prefix changed')
    initial = _audit_initial_records(records, identity=identity, agent_path=session['agent_path'], context_id=context_id, session_id=session['session_id'])
    if not initial['valid']:
        raise ValueError('Raw initial context differs from prospective profile')
    projected, requests, messages, first_tool = [], [], iter(initial['initial_messages']), False
    for ordinal, row in enumerate(records):
        kind, item = row.get('type'), row.get('payload', {})
        ptype = item.get('type')
        out = {'type': kind, 'payload': {}, 'source_ordinal': ordinal}
        if 'timestamp' in row:
            _timestamp(row['timestamp'])
            out['timestamp'] = row['timestamp']
        metadata = None
        if kind == 'session_meta':
            payload = {key: item.get(key) for key in ('id', 'parent_thread_id', 'agent_path')}
        elif kind == 'turn_context':
            payload = {'turn_id': item.get('turn_id'), 'model': item.get('model'),
                       'effort': item.get('effort') or item.get('collaboration_mode', {}).get('settings', {}).get('reasoning_effort')}
        elif kind == 'response_item':
            if ptype in {'message', 'agent_message'} and (ptype == 'agent_message' or item.get('role') in {'user', 'system', 'developer'}):
                if first_tool: raise ValueError('Late scientific/platform input cannot be exported')
                message = next(messages)
                payload = {'type': 'initial_context_hash', **message}
                if ptype == 'agent_message': payload.update(author=item.get('author'), recipient=item.get('recipient'))
            elif ptype == 'custom_tool_call':
                first_tool = True
                if item.get('name') != 'exec': raise ValueError('Unauthorized native tool')
                operation, value = parse_tool(item.get('input'), identity, session['session_id'])
                if operation == 'call': requests.append(canonical_bytes(value))
                payload = {key: item.get(key) for key in ('type', 'name', 'call_id', 'input')}
            elif ptype == 'custom_tool_call_output':
                payload = {'type': ptype, 'call_id': item.get('call_id'),
                           'output': _output(item.get('output'))}
            elif ptype == 'message' and item.get('role') == 'assistant':
                if item.get('phase') == 'final_answer':
                    content = item.get('content', [])
                    if len(content) != 1 or content[0].get('type') != 'output_text' or content[0].get('text') != 'SESSION_SEALED':
                        raise ValueError('Unexpected native final cannot be exported')
                    payload = {'type': 'message', 'role': 'assistant', 'phase': 'final_answer',
                               'content': [{'type': 'output_text', 'text': 'SESSION_SEALED'}],
                               'internal_chat_message_metadata_passthrough': {'turn_id': item.get('internal_chat_message_metadata_passthrough', {}).get('turn_id')}}
                else: metadata = 'assistant_commentary'
            elif ptype in {'reasoning', 'additional_tools'}: metadata = ptype
            elif ptype == 'configuration_update' and not first_tool and item == {'type': ptype, 'reasoning': {'effort': identity['effort']}}:
                payload = {'type': ptype, 'reasoning': {'effort': identity['effort']}}
            else: raise ValueError('Unknown native tool/input cannot be exported')
        elif kind == 'event_msg':
            if ptype == 'item_completed':
                native = item.get('item', {})
                if native.get('type') == 'CommandExecution': payload = {'type': ptype, 'item': _shell(native, identity, session, requests)}
                elif native.get('type') in {'Reasoning', 'AgentMessage'}: metadata = native['type'] if native['type'] == 'Reasoning' else 'assistant_commentary'
                else: raise ValueError('Unknown native execution cannot be exported')
            elif ptype == 'token_count': metadata = ptype
            elif ptype in {'task_started', 'thread_settings_applied', 'task_complete'}:
                if first_tool and ptype != 'task_complete': raise ValueError('Late task/settings input')
                payload = {'type': ptype}
                if ptype in {'task_started', 'task_complete'}: payload['turn_id'] = item.get('turn_id')
            else: raise ValueError('Unknown native event cannot be exported')
        elif kind in {'world_state', 'inter_agent_communication_metadata', 'token_usage_record'}:
            if kind == 'inter_agent_communication_metadata' and item != {'trigger_turn': True}:
                raise ValueError('Unexpected inter-agent context metadata')
            metadata = kind
        else: raise ValueError('Unknown native record cannot be exported')
        if metadata:
            out['type'], payload = 'sanitized_metadata', {'kind': metadata, 'record_sha256': _hash(row)}
            if metadata in INITIAL_METADATA:
                payload['payload_sha256'] = initial_metadata_sha256(metadata, item)
        out['payload'] = payload
        projected.append(out)
    result = {'schema_version': SCHEMA, 'binding': identity['trace_export'], 'source': source, 'prior_source': prior_source,
              'initial_audit': initial, 'records': projected}
    validate_admin_export(result, identity, session, context_id=context_id, prior_source=prior_source)
    if opted_in and not complete:
        # Check the full available tail above, including pending allowed status
        # calls, then export only the exact completed prefix reviewed by root.
        prefix_records = _trace_records_from_bytes(raw[:reviewed['prefix_bytes']], allow_partial=False)
        result['records'] = projected[:len(prefix_records)]
        result['source'] = {**source, 'raw_bytes': reviewed['prefix_bytes'], 'prefix_bytes': reviewed['prefix_bytes'],
                            'raw_sha256': reviewed['prefix_sha256'], 'prefix_sha256': reviewed['prefix_sha256']}
        validate_admin_export(result, identity, session, context_id=context_id, prior_source=prior_source)
        pre_task = _audit_native_records(result['records'], identity, session, None, initial, sanitized=True, pre_task=True)
        if not pre_task['valid']:
            raise ValueError('Reviewed prefix lacks a completed pre-task waiting gateway delivery: ' + '; '.join(pre_task['issues']))
    if complete:
        execution = _audit_native_records(projected, identity, session, None, initial, sanitized=True)
        if not execution['valid']:
            raise ValueError('Local native execution audit rejected export')
    return result


def validate_admin_export(value: dict, identity: dict, session: dict, *, context_id: str,
                          prior_source: dict | None = None) -> tuple[list, dict]:
    """Remote trusted-admin route only; uploaded bytes cannot enable this API."""
    validate_binding(identity)
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'binding', 'source', 'prior_source', 'initial_audit', 'records'}
            or value['schema_version'] != SCHEMA or value['binding'] != identity['trace_export'] or value['prior_source'] != prior_source):
        raise ValueError('Unenrolled export or raw-prefix chain')
    source = value['source']
    if (not isinstance(source, dict) or set(source) != {'raw_sha256', 'raw_bytes', 'path_sha256', 'prefix_sha256', 'prefix_bytes'}
            or type(source['raw_bytes']) is not int or type(source['prefix_bytes']) is not int
            or not 0 < source['prefix_bytes'] <= source['raw_bytes'] <= 64 * 1024**2
            or any(not _sha(source[key]) for key in ('raw_sha256', 'path_sha256', 'prefix_sha256'))
            or prior_source and (source['prefix_bytes'] < prior_source['prefix_bytes'] or source['raw_bytes'] < prior_source['raw_bytes']
                                 or source['path_sha256'] != prior_source['path_sha256'])):
        raise ValueError('Invalid local raw source provenance')
    audit = value['initial_audit']
    if (not isinstance(audit, dict) or set(audit) != {'valid', 'issues', 'context_id', 'agent_path', 'initial_messages', 'memory_summary_sha256', 'disclosure'}
            or audit['valid'] is not True or audit['issues'] != [] or audit['context_id'] != context_id or audit['agent_path'] != session['agent_path']
            or audit['memory_summary_sha256'] != identity['inherited_context']['memory_summary_sha256']
            or audit['disclosure'] != identity['inherited_context']['disclosure']):
        raise ValueError('Invalid trusted local initial audit')
    rows, markers, first_tool, requests = value['records'], [], False, []
    initial_metadata, contexts, inter_agent, calls, outputs = [], 0, 0, set(), set()
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict) or rows[0].get('type') != 'session_meta':
        raise ValueError('Sanitized native context start required')
    for ordinal, row in enumerate(rows):
        if (not isinstance(row, dict) or set(row) - {'type', 'payload', 'timestamp', 'source_ordinal'}
                or not {'type', 'payload', 'source_ordinal'} <= set(row) or not isinstance(row['payload'], dict)
                or type(row['source_ordinal']) is not int or row['source_ordinal'] != ordinal):
            raise ValueError('Altered source record ordering/projection')
        if 'timestamp' in row:
            _timestamp(row['timestamp'])
        item, kind = row['payload'], row['type']
        ptype = item.get('type')
        if kind == 'sanitized_metadata':
            expected = {'kind', 'record_sha256'} | ({'payload_sha256'} if item.get('kind') in INITIAL_METADATA else set())
            if set(item) != expected or item['kind'] not in METADATA or not _sha(item['record_sha256']):
                raise ValueError('Invalid redacted metadata')
            if item['kind'] in {'world_state', 'inter_agent_communication_metadata', 'additional_tools'} and first_tool:
                raise ValueError('Late native context metadata')
            if item['kind'] in INITIAL_METADATA:
                initial_metadata.append({'kind': item['kind'], 'payload_sha256': item['payload_sha256']})
            if item['kind'] == 'inter_agent_communication_metadata':
                inter_agent += 1
        elif kind == 'session_meta':
            if ordinal != 0 or item != {'id': context_id, 'parent_thread_id': identity['parent_thread'], 'agent_path': session['agent_path']}:
                raise ValueError('Sanitized context identity mismatch')
        elif kind == 'turn_context':
            contexts += 1
            if (first_tool or set(item) != {'turn_id', 'model', 'effort'} or not _identifier(item['turn_id'])
                    or (item['model'], item['effort']) != (identity['model'], identity['effort'])):
                raise ValueError('Sanitized model mismatch')
        elif kind == 'response_item':
            if ptype == 'initial_context_hash':
                expected = {'type', 'role', 'kinds', 'text_sha256', 'content_sha256'} | ({'author', 'recipient'} if item.get('role') == 'agent_message' else set())
                if first_tool or set(item) != expected: raise ValueError('Invalid or late initial hash marker')
                if item.get('role') == 'agent_message' and ((item['author'], item['recipient']) != ('/root', session['agent_path'])
                        or item['kinds'] != ['declared_bootstrap'] or item['text_sha256'] != item['content_sha256']
                        or not any(marker['role'] == 'user' for marker in markers)):
                    raise ValueError('Bootstrap metadata mismatch')
                markers.append({key: item[key] for key in ('role', 'kinds', 'text_sha256', 'content_sha256')})
            elif ptype == 'custom_tool_call':
                first_tool = True
                if (set(item) != {'type', 'name', 'call_id', 'input'} or item['name'] != 'exec'
                        or not _identifier(item['call_id']) or item['call_id'] in calls):
                    raise ValueError('Unauthorized exported tool')
                calls.add(item['call_id'])
                operation, request = parse_tool(item['input'], identity, session['session_id'])
                if operation == 'call':
                    if (('native_timing' in identity or 'session_context_policy' in identity['trace_export']) and prior_source is None
                            and request['operation'] not in {'task', 'request_status'}):
                        raise ValueError('Only task delivery and status may precede native admission')
                    if 'session_context_policy' in identity['trace_export'] and prior_source is None:
                        if (request['operation'] == 'task' and request != {'request_id': 'task', 'operation': 'task', 'payload': {}}
                                or request['operation'] == 'request_status' and request['payload'] != {'request_id': 'task'}):
                            raise ValueError('Pre-task gateway must follow the exact task bootstrap')
                    requests.append(canonical_bytes(request))
            elif ptype == 'custom_tool_call_output':
                if (set(item) != {'type', 'call_id', 'output'} or item['call_id'] not in calls or item['call_id'] in outputs
                        or _output(item['output']) != item['output']):
                    raise ValueError('Unexpected or out-of-order native output')
                outputs.add(item['call_id'])
            elif ptype == 'message':
                if (set(item) != {'type', 'role', 'phase', 'content', 'internal_chat_message_metadata_passthrough'} or item['role'] != 'assistant'
                        or item['phase'] != 'final_answer' or item['content'] != [{'type': 'output_text', 'text': 'SESSION_SEALED'}]
                        or set(item['internal_chat_message_metadata_passthrough']) != {'turn_id'}
                        or not _identifier(item['internal_chat_message_metadata_passthrough']['turn_id'])):
                    raise ValueError('Unexpected exported message')
            elif ptype == 'configuration_update':
                if first_tool or item != {'type': ptype, 'reasoning': {'effort': identity['effort']}}: raise ValueError('Unexpected settings')
            else: raise ValueError('Unknown exported response')
        elif kind == 'event_msg':
            if ptype == 'item_completed':
                if set(item) != {'type', 'item'} or set(item['item']) != {'type', 'command', 'aggregated_output', 'status', 'exit_code'}: raise ValueError('Unexpected execution metadata')
                _shell(item['item'], identity, session, requests)
            elif ptype in {'task_started', 'task_complete'}:
                if set(item) != {'type', 'turn_id'} or not _identifier(item['turn_id']):
                    raise ValueError('Unexpected task metadata')
            elif item != {'type': 'thread_settings_applied'}: raise ValueError('Unknown exported event')
        else: raise ValueError('Unknown exported record')
    if markers != audit['initial_messages']:
        raise ValueError('Initial proof marker mismatch')
    if contexts != 1 or inter_agent > 1:
        raise ValueError('Unenrolled initial metadata or multiple native turns')
    profile = [{key: item[key] for key in ('role', 'kinds', 'content_sha256')} for item in markers if item['role'] != 'agent_message']
    if 'context_variants' not in identity['trace_export'] and initial_metadata != identity['trace_export']['initial_metadata']:
        raise ValueError('Unenrolled initial metadata or multiple native turns')
    if (not matches_context_bundle(identity, profile, initial_metadata, audit['memory_summary_sha256'])
            or sum(item['role'] == 'agent_message' for item in markers) != 1):
        raise ValueError('Initial proof differs from prospective profile')
    for item in markers:
        if any(re.fullmatch('[0-9a-f]{64}', item[key]) is None for key in ('text_sha256', 'content_sha256')): raise ValueError('Initial proof requires hashes')
    return rows, audit
