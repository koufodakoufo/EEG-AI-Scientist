"""Synthetic boundary fixtures; no private paper content or model calibration."""
from __future__ import annotations

import copy
import hashlib

import pytest

from eegfm.evaluation import paper


def atomic(identifier: str = 'r1', text: str = 'Accuracy is 0.75.') -> dict:
    return {'claim_id': identifier, 'kind': 'point',
            'scope': {'dataset': 'synthetic', 'model': 'M1', 'split': 'validation',
                      'conditions': {'cohort': 'A', 'checkpoint': 'M1-frozen-v1', 'head': 'linear',
                                     'preprocessing': 'fixed', 'representation': 'frozen',
                                     'metric': 'accuracy', 'inference_unit': 'subject'}},
            'subject': 'classifier', 'predicate': 'accuracy', 'direction': 'positive',
            'qualifiers': [], 'payload': {'metric': 'accuracy', 'estimate': .75, 'unit': 'fraction'},
            'source_spans': [{'start': 0, 'end': len(text), 'quote': text}], 'evidence_ids': []}


def private_task() -> dict:
    text = 'Accuracy is 0.75.'
    span = {'start': 0, 'end': len(text), 'quote': text}
    return {'schema_version': 'paper_task_v1', 'task_id': 'synthetic-paper-task', 'revision': '1',
            'paper': {'title': 'Synthetic source', 'version': 'v1', 'uri': 'urn:synthetic', 'source_id': 'paper'},
            'sources': [{'source_id': 'paper', 'kind': 'paper', 'version': 'v1', 'uri': 'urn:synthetic',
                         'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}],
            'tree': [{'node_id': 'root', 'parent_id': None, 'role': 'root', 'text': 'Prediction', 'source_spans': [span]},
                     {'node_id': 'question', 'parent_id': 'root', 'role': 'question', 'text': 'How accurate is M1?', 'source_spans': [span]},
                     {'node_id': 'experiment', 'parent_id': 'question', 'role': 'experiment', 'text': 'Held validation', 'source_spans': [span]}],
            'selected_question_id': 'question', 'selected_experiment_id': 'experiment',
            'scope': copy.deepcopy(atomic()['scope']),
            'public': {'question': 'How accurate is M1?', 'resources': ['synthetic data'],
                       'constraints': ['validation split'], 'budget': {'calls': 1},
                       'report_contract': ['report and predictions']},
            'references': [{'claim': atomic(), 'provenance': {'kind': 'original_paper', 'source_id': 'paper',
                            'rationale': 'Synthetic original assertion.', 'artifact_ids': []}}]}


def test_private_validation_and_explicit_public_allowlist():
    task = private_task()
    validated = paper.validate_private_task(task)
    public = paper.export_public_task(task)
    assert set(public) == {'schema_version', 'task_id', 'revision', 'question', 'resources',
                           'constraints', 'budget', 'report_contract'}
    assert '0.75' not in str(public)
    assert 'references' not in public and 'tree' not in public
    validated['sources'][0]['text'] = 'mutated'
    assert task['sources'][0]['text'] != 'mutated'


@pytest.mark.parametrize('mutation', ['hash', 'quote', 'tree', 'question', 'extra', 'provenance', 'scope'])
def test_private_record_rejects_drift_and_ambiguous_provenance(mutation):
    task = private_task()
    if mutation == 'hash': task['sources'][0]['sha256'] = '0' * 64
    if mutation == 'quote': task['references'][0]['claim']['source_spans'][0]['quote'] = 'Accuracy is 0.90.'
    if mutation == 'tree': task['tree'][0]['parent_id'] = 'experiment'
    if mutation == 'question': task['public']['question'] = 'secret injected answer'
    if mutation == 'extra': task['public']['references'] = task['references']
    if mutation == 'provenance': task['references'][0]['provenance']['kind'] = 'adapted_computed'
    if mutation == 'scope': del task['scope']['conditions']['cohort']
    with pytest.raises(ValueError): paper.validate_private_task(task)


def test_adapted_and_extension_references_are_labelled_and_anchored():
    for kind, source_kind in [('adapted_computed', 'adapted_result'), ('task_extension', 'extension')]:
        task = private_task()
        source = copy.deepcopy(task['sources'][0])
        source.update(source_id='computed', kind=source_kind)
        task['sources'].append(source)
        provenance = task['references'][0]['provenance']
        provenance.update(kind=kind, source_id='computed', artifact_ids=['independent-replay'])
        assert paper.validate_private_task(task)['references'][0]['provenance']['kind'] == kind
        task['references'][0]['claim']['source_spans'][0]['end'] -= 1
        with pytest.raises(ValueError): paper.validate_private_task(task)
