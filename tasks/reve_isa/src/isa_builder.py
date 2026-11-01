"""Checked historical stimulus pairing, bound to a single LODO source.

The reference builder is extracted verbatim from the indexed dense ISA source.
Sampling preserves that source's subject-pair pools and row-offset alignment.
"""
from __future__ import annotations

import numpy as np
from data_contract import checked_session_ids, lodo_sources
from reference_core import TrialAlignedISABatchBuilder


class StimulusBatchBuilder:
    def __init__(self, *, source, target, subject_ids, session_ids, trial_indices):
        if source not in lodo_sources(target, posttrain_split="all"):
            raise ValueError("Source must be one of the five non-target datasets")
        self.source, self.target = source, target
        self.subjects = np.asarray(subject_ids).astype(str)
        self.sessions = checked_session_ids(source, self.subjects, session_ids)
        trials = np.asarray(trial_indices)
        if self.subjects.ndim != 1 or not self.subjects.size or trials.shape != self.subjects.shape:
            raise ValueError("Require nonempty aligned subject/trial arrays")
        if not np.issubdtype(trials.dtype, np.integer):
            raise ValueError("Trial indices must be verified integers, not truncated floats")
        if any(not value for value in self.subjects):
            raise ValueError("Empty subject identity")
        self.trials = trials.astype(np.int64, copy=True)
        self.reference = TrialAlignedISABatchBuilder(
            subject_ids=self.subjects, session_ids=self.sessions, trial_indices=self.trials
        )
        if not self.reference.pair_pools:
            raise ValueError("No cross-subject same-stimulus pairs; no fallback permitted")
        for pool in self.reference.pair_pools:
            self._check(pool[:, 0], pool[:, 1])

    def _check(self, left, right):
        if np.any(self.subjects[left] == self.subjects[right]):
            raise ValueError("Positive pair has the same subject")
        if np.any(self.trials[left] != self.trials[right]):
            raise ValueError("Positive pair has different stimuli")
        if self.reference.uses_session_key and np.any(self.sessions[left] != self.sessions[right]):
            raise ValueError("Positive pair has different protocol sessions")

    def sample_batch(self, *, batch_size: int, rng: np.random.Generator):
        if type(batch_size) is not int or batch_size < 4 or batch_size % 2:
            raise ValueError("Contrastive batch must be an even integer with negative examples")
        rows = self.reference.sample_batch(batch_size=batch_size, rng=rng)
        if rows is None or rows.numel() != batch_size:
            raise ValueError("Incomplete contrastive batch")
        half = batch_size // 2
        self._check(rows[:half].numpy(), rows[half:].numpy())
        return rows

    def diagnostics(self):
        return {
            "source": self.source,
            "target": self.target,
            "stimulus_key": self.reference.key_description,
            "cross_subject_stimulus_groups": self.reference.stimulus_group_count,
            "subject_pair_pools": len(self.reference.pair_pools),
            "eligible_aligned_pairs": sum(len(pool) for pool in self.reference.pair_pools),
            "pair_pool_sizes": [len(pool) for pool in self.reference.pair_pools],
            "short_pool_sampling": "with replacement, as in the historical builder; record duplicate rows",
        }
