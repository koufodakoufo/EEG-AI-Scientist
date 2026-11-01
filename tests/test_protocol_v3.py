"""Synthetic-only calibration: no current EEG outcomes or model judges."""
from __future__ import annotations
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


def atom(identifier: str, kind: str = 'point', value: object = .5,
         split: str = 'validation') -> dict:
    payload = {'metric': 'accuracy', 'estimate': value, 'unit': 'fraction'}
    if kind == 'interval':
        payload = {'metric': 'accuracy', 'low': .1, 'high': .9, 'level': .95, 'method': 'percentile', 'unit': 'fraction'}
    return {'claim_id': identifier, 'kind': kind,
            'scope': {'dataset': 'synthetic-calibration', 'model': 'fixture', 'split': split, 'conditions': {'group': 'all'}},
            'subject': 'fixed classifier', 'predicate': 'classification accuracy',
            'direction': 'equal', 'qualifiers': ['synthetic only'], 'payload': payload,
            'source_spans': [{'start': 0, 'end': 1, 'quote': 'x'}], 'evidence_ids': ['e1']}


class ClaimsV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec('eegfm.evaluation.claims'))
        self.c = importlib.import_module('eegfm.evaluation.claims')

    def test_split_merge_and_duplicate_writing_keep_point_separate_from_wrong_interval(self) -> None:
        point, interval = atom('p'), atom('i', 'interval')
        packed = self.c.canonicalize_claims([point, interval, atom('duplicate')])
        separated = self.c.canonicalize_claims([point, interval])
        self.assertEqual(len(packed['claims']), 2)
        self.assertEqual(packed['aliases']['duplicate'], 'p')
        self.assertEqual(packed['semantic_hashes'], separated['semantic_hashes'])
        judgments = [dict(agent_claim_id='p', reference_claim_id='r', direction=d,
                          relation='supported', judge_version='synthetic-fixed')
                     for d in ('reference_supports_agent', 'agent_covers_reference')]
        judgments.append(dict(agent_claim_id='i', reference_claim_id='r', direction='reference_supports_agent',
                              relation='not_covered', judge_version='synthetic-fixed'))
        result = self.c.summarize_dimensions([point, interval], [atom('r')], judgments,
            evidence_verdicts=[{'claim_id':'p','status':'valid'}, {'claim_id':'i','status':'invalid'}],
            judge_version='synthetic-fixed')
        self.assertEqual(result['reference_coverage']['covered_reference_ids'], ['r'])
        self.assertEqual(result['numerical_validity']['valid_claim_ids'], ['p'])
        self.assertEqual(result['numerical_validity']['invalid_claim_ids'], ['i'])
        self.assertNotIn('total_score', result)

    def test_segmentation_preserves_every_character_and_reports_service_failure(self) -> None:
        report = 'first\nsecond\n' * 5
        plan = self.c.build_extraction_plan(report, 'fixture.txt', segment_chars=20)
        self.assertEqual(''.join(s['text'] for s in plan['segments']), report)
        responses = [{'segment_id':s['segment_id'], 'status':'complete', 'claims':[], 'notes':''} for s in plan['segments']]
        responses[-1]['status'] = 'service_failure'
        assembled = self.c.assemble_extractions(plan, responses)
        self.assertEqual(assembled['status'], 'service_failure')
        self.assertFalse(assembled['eligible_for_scoring'])
        self.assertTrue(assembled['incomplete_segments'])
        with self.assertRaises(ValueError):
            self.c.assemble_extractions(plan, responses[:-1])

    def test_more_than_thirty_atomic_claims_are_not_repacked(self) -> None:
        plan = self.c.build_extraction_plan('x', 'fixture.txt')
        claims = [atom(f'p{i}', value=i / 100) for i in range(40)]
        out = self.c.assemble_extractions(plan, [{'segment_id':'s0001','status':'complete','claims':claims,'notes':''}])
        self.assertEqual(len(out['claims']), 40)
        self.assertEqual(out['status'], 'complete')

    def test_truncation_is_not_silently_scored_and_inexact_quotes_fail(self) -> None:
        plan = self.c.build_extraction_plan('x', 'fixture.txt')
        response = {'segment_id':'s0001','status':'truncated','claims':[atom('p')], 'notes':'more assertions remain'}
        self.assertFalse(self.c.assemble_extractions(plan,[response])['eligible_for_scoring'])
        response['claims'][0]['source_spans'][0]['quote'] = 'not in source'
        with self.assertRaises(ValueError):
            self.c.assemble_extractions(plan,[response])

    def test_new_valid_findings_empty_submission_and_wrong_split(self) -> None:
        new = atom('new', value=.75)
        judgments = [{'agent_claim_id':'new','reference_claim_id':'r','direction':'reference_supports_agent',
                      'relation':'not_covered','judge_version':'synthetic-fixed'}]
        out = self.c.summarize_dimensions([new], [atom('r')], judgments,
            evidence_verdicts=[{'claim_id':'new','status':'valid'}], judge_version='synthetic-fixed')
        self.assertEqual(out['new_evidence_valid_findings'], ['new'])
        self.assertNotIn('new', out['contradictions'])
        empty = self.c.summarize_dimensions([], [atom('r')], [], judge_version='synthetic-fixed')
        self.assertEqual(empty['reference_coverage']['recall'], 0)
        failed = self.c.summarize_dimensions([], [atom('r')], [], judge_version='synthetic-fixed', extraction_status='service_failure')
        self.assertIsNone(failed['reference_coverage']['recall'])
        judgments[0]['relation'] = 'supported'
        with self.assertRaises(ValueError):
            self.c.summarize_dimensions([atom('new', split='train')], [atom('r')], judgments, judge_version='synthetic-fixed')


