"""Finite CPU tests for the completed bootstrap core only.

Controlled arrays are unit-test inputs, never research observations. This does
not load official weights, access released binary data, publish broker requests,
train a model, certify CUDA, or certify the eventual scheduler adapter.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import time
import unittest

import numpy as np
import torch
import torch.nn.functional as F

from data_contract import (
    TARGETS, canonical_subject_ids, lodo_sources, protocol_session_ids,
    row_partition, token_shape,
)
from isa_builder import StimulusBatchBuilder
from isa_loss import flatten_normalize, paired_info_nce
from reference_core import SimCLRLoss, TrialAlignedISABatchBuilder

ROOT = Path(__file__).resolve().parent


class MetadataTests(unittest.TestCase):
    def test_lodo_all_sources_and_invalid_scope(self):
        for target in TARGETS:
            sources = lodo_sources(target, posttrain_split="all")
            self.assertEqual(set(sources), set(TARGETS) - {target})
            self.assertEqual(len(sources), 5)
        for target, split in (("other", "all"), ("SEED", "train"), ("SEED", "")):
            with self.assertRaises(ValueError):
                lodo_sources(target, posttrain_split=split)

    def test_seed_session_order_and_other_datasets(self):
        subjects = np.array(["a", "b", "a", "b", "a", "b"])
        sessions = np.array(["20130303", "20140606", "20130101", "20140404", "20130202", "20140505"])
        original = sessions.copy()
        actual = protocol_session_ids("SEED", subjects, sessions)
        np.testing.assert_array_equal(actual, ["3", "3", "1", "1", "2", "2"])
        np.testing.assert_array_equal(sessions, original)
        for target in TARGETS[1:]:
            np.testing.assert_array_equal(protocol_session_ids(target, subjects, sessions), original)

    def test_seed_bad_session_counts_and_missing_metadata(self):
        for sessions in (None, ["1", "2"], ["1", "1"], ["", "2"]):
            with self.assertRaises(ValueError):
                protocol_session_ids("SEED", ["a", "a"], sessions)

    def test_historical_subject_namespace_and_collisions(self):
        for target, published, expected in (
            ("DEAP", ["s01", "s32"], ["subj01", "subj32"]),
            ("SEEDIV", ["1", "15"], ["subj01", "subj15"]),
            ("SEED_VII", ["1", "20"], ["subj01", "subj20"]),
            ("SEED_V", ["01", "16"], ["1", "16"]),
            ("SEED", ["subject_a", "subject_b"], ["subject_a", "subject_b"]),
        ):
            np.testing.assert_array_equal(canonical_subject_ids(target, published), expected)
        with self.assertRaises(ValueError):
            canonical_subject_ids("SEED_V", ["01", "1"])

    def test_partition_matches_rows_and_rejects_leakage(self):
        fold = {
            "train_subjects": ["subj01"], "val_subjects": ["subj02"], "test_subjects": ["subj03"],
            "train_n": 2, "val_n": 1, "test_n": 2,
        }
        published = ["s01", "s02", "s03", "s01", "s03"]
        rows = row_partition("DEAP", published, fold)
        np.testing.assert_array_equal(rows["train"], [0, 3])
        np.testing.assert_array_equal(rows["val"], [1])
        np.testing.assert_array_equal(rows["test"], [2, 4])
        for mutated in (
            dict(fold, val_subjects=["subj01"]),
            dict(fold, train_subjects=["subj01", "subj01"]),
            dict(fold, test_subjects=["subj04"]),
            dict(fold, test_n=1),
        ):
            with self.assertRaises(ValueError):
                row_partition("DEAP", published, mutated)

    def test_actual_split_manifest_has_only_identity_fields(self):
        manifest = json.loads((ROOT / "split_manifest.json").read_text())
        self.assertEqual(set(manifest["targets"]), set(TARGETS))
        allowed = {"fold", "split_seed", "train_subjects", "val_subjects", "test_subjects", "train_n", "val_n", "test_n"}
        for item in manifest["targets"].values():
            self.assertEqual(len(item["sources"]), 4)
            self.assertEqual(len(item["folds"]), 6)
            for index, fold in enumerate(item["folds"]):
                self.assertEqual(set(fold), allowed)
                self.assertEqual(fold["split_seed"], 42 + index)
                groups = [set(fold[f"{part}_subjects"]) for part in ("train", "val", "test")]
                self.assertFalse(groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])

    def test_reve_geometry_uses_official_config_and_unfold(self):
        config = json.loads((ROOT / "vendor/reve/config.json").read_text())
        actual = token_shape(config)
        patches = torch.zeros(1, 60, 2000).unfold(2, config["patch_size"], config["patch_size"] - config["patch_overlap"])
        self.assertEqual(actual, (60, patches.shape[2], config["embed_dim"]))
        self.assertEqual(actual, (60, 11, 512))
        self.assertEqual(math.prod(actual), 337920)
        for invalid in (dict(config, patch_overlap=200), dict(config, patch_size=2001), dict(config, embed_dim=0)):
            with self.assertRaises(ValueError):
                token_shape(invalid)


class PairingTests(unittest.TestCase):
    def make_builder(self, **changed):
        # Two subjects x two sessions x two trials x two row-ordered segments.
        subjects, sessions, trials = [], [], []
        for subject in ("left", "right"):
            for session in ("1", "2"):
                for trial in (0, 1):
                    for _ in range(2):
                        subjects.append(subject); sessions.append(session); trials.append(trial)
        values = dict(source="SEEDIV", target="SEED", subject_ids=np.array(subjects), session_ids=np.array(sessions), trial_indices=np.array(trials))
        values.update(changed)
        return StimulusBatchBuilder(**values)

    def test_pair_pools_equal_historical_builder(self):
        builder = self.make_builder()
        historical = TrialAlignedISABatchBuilder(subject_ids=builder.subjects, session_ids=builder.sessions, trial_indices=builder.trials)
        self.assertEqual(builder.diagnostics()["eligible_aligned_pairs"], 8)
        self.assertEqual(builder.diagnostics()["cross_subject_stimulus_groups"], 4)
        for actual, expected in zip(builder.reference.pair_pools, historical.pair_pools, strict=True):
            np.testing.assert_array_equal(actual, expected)
        for seed in (42, 43, 100):
            actual = builder.sample_batch(batch_size=64, rng=np.random.default_rng(seed))
            expected = historical.sample_batch(batch_size=64, rng=np.random.default_rng(seed))
            torch.testing.assert_close(actual, expected)
            self.assertTrue(np.all(builder.subjects[actual[:32]] != builder.subjects[actual[32:]]))
            np.testing.assert_array_equal(builder.trials[actual[:32]], builder.trials[actual[32:]])
            # The two sides preserve the same within-trial segment offset.
            np.testing.assert_array_equal(actual[:32].numpy() % 2, actual[32:].numpy() % 2)

    def test_unpairable_source_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_builder(subject_ids=np.array(["same"] * 16))

    def test_target_and_missing_or_fractional_metadata_rejected(self):
        for changed in (
            {"source": "SEED"}, {"source": "extra"}, {"session_ids": None},
            {"subject_ids": np.array([["a"]] * 16)},
            {"trial_indices": np.array([0.9] * 16)},
            {"trial_indices": np.array([0, 1])},
        ):
            with self.assertRaises(ValueError):
                self.make_builder(**changed)

    def test_odd_and_too_small_contrastive_batches_rejected(self):
        builder = self.make_builder()
        for batch in (0, 2, 3, 63, 64.0):
            with self.assertRaises(ValueError):
                builder.sample_batch(batch_size=batch, rng=np.random.default_rng(42))


class LossTests(unittest.TestCase):
    def features(self, seed=42):
        generator = torch.Generator().manual_seed(seed)
        return torch.randn(8, 2, 2, 3, generator=generator, dtype=torch.float64, requires_grad=True)

    def test_loss_logits_and_gradient_equal_historical_implementation(self):
        tokens = self.features()
        features = flatten_normalize(tokens)
        actual, logits, labels = paired_info_nce(features, temperature=0.1)
        historical = SimCLRLoss(0.1)
        old_logits, old_labels = historical.info_nce_loss(features)
        expected = F.cross_entropy(old_logits, old_labels)
        torch.testing.assert_close(logits, old_logits, rtol=1e-12, atol=1e-12)
        torch.testing.assert_close(labels, old_labels)
        torch.testing.assert_close(actual, expected, rtol=1e-12, atol=1e-12)
        actual_gradient = torch.autograd.grad(actual, tokens, retain_graph=True)[0]
        expected_gradient = torch.autograd.grad(expected, tokens)[0]
        torch.testing.assert_close(actual_gradient, expected_gradient, rtol=1e-11, atol=1e-11)
        self.assertTrue(torch.isfinite(actual_gradient).all())
        self.assertGreater(float(actual_gradient.norm()), 0)

    def test_independent_formula_and_numerical_gradient(self):
        tokens = self.features(17)
        features = flatten_normalize(tokens)
        actual, _, _ = paired_info_nce(features, temperature=0.1)
        terms = []
        for anchor in range(8):
            positive = (anchor + 4) % 8
            other = [index for index in range(8) if index != anchor]
            terms.append(torch.logsumexp(features[anchor] @ features[other].T / 0.1, dim=0) - features[anchor] @ features[positive] / 0.1)
        torch.testing.assert_close(actual, torch.stack(terms).mean(), rtol=1e-12, atol=1e-12)
        small = torch.randn(4, 1, 1, 2, generator=torch.Generator().manual_seed(3), dtype=torch.float64, requires_grad=True)
        self.assertTrue(torch.autograd.gradcheck(lambda t: paired_info_nce(flatten_normalize(t), temperature=0.1)[0], (small,), eps=1e-6, atol=1e-5))

    def test_pair_order_changes_loss_and_true_negative_count(self):
        left = torch.eye(4, dtype=torch.float64).reshape(4, 1, 1, 4)
        tokens = torch.cat((left, left))
        aligned, logits, _ = paired_info_nce(flatten_normalize(tokens), temperature=0.1)
        reordered = torch.cat((left, left.roll(1, dims=0)))
        mismatched, _, _ = paired_info_nce(flatten_normalize(reordered), temperature=0.1)
        self.assertLess(float(aligned), float(mismatched))
        self.assertEqual(tuple(logits.shape), (8, 7))  # six negatives + one positive
        torch.testing.assert_close(aligned, torch.tensor(math.log1p(6 * math.exp(-10)), dtype=torch.float64))

    def test_nonfinite_zero_odd_shape_and_bad_temperature_fail(self):
        for tokens in (torch.zeros(8, 2, 2, 3), torch.full((8, 2, 2, 3), float("nan")), torch.ones(8, 3)):
            with self.assertRaises(ValueError):
                flatten_normalize(tokens)
        valid = flatten_normalize(self.features())
        for features, temperature in ((valid[:7], 0.1), (valid[:2], 0.1), (valid * 2, 0.1), (valid, 0.0), (valid, 0.5), (valid, float("nan"))):
            with self.assertRaises(ValueError):
                paired_info_nce(features, temperature=temperature)


def main():
    torch.set_num_threads(1)
    start = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    paths = ["data_contract.py", "isa_builder.py", "isa_loss.py", "reference_core.py", "split_manifest.json", "vendor/reve/config.json", "validate_core.py"]
    report = {
        "schema_version": "1.0", "action_id": "reve_isa_tione_20261008-engineer-r0-7",
        "passed": result.wasSuccessful(), "tests_run": result.testsRun,
        "failures": [name.id() for name, _ in result.failures],
        "errors": [name.id() for name, _ in result.errors],
        "elapsed_seconds": time.monotonic() - start,
        "scope": "Completed bootstrap metadata, frozen split, historical pair builder and InfoNCE core only",
        "evidence_level": "E0_smoke",
        "controlled_inputs": True, "research_observations": False,
        "official_weights_loaded": False, "real_data_opened": False,
        "cuda_smoke_completed": False, "scheduler_adapter_certified": False,
        "package_complete": False, "test_evaluations": 0,
        "versions": {"torch": torch.__version__, "numpy": np.__version__},
        "tested_artifacts": [{"path": str(ROOT / name), "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()} for name in paths],
    }
    (ROOT / "core_validation_r0_7.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
