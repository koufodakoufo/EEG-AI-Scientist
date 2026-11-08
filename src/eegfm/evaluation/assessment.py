"""Operational scoped paper assessment with injected, auditable model calls.

Independently authored adapter around claims.py. No model SDK, credentials,
execution of source text, implicit retries, or claims of semantic calibration.
Returned artifacts contain private paper/report text; keep them outside Git and
outside the researcher's context. The caller enforces transport/model timeouts.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Callable, Iterable, Mapping

from eegfm.evaluation import claims
from eegfm.evaluation.paper import CONDITION_FIELDS, validate_private_task

VERSION = 'paper_assessment_v1.1'
Provider = Callable[[dict[str, Any]], str]
MAX_RAW_RESPONSE_CHARS = 2_000_000
MAX_RESPONSE_DEPTH = 32
UNKNOWN_SCOPE_VALUES = {'', '?', 'unknown', 'unspecified', 'missing', 'none', 'null',
                        'n/a', 'na', 'not specified', 'not reported', 'unreported', 'unavailable', 'tbd'}
DIRECTIONS = ('reference_supports_agent', 'agent_covers_reference')
CLAIM_CONTRACT = {
    'claim_id': 'unique string across ALL segments; prefix with segment_id',
    'kind': ['point', 'interval', 'mechanism', 'qualitative'],
    'scope': {'dataset': 'string; unspecified if absent', 'model': 'string; unspecified if absent',
              'split': 'string; unspecified if absent', 'conditions': 'JSON object, preserve exact experimental conditions'},
    'subject': 'string', 'predicate': 'string', 'direction': 'string', 'qualifiers': ['strings'],
    'payload': ('One flat object, not an object nested under the kind name. '
                'point fields: metric, estimate (finite number), unit. '
                'interval fields: metric, low, high, level (0 < level < 1), method, unit. '
                'mechanism fields: relation. qualitative fields: statement. '
                'All fields except explicitly numeric fields are strings.'),
    'source_spans': [{'start': 'global Unicode integer offset inclusive', 'end': 'global Unicode integer offset exclusive', 'quote': 'exact source substring'}],
    'evidence_ids': ['strings; do not invent evidence'],
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _parse(raw: str) -> dict[str, Any]:
    if len(raw) > MAX_RAW_RESPONSE_CHARS:
        raise ValueError('Response exceeds declared character limit')
    value = json.loads(raw, object_pairs_hook=_no_duplicates,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
    if not isinstance(value, dict):
        raise ValueError('Response must be one JSON object')
    # Bound structure iteratively before claims.py's recursive copying and
    # canonicalization. Parsing itself may also raise RecursionError, retained
    # by the caller together with the original raw response.
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > MAX_RESPONSE_DEPTH:
            raise ValueError('Response exceeds declared nesting depth')
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif type(item) in (int, float):
            if not math.isfinite(item):
                raise ValueError('Response number is not finite')
    return value


def _scope_is_known(scope: Mapping[str, Any]) -> bool:
    """Unknown equals unknown is not evidence of identical conditions.

Missing required conditions and unknown values anywhere in the scope remain
pending. An inapplicable condition needs an explicit reviewed description,
such as 'none (reviewed: no filtering)', rather than null or an N/A sentinel.
"""
    conditions = scope.get('conditions')
    if not isinstance(conditions, dict) or not CONDITION_FIELDS <= set(conditions):
        return False
    if any(not isinstance(scope.get(key), str) for key in ('dataset', 'model', 'split')):
        return False
    pending = list(scope.values())
    while pending:
        item = pending.pop()
        if item is None:
            return False
        if isinstance(item, str):
            normalized = ' '.join(item.strip().lower().replace('_', ' ').replace('-', ' ').split())
            if normalized in UNKNOWN_SCOPE_VALUES:
                return False
        elif isinstance(item, dict):
            if not item:
                return False
            pending.extend(item.values())
        elif isinstance(item, list):
            if not item:
                return False
            pending.extend(item)
    return True


class ReplayMismatch(ValueError):
    """A changed request or incomplete replay is a caller error, never a model call."""


class _RecordedFailure(Exception):
    def __init__(self, failure: dict[str, Any]):
        self.failure = failure


class ReplayProvider:
    """Replay exact ordered requests without network calls; detect request/hash drift.