class EvidenceV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec('eegfm.evaluation.evidence'))
        self.e = importlib.import_module('eegfm.evaluation.evidence')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        text = 'sample_id,subject_id,split,pred,label\na,S0,train,0,1\nb,S1,validation,0,0\nc,S2,validation,1,0\n'
        (self.root/'mixed.csv').write_text(text, encoding='utf-8')
        self.manifest = {'schema_version':'split_manifest_v3','run_id':'fixture',
                         'samples':{'a':{'subject_id':'S0','split':'train'},
                                    'b':{'subject_id':'S1','split':'validation'},
                                    'c':{'subject_id':'S2','split':'validation'}}}
        self.binding = {'binding_id':'e1','run_id':'fixture','split':'validation',
                        'artifact_path':'mixed.csv','artifact_sha256':hashlib.sha256((self.root/'mixed.csv').read_bytes()).hexdigest(),
                        'split_manifest_sha256':self.e.canonical_sha256(self.manifest),
                        'row_selection':{'indices':[1,2],'sample_ids':['b','c']},'row_conditions':{},
                        'calculation':{'name':'accuracy','columns':{'prediction':'pred','target':'label'},'parameters':{}},
                        'reported_value':.5}
        self.receipt = {'run_id':'fixture','status':'completed','exit_code':0,
                        'artifacts':{'mixed.csv':self.binding['artifact_sha256']}}

    def audit(self, binding: dict | None = None) -> dict:
        return self.e.audit_metric_binding(binding or self.binding, self.root, self.manifest,
            expected_run_id='fixture', trusted_receipt=self.receipt)

    def test_exact_selected_rows_recomputed_and_wrong_split_or_tamper_rejected(self) -> None:
        result = self.audit()
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['computed_value'], .5)
        for field, value in [('reported_value', .9), ('split_manifest_sha256','0'*64),
                             ('row_selection',{'indices':[0,1],'sample_ids':['a','b']})]:
            bad = copy.deepcopy(self.binding); bad[field] = value
            self.assertFalse(self.audit(bad)['valid'])
        (self.root/'mixed.csv').write_text('tampered', encoding='utf-8')
        self.assertFalse(self.audit()['valid'])

    def test_mixed_artifact_requires_explicit_selector_and_trusted_receipt(self) -> None:
        bad = copy.deepcopy(self.binding); del bad['row_selection']
        self.assertFalse(self.audit(bad)['valid'])
        result = self.e.audit_metric_binding(self.binding, self.root, self.manifest, expected_run_id='fixture')
        self.assertFalse(result['valid'])

    def test_cluster_interval_keeps_whole_participants_and_wrong_interval_fails(self) -> None:
        rows = [{'sample_id':str(i),'subject_id':str(i//2),'split':'synthetic','value':str(i%2)} for i in range(6)]
        calculation = {'name':'cluster_bootstrap_mean_ci','columns':{'value':'value','group':'subject_id'},
                       'parameters':{'seed':12,'iterations':100,'level':.95}}
        # Every cluster has mean 1/2. Row bootstrap would create spurious variation.
        self.assertEqual(self.e.calculate_metric(rows,calculation), [.5,.5])
        calculation['columns']['group'] = 'sample_id'
        with self.assertRaises(ValueError):
            self.e.calculate_metric(rows,calculation)
        # The correct point estimate remains valid when a separately attached CI is wrong.
        self.assertTrue(self.audit()['valid'])
        interval = copy.deepcopy(self.binding)
        interval['calculation'] = {'name':'cluster_bootstrap_mean_ci',
            'columns':{'value':'pred','group':'subject_id'},
            'parameters':{'seed':12,'iterations':100,'level':.95}}
        interval['reported_value'] = [.2,.8]
        self.assertFalse(self.audit(interval)['valid'])
        interval['reported_value'] = [0.,1.]
        self.assertTrue(self.audit(interval)['valid'])

    def test_receipt_boolean_exit_and_nonmapping_artifacts_fail_closed(self) -> None:
        self.receipt['exit_code'] = False
        self.assertFalse(self.audit()['valid'])
        self.receipt['exit_code'] = 0
        self.receipt['artifacts'] = []
        self.assertFalse(self.audit()['valid'])

    def test_replay_dependency_and_diagnostic_contract(self) -> None:
        contract = {'schema_version':'replay_contract_v3','run_id':'fixture',
                    'limits':{'max_commands':3,'timeout_seconds':60,'storage_bytes':10000,'threads':1},
                    'seeded_inputs':{'input.csv':'1'*64,'analysis.py':'2'*64},
                    'commands':[{'command_id':'c1','argv':['python','-B','analysis.py'], 'cwd':'.',
                                 'env':{'PYTHONHASHSEED':'7'},'seeds':{'numpy':7},'depends_on':[],
                                 'inputs':['input.csv','analysis.py'],'writable_paths':['out'],
                                 'outputs':{'out/metric.json':{'role':'scientific','comparison':'json_numeric','atol':1e-8,'rtol':1e-6},
                                            'out/time.json':{'role':'diagnostic','comparison':'record_only'}}}]}
        valid = self.e.validate_replay_contract(contract)
        self.assertEqual(valid['execution_order'], ['c1'])
        bad = copy.deepcopy(contract); bad['commands'][0]['inputs'].append('undeclared.csv')
        with self.assertRaises(ValueError):
            self.e.validate_replay_contract(bad)
        bad = copy.deepcopy(contract); bad['commands'][0]['outputs']['out/metric.json']['comparison']='record_only'
        with self.assertRaises(ValueError):
            self.e.validate_replay_contract(bad)


if __name__ == '__main__':
    unittest.main()
