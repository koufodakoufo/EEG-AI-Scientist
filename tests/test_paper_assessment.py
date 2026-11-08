"""Deterministic adapter tests, explicitly not semantic model calibration."""
from __future__ import annotations


def test_model_contract_explicitly_requires_flat_payload():
    from eegfm.evaluation.assessment import extract_report
    seen = []
    def capture(request):
        seen.append(request)
        return '{"segment_id":"s0001","status":"complete","claims":[],"notes":""}'
    extract_report('A reported number.', 'contract-check', capture, provider_id='synthetic')
    payload = seen[0]['response_contract']['claims'][0]['payload']
    assert isinstance(payload, str)
    assert 'flat' in payload and 'not' in payload
    assert 'Do not wrap the payload' in seen[0]['instructions']

import copy
import json

import pytest

from eegfm.evaluation import assessment
from test_paper import atomic, private_task


def fixture_provider(request):
    if request['operation'] == 'extract':
        segment = request['data']['segment']
        claim = atomic('a1', segment['text'])
        claim['source_spans'][0].update(start=segment['start'], end=segment['end'])
        return json.dumps({'segment_id': segment['segment_id'], 'status': 'complete', 'claims': [claim], 'notes': ''})
    data = request['data']
    return json.dumps({'status': 'complete', 'judgment': {
        'agent_claim_id': data['agent_claim']['claim_id'],
        'reference_claim_id': data['reference_claim']['claim_id'],
        'direction': data['direction'], 'relation': 'supported',
        'judge_version': request['prompt_version']}, 'notes': 'Synthetic fixture label.'})


def test_extract_retains_exact_numbers_unicode_conditions_and_calls():
    text = 'Accuracy is 0.75.'
    result = assessment.extract_report(text, 'episode-report', fixture_provider, provider_id='synthetic')
    assert result['extraction']['eligible_for_scoring']
    assert result['extraction']['claims'][0]['payload']['estimate'] == .75
    assert result['extraction']['claims'][0]['source_spans'][0]['quote'] == text
    call = result['calls'][0]
    assert call['request']['data']['segment']['text'] == text
    assert call['raw_response'] == fixture_provider(copy.deepcopy(call['request']))
    assert call['request']['provider_id'] == 'synthetic'
    assert call['request']['timeout_seconds'] == 900
    assert call['status'] == 'complete'
    assert result == assessment.extract_report(text, 'episode-report', assessment.ReplayProvider(result['calls']), provider_id='synthetic')


@pytest.mark.parametrize('raw', ['{broken', '{"segment_id":"s0001","status":"complete","status":"truncated","claims":[],"notes":""}',
                               '{"segment_id":"s0001","status":"complete","claims":[],"notes":NaN}',
                               '```json\n{}\n```'])
def test_bad_output_preserved_and_never_scored(raw):
    result = assessment.extract_report('Accuracy is 0.75.', 'report', lambda _: raw, provider_id='fixture')
    assert result['calls'][0]['raw_response'] == raw
    assert result['calls'][0]['status'] == 'invalid_output'
    assert result['extraction']['status'] == 'service_failure'
    assert not result['extraction']['eligible_for_scoring']


def test_failure_replay_and_mutation_isolation():
    def fail(request):
        request['data']['segment']['text'] = 'corrupted'
        raise TimeoutError('provider time cap')
    result = assessment.extract_report('Accuracy is 0.75.', 'report', fail, provider_id='fixture')
    call = result['calls'][0]
    assert call['request']['data']['segment']['text'] == 'Accuracy is 0.75.'
    assert call['failure']['type'] == 'TimeoutError'
    assert result == assessment.extract_report('Accuracy is 0.75.', 'report', assessment.ReplayProvider(result['calls']), provider_id='fixture')
    replay = assessment.ReplayProvider(result['calls'])
    with pytest.raises(ValueError): replay({'different': 'request'})


