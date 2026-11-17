"""Only a prospectively bound, deterministic pre-RPC byte-cap rejection recovers."""
import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from eegfm.agent import provider, provider_export, provider_trace
from test_provider_export import fixture


POLICY = 'fixed_windows_payload_limit_v1'
CLIENT_SHA = '0c4ea5dcaeb0bf6e41461f5b0ea74b12d9e70aaf9dc59ca8547cb1c1ac75539a'
ERROR = provider.canonical_bytes({'error_type': 'ValueError', 'status': 'gateway_rejected'}).decode()


def rejection_trace(tmp_path, *, opted_in=True, sizes=(8200, 9000)):
    path, identity, session, deliveries = fixture(tmp_path)
    if opted_in:
        identity['trace_export'].update(local_validation_rejections=POLICY, client_source_sha256=CLIENT_SHA)
    rows = provider._trace_records(path)
    at = next(i for i, row in enumerate(rows) if row['payload'].get('type') == 'custom_tool_call')
    failures = []
    for index, size in enumerate(sizes):
        request = {'request_id': 'oversized-' + str(index), 'operation': 'write',
                   'payload': {'path': 'draft.py', 'text': 'x' * size}}
        command = provider.command(identity, 'session-01') + provider_trace.percent_encode(request)
        failures.extend([
            {'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'exec',
                'call_id': 'rejected-' + str(index),
                'input': provider.call_template(identity, 'session-01', json.dumps(request))}},
            {'type': 'event_msg', 'payload': {'type': 'item_completed', 'item': {
                'type': 'CommandExecution', 'command': provider_trace.SHELL_PREFIX + [command],
                'aggregated_output': ERROR, 'status': 'failed', 'exit_code': 1}}},
            {'type': 'response_item', 'payload': {'type': 'custom_tool_call_output',
                'call_id': 'rejected-' + str(index), 'output': [
                    {'type': 'input_text', 'text': 'Script completed\nWall time 0.1 seconds\nOutput:\n'},
                    {'type': 'input_text', 'text': json.dumps({'output': ERROR, 'exit_code': 1})}]}},
        ])
    rows[at:at] = failures
    start = datetime(2026, 11, 8, 20, tzinfo=timezone.utc)
    for index, row in enumerate(rows):
        row['timestamp'] = (start + timedelta(seconds=index)).isoformat()
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return path, identity, session, deliveries


def test_two_local_rejections_then_success_preserve_full_audit_and_delivery_positions(tmp_path):
    path, identity, session, deliveries = rejection_trace(tmp_path)
    native = provider_trace.audit_native_context(path, identity, session, deliveries)
    assert native['valid'], native['issues']
    assert native['gateway_calls'] == 3
    assert native['gateway_dispatched_calls'] == 1
    assert len(native['local_validation_rejections']) == 2
    assert native['actual_tool_calls'] == 4  # Two failures, one successful call, one poll.
    assert len(native['deliveries']) == 1
    exported = provider_export.sanitize_admin_trace(path, identity, session, context_id='context', complete=True)
    rows, initial = provider_export.validate_admin_export(exported, identity, session, context_id='context')
    audited = provider_trace._audit_native_records(rows, identity, session, deliveries, initial, sanitized=True)
    assert audited['valid'], audited['issues']
    assert audited['local_validation_rejections'] == native['local_validation_rejections']


def test_legacy_profile_still_rejects_every_nonzero_gateway_exit(tmp_path):
    args = rejection_trace(tmp_path, opted_in=False)
    assert not provider_trace.audit_native_context(*args)['valid']
    with pytest.raises(ValueError):
        provider_export.sanitize_admin_trace(*args[:3], context_id='context', complete=True)


@pytest.mark.parametrize(('decoded_bytes', 'valid'), [(8192, False), (8193, True)])
def test_exact_decoded_byte_limit_is_required(tmp_path, decoded_bytes, valid):
    empty = {'request_id': 'oversized-0', 'operation': 'write', 'payload': {'path': 'draft.py', 'text': ''}}
    overhead = len(json.dumps(empty, separators=(',', ':')).encode())
    args = rejection_trace(tmp_path, sizes=(decoded_bytes - overhead,))
    audit = provider_trace.audit_native_context(*args)
    assert audit['valid'] is valid, audit['issues']
    if valid:
        assert audit['local_validation_rejections'][0]['decoded_bytes'] == decoded_bytes


