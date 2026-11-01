"""Read-only released Lance data, checked metadata and run-scoped signal caches."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid

import numpy as np

from artifact_io import atomic_json, file_lock, fingerprint, read_json, sha256_file
from data_contract import RELEASES, protocol_session_ids, row_partition

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path("/mnt/omni-eeg-01/downstream_preprocess/wzf_dataset")


def released_source_attributes(root, audit, channels):
    """Read only the published sibling metadata bound by the export config hash."""
    historical = Path(audit["source_zarr"])
    # Preserve the audited package/Zarr basenames after directory relocation.
    # The historical source path is provenance, never a filesystem fallback.
    attrs_path = root.parent / historical.parent.name / historical.name / ".zattrs"
    if not attrs_path.exists() and not attrs_path.is_symlink():
        return {}, None
    if (not root.resolve().is_relative_to(DATA_ROOT.resolve())
            or not attrs_path.resolve().is_relative_to(root.parent.resolve())
            or any(path.is_symlink() for path in (attrs_path, attrs_path.parent, attrs_path.parent.parent))
            or not attrs_path.is_file()):
        raise ValueError("Released source attribute path escapes its approved package")
    attrs = read_json(attrs_path)
    # Exact payload of emotion_zarr.lance_export._config_hash: the audit stores
    # its original resolved source path and tree hash, so no full Zarr scan is needed.
    payload = {"schema": audit["conversion_schema"], "protocol": audit["protocol"],
               "release_name": audit["dataset"], "source_zarr": audit["source_zarr"],
               "source_zarr_tree_sha256": audit["source_zarr_tree_sha256"],
               "source_attrs": attrs, "signal_shape": audit["signal_shape"],
               "row_policy": audit["row_policy"], "duplicate_policy": audit["duplicate_policy"],
               "target_channels": channels}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != audit["preprocess_config_hash"]:
        raise ValueError("Released source attributes differ from audited exporter configuration")
    return attrs, attrs_path


def checked_trial_indices(values):
    """These six releases use integer trial_id; arbitrary vocabulary fallback is forbidden."""
    if any(value is None for value in values):
        raise ValueError("Null stimulus/trial identity")
    result = []
    for value in values:
        if isinstance(value, (float, np.floating)) and not float(value).is_integer():
            raise ValueError("Fractional stimulus identity")
        try:
            parsed = int(str(value))
        except ValueError as exc:
            raise ValueError("Release trial IDs must be the verified integer identities") from exc
        result.append(parsed)
    return np.asarray(result, dtype=np.int64)


def check_metadata_table(target, columns, *, expected_rows, expected_subjects, expected_classes):
    required = {"sample_id", "subject_id", "label_id", "channel_names_json", "global_idx", "session_id", "trial_id"}
    if not required <= set(columns):
        raise ValueError(f"Missing metadata: {sorted(required-set(columns))}")
    if any(len(values) != expected_rows for values in columns.values()):
        raise ValueError("Metadata columns are not row aligned")
    for name in required:
        if any(value is None for value in columns[name]):
            raise ValueError(f"Null release metadata: {name}")
    if not np.array_equal(np.asarray(columns["global_idx"]), np.arange(expected_rows)):
        raise ValueError("global_idx is not contiguous and ordered")
    if len(set(map(str, columns["sample_id"]))) != expected_rows:
        raise ValueError("Duplicate released sample identities")
    subjects = np.asarray(columns["subject_id"]).astype(str)
    if len(set(subjects)) != expected_subjects:
        raise ValueError("Released subject count changed")
    raw_labels = np.asarray(columns["label_id"])
    if not np.issubdtype(raw_labels.dtype, np.integer):
        raise ValueError("Released labels are not integer IDs")
    labels = raw_labels.astype(np.int64)
    if set(labels.tolist()) != set(range(expected_classes)):
        raise ValueError("Released label vocabulary changed")
    ordered_channels = [json.loads(value) for value in columns["channel_names_json"]]
    if any(names != ordered_channels[0] for names in ordered_channels):
        raise ValueError("Within-release channel order varies")
    channels = ordered_channels[0]
    if len(channels) != 60 or len(set(channels)) != 60:
        raise ValueError("Incomplete or duplicated montage")
    sessions = protocol_session_ids(target, subjects, columns["session_id"])
    trials = checked_trial_indices(columns["trial_id"])
    if "trial_index" in columns and not np.array_equal(checked_trial_indices(columns["trial_index"]), trials):
        raise ValueError("trial_index disagrees with released trial_id")
    if target == "DEAP":
        if "aux_valence" not in columns:
            raise ValueError("DEAP valence metadata required to verify the published threshold")
        valence = np.asarray(columns["aux_valence"], dtype=np.float64)
        if not np.isfinite(valence).all() or not np.array_equal((valence >= 5).astype(np.int64), labels):
            raise ValueError("DEAP labels disagree with released valence>=5 semantics")
        if np.count_nonzero(valence == 5) != 96:
            raise ValueError("DEAP threshold boundary count changed")
    return subjects, labels, channels, sessions, trials


@dataclass
class Release:
    target: str
    root: Path
    dataset: object
    subjects: np.ndarray
    labels: np.ndarray
    channel_names: list
    sessions: np.ndarray
    trials: np.ndarray
    sample_ids: list
    identity: dict
    signal_cache: object = None

    @classmethod
    def open(cls, target, *, source_root=ROOT):
        import lance
        import pyarrow.parquet as pq
        relative, count, subjects, classes, _ = RELEASES[target]
        root = DATA_ROOT / relative
        references = read_json(Path(source_root) / "release_reference.json")[relative]
        audit_path = root / "conversion_audit.json"
        vocab_path = root / "label_vocab.json"
        for kind, path in (("conversion_audit", audit_path), ("label_vocab", vocab_path)):
            if sha256_file(path) != references[kind]["source"]["sha256"]:
                raise ValueError(f"Released text identity changed: {target}/{kind}")
        audit = read_json(audit_path)
        if audit.get("errors") or audit["rows"] != count or audit["signal_shape"] != [60, 2000]:
            raise ValueError("Release audit/shape/count failed")
        index_path = root / "sample_index.parquet"
        if sha256_file(index_path) != audit["sample_index_sha256"]:
            raise ValueError("Binary sample index differs from conversion audit")
        table = pq.read_table(index_path)
        columns = {name: table[name].to_pylist() for name in table.column_names}
        subject_ids, labels, channels, sessions, trials = check_metadata_table(
            target, columns, expected_rows=count, expected_subjects=subjects, expected_classes=classes)
        # Inspect rate and unit in actual metadata/attributes; never manufacture missing values.
        attrs, attrs_path = released_source_attributes(root, audit, channels)
        attrs_available = attrs_path is not None
        rates = []
        for name in ("sampling_rate", "sample_rate", "sfreq", "fs"):
            if name in columns:
                rates.extend(float(value) for value in columns[name])
            if name in attrs:
                rates.append(float(attrs[name]))
        if not rates or any(rate != 200 for rate in rates):
            raise ValueError("Actual release sampling rate unavailable or differs from 200Hz")
        units = []
        for name in ("signal_unit", "unit", "units"):
            if name in columns:
                units.extend(str(value) for value in columns[name])
            if name in attrs:
                units.append(str(attrs[name]))
        if not units or any(unit not in {"uV", "µV", "μV", "microvolts"} for unit in units):
            raise ValueError("Actual released uV signal unit unavailable or changed")
        paths = sorted(root.glob("*.lance"))
        # Audits preserve the original build location after a release moves.
        # Resolve only its verified basename inside this approved release;
        # never fall back to or follow the historical path.
        if (len(paths) != 1 or paths[0].name != Path(audit["lance_path"]).name
                or not paths[0].is_dir()
                or not root.resolve().is_relative_to(DATA_ROOT.resolve())
                or paths[0].resolve().parent != root.resolve()):
            raise ValueError("Lance dataset identity changed")
        dataset = lance.dataset(str(paths[0]))
        if dataset.count_rows() != count or int(dataset.version) != 1:
            raise ValueError("Lance version or rows changed")
        # Preserve sample identity and label order in the signal store too.
        # mdjpt60_zarr_to_lance_v1 exports index label_id as Lance label;
        # the integer IDs are unchanged. Require all four identity columns.
        compare = {"sample_id": "sample_id", "global_idx": "global_idx",
                   "label": "label_id", "subject_id": "subject_id"}
        if not set(compare) <= set(dataset.schema.names):
            raise ValueError("Lance lacks row/label identity columns")
        observed = dataset.to_table(columns=list(compare))
        for lance_name, index_name in compare.items():
            if observed[lance_name].to_pylist() != columns[index_name]:
                raise ValueError(f"Lance/index row identity differs: {lance_name}/{index_name}")
        identity = {"target": target, "release": relative, "version": 1, "rows": count,
                    "lance_path": str(paths[0]), "audit_lance_path": audit["lance_path"],
                    "sample_index_sha256": audit["sample_index_sha256"],
                    "conversion_audit_sha256": sha256_file(audit_path),
                    "label_vocab_sha256": sha256_file(vocab_path),
                    "source_signal_aggregate_sha256": audit["source_signal_aggregate_sha256"],
                    "source_zarr_attributes_sha256": sha256_file(attrs_path) if attrs_available else None,
                    "channel_names": channels, "signal_shape": [60, 2000], "sampling_rate": 200,
                    "signal_unit": units[0], "label_semantics": read_json(vocab_path),
                    "session_policy": "subject_sorted_date_1_2_3" if target == "SEED" else "preserve",
                    "metadata_columns": list(columns), "duplicate_policy": audit["duplicate_policy"]}
        release = cls(target, root, dataset, subject_ids, labels, channels, sessions, trials,
                      list(map(str, columns["sample_id"])), identity)
        for row, expected in audit["signal_sample_sha256"].items():
            values = release.load_signals(np.asarray([int(row)], dtype=np.int64))
            import hashlib
            if hashlib.sha256(values[0].tobytes()).hexdigest() != expected:
                raise ValueError("Bounded signal hash differs from release audit")
        return release

    def partitions(self, fold):
        rows = row_partition(self.target, self.subjects, fold)
        for part in ("train", "val", "test"):
            if set(self.labels[rows[part]].tolist()) != set(range(RELEASES[self.target][3])):
                raise ValueError(f"{part} split omits a released class")
        return rows

    def load_signals(self, rows):
        rows = np.asarray(rows)
        if rows.ndim != 1 or not np.issubdtype(rows.dtype, np.integer):
            raise ValueError("Require integer signal row indices")
        if len(rows) == 0 or rows.min() < 0 or rows.max() >= len(self.labels):
            raise ValueError("Empty or out-of-range signal selection")
        if self.signal_cache is not None:
            values = np.asarray(self.signal_cache[rows], dtype=np.float32)
        else:
            column = self.dataset.take(rows.tolist(), columns=["signals"])["signals"].combine_chunks()
            values = np.asarray(column.values.to_numpy(zero_copy_only=False), dtype=np.float32).reshape(len(rows), 60, 2000)
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite signal in released store")
        return values

    def preload_signals(self, artifacts, *, deadline):
        """Decode once, under a file lock, without writing inside the release."""
        from artifact_io import check_deadline
        directory = Path(artifacts) / "cache/signals" / fingerprint(self.identity)
        directory.mkdir(parents=True, exist_ok=True)
        path, marker = directory / "signals.npy", directory / "COMPLETE.json"
        with file_lock(directory / "build.lock"):
            if marker.is_file():
                saved = read_json(marker)
                if (saved["identity"] != self.identity or saved["bytes"] != path.stat().st_size
                        or saved.get("mtime_ns") != path.stat().st_mtime_ns):
                    raise ValueError("Signal cache provenance failed")
                cache = np.load(path, mmap_mode="r")
                if cache.shape != (len(self.labels), 60, 2000) or cache.dtype != np.float32:
                    raise ValueError("Signal cache geometry failed")
                self.signal_cache = cache
                return saved
            needed = len(self.labels) * 60 * 2000 * 4
            if shutil.disk_usage(directory).free < needed * 1.1:
                raise OSError("Insufficient run-artifact disk space for complete signal cache")
            pending = directory / f"signals.{uuid.uuid4().hex}.pending.npy"
            start = time.monotonic()
            mapped = np.lib.format.open_memmap(pending, mode="w+", dtype=np.float32,
                                             shape=(len(self.labels), 60, 2000))
            try:
                for offset in range(0, len(self.labels), 64):
                    check_deadline(deadline)
                    rows = np.arange(offset, min(offset + 64, len(self.labels)), dtype=np.int64)
                    mapped[rows] = self.load_signals(rows)
                mapped.flush()
                del mapped
                os.replace(pending, path)
                path.chmod(0o444)
                saved = {"identity": self.identity, "bytes": path.stat().st_size,
                         "sha256": sha256_file(path), "mtime_ns": path.stat().st_mtime_ns,
                         "reuse_check": "completed full digest and unchanged read-only file size/mtime",
                         "decode_seconds": time.monotonic() - start,
                         "storage": "run_scoped_readonly_numpy_memmap", "batch_rows": 64}
                atomic_json(marker, saved)
                self.signal_cache = np.load(path, mmap_mode="r")
                return saved
            finally:
                pending.unlink(missing_ok=True)


def overlap_audit(releases):
    result = []
    names = sorted(releases)
    for i, left in enumerate(names):
        for right in names[i+1:]:
            shared = sorted(set(releases[left].sample_ids) & set(releases[right].sample_ids))
            result.append({"left": left, "right": right, "same_sample_ids": len(shared)})
    return {"sample_id_overlap": result,
            "trial_identity": "Dataset-scoped (session,trial,ordered within-trial segment); trial IDs are not global identities",
            "seed_family_boundary": "LODO excludes the named release; metadata does not prove disjoint physical people or stimuli across SEED-family datasets",
            "duplicate_policy": "Preserve all released rows; duplicate audit is descriptive, not a filter"}
