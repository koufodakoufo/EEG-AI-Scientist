"""Verbatim definitions extracted from indexed historical ISA source.

Source SHA256: 51d6e44bef5527fa064a9babb8d8ee297ebe79e15a91c95f68806819b42ab1a2
No historical entrypoint or external dependencies are executed.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any
import numpy as np
import torch
from torch import nn

def _top_k_accuracy(logits: torch.Tensor, labels: torch.Tensor, ks: list[int] | None = None) -> list[float]:
    """PyTorch-only copy of mdJPT ``src.utils.top_k_accuracy``."""
    if ks is None:
        ks = [1, 5]
    n_columns = int(logits.shape[1])
    batch_size = labels.size(0)
    if batch_size == 0 or n_columns == 0:
        return [0.0 for _k in ks]
    max_k = min(max(ks), n_columns)
    _, top_preds = logits.topk(max_k, dim=1, largest=True, sorted=True)
    top_preds = top_preds.t()
    correct = top_preds.eq(labels.view(1, -1).expand_as(top_preds))
    acc_list = []
    for k in ks:
        clipped_k = min(int(k), n_columns)
        correct_k = correct[:clipped_k].reshape(-1).float().sum(0, keepdim=True)
        accuracy = correct_k.mul_(100.0 / batch_size).item()
        acc_list.append(accuracy)
    return acc_list

class SimCLRLoss(nn.Module):
    """mdJPT SimCLR/InfoNCE loss.

    The batch is expected to be ordered as ``[view_a; view_b]``.  For a batch of
    size ``2 * bs``, row ``i`` is positive with row ``i + bs``.
    """

    def __init__(self, temperature: float):
        super().__init__()
        self.temperature = temperature
        self.CEL = torch.nn.CrossEntropyLoss()
        self.device = torch.device("cpu")

    def to(self, device: torch.device | str) -> "SimCLRLoss":
        self.device = torch.device(device)
        self.CEL = self.CEL.to(device)
        return self

    def info_nce_loss(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        device = self.device
        bs = int(features.shape[0] // 2)
        labels = torch.cat([torch.arange(bs) for _i in range(2)], dim=0)
        labels = (labels.unsqueeze(0) == labels.unsqueeze(1)).float()
        labels = labels.to(device)

        similarity_matrix = torch.matmul(features, features.T)

        mask = torch.eye(labels.shape[0], dtype=torch.bool).to(device)
        labels = labels[~mask].view(labels.shape[0], -1)
        similarity_matrix = similarity_matrix[~mask].view(similarity_matrix.shape[0], -1)

        positives = similarity_matrix[labels.bool()].view(labels.shape[0], -1)
        negatives = similarity_matrix[~labels.bool()].view(similarity_matrix.shape[0], -1)

        logits = torch.cat([negatives, positives], dim=1)
        labels = torch.ones(logits.shape[0], dtype=torch.long) * (logits.shape[1] - 1)
        labels = labels.to(device)

        logits = logits / self.temperature
        return logits, labels

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, list[float]]:
        self.to(features.device)
        logits, labels = self.info_nce_loss(features)
        loss = self.CEL(logits, labels)
        acc_1, acc_5 = _top_k_accuracy(logits, labels)
        return loss, logits, labels, [acc_1, acc_5]

class TrialAlignedISABatchBuilder:
    """Build mdJPT-style cross-subject same-stimulus batches for one source dataset."""

    def __init__(
        self,
        *,
        subject_ids: np.ndarray,
        session_ids: np.ndarray | None,
        trial_indices: np.ndarray,
    ) -> None:
        subjects = np.asarray(subject_ids).astype(str)
        trials = np.asarray(trial_indices, dtype=np.int64)
        sessions = None if session_ids is None else np.asarray(session_ids).astype(str)
        if subjects.shape[0] != trials.shape[0] or (
            sessions is not None and sessions.shape[0] != subjects.shape[0]
        ):
            raise ValueError(
                "subject_ids, session_ids, and trial_indices must have the same length"
            )
        self.uses_session_key = self._has_shared_session_axis(subjects, sessions)
        self.stimulus_group_count = self._count_cross_subject_stimulus_groups(
            subjects,
            sessions,
            trials,
            use_session_key=self.uses_session_key,
        )
        self.pair_pools = self._build_pair_pools(
            subjects,
            sessions,
            trials,
            use_session_key=self.uses_session_key,
        )

    @staticmethod
    def _has_shared_session_axis(subjects: np.ndarray, sessions: np.ndarray | None) -> bool:
        if sessions is None:
            return False
        by_session_subjects: dict[str, set[str]] = defaultdict(set)
        for subject, session in zip(subjects, sessions, strict=True):
            by_session_subjects[str(session)].add(str(subject))
        return (
            max((len(session_subjects) for session_subjects in by_session_subjects.values()), default=0)
            >= 2
        )

    @staticmethod
    def _stimulus_key(
        *,
        session: str | None,
        trial_index: int,
        use_session_key: bool,
    ) -> tuple[Any, ...]:
        if use_session_key:
            return (str(session), int(trial_index))
        return (int(trial_index),)

    @classmethod
    def _build_stimulus_subject_index(
        cls,
        subjects: np.ndarray,
        sessions: np.ndarray | None,
        trials: np.ndarray,
        *,
        use_session_key: bool,
    ) -> dict[tuple[Any, ...], dict[str, list[int]]]:
        by_stimulus_subject: dict[tuple[Any, ...], dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        if use_session_key:
            if sessions is None:
                raise ValueError("session_ids are required when use_session_key=True")
            iterator = zip(subjects, sessions, trials, strict=True)
            for local_idx, (subject, session, trial) in enumerate(iterator):
                key = cls._stimulus_key(
                    session=str(session),
                    trial_index=int(trial),
                    use_session_key=True,
                )
                by_stimulus_subject[key][str(subject)].append(int(local_idx))
        else:
            for local_idx, (subject, trial) in enumerate(zip(subjects, trials, strict=True)):
                key = cls._stimulus_key(
                    session=None,
                    trial_index=int(trial),
                    use_session_key=False,
                )
                by_stimulus_subject[key][str(subject)].append(int(local_idx))
        return by_stimulus_subject

    @classmethod
    def _count_cross_subject_stimulus_groups(
        cls,
        subjects: np.ndarray,
        sessions: np.ndarray | None,
        trials: np.ndarray,
        *,
        use_session_key: bool,
    ) -> int:
        by_stimulus_subject = cls._build_stimulus_subject_index(
            subjects,
            sessions,
            trials,
            use_session_key=use_session_key,
        )
        return sum(
            1
            for subject_to_indices in by_stimulus_subject.values()
            if len(subject_to_indices) >= 2
        )

    @staticmethod
    def _build_pair_pools(
        subjects: np.ndarray,
        sessions: np.ndarray | None,
        trials: np.ndarray,
        *,
        use_session_key: bool,
    ) -> list[np.ndarray]:
        by_stimulus_subject = TrialAlignedISABatchBuilder._build_stimulus_subject_index(
            subjects,
            sessions,
            trials,
            use_session_key=use_session_key,
        )
        by_subject_pair: dict[tuple[Any, ...], list[tuple[int, int]]] = defaultdict(list)
        for stimulus_key, subject_to_indices in by_stimulus_subject.items():
            trial_subjects = sorted(subject_to_indices)
            for left_pos, left_subject in enumerate(trial_subjects):
                left_indices = sorted(subject_to_indices[left_subject])
                for right_subject in trial_subjects[left_pos + 1 :]:
                    right_indices = sorted(subject_to_indices[right_subject])
                    n_matched = min(len(left_indices), len(right_indices))
                    if n_matched <= 0:
                        continue
                    key = (*stimulus_key[:-1], left_subject, right_subject)
                    by_subject_pair[key].extend(
                        (left_indices[offset], right_indices[offset])
                        for offset in range(n_matched)
                    )

        return [
            np.asarray(pairs, dtype=np.int64)
            for _key, pairs in sorted(by_subject_pair.items())
            if pairs
        ]

    @property
    def n_subject_pair_pools(self) -> int:
        return len(self.pair_pools)

    @property
    def n_subject_session_pairs(self) -> int:
        return self.n_subject_pair_pools

    @property
    def key_description(self) -> str:
        return "(session_id, trial_index)" if self.uses_session_key else "(trial_index)"

    def sample_batch(
        self,
        *,
        batch_size: int,
        rng: np.random.Generator,
    ) -> torch.Tensor | None:
        half = int(batch_size) // 2
        if half <= 0 or not self.pair_pools:
            return None
        pool = self.pair_pools[int(rng.integers(0, len(self.pair_pools)))]
        replace = pool.shape[0] < half
        selected = rng.choice(pool.shape[0], size=half, replace=replace)
        pairs = pool[selected]
        batch = np.concatenate([pairs[:, 0], pairs[:, 1]]).astype(np.int64, copy=False)
        return torch.from_numpy(batch)