def test_local_rejection_can_finish_through_its_existing_native_poll(tmp_path):
    path, identity, session, deliveries = rejection_trace(tmp_path, sizes=(8200,))
    rows = provider._trace_records(path)
    native_index = next(i for i, row in enumerate(rows) if row['payload'].get('item', {}).get('exit_code') == 1)
    native, output = rows[native_index:native_index + 2]
    running = copy.deepcopy(output)
    running['payload']['output'][1]['text'] = json.dumps({'output': ERROR[:10], 'session_id': 900})
    output['payload']['call_id'] = 'local-rejection-poll'
    output['payload']['output'][1]['text'] = json.dumps({'output': ERROR[10:], 'exit_code': 1})
    poll = {'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'exec',
        'call_id': 'local-rejection-poll', 'input': provider.poll_template(900, identity=identity)}}
    rows[native_index:native_index + 2] = [running, poll, native, output]
    start = datetime(2026, 11, 8, 20, tzinfo=timezone.utc)
    for index, row in enumerate(rows):
        row['timestamp'] = (start + timedelta(seconds=index)).isoformat()
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    audit = provider_trace.audit_native_context(path, identity, session, deliveries)
    assert audit['valid'], audit['issues']
    assert audit['native_poll_calls'] == 2
    assert len(audit['local_validation_rejections']) == 1
    provider_export.sanitize_admin_trace(path, identity, session, context_id='context', complete=True)


@pytest.mark.parametrize('change', ['unknown_policy', 'unbound_client'])
def test_rejection_policy_requires_exact_reviewed_client(tmp_path, change):
    path, identity, session, deliveries = rejection_trace(tmp_path)
    if change == 'unknown_policy':
        identity['trace_export']['local_validation_rejections'] = 'all_failures_allowed'
    else:
        identity['trace_export']['client_source_sha256'] = 'b' * 64
    with pytest.raises(ValueError):
        provider_export.validate_binding(identity)
    assert not provider_trace.audit_native_context(path, identity, session, deliveries)['valid']


@pytest.mark.parametrize('mutation', [
    'under_limit', 'changed_literal', 'ssh_error', 'extra_output', 'different_error_type',
    'wrong_exit', 'wrong_native_status', 'output_disagrees', 'unsafe_shell',
    'bad_percent', 'different_gateway', 'missing_shell', 'reordered_shell',
    'nonterminal', 'extra_delivery',
])
def test_local_rejection_cannot_hide_uncertain_or_unrelated_failures(tmp_path, mutation):
    args = rejection_trace(tmp_path, sizes=(8,) if mutation == 'under_limit' else (8200,))
    path, identity, session, deliveries = args
    rows = provider._trace_records(path)
    call = next(r['payload'] for r in rows if r['payload'].get('call_id') == 'rejected-0')
    native_row = next(r for r in rows if r['payload'].get('item', {}).get('exit_code') == 1)
    native = native_row['payload']['item']
    output = next(r['payload'] for r in rows if r['payload'].get('type') == 'custom_tool_call_output'
                  and r['payload'].get('call_id') == 'rejected-0')
    envelope = json.loads(output['output'][1]['text'])
    if mutation == 'changed_literal':
        call['input'] = call['input'].replace('draft.py', 'other.py')
    elif mutation in {'ssh_error', 'extra_output', 'different_error_type'}:
        message = ('ssh transport failed\n' if mutation == 'ssh_error' else
                   ERROR + 'extra\n' if mutation == 'extra_output' else ERROR.replace('ValueError', 'OSError'))
        envelope['output'] = native['aggregated_output'] = message
    elif mutation == 'wrong_exit':
        envelope['exit_code'] = native['exit_code'] = 2
    elif mutation == 'wrong_native_status':
        native['status'] = 'completed'
    elif mutation == 'output_disagrees':
        envelope['output'] = ERROR + '\n'
    elif mutation == 'unsafe_shell':
        native['command'][-1] += '; whoami'
    elif mutation == 'bad_percent':
        native['command'][-1] += '%ZZ'
    elif mutation == 'different_gateway':
        native['command'][-1] = native['command'][-1].replace('gateway.py', 'different.py')
    elif mutation == 'missing_shell':
        rows.remove(native_row)
    elif mutation == 'reordered_shell':
        rows.remove(native_row)
        rows.insert(len(rows) - 2, native_row)
    elif mutation == 'nonterminal':
        envelope.pop('exit_code')
        envelope['session_id'] = 900
    elif mutation == 'extra_delivery':
        deliveries.insert(0, copy.deepcopy(deliveries[0]))
    output['output'][1]['text'] = json.dumps(envelope)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    assert not provider_trace.audit_native_context(path, identity, session, deliveries)['valid']
