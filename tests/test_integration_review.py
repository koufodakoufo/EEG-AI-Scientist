"""Focused R14 integration-review regressions; no real data/model execution."""
from __future__ import annotations

import importlib.util
import sys
import unittest
import zipfile


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy required for numeric boundary')
class NumericBoundaryReviewTests(unittest.TestCase):
    def test_overflowing_off_span_interventions_are_rejected(self) -> None:
        import numpy as np
        import test_real_aggregate as fixtures

        fixture = fixtures.ScientificAggregatorTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.analysis()
        selection = fixture.selection()
        fixture.interventions()
        path = fixture.out / 'interventions.npz'
        with np.load(path, allow_pickle=False) as archive:
            arrays = dict(archive)
        # All declared direction spans use coordinates 0-3. Coordinate 199
        # is outside every span, while a finite 1e200 squares to infinity.
        arrays['original_pooled'][:] = 0
        arrays['altered_pooled'][:] = 0
        arrays['altered_pooled'][..., 199] = 1e200
        np.savez(path, **arrays)
        aggregate = fixture.aggregator(selection_by_candidate={'a' * 64: selection})
        with self.assertRaises(ValueError):
            aggregate(fixture.out, fixture.spec)


@unittest.skipUnless(sys.platform == 'linux', 'Linux worker enrollment')
class InputBoundaryReviewTests(unittest.TestCase):
    def test_evaluation_features_cannot_cross_candidate_boundary(self) -> None:
        import test_real_worker as fixtures

        fixture = fixtures.WorkerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with zipfile.ZipFile(fixture.inputs / 'test.npz', 'a') as archive:
            archive.writestr('features.npy', b'private feature target placeholder')
        evaluator = fixture.evaluator()
        with self.assertRaises(ValueError):
            evaluator._verify(fixture.spec('test'))


if __name__ == '__main__':
    unittest.main()