Use ``assert_consumed()`` after replay when checking a saved run as a whole.
Calls are copied and both request and raw-response hashes are checked on load.
"""
    def __init__(self, calls: Iterable[Mapping[str, Any]]):
        self.calls = copy.deepcopy(list(calls))
        self.position = 0
        for call in self.calls:
            request = copy.deepcopy(call['request'])
            request_hash = request.pop('request_sha256')
            if claims.canonical_sha256(request) != request_hash or call['request_sha256'] != request_hash:
                raise ReplayMismatch('Saved request hash changed')
            raw = call['raw_response']
            if (None if raw is None else _sha(raw)) != call['response_sha256']:
                raise ReplayMismatch('Saved raw response hash changed')

    def __call__(self, request: dict[str, Any]) -> str:
        if self.position >= len(self.calls) or self.calls[self.position]['request'] != request:
            raise ReplayMismatch('Replay request changed, reordered, or exhausted')
        call = self.calls[self.position]
        self.position += 1
        if call['failure'] is not None and call['raw_response'] is None:
            raise _RecordedFailure(copy.deepcopy(call['failure']))
        return call['raw_response']

    def assert_consumed(self) -> None:
        if self.position != len(self.calls):
            raise ReplayMismatch('Replay contains unconsumed calls')


def _settings(provider_id: str, timeout_seconds: int) -> None:
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise ValueError('Explicit provider identity/version required')
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError('Positive integer timeout required')


def _request(operation: str, request_id: str, data: dict[str, Any], provider_id: str,
             timeout_seconds: int, provider_metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    extracting = operation == 'extract'
    contract = ({'segment_id': data['segment']['segment_id'], 'status': ['complete', 'truncated', 'service_failure'],
                 'claims': [CLAIM_CONTRACT], 'notes': 'string; describe omissions/failure'} if extracting else
                {'status': ['complete', 'truncated', 'service_failure'],
                 'judgment': {'agent_claim_id': data['agent_claim']['claim_id'],
                              'reference_claim_id': data['reference_claim']['claim_id'], 'direction': data['direction'],
                              'relation': ['supported', 'contradicted', 'not_covered', 'needs_review'],
                              'judge_version': claims.JUDGE_PROMPT_VERSION},
                 'notes': 'string; explain directional decision; judgment must be null for noncomplete status'})
    request = {'adapter_version': VERSION, 'request_id': request_id, 'operation': operation,
               'provider_id': provider_id, 'provider_metadata': copy.deepcopy(dict(provider_metadata or {})),
               'timeout_seconds': timeout_seconds,
               'prompt_version': claims.EXTRACTION_PROMPT_VERSION if extracting else claims.JUDGE_PROMPT_VERSION,
               'instructions': (claims.EXTRACTION_PROMPT + '\nDo not wrap the payload in a kind key. '
                   'For kind="point", use payload={"metric":"accuracy","estimate":0.75,"unit":"fraction"}, '
                   'NOT payload={"point":{...}}. Each other kind likewise uses its direct fields.')
                   if extracting else claims.JUDGE_PROMPT,
               'data': copy.deepcopy(data), 'response_contract': contract}
    request['request_sha256'] = claims.canonical_sha256(request)
    return request


def _invoke(provider: Provider, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    record = {'request': copy.deepcopy(request), 'request_sha256': request['request_sha256'],
              'raw_response': None, 'response_sha256': None, 'failure': None, 'status': 'service_failure'}
    try:
        raw = provider(copy.deepcopy(request))
        if not isinstance(raw, str):
            raise TypeError('Provider must return raw JSON text')
        record.update(raw_response=raw, response_sha256=_sha(raw))
    except ReplayMismatch:
        raise
    except _RecordedFailure as exc:
        record['failure'] = exc.failure
        return record, None
    except Exception as exc:
        record['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
        return record, None
    try:
        response = _parse(raw)
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        record.update(status='invalid_output', failure={'type': type(exc).__name__, 'message': str(exc)})
        return record, None
    return record, response


def extract_report(report: str, source_id: str, provider: Provider, *, provider_id: str,
                   segment_chars: int = 4000, timeout_seconds: int = 900,
                   provider_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Extract every primary segment; retain raw failures and exact global spans.

Provider is called once per segment with no hidden repair or retry. Invalid
responses become explicit service-failure segments; partial output never scores.
"""
    _settings(provider_id, timeout_seconds)
    plan = claims.build_extraction_plan(report, source_id, segment_chars=segment_chars)
    calls, responses = [], []
    for segment in plan['segments']:
        request = _request('extract', f"extract:{segment['segment_id']}",
                           {'source_id': source_id, 'report_sha256': plan['report_sha256'], 'segment': segment,
                            'max_claims_per_segment': claims.MAX_CLAIMS_PER_SEGMENT},
                           provider_id, timeout_seconds, provider_metadata)
        call, response = _invoke(provider, request)
        if response is not None:
            try:
                if set(response) != {'segment_id', 'status', 'claims', 'notes'} or response['segment_id'] != segment['segment_id'] or response['status'] not in {'complete', 'truncated', 'service_failure'}:
                    raise ValueError('Segment response fields/identity/status mismatch')
                if not isinstance(response['notes'], str) or not isinstance(response['claims'], list) or len(response['claims']) > claims.MAX_CLAIMS_PER_SEGMENT:
                    raise ValueError('Invalid notes, claims or per-segment cap')
                for value in response['claims']:
                    claim = claims.validate_claim(value)
                    for span in claim['source_spans']:
                        if not segment['start'] <= span['start'] < span['end'] <= segment['end'] or report[span['start']:span['end']] != span['quote']:
                            raise ValueError('Claim is not anchored to exact primary segment')
                if response['status'] == 'complete' and len(response['claims']) == claims.MAX_CLAIMS_PER_SEGMENT:
                    # The frozen extraction contract says reaching the cap is
                    # incomplete. Keep all claims/raw output, but never score.
                    response = {**response, 'status': 'truncated',
                                'notes': response['notes'] + '\nAdapter: extraction reached the declared claim cap.'}
                call['status'] = response['status']
            except (ValueError, TypeError, RecursionError, OverflowError) as exc:
                call.update(status='invalid_output', failure={'type': type(exc).__name__, 'message': str(exc)})
                response = None
        if response is None:
            response = {'segment_id': segment['segment_id'], 'status': 'service_failure', 'claims': [],
                        'notes': json.dumps(call['failure'], ensure_ascii=False)}
        calls.append(call)
        responses.append(response)
    assembly_failure = None
    try:
        extraction = claims.assemble_extractions(plan, responses)
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        # For example globally duplicated IDs. Keep every raw response and fail
        # the whole extraction, rather than using a seemingly successful subset.
        assembly_failure = {'type': type(exc).__name__, 'message': str(exc)}
        extraction = claims.assemble_extractions(plan, [
            {'segment_id': s['segment_id'], 'status': 'service_failure', 'claims': [], 'notes': str(exc)}
            for s in plan['segments']])
    return {'version': VERSION, 'plan': plan, 'extraction': extraction, 'calls': calls,
            'assembly_failure': assembly_failure}