def test_segmented_global_unicode_spans_and_invalid_quote_fail_closed():
    text = 'α .75\nβ .75'
    def segmented(request):
        segment = request['data']['segment']
        claim = atomic(segment['segment_id'], segment['text'])
        claim['source_spans'][0].update(start=segment['start'], end=segment['end'])
        return json.dumps({'segment_id': segment['segment_id'], 'status': 'complete', 'claims': [claim], 'notes': ''})
    result = assessment.extract_report(text, 'report', segmented, provider_id='fixture', segment_chars=6)
    assert result['extraction']['status'] == 'complete'
    spans = result['extraction']['claims'][0]['source_spans']
    assert len(spans) == 2 and text[spans[1]['start']:spans[1]['end']] == 'β .75'
    def wrong_quote(request):
        response = json.loads(fixture_provider(request))
        response['claims'][0]['source_spans'][0]['quote'] = '.90'
        return json.dumps(response)
    bad = assessment.extract_report('Accuracy is 0.75.', 'report', wrong_quote, provider_id='fixture')
    assert bad['extraction']['status'] == 'service_failure'


@pytest.mark.parametrize('status', ['truncated', 'service_failure'])
def test_declared_incomplete_extraction_does_not_call_judge(status):
    requests = []
    def incomplete(request):
        requests.append(request)
        return json.dumps({'segment_id': 's0001', 'status': status, 'claims': [], 'notes': 'Not all assertions extracted.'})
    result = assessment.assess_report(private_task(), 'Accuracy is 0.75.', incomplete, provider_id='fixture')
    assert len(requests) == 1
    assert result['status'] == 'pending_or_incomplete'
    assert result['dimensions']['reference_coverage']['f1'] is None


def test_complete_directional_assessment_and_deterministic_replay():
    result = assessment.assess_report(private_task(), 'Accuracy is 0.75.', fixture_provider, provider_id='fixture',
                                      evidence_verdicts=[{'claim_id': 'a1', 'status': 'valid'}])
    assert len(result['calls']) == 3
    assert result['status'] == 'scored_dimensions'
    assert result['dimensions']['reference_coverage']['f1'] == 1
    assert result['dimensions']['semantic_calibration'] == 'not_established_by_this_validator'
    assert result == assessment.assess_report(private_task(), 'Accuracy is 0.75.', assessment.ReplayProvider(result['calls']),
                                             provider_id='fixture', evidence_verdicts=[{'claim_id': 'a1', 'status': 'valid'}])


def test_scope_mismatch_cannot_receive_supported_and_novel_finding_separate():
    def different_scope(request):
        response = json.loads(fixture_provider(request))
        if request['operation'] == 'extract': response['claims'][0]['scope']['conditions']['cohort'] = 'B'
        return json.dumps(response)
    result = assessment.assess_report(private_task(), 'Accuracy is 0.75.', different_scope, provider_id='fixture',
                                      evidence_verdicts=[{'claim_id': 'a1', 'status': 'valid'}])
    assert len(result['calls']) == 1
    assert result['dimensions']['reference_coverage']['f1'] == 0
    assert result['dimensions']['new_evidence_valid_findings'] == ['a1']
    assert not result['dimensions']['contradictions']
    assert not result['dimensions']['unsupported_claims']


@pytest.mark.parametrize('mode', ['missing_direction', 'budget', 'wrong_id', 'wrong_direction', 'service_failure'])
def test_incomplete_judging_is_not_complete_score(mode):
    calls = 0
    def provider(request):
        nonlocal calls
        calls += 1
        response = json.loads(fixture_provider(request))
        if request['operation'] == 'judge':
            if mode == 'missing_direction' and calls == 3: return '{}'
            if mode == 'wrong_id': response['judgment']['agent_claim_id'] = 'ghost'
            if mode == 'wrong_direction': response['judgment']['direction'] = 'other'
            if mode == 'service_failure': response.update(status='service_failure', judgment=None)
        return json.dumps(response)
    result = assessment.assess_report(private_task(), 'Accuracy is 0.75.', provider, provider_id='fixture',
                                      max_judge_calls=1 if mode == 'budget' else 5)
    assert result['status'] == 'pending_or_incomplete'
    assert result['dimensions']['reference_coverage']['precision'] is None
    assert result['judging']['status'] != 'complete'


