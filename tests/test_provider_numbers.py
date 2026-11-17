"""Literal request numbers must match the value JSON.stringify transmits."""
import json

import pytest

from eegfm.agent import provider, provider_export, provider_trace
from test_provider_export import fixture
from test_provider_trace import IDENTITY


def request_literal(number: str) -> str:
    return '{"request_id":"one","operation":"task","payload":{"nested":[{"number":' + number + '}]}}'


@pytest.mark.parametrize(('literal', 'wire'), [
    ('1.0', '1'), ('10.0', '10'), ('1e0', '1'), ('-0.0', '0'),
    ('-0', '0'), ('1e-7', '1e-7'), ('0.125', '0.125'),
    ('5e-324', '5e-324'), ('1e-999', '0'),
    ('9007199254740991', '9007199254740991'),
    ('-9007199254740991', '-9007199254740991'),
    ('true', 'true'), ('false', 'false'), ('"1.0"', '"1.0"'),
])
def test_literal_numbers_have_the_exact_supported_javascript_wire_value(literal, wire):
    code = provider.call_template(IDENTITY, 'session-01', request_literal(literal))
    operation, value = provider_trace.parse_tool(code, IDENTITY, 'session-01')
    assert operation == 'call'
    # Python equality alone would conceal both float/int and bool/int mistakes.
    assert provider.canonical_bytes(value) == provider.canonical_bytes(json.loads(request_literal(wire)))


@pytest.mark.parametrize('literal', [
    '9007199254740992', '9007199254740993', '-9007199254740992',
    '9007199254740993.0', '1e20', '1e309', '-1e309', 'NaN', 'Infinity',
])
def test_unsupported_or_nonfinite_number_literals_fail_closed(literal):
    code = provider.call_template(IDENTITY, 'session-01', request_literal(literal))
    with pytest.raises(ValueError):
        provider_trace.parse_tool(code, IDENTITY, 'session-01')


def test_numeric_normalization_does_not_accept_duplicate_keys():
    literal = request_literal('1.0').replace('"number":1.0', '"number":1.0,"number":1')
    with pytest.raises(ValueError, match='Duplicate'):
        provider_trace.parse_tool(provider.call_template(IDENTITY, 'session-01', literal), IDENTITY, 'session-01')


def numeric_trace(tmp_path, *, wire='1', delivered='1'):
    path, identity, session, deliveries = fixture(tmp_path)
    rows = provider._trace_records(path)
    for row in rows:
        item = row['payload']
        if item.get('type') == 'custom_tool_call' and item.get('call_id') == 'a':
            item['input'] = provider.call_template(identity, 'session-01', request_literal('1.0'))
        native = item.get('item', {})
        if native.get('type') == 'CommandExecution':
            native['command'][-1] = (provider.command(identity, 'session-01')
                                    + provider_trace.percent_encode(json.loads(request_literal(wire))))
    deliveries[0]['request'] = json.loads(request_literal(delivered))
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return path, identity, session, deliveries


def test_integral_float_literal_survives_export_and_durable_delivery_audit(tmp_path):
    path, identity, session, deliveries = numeric_trace(tmp_path)
    native = provider_trace.audit_native_context(path, identity, session, deliveries)
    assert native['valid'], native['issues']
    exported = provider_export.sanitize_admin_trace(path, identity, session, context_id='context', complete=True)
    rows, initial = provider_export.validate_admin_export(exported, identity, session, context_id='context')
    audited = provider_trace._audit_native_records(rows, identity, session, deliveries, initial, sanitized=True)
    assert audited['valid'], audited['issues']
    # Keep the original literal in the trace; normalize only its parsed value.
    assert any('"number":1.0' in row['payload'].get('input', '') for row in rows)


@pytest.mark.parametrize('wire', ['true', '"1"', '2', '1.0000000000000002', '1.0'])
def test_number_fix_does_not_accept_altered_wire_values_or_types(tmp_path, wire):
    args = numeric_trace(tmp_path, wire=wire)
    assert not provider_trace.audit_native_context(*args)['valid']
    with pytest.raises(ValueError):
        provider_export.sanitize_admin_trace(*args[:3], context_id='context', complete=True)


@pytest.mark.parametrize('delivered', ['true', '"1"', '2', '1.0'])
def test_number_fix_does_not_loosen_durable_delivery_matching(tmp_path, delivered):
    args = numeric_trace(tmp_path, delivered=delivered)
    assert not provider_trace.audit_native_context(*args)['valid']
