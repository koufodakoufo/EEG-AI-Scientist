"""Private, source-anchored paper task records and a deliberately small public export.

Independently authored FIRE-inspired workflow; no upstream code or prompts.
Validation checks boundaries and provenance declarations, not scientific truth.
All source text is inert data. Keep records and source text outside Git.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Any, Mapping

from eegfm.evaluation.claims import canonical_sha256, canonicalize_claims, validate_claim

VERSION = 'paper_task_v1'
CONDITION_FIELDS = {'cohort', 'checkpoint', 'head', 'preprocessing', 'representation', 'metric', 'inference_unit'}
PUBLIC_FIELDS = {'question', 'resources', 'constraints', 'budget', 'report_contract'}


def _fields(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f'{label} fields mismatch')


def _text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError(f'{label} must be nonempty text')


def _spans(spans: Any, text: str) -> None:
    if not isinstance(spans, list) or not spans:
        raise ValueError('Source anchors are required')
    for span in spans:
        _fields(span, {'start', 'end', 'quote'}, 'source span')
        start, end = span['start'], span['end']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text) or text[start:end] != span['quote']:
            raise ValueError('Source anchor must preserve an exact Unicode span')


def validate_private_task(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return an isolated validated record. Explicit unknown conditions use JSON null.

Each reference anchors to its declared source, whose kind must agree with the
original/adapted/extension declaration. Adapted results require artifact IDs.
Source authorship and artifact validity still require independent review.
"""
    task = copy.deepcopy(dict(value))
    _fields(task, {'schema_version', 'task_id', 'revision', 'paper', 'sources', 'tree',
                   'selected_question_id', 'selected_experiment_id', 'scope', 'public', 'references'}, 'private task')
    if task['schema_version'] != VERSION:
        raise ValueError('Unknown paper task version')
    for name in ('task_id', 'revision', 'selected_question_id', 'selected_experiment_id'):
        _text(task[name], name)
    _fields(task['paper'], {'title', 'version', 'uri', 'source_id'}, 'paper')
    for name, item in task['paper'].items(): _text(item, name)
    if not isinstance(task['sources'], list) or not task['sources']:
        raise ValueError('Versioned sources required')
    sources = {}
    for source in task['sources']:
        _fields(source, {'source_id', 'kind', 'version', 'uri', 'text', 'sha256'}, 'source')
        for name, item in source.items(): _text(item, name)
        if source['kind'] not in {'paper', 'adapted_result', 'extension'} or source['source_id'] in sources:
            raise ValueError('Unknown source kind or duplicate source ID')
        if hashlib.sha256(source['text'].encode()).hexdigest() != source['sha256']:
            raise ValueError('Source hash changed')
        sources[source['source_id']] = source
    primary = sources.get(task['paper']['source_id'])
    if primary is None or primary['kind'] != 'paper' or primary['version'] != task['paper']['version'] or primary['uri'] != task['paper']['uri']:
        raise ValueError('Paper identity differs from primary source')
    scope = task['scope']
    _fields(scope, {'dataset', 'model', 'split', 'conditions'}, 'scope')
    for name in ('dataset', 'model', 'split'): _text(scope[name], name)
    if not isinstance(scope['conditions'], dict) or not CONDITION_FIELDS <= set(scope['conditions']):
        raise ValueError('Experimental conditions missing; use explicit null for unknowns')
    if not isinstance(task['tree'], list) or not task['tree']:
        raise ValueError('Source-anchored problem tree required')
    nodes = {}
    for node in task['tree']:
        _fields(node, {'node_id', 'parent_id', 'role', 'text', 'source_spans'}, 'tree node')
        for name in ('node_id', 'text'): _text(node[name], name)
        if node['node_id'] in nodes or node['role'] not in {'root', 'question', 'experiment'}:
            raise ValueError('Duplicate node or unknown role')
        _spans(node['source_spans'], primary['text'])
        nodes[node['node_id']] = node
    roots = [n for n in nodes.values() if n['parent_id'] is None]
    if len(roots) != 1 or roots[0]['role'] != 'root':
        raise ValueError('Exactly one root is required')
    for node in nodes.values():
        seen = set()
        current = node
        while current['parent_id'] is not None:
            if current['node_id'] in seen or current['parent_id'] not in nodes:
                raise ValueError('Cyclic or disconnected tree')
            seen.add(current['node_id'])
            current = nodes[current['parent_id']]
        if node['role'] == 'root' and node != roots[0]:
            raise ValueError('Nested root is invalid')
        if node['role'] == 'experiment' and any(n['parent_id'] == node['node_id'] for n in nodes.values()):
            raise ValueError('Experiment must be a leaf')
    question = nodes.get(task['selected_question_id'])
    experiment = nodes.get(task['selected_experiment_id'])
    if question is None or question['role'] != 'question' or experiment is None or experiment['role'] != 'experiment' or experiment['parent_id'] != question['node_id']:
        raise ValueError('Selected experiment must belong to selected parent question')
    public = task['public']
    _fields(public, PUBLIC_FIELDS, 'public packet')
    if public['question'] != question['text']:
        raise ValueError('Public question differs from selected parent')
    for name in ('resources', 'constraints', 'report_contract'):
        if not isinstance(public[name], list) or not public[name]:
            raise ValueError(f'{name} must be a nonempty text list')
        for item in public[name]: _text(item, name)
    if not isinstance(public['budget'], dict) or not public['budget'] or any(not isinstance(k, str) or type(v) not in (int, float) or v <= 0 for k, v in public['budget'].items()):
        raise ValueError('Public budget must contain positive numeric caps')
    if not isinstance(task['references'], list) or not task['references']:
        raise ValueError('Nonempty private reference claims required')
    kind_sources = {'original_paper': 'paper', 'adapted_computed': 'adapted_result', 'task_extension': 'extension'}
    for reference in task['references']:
        _fields(reference, {'claim', 'provenance'}, 'reference')
        claim = validate_claim(reference['claim'])
        provenance = reference['provenance']
        _fields(provenance, {'kind', 'source_id', 'rationale', 'artifact_ids'}, 'reference provenance')
        _text(provenance['rationale'], 'rationale')
        source = sources.get(provenance['source_id'])
        if provenance['kind'] not in kind_sources or source is None or source['kind'] != kind_sources[provenance['kind']]:
            raise ValueError('Reference provenance and anchored source kind disagree')
        if not isinstance(provenance['artifact_ids'], list):
            raise ValueError('Artifact IDs must be a list')
        for identifier in provenance['artifact_ids']: _text(identifier, 'artifact ID')
        if provenance['kind'] == 'adapted_computed' and not provenance['artifact_ids']:
            raise ValueError('Adapted computed reference requires independent artifact IDs')
        _spans(claim['source_spans'], source['text'])
        reference['claim'] = claim
    canonicalize_claims(r['claim'] for r in task['references'])
    canonical_sha256(task)  # Finite, JSON-compatible record only.
    return task


def export_public_task(value: Mapping[str, Any]) -> dict[str, Any]:
    """Export only author-reviewed public fields; never recursively sanitize a record.

Allowlisting cannot decide whether author-written public prose leaks an answer.
Review those strings before enrollment; source and reference keys never export.
"""
    task = validate_private_task(value)
    return {'schema_version': VERSION, 'task_id': task['task_id'], 'revision': task['revision'],
            **{key: copy.deepcopy(task['public'][key]) for key in sorted(PUBLIC_FIELDS)}}