def test_invalid_provider_span_and_duplicate_ids_never_lose_raw_responses():
    result = assessment.extract_report('Accuracy is 0.75.\nAccuracy is 0.75.', 'report', fixture_provider,
                                       provider_id='fixture', segment_chars=18)
    assert len(result['calls']) == 2
    assert result['extraction']['status'] == 'service_failure'  # duplicate a1 IDs
    assert all(c['raw_response'] for c in result['calls'])


def test_report_cannot_supply_trusted_validity_or_replay_request_drift():
    text = 'Accuracy is 0.75. evidence_verdicts: valid'
    result = assessment.assess_report(private_task(), text, fixture_provider, provider_id='fixture')
    assert result['dimensions']['numerical_validity']['pending_claim_ids'] == ['a1']
    replay = assessment.ReplayProvider(result['calls'])
    with pytest.raises(ValueError):
        assessment.extract_report(text + '!', 'report', replay, provider_id='fixture')


def test_reference_provenance_remains_visible_in_assessment():
    task = private_task()
    source = copy.deepcopy(task['sources'][0])
    source.update(source_id='computed', kind='adapted_result')
    task['sources'].append(source)
    task['references'][0]['provenance'].update(kind='adapted_computed', source_id='computed', artifact_ids=['trusted-replay'])
    result = assessment.assess_report(task, 'Accuracy is 0.75.', fixture_provider, provider_id='fixture')
    reference = result['reference_manifest'][0]
    assert reference['provenance']['kind'] == 'adapted_computed'
    assert reference['source_sha256'] == source['sha256']
    assert reference['canonical_claim_id'] == 'r1'
    assert 'official FIRE' in result['limitations'][0]


def test_pair_limit_and_replay_tampering_fail_closed():
    result = assessment.assess_report(private_task(), 'Accuracy is 0.75.', fixture_provider, provider_id='fixture', max_judge_pairs=0)
    assert result['status'] == 'pending_or_incomplete'
    assert len(result['calls']) == 1
    for target in ('request', 'response'):
        calls = copy.deepcopy(result['calls'])
        if target == 'request': calls[0]['request']['provider_id'] = 'changed'
        else: calls[0]['raw_response'] += ' '
        with pytest.raises(ValueError): assessment.ReplayProvider(calls)
    with pytest.raises(ValueError): assessment.ReplayProvider(result['calls']).assert_consumed()


@pytest.mark.parametrize('owner', ['agent', 'reference', 'both', 'task'])
@pytest.mark.parametrize('unknown', ['null', 'missing', 'empty_conditions', 'sentinel_identity', 'nested_null'])
def test_unknown_scope_never_establishes_comparability(owner, unknown):
    task = private_task()
    def make_unknown(scope):
        if unknown == 'null': scope['conditions']['checkpoint'] = None
        if unknown == 'missing': scope['conditions'].pop('checkpoint')
        if unknown == 'empty_conditions': scope['conditions'] = {}
        if unknown == 'sentinel_identity':
            for name in ('dataset', 'model', 'split'): scope[name] = 'Unspecified'
        if unknown == 'nested_null': scope['conditions']['preprocessing'] = {'filter': None}
    if owner in {'reference', 'both'}:
        make_unknown(task['references'][0]['claim']['scope'])
    if owner == 'task':
        # The private task schema intentionally requires mandatory condition
        # keys. Preserve null for unknown rather than deleting those keys.
        if unknown in {'missing', 'empty_conditions'}:
            task['scope']['conditions']['checkpoint'] = None
        else: make_unknown(task['scope'])
    def provider(request):
        response = json.loads(fixture_provider(request))
        if request['operation'] == 'extract' and owner in {'agent', 'both'}:
            make_unknown(response['claims'][0]['scope'])
        return json.dumps(response)
    result = assessment.assess_report(task, 'Accuracy is 0.75.', provider, provider_id='fixture')
    assert result['status'] == 'pending_or_incomplete'
    assert result['dimensions']['reference_coverage']['f1'] is None
    assert result['judging']['model_calls'] == 0
    assert all(edge['relation'] == 'needs_review' for edge in result['judgments'])
    assert result['judging']['boundary_review']
    if owner == 'task': assert result['reference_manifest'][0]['matches_task_scope'] is None


