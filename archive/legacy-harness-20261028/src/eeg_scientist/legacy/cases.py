"""Synthetic EEG-style cases, global identifiers, and the public view."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from ..schema import BaselineBundle, CaseSpec, FeatureDataset, PublicCase

ALLOWED_TOOLS = [
    "split_audit",
    "trial_random_labels",
    "trial_shuffle_within_subject",
    "window_random_labels",
    "metadata_only",
]

DEFAULT_PARAMS: dict[str, dict[str, float]] = {
    "T": {"noise_std": 0.5, "trial_scale": 4.0},
    "G": {"noise_std": 1.0, "task_scale": 2.2},
    "D": {"noise_std": 0.5, "task_scale": 2.5, "subject_scale": 0.5},
    "N": {"noise_std": 1.0},
}


def _unit_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def generate_case(spec: CaseSpec) -> FeatureDataset:
    """Generate a deterministic case from its private seed specification."""
    params = dict(DEFAULT_PARAMS[spec.family])
    params.update(spec.params)
    noise_std = float(params.get("noise_std", 1.0))

    data_rng = np.random.default_rng(spec.data_seed)
    label_rng = np.random.default_rng(spec.label_seed)

    subject_ids: list[str] = []
    session_uids: list[str] = []
    trial_uids: list[str] = []
    sample_ids: list[str] = []
    labels: list[int] = []
    subject_index: list[int] = []
    session_index: list[int] = []
    trial_index: list[int] = []
    trial_order: list[str] = []
    trial_labels: list[int] = []
    trial_to_pos: dict[str, int] = {}

    for subject in range(spec.n_subjects):
        for session in range(spec.n_sessions):
            session_uid = f"sub-{subject:02d}_ses-{session:02d}"
            session_labels = np.array([-1] * (spec.n_trials // 2) + [1] * (spec.n_trials // 2), dtype=np.int64)
            label_rng.shuffle(session_labels)
            for trial in range(spec.n_trials):
                trial_uid = f"{session_uid}_trial-{trial:02d}"
                trial_to_pos[trial_uid] = len(trial_order)
                trial_order.append(trial_uid)
                trial_labels.append(int(session_labels[trial]))
                for window in range(spec.n_windows):
                    sample_ids.append(f"{trial_uid}_win-{window:02d}")
                    subject_ids.append(f"sub-{subject:02d}")
                    session_uids.append(session_uid)
                    trial_uids.append(trial_uid)
                    labels.append(int(session_labels[trial]))
                    subject_index.append(subject)
                    session_index.append(subject * spec.n_sessions + session)
                    trial_index.append(trial_to_pos[trial_uid])

    n_rows = len(sample_ids)
    n_trials = len(trial_order)
    x = data_rng.normal(0.0, noise_std, size=(n_rows, spec.n_features)).astype(np.float64)
    y = np.asarray(labels, dtype=np.int64)
    subject_idx = np.asarray(subject_index, dtype=np.int64)
    trial_pos = np.asarray(trial_index, dtype=np.int64)
    trial_label = np.asarray(trial_labels, dtype=np.int64)

    if spec.family == "T":
        signature = _unit_rows(data_rng.normal(size=(n_trials, spec.n_features)))
        x += float(params["trial_scale"]) * trial_label[trial_pos, None] * signature[trial_pos]
    elif spec.family == "G":
        direction = _unit_rows(data_rng.normal(size=spec.n_features))
        x += float(params["task_scale"]) * y[:, None] * direction[None, :]
    elif spec.family == "D":
        directions = _unit_rows(data_rng.normal(size=(spec.n_subjects, spec.n_features)))
        signs = data_rng.choice(np.array([-1.0, 1.0]), size=spec.n_subjects)
        subject_features = _unit_rows(data_rng.normal(size=(spec.n_subjects, spec.n_features)))
        x += (
            float(params["task_scale"])
            * y[:, None]
            * signs[subject_idx, None]
            * directions[subject_idx, :]
        )
        x += float(params["subject_scale"]) * subject_features[subject_idx, :]
    elif spec.family == "N":
        pass
    else:  # pragma: no cover - Literal validation protects this path
        raise ValueError(f"unknown family {spec.family}")

    feature_names = [f"f{index:02d}" for index in range(spec.n_features)]
    return FeatureDataset(
        x=x,
        y=y,
        sample_ids=sample_ids,
        subject_ids=subject_ids,
        session_uids=session_uids,
        trial_uids=trial_uids,
        feature_names=feature_names,
        case_id=spec.case_id,
    )


def hash_dataset(dataset: FeatureDataset) -> str:
    digest = hashlib.sha256()
    digest.update(dataset.x.astype("<f8").tobytes(order="C"))
    digest.update(dataset.y.astype("<i8").tobytes(order="C"))
    for column in (
        dataset.sample_ids,
        dataset.subject_ids,
        dataset.session_uids,
        dataset.trial_uids,
        dataset.feature_names,
    ):
        digest.update(json.dumps(column, separators=(",", ":")).encode("utf-8"))
    digest.update(dataset.case_id.encode("utf-8"))
    return digest.hexdigest()


def build_public_case(dataset: FeatureDataset, baseline: BaselineBundle) -> PublicCase:
    """Create the only case object the Scientist may see."""
    structure = {
        "n_rows": len(dataset.sample_ids),
        "n_subjects": len(set(dataset.subject_ids)),
        "n_sessions": len(set(dataset.session_uids)),
        "n_trials": len(set(dataset.trial_uids)),
        "n_features": len(dataset.feature_names),
        "windows_per_trial": len(dataset.sample_ids) // len(set(dataset.trial_uids)),
        "n_positive_rows": int((dataset.y == 1).sum()),
        "n_negative_rows": int((dataset.y == -1).sum()),
        "n_positive_trials": len({uid for uid, label in zip(dataset.trial_uids, dataset.y.tolist()) if label == 1}),
        "n_negative_trials": len({uid for uid, label in zip(dataset.trial_uids, dataset.y.tolist()) if label == -1}),
    }
    audit_summary: dict[str, object] = {}
    for level, audit in baseline.audits.items():
        audit_summary[level] = {
            "counts": audit.get("counts", {}),
            "overlap": audit.get("overlap", {}),
            "label_counts": audit.get("label_counts", {}),
            "n_groups": audit.get("n_groups", {}),
            "invalid_reason": audit.get("invalid_reason"),
        }
    return PublicCase(
        case_id=dataset.case_id,
        data_source_type=dataset.data_source_type,
        structure_summary=structure,
        baseline=dict(baseline.metrics),
        audit_summary=audit_summary,
        allowed_tools=list(ALLOWED_TOOLS),
        data_hash=baseline.data_hash,
    )


def load_case_specs(path: Path) -> dict[str, CaseSpec]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = raw.get("cases", raw if isinstance(raw, list) else [])
    specs: dict[str, CaseSpec] = {}
    for item in cases:
        spec = CaseSpec.model_validate(item)
        if spec.case_id in specs:
            raise ValueError(f"duplicate case_id {spec.case_id}")
        specs[spec.case_id] = spec
    return specs


def write_case_specs(path: Path, specs: list[CaseSpec], generator_version: str = "1.0") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generator_version": generator_version, "cases": [spec.model_dump(mode="json") for spec in specs]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
