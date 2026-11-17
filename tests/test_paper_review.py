"""Prospective full-report review; no model/network calls in these fixtures."""
import copy
import json

import pytest

from eegfm.evaluation import assessment, claims, paper_workflow


def review_module():
    from eegfm.evaluation import paper_review
    return paper_review


def plan(**changes):
    return review_module().resolve_plan({
        'schema_version': 'paper_comparison_review_v1',
        'reason': 'Prospective lossless extraction and complete alignment review.',
        'provider_id': 'review-fixture', 'provider_metadata': {},
        **changes,
    })


def atom(segment, quote, *, kind='qualitative', payload=None):
    start = segment['start'] + segment['text'].index(quote)
    return {'claim_id': segment['segment_id'] + ':claim', 'kind': kind,
            'scope': {'dataset': 'unknown', 'model': 'unknown', 'split': 'unknown', 'conditions': {}},
            'subject': 'signal', 'predicate': 'contains information', 'direction': 'reported',
            'qualifiers': [], 'payload': payload or {'statement': quote},
            'source_spans': [{'start': start, 'end': start + len(quote), 'quote': quote}],
            'evidence_ids': ['report']}


def test_only_truncated_segments_refined_and_root_requests_exactly_legacy():
    module = review_module()
    report = 'one\ntwo\nthree\nfour\n'
    settings = {'provider_id': 'old-fixture', 'provider_metadata': {},
                'segment_chars': 10, 'timeout_seconds': 900}
    seen = []

    def provider(request):
        seen.append(copy.deepcopy(request))
        s = request['data']['segment']
        status = 'truncated' if s['segment_id'] == 's0001' else 'complete'
        quote = s['text'].strip().splitlines()[0]
        return json.dumps({'segment_id': s['segment_id'], 'status': status,
                           'claims': [atom(s, quote)], 'notes': 'fixture'})

    result = module.extract_refined_report(report, 'source', provider, settings=settings,
                                           plan=plan(refinement_chars=4))
    roots = claims.build_extraction_plan(report, 'source', segment_chars=10)['segments']
    assert seen[:len(roots)] == [assessment._request(
        'extract', 'extract:' + s['segment_id'],
        {'source_id': 'source', 'report_sha256': assessment._sha(report), 'segment': s,
         'max_claims_per_segment': 64}, 'old-fixture', 900, {}) for s in roots]
    assert result['extraction']['eligible_for_scoring']
    leaves = result['leaf_segments']
    assert ''.join(s['text'] for s in leaves) == report
    assert all(a['end'] == b['start'] for a, b in zip(leaves, leaves[1:]))
    assert all(c['claim_id'] != 's0001:claim' for c in result['extraction']['claims'])
    assert len(result['refinements']) == 1
    assert all(request['data']['original_report'] == report for request in seen[len(roots):])
    replay = assessment.ReplayProvider(result['calls'])
    assert module.extract_refined_report(report, 'source', replay, settings=settings,
                                        plan=plan(refinement_chars=4)) == result
    replay.assert_consumed()


def test_service_failure_never_retried_or_refined():
    module = review_module()
    calls = []
    def provider(request):
        calls.append(request)
        raise RuntimeError('terminal failure')
    result = module.extract_refined_report('text', 'source', provider,
        settings={'provider_id': 'old', 'provider_metadata': {}, 'segment_chars': 4000,
                  'timeout_seconds': 900}, plan=plan())
    assert len(calls) == 1
    assert not result['extraction']['eligible_for_scoring']
    assert not result['refinements']
    persisted = json.loads(paper_workflow.json_bytes(result))
    replay = assessment.ReplayProvider(persisted['calls'])
    assert module.extract_refined_report('text', 'source', replay,
        settings={'provider_id': 'old', 'provider_metadata': {}, 'segment_chars': 4000,
                  'timeout_seconds': 900}, plan=plan()) == result


def test_refinement_preserves_dense_table_rows_and_declines_unsplittable_unit():
    module = review_module()
    report = '| group | estimate | interval |\n' + ''.join(
        f'| g{i:02d} | 0.1234 | [0.01, 0.23] |\n' for i in range(12))
    parent = {'segment_id': 's0001', 'start': 0, 'end': len(report), 'text': report}
    children = module._children(report, parent, 80)
    assert ''.join(c['text'] for c in children) == report
    assert all(c['text'].endswith('\n') for c in children)
    long_row = '| one indivisible row with many values |'
    parent = {'segment_id': 's0001', 'start': 0, 'end': len(long_row), 'text': long_row}
    assert module._children(long_row, parent, 8) == []