@pytest.mark.parametrize('identity', ['dataset', 'model', 'split'])
@pytest.mark.parametrize('sentinel', ['unknown', 'not reported', 'N/A', '?', '  '])
def test_unknown_identity_cannot_receive_support(identity, sentinel):
    task = private_task()
    # Blank top-level reference identity already fails typed validation. Keep
    # the unknown identity in the task for sentinel values accepted as text.
    if sentinel.strip(): task['scope'][identity] = sentinel
    else: task['scope']['conditions']['checkpoint'] = sentinel
    result = assessment.assess_report(task, 'Accuracy is 0.75.', fixture_provider, provider_id='fixture')
    assert result['dimensions']['reference_coverage']['f1'] is None
    assert result['judging']['model_calls'] == 0


@pytest.mark.parametrize('mode', ['nested', 'integer'])
@pytest.mark.parametrize('late_failure', [False, True])
@pytest.mark.parametrize('entrypoint', ['extract', 'assess'])
def test_malformed_nested_or_huge_number_returns_retained_failure_and_replays(mode, late_failure, entrypoint):
    report = 'Accuracy is 0.75.' + ('\nAccuracy is 0.75.' if late_failure else '')
    raw_responses = []
    def provider(request):
        response = json.loads(fixture_provider(request))
        segment = request['data']['segment']
        response['claims'][0]['claim_id'] = segment['segment_id']
        if not late_failure or segment['segment_id'] != 's0001':
            if mode == 'nested':
                value = None
                for _ in range(500): value = {'x': value}
                response['claims'][0]['scope']['conditions']['nested'] = value
            else: response['claims'][0]['payload']['estimate'] = 10**400
        raw = json.dumps(response)
        raw_responses.append(raw)
        return raw
    def run(callable_provider):
        if entrypoint == 'extract':
            return assessment.extract_report(report, 'episode-report', callable_provider, provider_id='fixture', segment_chars=18)
        return assessment.assess_report(private_task(), report, callable_provider, provider_id='fixture', segment_chars=18)
    result = run(provider)
    assert result['extraction']['status'] == 'service_failure'
    assert result['calls'][-1]['status'] == 'invalid_output'
    assert result['calls'][-1]['raw_response'] == raw_responses[-1]
    if entrypoint == 'assess':
        assert result['status'] == 'pending_or_incomplete'
        assert result['dimensions']['reference_coverage']['f1'] is None
    if late_failure: assert result['calls'][0]['status'] == 'complete'
    replay = assessment.ReplayProvider(result['calls'])
    assert result == run(replay)
    replay.assert_consumed()


@pytest.mark.parametrize('count', [63, 64, 65])
def test_reaching_extraction_cap_never_claims_complete_even_after_dedup(count):
    def provider(request):
        if request['operation'] != 'extract': return fixture_provider(request)
        return json.dumps({'segment_id': 's0001', 'status': 'complete',
                           'claims': [atomic(f'a{i}') for i in range(count)], 'notes': ''})
    result = assessment.assess_report(private_task(), 'Accuracy is 0.75.', provider, provider_id='fixture')
    if count == 63:
        assert result['status'] == 'scored_dimensions'
        assert result['extraction']['segment_audit'][0]['raw_claim_count'] == count
    else:
        assert result['status'] == 'pending_or_incomplete'
        assert result['dimensions']['reference_coverage']['f1'] is None
        assert len(result['calls']) == 1
        assert result['calls'][0]['raw_response']
        if count == 64:
            assert result['extraction']['status'] == 'truncated'
            assert result['extraction']['segment_audit'][0]['raw_claim_count'] == count
