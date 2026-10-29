"""Prospective synthetic calibration harness tests; never invokes a model."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/research/semantic_calibration_v3.py'
FIXTURES = ROOT / 'docs/research/2026-10-30-extension/semantic-calibration'


class SemanticCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location('semantic_calibration', SCRIPT)
        assert spec is not None and spec.loader is not None
        cls.h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.h)
        cls.data = cls.h.load_fixtures(FIXTURES)

    def test_fixed_synthetic_oracle_is_consistent_and_not_model_evidence(self) -> None:
        report = self.h.validate_fixtures(self.data)
        self.assertEqual((report['extraction_cases'], report['directional_pairs']), (12, 16))
        extraction, judge = self.h.oracle_responses(self.data)
        scored = self.h.score(self.data, extraction, judge)
        self.assertEqual(scored['status'], 'passed_synthetic_development_calibration')
        self.assertEqual(scored['atom_recall'], 1)
        self.assertEqual(scored['pair_accuracy'], 1)
        self.assertEqual(scored['critical_errors'], [])
        self.assertEqual(scored['general_or_clinical_validity'], 'not_established')

    def test_utf16_offsets_are_rejected_and_duplicate_locations_retained(self) -> None:
        extraction, judge = self.h.oracle_responses(self.data)
        duplicate = next(r for r in extraction['results'] if r['case_id'] == 'X05')
        self.assertEqual(len(duplicate['responses'][0]['claims'][0]['source_spans']), 2)
        unicode_case = next(r for r in extraction['results'] if r['case_id'] == 'X12')
        span = unicode_case['responses'][0]['claims'][0]['source_spans'][0]
        span['start'] += 1
        span['end'] += 1
        result = self.h.score(self.data, extraction, judge)
        self.assertEqual(result['status'], 'pending_invalid_or_incomplete_response')
        self.assertIsNone(result['atom_recall'])

    def test_missing_output_never_becomes_zero_ability_or_pass(self) -> None:
        extraction, judge = self.h.oracle_responses(self.data)
        extraction['results'].pop()
        result = self.h.score(self.data, extraction, judge)
        self.assertEqual(result['status'], 'pending_invalid_or_incomplete_response')
        self.assertIsNone(result['pair_accuracy'])
        result = self.h.score(self.data, None, judge)
        self.assertIsNone(result['atom_recall'])

    def test_scope_overreach_and_empty_failure_are_critical_even_above_90_percent(self) -> None:
        extraction, judge = self.h.oracle_responses(self.data)
        judge['results'][5]['judgment']['relation'] = 'supported'
        result = self.h.score(self.data, extraction, judge)
        self.assertEqual(result['status'], 'failed_synthetic_development_calibration')
        self.assertGreaterEqual(result['pair_accuracy'], .9)
        self.assertTrue(result['critical_errors'])
        extraction, judge = self.h.oracle_responses(self.data)
        failed = next(r for r in extraction['results'] if r['case_id'] == 'X10')
        failed['responses'][0]['status'] = 'complete'
        result = self.h.score(self.data, extraction, judge)
        self.assertEqual(result['status'], 'failed_synthetic_development_calibration')
        self.assertTrue(any('empty_failure' in e for e in result['critical_errors']))

    def test_point_cannot_validate_invented_mechanism(self) -> None:
        extraction, judge = self.h.oracle_responses(self.data)
        extra = copy.deepcopy(extraction['results'][0]['responses'][0]['claims'][0])
        extra.update(claim_id='invented', kind='mechanism', predicate='mechanistic explanation',
                     direction='asserted', payload={'relation': 'This proves a causal mechanism.'})
        extraction['results'][0]['responses'][0]['claims'].append(extra)
        result = self.h.score(self.data, extraction, judge)
        self.assertTrue(any('causal_overreach' in e for e in result['critical_errors']))

    def test_scope_swap_within_multiscope_report_is_critical(self) -> None:
        extraction, judge = self.h.oracle_responses(self.data)
        row = next(r for r in extraction['results'] if r['case_id'] == 'X04')
        row['responses'][0]['claims'][1]['scope']['split'] = 'validation'
        result = self.h.score(self.data, extraction, judge)
        self.assertTrue(any('scope' in e for e in result['critical_errors']))

    def test_duplicate_identical_giant_spans_cannot_fake_two_occurrences(self) -> None:
        extraction, judge = self.h.oracle_responses(self.data)
        row = next(r for r in extraction['results'] if r['case_id'] == 'X05')
        source = next(c for c in self.data['extraction']['cases'] if c['case_id'] == 'X05')['report']
        giant = {'start': 0, 'end': len(source), 'quote': source}
        row['responses'][0]['claims'][0]['source_spans'] = [giant, copy.deepcopy(giant)]
        result = self.h.score(self.data, extraction, judge)
        case = next(c for c in result['case_results'] if c['case_id'] == 'X05')
        self.assertEqual(case['matched_atoms'], 0)

    def test_parser_rejects_duplicate_keys_fences_and_nonfinite(self) -> None:
        for text in ('{"x":1,"x":2}', '```json\n{}\n```', '{"x":NaN}'):
            with self.assertRaises(ValueError):
                self.h.parse_json(text)

    def test_stage_keeps_oracle_private_and_tamper_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / 'stage'
            manifest = self.h.stage(FIXTURES, stage, 'R85', 'R86')
            self.h.verify_stage(stage, self.h.file_sha256(stage / 'FREEZE.json'))
            for kind in ('extraction', 'judge'):
                names = {p.name for p in (stage / 'source' / kind).iterdir()}
                self.assertEqual(names, {'INPUT.json', 'PROTOCOL.md', 'PROMPT.txt'})
                public = json.loads((stage / 'source' / kind / 'INPUT.json').read_text(encoding='utf-8'))
                self.assertNotIn('oracle', public)
                self.assertNotIn('expected_relation', json.dumps(public))
            self.assertEqual(manifest['model_configuration']['role'], 'judge')
            self.assertEqual(manifest['model_configuration']['timeout_seconds'], 900)
            self.assertEqual(manifest['model_configuration']['reasoning_effort'], 'medium')
            (stage / 'source' / 'judge' / 'INPUT.json').write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError):
                self.h.verify_stage(stage, self.h.file_sha256(stage / 'FREEZE.json'))


if __name__ == '__main__':
    unittest.main()