def test_alignment_has_no_automatic_negative_for_unmatched_tokens():
    module = review_module()
    s = {'start': 0, 'text': 'opaque wording', 'segment_id': 'agent'}
    a = atom(s, 'opaque wording')
    r = atom({**s, 'segment_id': 'reference'}, 'opaque wording')
    r['subject'], r['predicate'] = 'unrelated vocabulary', 'other wording'
    hints = module.candidate_hints([a], [r])
    assert hints == []
    requests = []
    def provider(request):
        requests.append(request)
        return json.dumps({'batch_id': request['data']['batch_id'], 'status': 'complete',
            'report_claims': [{'claim_id': a['claim_id'], 'classification': 'needs_review',
                              'candidate_ids': [], 'reason': 'Semantic relation remains uncertain.'}],
            'reference_claims': [{'claim_id': r['claim_id'], 'classification': 'needs_review',
                                 'candidate_ids': [], 'reason': 'No confident alignment in this batch.'}],
            'notes': 'No token match is not scientific noncoverage.'})
    result = module.align_report([a], [r], 'opaque wording', provider, plan=plan())
    assert len(requests) == 1
    assert result['complete']
    assert result['report_inventory'][0]['classification'] == 'needs_review'
    assert result['reference_inventory'][0]['classification'] == 'needs_review'
    assert not result['candidate_pairs']


def test_alignment_requires_every_id_and_accepts_non_hint_candidate():
    module = review_module()
    a = atom({'start': 0, 'text': 'a', 'segment_id': 'a'}, 'a')
    r = atom({'start': 0, 'text': 'r', 'segment_id': 'r'}, 'r')
    def provider(request):
        return json.dumps({'batch_id': request['data']['batch_id'], 'status': 'complete',
            'report_claims': [{'claim_id': a['claim_id'], 'classification': 'potential_match',
                              'candidate_ids': [r['claim_id']], 'reason': 'Possible shared meaning.'}],
            'reference_claims': [], 'notes': ''})
    result = module.align_report([a], [r], 'a', provider, plan=plan())
    assert not result['complete']
    assert not result['candidate_pairs']


