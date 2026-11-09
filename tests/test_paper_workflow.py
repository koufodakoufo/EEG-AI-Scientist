import hashlib
import json
from pathlib import Path

import pytest

from eegfm.evaluation import assessment, claims, paper_workflow


def _resources() -> dict:
    return {
        'schema_version': 'paper_resources_v1',
        'task_id': 'synthetic',
        'revision': 'r01',
        'paper': {'title': 'Synthetic paper', 'version': 'v1', 'uri': 'urn:synthetic:paper'},
        'scope': {
            'dataset': 'available data', 'model': 'available model', 'split': 'held out',
            'conditions': {
                'cohort': 'resource cohort', 'checkpoint': None, 'head': None,
                'preprocessing': None, 'representation': None, 'metric': 'accuracy',
                'inference_unit': None,
            },
        },
        'resources': ['Local fixture'],
        'constraints': ['No external calls'],
        'budget': {'calls': 4},
        'resource_text': 'Synthetic inputs only.',
    }


def _request(name: str = 'one') -> dict:
    request = {'request_id': name, 'data': {'output_path': '../../unused.json'}}
    return {**request, 'request_sha256': claims.canonical_sha256(request)}


def _response_record(request: dict, *, raw: str | None = '{"status":"complete"}',
                     failure: dict | None = None, status: str = 'complete') -> dict:
    return {
        'request': request, 'request_sha256': request['request_sha256'],
        'raw_response': raw, 'response_sha256': None if raw is None else hashlib.sha256(raw.encode()).hexdigest(),
        'status': status, 'failure': failure,
    }


def _deliver(root: Path, request: dict, record: dict) -> Path:
    path = root / 'responses' / (request['request_sha256'] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(record).encode())
    return path


def test_source_bytes_unicode_and_duplicate_quote_offsets(tmp_path: Path) -> None:
    source = tmp_path / 'original.txt'
    raw = b'\xf0\x9f\x9a\x80\r\nEcho\r\nEcho'
    source.write_bytes(raw)
    source_bytes, paper = paper_workflow.read_utf8(source)
    copied = tmp_path / 'work' / 'inputs' / 'paper.txt'
    paper_workflow.write_immutable(copied, source_bytes)

    assert copied.read_bytes() == raw
    assert paper == '\U0001f680\r\nEcho\r\nEcho'
    span = {'start': 9, 'end': 13, 'quote': 'Echo'}
    assert paper_workflow.verbatim_reference(paper, span) == {
        **span, 'paper_sha256': hashlib.sha256(raw).hexdigest(),
        'reference_sha256': hashlib.sha256(b'Echo').hexdigest(),
    }

    source.write_bytes(b'\xff')
    with pytest.raises(UnicodeDecodeError):
        paper_workflow.read_utf8(source)


@pytest.mark.parametrize('span', [
    {'start': 0, 'end': 4, 'quote': 'Else'},
    {'start': 0, 'end': 5, 'quote': 'Echo'},
    {'start': 0.0, 'end': 4, 'quote': 'Echo'},
    {'start': False, 'end': 4, 'quote': 'Echo'},
    {'start': 0, 'end': 0, 'quote': ''},
    {'start': 0, 'end': 4, 'quote': 'Echo', 'scope': {'dataset': 'invented'}},
])
def test_resource_scope_and_excerpt_reject_invention(span: dict) -> None:
    with pytest.raises(ValueError, match='span'):
        paper_workflow.verbatim_reference('Echo', span)


def test_resource_manifest_preserves_declared_unknowns(tmp_path: Path) -> None:
    path = tmp_path / 'resources.json'
    resources = _resources()
    path.write_bytes(json.dumps(resources).encode())
    assert paper_workflow.load_resources(path) == resources


@pytest.mark.parametrize('invalid', ['missing condition', 'infinite', 'overflow', 'bool', 'extra field', 'duplicate'])
def test_resource_manifest_rejects_invalid_fields_and_budgets(tmp_path: Path, invalid: str) -> None:
    path = tmp_path / 'resources.json'
    resources = _resources()
    if invalid == 'missing condition':
        del resources['scope']['conditions']['checkpoint']
    elif invalid == 'infinite':
        resources['budget']['calls'] = float('inf')
    elif invalid == 'bool':
        resources['budget']['calls'] = True
    elif invalid == 'extra field':
        resources['private_answer'] = 'not public resources'
    raw = json.dumps(resources).encode()
    if invalid == 'overflow':
        raw = raw.replace(b'"calls": 4', b'"calls": 1e999')
    elif invalid == 'duplicate':
        raw = raw.replace(b'"calls": 4', b'"calls": 2, "calls": 4')
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        paper_workflow.load_resources(path)


