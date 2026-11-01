"""Fixed metadata semantics for the six-dataset REVE ISA migration.

No signal loading, training, filesystem writes, or released-label remapping.
The subject-ID conversions match the inspected historical downstream runner.
"""
from __future__ import annotations

import numpy as np

TARGETS = ("SEED", "SEEDIV", "SEED_V", "SEED_VII", "FACED", "DEAP")
RELEASES = {
    "SEED": ("SEED/derived/lance_mdjpt60_badch", 14895, 15, 3, 4),
    "SEEDIV": ("SEED-IV_10s_v1/derived/lance_mdjpt60_badch", 14655, 15, 4, 4),
    "SEED_V": ("SEED-V_10s_v1/derived/lance_mdjpt60_badch", 11424, 16, 5, 4),
    "SEED_VII": ("SEED-VII/derived/lance_mdjpt60_badch", 27340, 20, 7, 5),
    "FACED": ("FACED/derived/lance_mdjpt60_badch", 10332, 123, 9, 31),
    "DEAP": ("DEAP/derived/lance_mdjpt60_badch", 7680, 32, 2, 8),
}
FOLD_SEEDS = (42, 43, 44, 45, 46, 47)


def lodo_sources(target: str, *, posttrain_split: str) -> tuple[str, ...]:
    if target not in TARGETS or posttrain_split != "all":
        raise ValueError("Require one of six targets and explicit posttrain_split=all")
    return tuple(name for name in TARGETS if name != target)


def canonical_subject_ids(target: str, subject_ids) -> np.ndarray:
    if target not in TARGETS:
        raise ValueError("Unknown dataset")
    values = np.asarray(subject_ids).astype(str)
    if values.ndim != 1 or any(not value for value in values):
        raise ValueError("Require one-dimensional nonempty subject IDs")
    if target == "DEAP":
        result = np.asarray([f"subj{value.removeprefix('s')}" for value in values])
    elif target in {"SEEDIV", "SEED_VII"}:
        result = np.asarray([f"subj{int(value):02d}" for value in values])
    elif target == "SEED_V":
        result = np.asarray([str(int(value)) for value in values])
    else:
        result = values.copy()
    # Conversions may repeat within a subject, but cannot merge distinct IDs.
    if len(set(values)) != len(set(result)):
        raise ValueError("Subject ID conversion is not injective")
    return result


def checked_session_ids(target: str, subject_ids, session_ids) -> np.ndarray:
    """Preserve released IDs, including verified all-empty FACED/DEAP markers.

    The hash-verified selected FACED/DEAP indices contain present string columns
    with only ''. Historical loaders preserve them and the ISA builder groups
    by ('', trial_index). This exception is not a missing-column fallback.
    """
    if target not in TARGETS or session_ids is None:
        raise ValueError("Require known dataset and released session metadata")
    subjects = np.asarray(subject_ids)
    raw_sessions = np.asarray(session_ids, dtype=object)
    if subjects.ndim != 1 or raw_sessions.shape != subjects.shape or not subjects.size:
        raise ValueError("Subject/session arrays must be nonempty and row-aligned")
    if any(value is None or (isinstance(value, (float, np.floating)) and not np.isfinite(value))
           for value in raw_sessions):
        raise ValueError("Null or unknown missing session identity")
    sessions = raw_sessions.astype(str)
    if any(value and not value.strip() for value in sessions):
        raise ValueError("Whitespace-only session identity is not a released empty marker")
    empty = sessions == ""
    if np.any(empty) and not (target in {"FACED", "DEAP"} and np.all(empty)):
        raise ValueError("Mixed or unsupported empty session identity")
    return sessions.copy()


def protocol_session_ids(target: str, subject_ids, session_ids) -> np.ndarray:
    sessions = checked_session_ids(target, subject_ids, session_ids)
    subjects = np.asarray(subject_ids).astype(str)
    if target != "SEED":
        return sessions.copy()
    normalized = np.empty(sessions.shape, dtype=object)
    for subject in sorted(np.unique(subjects).tolist()):
        mask = subjects == subject
        unique_sessions = sorted(np.unique(sessions[mask]).tolist())
        if len(unique_sessions) != 3:
            raise ValueError("SEED requires exactly three sessions per subject")
        mapping = {session: str(index + 1) for index, session in enumerate(unique_sessions)}
        normalized[mask] = [mapping[session] for session in sessions[mask]]
    return normalized.astype(str)


def row_partition(target: str, published_subject_ids, fold: dict) -> dict[str, np.ndarray]:
    subjects = canonical_subject_ids(target, published_subject_ids)
    groups = {part: list(fold[f"{part}_subjects"]) for part in ("train", "val", "test")}
    sets = {part: set(ids) for part, ids in groups.items()}
    if any(len(sets[part]) != len(groups[part]) or not sets[part] for part in groups):
        raise ValueError("Duplicate or empty split subject IDs")
    if any(sets[a] & sets[b] for a, b in (("train", "val"), ("train", "test"), ("val", "test"))):
        raise ValueError("Overlapping train/validation/test subjects")
    if set(subjects) != set.union(*sets.values()):
        raise ValueError("Frozen split does not exactly cover released subjects")
    rows = {part: np.flatnonzero(np.isin(subjects, ids)) for part, ids in groups.items()}
    if any(len(rows[part]) != int(fold[f"{part}_n"]) for part in groups):
        raise ValueError("Released rows differ from historical split counts")
    return rows


def token_shape(config: dict, *, channels: int = 60, samples: int = 2000) -> tuple[int, int, int]:
    patch, overlap, embedding = (int(config[key]) for key in ("patch_size", "patch_overlap", "embed_dim"))
    if not (channels > 0 and samples >= patch > overlap >= 0 and embedding > 0):
        raise ValueError("Invalid REVE patch geometry")
    return channels, 1 + (samples - patch) // (patch - overlap), embedding
