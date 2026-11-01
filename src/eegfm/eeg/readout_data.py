"""Private Builder preparation for the fixed new-cohort cached-readout study.

Only ``output/public`` may be mounted to a researcher. All inference views,
truth, source identities and randomization stay under ``output/private``.
Directories alone do not enforce isolation: the caller owns mounts and admission.
This does no fitting, selection or evaluation, and never updates the old head.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import platform
import random
import re
import secrets
from types import ModuleType
from typing import Any

import numpy as np

from eegfm.eeg import api
from eegfm.eeg.eegmmidb import CHANNELS, read_windows, sha256_file
from eegfm.eeg.public import _atomic_bytes, _atomic_npz, _canonical, _path, _permutation


# Official metadata identity verified in the single primary raw mirror preflight.
_CHECKSUMS_SHA256 = '7f5d16957d8ee7bce86cc7ccba0e5994f63f33781607eb3f838392d49311a208'
_BATCH_SIZE = 8


def cohort_splits() -> dict[str, tuple[int, ...]]:
    """Seeded S037-S072 development/diagnostic allocation; S073-S108 held out."""
    subjects = list(range(37, 73))
    random.Random(314159).shuffle(subjects)
    return {'train': tuple(subjects[:24]), 'validation': tuple(subjects[24:30]),
            'test': tuple(subjects[30:]), 'confirmation': tuple(range(73, 109))}


def _identity(path: Path) -> dict[str, Any]:
    checked = _path(path, existing=True)
    return {'sha256': sha256_file(checked), 'bytes': checked.stat().st_size}


def _inventory(raw_root: Path, model_public: Path) -> dict[str, Any]:
    checksum_path = raw_root / 'SHA256SUMS.txt'
    metadata = {name: _identity(raw_root / name) for name in ('SHA256SUMS.txt', 'RECORDS')}
    if metadata['SHA256SUMS.txt']['sha256'] != _CHECKSUMS_SHA256:
        raise ValueError('Official checksum manifest hash mismatch')
    checksums: dict[str, str] = {}
    for line in checksum_path.read_text(encoding='ascii').splitlines():
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r'[0-9a-f]{64}', parts[0]) or parts[1] in checksums:
            raise ValueError('Malformed or duplicate official checksum entry')
        checksums[parts[1]] = parts[0]
    records = set((raw_root / 'RECORDS').read_text(encoding='ascii').splitlines())
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for split, subjects in cohort_splits().items():
        for number in subjects:
            subject = f'S{number:03d}'
            for run in (1, 2):
                relative = f'{subject}/{subject}R{run:02d}.edf'
                if relative not in checksums or relative not in records:
                    raise ValueError(f'Official inventory missing {relative}; no replacements')
                identity = _identity(raw_root / relative)
                if identity['sha256'] != checksums[relative]:
                    raise ValueError(f'EDF hash mismatch: {relative}')
                if identity['sha256'] in seen:
                    raise ValueError('Duplicate selected EDF bytes')
                seen.add(identity['sha256'])
                selected.append({'path': relative, 'subject': subject, 'label': run - 1,
                                 'split': split, **identity})

    helper = model_public / 'eeg_api.py'
    helper_identity = _identity(helper)
    if helper_identity['sha256'] != sha256_file(Path(api.__file__)):
        raise ValueError('Public EEG helper differs from the trusted original helper')
    manifest_path = model_public / 'resources/API_RESOURCES.json'
    manifest_identity = _identity(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if set(manifest) != {'schema_version', 'files'} or manifest['schema_version'] != 'public_eeg_resources_v1':
        raise ValueError('Unexpected frozen model resource manifest')
    if set(manifest['files']) != set(api._OFFICIAL_FILES) | {'FROZEN_HEAD.json'}:
        raise ValueError('Frozen model resource allowlist mismatch')
    model_files = {'eeg_api.py': helper_identity, 'resources/API_RESOURCES.json': manifest_identity}
    for name, expected in manifest['files'].items():
        if name in api._OFFICIAL_FILES:
            digest, size = api._OFFICIAL_FILES[name]
            if expected != {'sha256': digest, 'bytes': size}:
                raise ValueError('Official model identity mismatch')
        actual = _identity(model_public / 'resources' / name)
        if actual != expected:
            raise ValueError(f'Model resource hash/size mismatch: {name}')
        model_files['resources/' + name] = actual
    api._head_parameters(json.loads((model_public / 'resources/FROZEN_HEAD.json').read_text(encoding='utf-8')))
    return {'schema_version': 'readout_resources_v1', 'raw_root': str(raw_root),
            'model_public': str(model_public), 'raw_metadata': metadata,
            'records': selected, 'model_files': model_files,
            'source_code': {name: sha256_file(Path(__file__).with_name(name))
                            for name in ('readout_data.py', 'eegmmidb.py', 'api.py', 'public.py')}}


def _load_helper(path: Path) -> ModuleType:
    """Load verified bytes directly; avoid writing bytecode into a shared source."""
    source = _path(path, existing=True).read_bytes()
    if hashlib.sha256(source).hexdigest() != sha256_file(Path(api.__file__)):
        raise ValueError('Public EEG helper hash changed before loading')
    module = ModuleType('_readout_original_eeg_api')
    module.__file__ = str(path)
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def _random_columns(sample_ids: np.ndarray) -> np.ndarray:
    """Gaussian seed271828, keyed by opaque ID so row order reveals no source."""
    result = []
    for sample in sample_ids:
        digest = hashlib.sha256(f'271828|{sample}'.encode('ascii')).digest()
        rng = np.random.default_rng(int.from_bytes(digest, 'big'))
        result.append(rng.standard_normal(62))
    return np.asarray(result, dtype=np.float64)


def _finite(value: np.ndarray, shape: tuple[int, ...], description: str) -> np.ndarray:
    array = np.asarray(value)
    if array.shape != shape or not np.issubdtype(array.dtype, np.floating) or not np.isfinite(array).all():
        raise ValueError(f'Invalid finite floating {description}; expected {shape}')
    return array


def prepare_task(raw_root: Path, model_public: Path, output: Path) -> dict[str, Any]:
    """Create one immutable private cache and public train/validation package.

    ``raw_root`` is the single EEGMMIDB1.0.0 directory containing Sxxx/, RECORDS,
    and the pinned SHA256SUMS.txt. ``model_public`` contains the original exported
    eeg_api.py and resources/. Root must admit/freeze that original head identity
    before this call; hashing a supplied head alone does not establish its lineage.
    Caller must choose a fresh owned output directory and separately authorize
    held-out mechanical preprocessing. Failed attempts are preserved, never resumed.

    x has 325 columns: embedding[0:200], handcrafted[200:262], old_logit[262],
    Gaussian[263:325]. All model operations are the trusted frozen CPU helper.
    """
    raw_root, model_public, output = (_path(path) for path in (raw_root, model_public, output))
    if output.exists():
        raise FileExistsError('Readout output must be fresh; no overwrite or resume')
    for source in (raw_root, model_public):
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError('Output and input roots must be disjoint')
    resources = _inventory(raw_root, model_public)
    output.mkdir(parents=True, exist_ok=False)
    private = output / 'private'
    _atomic_bytes(private / 'RESOURCES.json', _canonical(resources))
    nonce = secrets.token_bytes(32)
    _atomic_bytes(private / 'RANDOMIZATION.json', _canonical({
        'id_nonce_hex': nonce.hex(), 'id_method': 'HMAC-SHA256 truncated128; private nonce',
        'row_order': 'independent SystemRandom shuffle per split; explicit permutations in MAPPINGS.json',
        'random_features': 'default_rng(SHA256(271828|opaque_sample_id) big-endian integer), standard_normal62',
        'cohort_seed': 314159, 'random_feature_seed': 271828}))
    protocol = {'schema_version': 'readout_preparation_v1', 'participants': cohort_splits(),
                'channels': CHANNELS, 'sample_rate': 200, 'native_sample_rate': 160,
                'input_unit': 'uV/100', 'windows_per_record': 12, 'window_seconds': 5,
                'selection': 'R01/R02 first60s; no overlap; no exclusions/replacements',
                'labels': {'R01': 0, 'R02': 1}, 'model': 'frozen CPU CBraMod and unchanged original head',
                'batch_size': _BATCH_SIZE, 'fitting': False,
                'runtime': {'python': platform.python_version(), 'numpy': np.__version__}}
    _atomic_bytes(private / 'PROTOCOL.json', _canonical(protocol))
    helper = _load_helper(model_public / 'eeg_api.py')
    model = helper.EEGModel(resource_dir=model_public / 'resources')
    mappings: dict[str, Any] = {'splits': {}}
    public_views: dict[str, dict[str, np.ndarray]] = {}
    receipt_splits: dict[str, Any] = {}
    tokens: set[str] = set()

    def token(prefix: str, source: str) -> str:
        result = prefix + hmac.new(nonce, (prefix + source).encode('ascii'), hashlib.sha256).hexdigest()[:32]
        if result in tokens:
            raise ValueError('Opaque ID collision; preserve failed attempt')
        tokens.add(result)
        return result

    for split, subjects in cohort_splits().items():
        rows, features, embeddings, logits = [], [], [], []
        labels, sample_ids, subject_ids, recording_ids, windows, headers = [], [], [], [], [], []
        for record in resources['records']:
            if record['split'] != split:
                continue
            source = raw_root / record['path']
            if _identity(source) != {key: record[key] for key in ('sha256', 'bytes')}:
                raise ValueError('EDF changed before signal decoding')
            values, header = read_windows(source)
            values = _finite(values, (12, 20, 5, 200), 'EEG windows')
            if sha256_file(source) != record['sha256']:
                raise ValueError('EDF changed during signal decoding')
            rows.append(values)
            headers.append({'path': record['path'], 'header': header})
            recording = Path(record['path']).stem
            labels.extend([record['label']] * 12)
            sample_ids.extend(f'{recording}-{index}' for index in range(12))
            subject_ids.extend([record['subject']] * 12)
            recording_ids.extend([recording] * 12)
            windows.extend(range(12))
            for start in range(0, 12, _BATCH_SIZE):
                batch = values[start:start + _BATCH_SIZE]
                embedding = _finite(model.encode(batch), (len(batch), 200), 'embedding')
                embeddings.append(embedding)
                features.append(_finite(helper.compute_feature_panel(batch), (len(batch), 62), 'features'))
                logits.append(_finite(model.head_logits(embedding), (len(batch),), 'old logits'))
        n = len(subjects) * 24
        prepared = {'x': np.concatenate(rows), 'y': np.asarray(labels, dtype=np.int64),
                    'sample_ids': np.asarray(sample_ids), 'subject_ids': np.asarray(subject_ids),
                    'recording_ids': np.asarray(recording_ids), 'window_indices': np.asarray(windows),
                    'channels': np.asarray(CHANNELS), 'sample_rate': np.asarray(200),
                    'input_unit': np.asarray('uV/100'), 'split': np.asarray(split)}
        _finite(prepared['x'], (n, 20, 5, 200), 'prepared windows')
        _atomic_npz(private / 'prepared' / f'{split}.npz', prepared)
        _atomic_bytes(private / 'prepared' / f'{split}.json', _canonical(headers))
        subject_mapping = {source: token('p_', source) for source in sorted(set(subject_ids))}
        opaque_samples = np.asarray([token('s_', source) for source in sample_ids])
        opaque_subjects = np.asarray([subject_mapping[source] for source in subject_ids])
        x = np.column_stack((np.concatenate(embeddings), np.concatenate(features),
                             np.concatenate(logits), _random_columns(opaque_samples)))
        _finite(x, (n, 325), 'cached columns')
        _atomic_npz(private / 'cache' / f'{split}.npz', {
            'x': x, **{name: prepared[name] for name in ('y', 'sample_ids', 'subject_ids')}})
        permutation = _permutation(prepared['y'])
        view = {'x': x[permutation], 'sample_ids': opaque_samples[permutation],
                'subject_ids': opaque_subjects[permutation]}
        truth = {'y': prepared['y'][permutation], **{name: view[name] for name in ('sample_ids', 'subject_ids')}}
        _atomic_npz(private / 'inference' / f'{split}.npz', view)
        _atomic_npz(private / 'truth' / f'{split}.npz', truth)
        mappings['splits'][split] = [
            {'view_row': row, 'source_row': index, 'source_sample_id': sample_ids[index],
             'source_subject_id': subject_ids[index], 'opaque_sample_id': str(opaque_samples[index]),
             'opaque_subject_id': str(opaque_subjects[index])} for row, index in enumerate(permutation)]
        if split in ('train', 'validation'):
            public_views[split] = {**view, 'y': truth['y']}
        receipt_splits[split] = {'subjects': len(subjects), 'rows': n,
                                'inference': f'private/inference/{split}.npz', 'truth': f'private/truth/{split}.npz'}
    # Recheck all immutable inputs before public publication and completion receipt.
    if _inventory(raw_root, model_public) != resources:
        raise ValueError('Input/source identity changed during preparation')
    _atomic_bytes(private / 'MAPPINGS.json', _canonical(mappings))
    for split, arrays in public_views.items():
        _atomic_npz(output / 'public' / f'{split}.npz', arrays)
    schema = {'schema_version': 'cached_readout_x325_v1', 'x_columns': 325,
              'embedding': [0, 200], 'handcrafted': [200, 262], 'old_logit': 262,
              'random_gaussian': [263, 325], 'slice_convention': 'start inclusive, stop exclusive',
              'feature_columns': list(helper.FEATURE_COLUMNS), 'labels': {'0': 'eyes_open', '1': 'eyes_closed'},
              'inference_arrays': ['x', 'sample_ids', 'subject_ids'],
              'train_validation_arrays': ['x', 'y', 'sample_ids', 'subject_ids'],
              'task': 'cached readout; no raw EEG intervention; original model/head remain frozen'}
    _atomic_bytes(output / 'public/CACHE_SCHEMA.json', _canonical(schema))
    receipt = {'schema_version': 'readout_preparation_receipt_v1', 'status': 'prepared',
               'created_utc': datetime.now(timezone.utc).isoformat(), 'splits': receipt_splits,
               'artifacts': {path.relative_to(output).as_posix(): sha256_file(path)
                             for path in sorted(output.rglob('*')) if path.is_file()}}
    _atomic_bytes(private / 'PREPARATION.json', _canonical(receipt))
    return receipt