def test_queue_pending_is_not_terminal_failure(tmp_path: Path) -> None:
    root = tmp_path / 'work'
    request = _request()
    provider = paper_workflow.FileProvider(root, max_requests=1)
    with pytest.raises(paper_workflow.AwaitingResponse):
        provider(request)
    digest = request['request_sha256']
    assert provider.pending == [{
        'request_sha256': digest, 'request_path': f'requests/{digest}.json',
        'response_path': f'responses/{digest}.json',
    }]
    assert json.loads((root / 'pending.json').read_bytes()) == {'pending': provider.pending}
    assert json.loads((root / 'requests' / f'{digest}.json').read_bytes()) == request
    assert not (tmp_path / 'unused.json').exists()
    assert not list((root / 'responses').glob('*.json'))

    _deliver(root, request, _response_record(request))
    resumed = paper_workflow.FileProvider(root, max_requests=1)
    assert resumed(request) == '{"status":"complete"}'
    assert resumed.pending == []
    assert json.loads((root / 'pending.json').read_bytes()) == {'pending': []}


@pytest.mark.parametrize('corrupt', [
    'embedded request', 'null request', 'request digest', 'response digest', 'missing failure',
    'status', 'unexpected field', 'response JSON', 'response disappeared',
])
def test_response_request_hash_mismatch_rejected(tmp_path: Path, corrupt: str) -> None:
    request = _request()
    record = _response_record(request)
    if corrupt == 'embedded request':
        other = _request('different')
        record = _response_record(other)
    elif corrupt == 'null request':
        record['request'] = None
    elif corrupt == 'request digest':
        record['request_sha256'] = 'a' * 64
    elif corrupt == 'response digest':
        record['response_sha256'] = 'a' * 64
    elif corrupt == 'missing failure':
        record = _response_record(request, raw=None, status='service_failure')
    elif corrupt == 'status':
        record['status'] = 'awaiting_responses'
    elif corrupt == 'unexpected field':
        record['command'] = 'ignored?'
    path = _deliver(tmp_path, request, record)
    provider = paper_workflow.FileProvider(tmp_path, max_requests=1)
    if corrupt == 'response JSON':
        path.write_bytes(b'{')
    elif corrupt == 'response disappeared':
        assert provider(request) == '{"status":"complete"}'
        path.unlink()

    # The assessment adapter must propagate this local corruption instead of
    # treating it as a real provider failure.
    with pytest.raises(assessment.ReplayMismatch):
        assessment._invoke(provider, request)
    assert provider.pending == []


def test_terminal_failure_replays_exactly(tmp_path: Path) -> None:
    request = _request()
    terminal = _response_record(request, raw=None, status='service_failure',
                                failure={'type': 'TimeoutError', 'message': 'External limit exceeded'})
    _deliver(tmp_path, request, terminal)
    provider = paper_workflow.FileProvider(tmp_path, max_requests=1)
    assert assessment._invoke(provider, request) == (terminal, None)
    assert assessment._invoke(provider, request) == (terminal, None)
    assert provider.pending == []


def test_queue_repeated_stage_is_idempotent_and_no_overwrite(tmp_path: Path) -> None:
    request = _request()
    path = _deliver(tmp_path, request, _response_record(request))
    for _ in range(2):
        provider = paper_workflow.FileProvider(tmp_path, max_requests=1)
        assert provider(request) == provider(request) == '{"status":"complete"}'
        with pytest.raises(assessment.ReplayMismatch, match='budget'):
            assessment._invoke(provider, _request('over budget'))
        assert len(list((tmp_path / 'requests').glob('*.json'))) == 1

    path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises(assessment.ReplayMismatch, match='response bytes'):
        provider(request)

    request_path, = (tmp_path / 'requests').glob('*.json')
    conflict = request_path.read_bytes() + b'\n'
    request_path.write_bytes(conflict)
    with pytest.raises(assessment.ReplayMismatch, match='existing bytes'):
        paper_workflow.FileProvider(tmp_path, max_requests=1)(request)
    assert request_path.read_bytes() == conflict
