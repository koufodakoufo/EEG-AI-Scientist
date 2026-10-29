"""Scientific output boundary and independently checkable metric fixtures."""
from __future__ import annotations

import importlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Any
import unittest
import zipfile

import numpy as np

from eegfm.research_bench.real_worker import FileBinding
from eegfm.research_bench.real_worker import candidate_digest
from eegfm.research_bench.bundle import digest_file


class ScientificAggregatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec('eegfm.research_bench.real_aggregate'),
                             'trusted scientific aggregation is missing')
        self.mod = importlib.import_module('eegfm.research_bench.real_aggregate')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root/'out'
        self.out.mkdir()
        self.ids = np.array([f's_{i}' for i in range(8)])
        self.y = np.tile([0, 1], 4)
        self.subjects = np.repeat(['a', 'b', 'c', 'd'], 2)
        self.features = np.repeat(np.arange(8.)[:, None], 62, axis=1)
        self.train = self.root/'train.npz'
        self.truth = self.root/'truth.npz'
        np.savez(self.truth, sample_ids=self.ids, subject_ids=self.subjects,
                 y=self.y, features=self.features)
        np.savez(self.train, sample_ids=np.char.add('t_', self.ids),
                 subject_ids=np.char.add('t_', self.subjects), y=self.y, features=self.features)
        self.spec = SimpleNamespace(split='validation', candidate_digest='a'*64)
        self.baseline()

    def binding(self, path: Path) -> FileBinding:
        return FileBinding(path, digest_file(path))

    def aggregator(self, **kwargs: Any) -> Any:
        return self.mod.ScientificAggregator(
            {'validation': self.binding(self.truth), 'test': self.binding(self.truth)},
            self.binding(self.train), bootstrap_resamples=32, **kwargs)

    def baseline(self) -> None:
        np.savez(self.out/'results.npz', logits=self.y*2.-1, sample_ids=self.ids)

    def analysis(self, **changes: Any) -> None:
        arrays = dict(sample_ids=self.ids,
                      feature_predictions=np.repeat(self.features[:, None, :], 2, axis=1),
                      negative_predictions=np.zeros((8, 2, 62)),
                      negative_train_permutation=np.array([3, 2, 5, 4, 7, 6, 1, 0]))
        arrays.update(changes)
        np.savez(self.out/'analysis.npz', **arrays)

    def selection(self) -> FileBinding:
        path = self.root/'selection.json'
        self.aggregator().freeze_selection(self.out, self.spec, path)
        return self.binding(path)

    def interventions(self, **changes: Any) -> None:
        directions = np.zeros((2, 200, 6))
        directions[:, 0, 0] = 1
        controls = np.zeros((2, 3, 200, 6))
        for i in range(3):
            controls[:, i, i+1, 0] = 1
        original = np.ones((2, 8, 200))
        altered = np.repeat(original[:, None, :, :], 4, axis=1)
        for i in range(4):
            altered[:, i, :, i] -= 1
        arrays = dict(sample_ids=self.ids, selected_groups=np.array([0, 1]),
                      selected_layers=np.array([6, 6]), directions=directions,
                      control_directions=controls, original_pooled=original,
                      altered_pooled=altered, altered_logits=np.tile((self.y*2.-1), (2,4,1)),
                      residual_predictions=np.tile(self.features, (2,4,1,1)))
        arrays.update(changes)
        np.savez(self.out/'interventions.npz', **arrays)

    def test_baseline_does_not_claim_scientific_completion(self) -> None:
        result = self.aggregator()(self.out, self.spec)
        self.assertEqual(result['metrics']['accuracy'], 1.)
        self.assertEqual(result['metrics']['q1_groups'], 0.)
        self.assertEqual(result['metrics']['numeric_scope_complete'], 0.)
        self.assertEqual(result['metrics']['baseline_only'], 1.)

    def test_q1_raw_unclipped_r2_and_subject_intervals(self) -> None:
        self.analysis()
        result = self.aggregator()(self.out, self.spec)
        metrics = result['metrics']
        self.assertEqual(metrics['q1_l6_g00_r2'], 1.)
        self.assertAlmostEqual(metrics['q1_l6_g00_negative_r2'], -7/3)
        self.assertEqual(metrics['q1_l6_g00_r2_ci95_low'], 1.)
        self.assertEqual(metrics['q1_groups'], 24.)
        self.assertEqual(metrics['q2_interventions'], 0.)
        self.assertEqual(metrics['q1_only'], 1.)
        self.assertTrue(set(metrics) <= self.aggregator().released_metrics)
        report = json.loads((self.out/'trusted_analysis.json').read_text())
        self.assertEqual(report['uncertainty']['unit'], 'participant')
        self.assertEqual(report['q1'][0]['column_r2'], [1.]*6)

    def test_constant_training_columns_are_excluded_and_counted(self) -> None:
        train = self.features.copy()
        train[:, :6] = 1
        np.savez(self.train, sample_ids=np.char.add('t_', self.ids),
                 subject_ids=np.char.add('t_', self.subjects), y=self.y, features=train)
        self.analysis()
        result = self.aggregator()(self.out, self.spec)['metrics']
        self.assertNotIn('q1_l6_g00_r2', result)
        self.assertEqual(result['q1_l6_g00_active_columns'], 0.)
        self.assertEqual(result['q1_groups'], 22.)

    def test_reordered_rows_labels_scalars_and_nonfinite_are_rejected(self) -> None:
        for changes in ({'sample_ids': self.ids[::-1]}, {'y': self.y},
                        {'accuracy': np.asarray(1.)},
                        {'feature_predictions': np.full((8,2,62), np.nan)}):
            with self.subTest(changes=list(changes)):
                self.analysis(**changes)
                with self.assertRaises(ValueError):
                    self.aggregator()(self.out, self.spec)

    def test_negative_control_requires_actual_subject_derangement(self) -> None:
        for permutation in (np.arange(8), np.array([1,0,3,2,5,4,7,6]), np.zeros(8, dtype=int)):
            self.analysis(negative_train_permutation=permutation)
            with self.assertRaises(ValueError):
                self.aggregator()(self.out, self.spec)

    def test_archive_rejects_huge_header_shape_before_allocation(self) -> None:
        self.analysis()
        malformed = io.BytesIO()
        np.lib.format.write_array_header_1_0(malformed, {'descr':'<f8', 'fortran_order':False,
                                                       'shape':(10**12,2,62)})
        with zipfile.ZipFile(self.out/'analysis.npz', 'w') as archive:
            archive.writestr('feature_predictions.npy', malformed.getvalue())
            for name, value in {'sample_ids':self.ids, 'negative_predictions':np.zeros((8,2,62)),
                                'negative_train_permutation':np.arange(8)}.items():
                content = io.BytesIO(); np.save(content, value)
                archive.writestr(name+'.npy', content.getvalue())
        with self.assertRaises(ValueError):
            self.aggregator()(self.out, self.spec)

    def test_bound_truth_tampering_is_rejected(self) -> None:
        aggregate = self.aggregator()
        self.truth.write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            aggregate(self.out, self.spec)

    def test_selection_freezes_validation_only_and_binds_candidate(self) -> None:
        self.analysis()
        binding = self.selection()
        document = json.loads(binding.path.read_text())
        self.assertEqual(document['selected'], [{'group':0, 'layer':6}, {'group':1, 'layer':6}])
        with self.assertRaises(ValueError):
            self.aggregator().freeze_selection(self.out, SimpleNamespace(split='test', candidate_digest='a'*64), self.root/'bad.json')
        self.interventions()
        aggregate = self.aggregator(selection_by_candidate={'b'*64: binding})
        with self.assertRaises(ValueError):
            aggregate(self.out, SimpleNamespace(split='test', candidate_digest='b'*64))

    def test_q2_actual_rank_norm_and_paired_task_contrast(self) -> None:
        self.analysis()
        binding = self.selection()
        self.interventions()
        result = self.aggregator(selection_by_candidate={'a'*64:binding})(self.out, self.spec)['metrics']
        self.assertEqual(result['q2_interventions'], 2.)
        self.assertEqual(result['q2_s0_rank'], 1.)
        self.assertEqual(result['q2_s0_balanced_accuracy_contrast'], 0.)
        self.assertEqual(result['q3_s0_learned_r2'], 1.)
        self.assertEqual(result['numeric_scope_complete'], 1.)

    def test_q2_rejects_mismatched_strength_rank_or_selection(self) -> None:
        self.analysis()
        binding = self.selection()
        aggregate = self.aggregator(selection_by_candidate={'a'*64:binding})
        for name in ('strength', 'rank', 'selection'):
            self.interventions()
            with np.load(self.out/'interventions.npz') as archive:
                arrays = dict(archive)
            if name == 'strength': arrays['altered_pooled'][0,1,0,1] = -1
            if name == 'rank': arrays['control_directions'][0,0,2,1] = 1
            if name == 'selection': arrays['selected_layers'][0] = 12
            np.savez(self.out/'interventions.npz', **arrays)
            with self.subTest(name=name), self.assertRaises(ValueError):
                aggregate(self.out, self.spec)

    def test_q2_cannot_select_using_test_scores(self) -> None:
        self.analysis()
        self.interventions()
        with self.assertRaises(ValueError):
            self.aggregator()(self.out, SimpleNamespace(split='test', candidate_digest='a'*64))

    def test_candidate_frozen_validation_predictions_must_match_validation_evidence(self) -> None:
        self.analysis()
        candidate = self.root/'candidate'
        candidate.mkdir()
        (candidate/'main.py').write_text('pass\n')
        np.savez(candidate/'validation_selection.npz', sample_ids=self.ids,
                 feature_predictions=np.zeros((8,2,62)))
        spec = SimpleNamespace(split='validation', candidate_dir=candidate,
                               candidate_digest=candidate_digest(candidate))
        with self.assertRaises(ValueError):
            self.aggregator()(self.out, spec)

    def test_duplicate_archive_members_and_structured_dtype_are_rejected(self) -> None:
        self.analysis()
        with zipfile.ZipFile(self.out/'analysis.npz', 'a') as archive:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                archive.writestr('sample_ids.npy', b'duplicate')
        with self.assertRaises(ValueError):
            self.aggregator()(self.out, self.spec)
        self.analysis(feature_predictions=np.zeros((8,2,62), dtype=[('unsafe', '<f8')]))
        with self.assertRaises(ValueError):
            self.aggregator()(self.out, self.spec)

    def test_candidate_precreated_trusted_report_is_rejected(self) -> None:
        (self.out/'trusted_analysis.json').write_text('{"numeric_scope_complete":true}')
        with self.assertRaises(FileExistsError):
            self.aggregator()(self.out, self.spec)

    def test_frozen_selection_cannot_skip_validation_analysis(self) -> None:
        candidate = self.root/'candidate'
        candidate.mkdir()
        (candidate/'main.py').write_text('pass\n')
        np.savez(candidate/'validation_selection.npz', sample_ids=self.ids,
                 feature_predictions=np.repeat(self.features[:, None, :],2,axis=1))
        spec = SimpleNamespace(split='validation', candidate_dir=candidate,
                               candidate_digest=candidate_digest(candidate))
        with self.assertRaises(ValueError):
            self.aggregator()(self.out, spec)

    def test_finite_but_overflowing_predictions_cannot_hide_control_metrics(self) -> None:
        self.analysis(negative_predictions=np.full((8,2,62), 1e308))
        with self.assertRaises(ValueError):
            self.aggregator()(self.out, self.spec)


if __name__ == '__main__':
    unittest.main()