def test_numerical_review_rejects_claim_drift_and_missing_artifact_pointer(tmp_path):
    module = review_module()
    a = atom({'start': 0, 'text': '0.5', 'segment_id': 'a'}, '0.5', kind='point',
             payload={'metric': 'accuracy', 'estimate': .5, 'unit': 'fraction'})
    artifact = tmp_path / 'metrics.json'
    artifact.write_text('{"accuracy":0.5}', encoding='utf8')
    import hashlib
    review = {'schema_version': 'paper_numerical_review_v1', 'reviewer_id': 'independent-review',
        'report_sha256': 'a' * 64, 'claims_sha256': claims.canonical_sha256([a]),
        'artifacts': [{'artifact_id': 'metrics', 'path': str(artifact),
                       'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}],
        'verdicts': [{'claim_id': a['claim_id'], 'claim_sha256': claims.canonical_sha256(a),
                     'status': 'valid', 'reason': 'Matches metric exactly.',
                     'evidence': [{'artifact_id': 'metrics', 'json_pointer': '/accuracy',
                                   'value_sha256': claims.canonical_sha256(.5)}]}]}
    assert module.validate_numerical_review(review, [a], 'a' * 64, tmp_path)['complete']
    bad = copy.deepcopy(review)
    bad['verdicts'][0]['evidence'][0]['json_pointer'] = '/missing'
    with pytest.raises(ValueError):
        module.validate_numerical_review(bad, [a], 'a' * 64, tmp_path)
    bad = copy.deepcopy(review)
    bad['verdicts'][0]['claim_sha256'] = 'b' * 64
    with pytest.raises(ValueError, match='claim'):
        module.validate_numerical_review(bad, [a], 'a' * 64, tmp_path)


@pytest.mark.parametrize('corruption', ['missing_edge', 'unknown_supported', 'duplicate_edge'])
def test_judge_rejects_entire_inexact_or_incomparable_batch(corruption):
    module = review_module()
    a = atom({'start': 0, 'text': 'a', 'segment_id': 'a'}, 'a')
    r = atom({'start': 0, 'text': 'r', 'segment_id': 'r'}, 'r')
    alignment = {'complete': True, 'candidate_pairs': [
        {'agent_claim_id': a['claim_id'], 'reference_claim_id': r['claim_id']} ]}
    def provider(request):
        edges = request['data']['edges']
        values = [{k: e[k] for k in ('edge_id', 'agent_claim_id', 'reference_claim_id', 'direction')}
                  | {'relation': 'supported' if corruption == 'unknown_supported' else 'needs_review',
                     'reason': 'Unknown original conditions.'} for e in edges]
        if corruption == 'missing_edge':
            values.pop()
        if corruption == 'duplicate_edge':
            values[1] = values[0]
        return json.dumps({'batch_id': request['data']['batch_id'], 'status': 'complete',
                           'judgments': values, 'notes': ''})
    result = module.judge_alignment([a], [r], alignment, provider, plan=plan())
    assert not result['complete']
    assert result['judgments'] == []
    assert result['calls'][0]['status'] == 'invalid_output'


def test_opt_in_workflow_binds_plan_and_allows_late_numerical_review(tmp_path):
    from test_paper_workflow import _frozen_compare, _compare_response
    module = review_module()
    work, report, out = _frozen_compare(tmp_path)
    review_plan = tmp_path / 'review-plan.json'
    review_plan.write_text(json.dumps(plan()), encoding='utf8')
    evidence = tmp_path / 'original-evidence.json'
    evidence.write_text(json.dumps({'process_checks': {'assessment_status': 'complete'}}), encoding='utf8')
    seen = []
    def provider(request):
        seen.append(request)
        if request['operation'] == 'extract':
            return _compare_response(request)
        if request['operation'] == 'align_claims':
            data = request['data']
            return json.dumps({'batch_id': data['batch_id'], 'status': 'complete',
                'report_claims': [{'claim_id': a['claim_id'], 'classification': 'needs_review',
                                  'candidate_ids': [], 'reason': 'No independently comparable evidence.'}
                                 for a in data['report_claims']],
                'reference_claims': [{'claim_id': r['claim_id'], 'classification': 'needs_review',
                                     'candidate_ids': [], 'reason': 'Scope remains uncertain.'}
                                    for r in data['reference_claims']], 'notes': ''})
        pytest.fail('No candidate pair should be invented')
    first = paper_workflow.compare_workflow(work, report, out, provider=provider,
                    evidence_path=evidence, review_plan_path=review_plan)
    assert first['pipeline_status'] == 'awaiting_evidence_review'
    extracted = paper_workflow.read_json(out / 'extraction-review.json')['extraction']
    agents = extracted['claims']
    numerical = tmp_path / 'numerical-review.json'
    value = {'schema_version': 'paper_numerical_review_v1', 'reviewer_id': 'independent-fixture',
             'report_sha256': extracted['report_sha256'], 'claims_sha256': claims.canonical_sha256(agents),
             'artifacts': [], 'verdicts': [
                 {'claim_id': a['claim_id'], 'claim_sha256': claims.canonical_sha256(a),
                  'status': 'unverifiable', 'reason': 'No independent numerical artifact available.', 'evidence': []}
                 for a in agents]}
    numerical.write_text(json.dumps(value), encoding='utf8')
    count = len(seen)
    result = paper_workflow.compare_workflow(work, report, out,
                    evidence_path=evidence, review_plan_path=review_plan, evidence_review_path=numerical)
    assert len(seen) == count
    assert result['pipeline_status'] == 'compared'
    assert result['review_coverage_complete']
    assert not result['scientific_assessment_complete']
    assessment_file = paper_workflow.read_json(out / 'assessment.json')
    assert assessment_file['dimensions']['reference_coverage']['precision'] is None
    assert assessment_file['dimensions']['numerical_validity']['unverifiable_claim_ids']
    assert paper_workflow.compare_workflow(work, report, out, evidence_path=evidence,
            review_plan_path=review_plan, evidence_review_path=numerical) == result
    changed = plan(reason='Changed prospective plan after calls')
    review_plan.write_text(json.dumps(changed), encoding='utf8')
    with pytest.raises(assessment.ReplayMismatch):
        paper_workflow.compare_workflow(work, report, out, evidence_path=evidence,
            review_plan_path=review_plan, evidence_review_path=numerical)


def test_queue_resume_and_consumed_response_bytes_are_bound(tmp_path):
    from test_paper_workflow import _frozen_compare, _compare_response, _deliver, _response_record
    work, report, out = _frozen_compare(tmp_path)
    review_plan = tmp_path / 'review-plan.json'
    review_plan.write_text(json.dumps(plan()), encoding='utf8')
    for _ in range(4):
        result = paper_workflow.compare_workflow(work, report, out, review_plan_path=review_plan)
        if result['pipeline_status'] != 'awaiting_responses':
            break
        for pending in result['pending']:
            request = paper_workflow.read_json(out / pending['request_path'])
            if request['operation'] == 'extract':
                raw = _compare_response(request)
            else:
                data = request['data']
                def entry(item):
                    return {'claim_id': item['claim_id'], 'classification': 'needs_review',
                            'candidate_ids': [], 'reason': 'Identity remains unknown.'}
                raw = json.dumps({'batch_id': data['batch_id'], 'status': 'complete',
                                  'report_claims': [entry(x) for x in data['report_claims']],
                                  'reference_claims': [entry(x) for x in data['reference_claims']], 'notes': ''})
            _deliver(out, request, _response_record(request, raw=raw))
    assert result['pipeline_status'] == 'awaiting_evidence_review'
    response = next((out / 'responses').glob('*.json'))
    response.write_bytes(response.read_bytes() + b' ')
    with pytest.raises(assessment.ReplayMismatch, match='response'):
        paper_workflow.compare_workflow(work, report, out, review_plan_path=review_plan)


def test_interrupted_injected_review_requires_exact_replay_before_provider_access(tmp_path):
    from test_paper_workflow import _frozen_compare, _compare_response
    work, report, out = _frozen_compare(tmp_path)
    review_plan = tmp_path / 'review-plan.json'
    review_plan.write_text(json.dumps(plan()), encoding='utf8')

    def provider(request):
        if request['operation'] == 'extract':
            return _compare_response(request)
        data = request['data']
        def entry(item):
            return {'claim_id': item['claim_id'], 'classification': 'needs_review',
                    'candidate_ids': [], 'reason': 'Independent comparison remains uncertain.'}
        return json.dumps({'batch_id': data['batch_id'], 'status': 'complete',
                          'report_claims': [entry(x) for x in data['report_claims']],
                          'reference_claims': [entry(x) for x in data['reference_claims']], 'notes': ''})

    expected = paper_workflow.compare_workflow(work, report, out, provider=provider,
                                               review_plan_path=review_plan)
    saved_path = out / 'model-review.json'
    saved = paper_workflow.read_json(saved_path)
    # Reproduce persisted input/stage files without a final model-call record.
    # This file belongs only to the disposable pytest fixture.
    saved_path.unlink()
    called = []
    def live_provider(request):
        called.append(request)
        return provider(request)
    with pytest.raises(ValueError, match='Interrupted injected review'):
        paper_workflow.compare_workflow(work, report, out, provider=live_provider,
                                       review_plan_path=review_plan)
    assert called == []
    replay = assessment.ReplayProvider(saved['calls'])
    assert paper_workflow.compare_workflow(work, report, out, provider=replay,
                                           review_plan_path=review_plan) == expected
    replay.assert_consumed()


@pytest.mark.parametrize('pointer', ['/rows/-1', '/rows/01', '/rows/+1', '/rows/ 1',
                                     '/rows/١', '/~2', '/bad~'])
def test_json_pointer_rejects_non_rfc6901_tokens(pointer):
    module = review_module()
    value = {'rows': ['zero', 'one'], '~2': 'must not resolve', 'bad~': 'must not resolve'}
    with pytest.raises(ValueError):
        module._json_pointer(value, pointer)


@pytest.mark.parametrize('pointer,expected', [('/rows/0', 'zero'), ('/rows/1', 'one'),
    ('/a~1b/~0value', 4), ('/~01', 'literal tilde-one'), ('/01', 'object key'), ('/', 'empty key')])
def test_json_pointer_preserves_valid_escapes_and_object_keys(pointer, expected):
    value = {'rows': ['zero', 'one'], 'a/b': {'~value': 4}, '~1': 'literal tilde-one',
             '01': 'object key', '': 'empty key'}
    assert review_module()._json_pointer(value, pointer) == expected
    assert review_module()._json_pointer(value, '') is value