def assess_report(private_task: Mapping[str, Any], report: str, provider: Provider, *, provider_id: str,
                  source_id: str = 'episode-report', segment_chars: int = 4000,
                  timeout_seconds: int = 900, max_judge_calls: int = 512, max_judge_pairs: int = 4096,
                  provider_metadata: Mapping[str, Any] | None = None,
                  evidence_verdicts: Iterable[Mapping[str, Any]] = (),
                  process_checks: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Extract, judge both directions, and retain separated scientific dimensions.

Only the trusted controller may supply evidence_verdicts/process_checks. Text
never grants evidence validity. Model-call and pair limits are explicit; any
missing direction/failure/budget exhaustion prevents a complete coverage score.
Differing scope/kind gets deterministic noncoverage, never contradiction.
"""
    for name, limit in [('max_judge_calls', max_judge_calls), ('max_judge_pairs', max_judge_pairs)]:
        if type(limit) is not int or limit < 0:
            raise ValueError(f'{name} must be a nonnegative integer')
    task = validate_private_task(private_task)
    extracted = extract_report(report, source_id, provider, provider_id=provider_id,
                               segment_chars=segment_chars, timeout_seconds=timeout_seconds, provider_metadata=provider_metadata)
    agents = extracted['extraction']['claims']
    canonical_references = claims.canonicalize_claims(r['claim'] for r in task['references'])
    references = canonical_references['claims']
    task_scope_known = _scope_is_known(task['scope'])
    sources = {source['source_id']: source for source in task['sources']}
    reference_manifest = [
        {'claim_id': reference['claim']['claim_id'],
         'canonical_claim_id': canonical_references['aliases'][reference['claim']['claim_id']],
         'scope': copy.deepcopy(reference['claim']['scope']),
         'matches_task_scope': (reference['claim']['scope'] == task['scope']
                                if task_scope_known and _scope_is_known(reference['claim']['scope']) else None),
         'provenance': copy.deepcopy(reference['provenance']),
         'source_sha256': sources[reference['provenance']['source_id']]['sha256'],
         'source_spans': copy.deepcopy(reference['claim']['source_spans'])}
        for reference in task['references']]
    calls = list(extracted['calls'])
    judgments, boundaries, review_boundaries = [], [], []
    pair_count, judge_calls = len(agents) * len(references), 0
    complete = extracted['extraction']['eligible_for_scoring']
    notes = []
    if not complete:
        notes.append('Extraction incomplete; directional judging not attempted.')
    elif pair_count > max_judge_pairs:
        complete = False
        notes.append('Declared maximum pair count exceeded; no judging attempted.')
    else:
        for agent in agents:
            for reference in references:
                mismatch = agent['scope'] != reference['scope'] or agent['kind'] != reference['kind']
                scope_unknown = not task_scope_known or not _scope_is_known(agent['scope']) or not _scope_is_known(reference['scope'])
                for direction in DIRECTIONS:
                    edge = {'agent_claim_id': agent['claim_id'], 'reference_claim_id': reference['claim_id'],
                            'direction': direction, 'judge_version': claims.JUDGE_PROMPT_VERSION}
                    if scope_unknown:
                        complete = False
                        judgments.append({**edge, 'relation': 'needs_review'})
                        review_boundaries.append({**edge, 'reason': 'Task, agent or reference scope contains missing/unknown identity or conditions.'})
                        continue
                    if mismatch:
                        judgments.append({**edge, 'relation': 'not_covered'})
                        boundaries.append({**edge, 'reason': 'Different experimental scope or claim kind; incomparable for direct support.'})
                        continue
                    if judge_calls >= max_judge_calls:
                        complete = False
                        continue
                    judge_calls += 1
                    request = _request('judge', f'judge:{judge_calls:06d}',
                                       {'agent_claim': agent, 'reference_claim': reference, 'direction': direction},
                                       provider_id, timeout_seconds, provider_metadata)
                    call, response = _invoke(provider, request)
                    if response is not None:
                        try:
                            if set(response) != {'status', 'judgment', 'notes'} or response['status'] not in {'complete', 'truncated', 'service_failure'} or not isinstance(response['notes'], str):
                                raise ValueError('Judgment response fields/status mismatch')
                            if response['status'] != 'complete':
                                if response['judgment'] is not None:
                                    raise ValueError('Noncomplete judgment must be null')
                                complete = False
                            else:
                                judgment = response['judgment']
                                if not isinstance(judgment, dict) or set(judgment) != set(edge) | {'relation'} or any(judgment[k] != v for k, v in edge.items()) or judgment['relation'] not in {'supported', 'contradicted', 'not_covered', 'needs_review'}:
                                    raise ValueError('Judgment must bind exact requested IDs/direction/version')
                                judgments.append(judgment)
                            call['status'] = response['status']
                        except (ValueError, TypeError, RecursionError, OverflowError) as exc:
                            call.update(status='invalid_output', failure={'type': type(exc).__name__, 'message': str(exc)})
                            complete = False
                    else:
                        complete = False
                    calls.append(call)
    expected = 2 * pair_count
    if not task_scope_known:
        complete = False
        notes.append('Task scope contains missing/unknown identity or conditions; comparability requires review.')
    if len(judgments) != expected:
        complete = False
    if not complete and judge_calls >= max_judge_calls and len(judgments) < expected:
        notes.append('Judgments incomplete; model call cap reached or provider output failed.')
    dimensions = claims.summarize_dimensions(agents, references, judgments,
                    judge_version=claims.JUDGE_PROMPT_VERSION, evidence_verdicts=evidence_verdicts,
                    process_checks=process_checks, extraction_status='complete' if complete else 'assessment_incomplete')
    return {'version': VERSION, 'task_id': task['task_id'], 'task_revision': task['revision'],
            'private_task_sha256': claims.canonical_sha256(task), 'report_sha256': _sha(report),
            'status': dimensions['status'], 'extraction': extracted['extraction'], 'extraction_plan': extracted['plan'],
            'assembly_failure': extracted['assembly_failure'], 'calls': calls,
            'judging': {'status': 'complete' if complete else 'incomplete', 'expected_directional_edges': expected,
                        'completed_directional_edges': len(judgments), 'model_calls': judge_calls,
                        'max_judge_calls': max_judge_calls, 'max_judge_pairs': max_judge_pairs,
                        'boundary_noncoverage': boundaries, 'boundary_review': review_boundaries,
                        'task_scope_known': task_scope_known, 'notes': notes},
            'reference_manifest': reference_manifest,
            'judgments': judgments, 'dimensions': dimensions,
            'limitations': ['Adaptation assessment, not an official FIRE score; reference provenance remains distinct.',
                            'Exact spans/schema checks and deterministic replay do not establish semantic calibration.',
                            'Provider bridge must enforce the recorded timeout and separately retain actual cost.']}
