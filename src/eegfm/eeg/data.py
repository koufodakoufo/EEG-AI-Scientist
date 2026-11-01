"""Trusted, split-specific EEGMAT / CBraMod adapters; never mount the cache to Actors.

Provenance: CBraMod b9e961003214326972c567eff390e75b0287e32a (MIT),
HF weighting666/CBraMod 500543c7e30bda1b22bfd51a49301b238dee21fd
(model card: Apache-2.0), EEGMAT 1.0.0 (ODC-By 1.0).
The twelve generic signal definitions follow BrainPEC
982b1df393a846e6418cee715bdfaa57d041cee3 (MIT), factor_atlas.py.
No probing, erasure algorithm, classifier fitting, gold, or paper outcomes are
included here. This is a new frozen-backbone configuration, not the released
downstream model. See docs/history/brainpec-pilot/RESOURCE_RECON.md.

Generic feature adaptation copyright (c) 2026 Kian Chen, MIT License:
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import types
from typing import Any, Sequence
import urllib.parse
import urllib.request

import numpy as np

CBRAMOD_COMMIT = 'b9e961003214326972c567eff390e75b0287e32a'
CHECKPOINT_REVISION = '500543c7e30bda1b22bfd51a49301b238dee21fd'
CHECKPOINT_SHA256 = '0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178'
EEGMAT_URL = 'https://physionet.org/files/eegmat/1.0.0/'
CHANNELS = tuple('EEG ' + name for name in (
    'Fp1', 'Fp2', 'F3', 'F4', 'F7', 'F8', 'T3', 'T4', 'C3', 'C4',
    'T5', 'T6', 'P3', 'P4', 'O1', 'O2', 'Fz', 'Cz', 'Pz', 'A2-A1'))
SPLITS = ('train', 'validation', 'test')
FEATURE_IDS = (
    'T001_hjorth_activity', 'T002_hjorth_mobility', 'F001_delta_log_power',
    'F002_theta_log_power', 'TF001_wavelet_entropy', 'TF002_wavelet_detail_var_l1',
    'C001_permutation_entropy', 'C002_sample_entropy', 'X001_pac_delta_beta',
    'X002_pac_theta_gamma', 'R001_corr_abs_mean', 'R002_corr_abs_std')
AGGREGATIONS = ('mean', 'std', 'median', 'q25', 'q75', 'max')
FEATURE_COLUMNS = tuple(f'{name}:{agg}' for name in FEATURE_IDS[:10] for agg in AGGREGATIONS) + FEATURE_IDS[10:]
EXPECTED_RECORDS = tuple(f'Subject{s:02d}_{condition}.edf' for s in range(36) for condition in (1, 2))
_MARKER = '.eegfm-real-resources-v1'
_EPS = 1e-12


@dataclass(frozen=True)
class ResourceFile:
    relative_path: str
    url: str
    sha256: str
    size: int | None
    max_bytes: int = 8 * 1024 * 1024


@dataclass
class DownloadBudget:
    limit: int
    used: int = 0

    def consume(self, count: int) -> None:
        self.used += count
        if self.used > self.limit:
            raise ValueError('Aggregate download byte cap exceeded')


_RAW = f'https://raw.githubusercontent.com/wjq-learning/CBraMod/{CBRAMOD_COMMIT}/'
MODEL_RESOURCES = (
    ResourceFile('vendor/models/cbramod.py', _RAW + 'models/cbramod.py',
                 'caa7c5a0e4acd488a6f625b56f7b54dc4e7190d6b68ef5b76dff2cef86874a14', 4593),
    ResourceFile('vendor/models/criss_cross_transformer.py', _RAW + 'models/criss_cross_transformer.py',
                 '90e90b8c98ca7eb543c44e32afc29674d3f71cb090692ad9f82db3a43edf334c', 8521),
    ResourceFile('vendor/LICENSE', _RAW + 'LICENSE',
                 'eb839b706e4d7219842e96d7dc33285844abc794292602deb3498be7b699537c', 1068),
    ResourceFile('pretrained_weights.pth', f'https://huggingface.co/weighting666/CBraMod/resolve/{CHECKPOINT_REVISION}/pretrained_weights.pth',
                 CHECKPOINT_SHA256, 19775842, 19775842),
)
DATA_METADATA = (
    ResourceFile('eegmat/RECORDS', EEGMAT_URL + 'RECORDS',
                 'c5786ce9f3b980d56f1ac4c4052271b49f5d9339082464e03b1855f88da9264b', 1152),
    ResourceFile('eegmat/SHA256SUMS.txt', EEGMAT_URL + 'SHA256SUMS.txt',
                 '85c71151495c8543e80fd48559cb62eca7b6c407ed5e96c8e490db7ecabf1fa0', 6063),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def owned_destination(destination: Path | str, allowed_parent: Path | str) -> Path:
    """Require a proper child of an explicitly supplied owned parent; no aliases."""
    parent = Path(allowed_parent).resolve(strict=True)
    original = Path(destination).absolute()
    resolved = original.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise ValueError('Destination must be a proper child of allowed_parent')
    for component in (original, *original.parents):
        if component == parent:
            break
        if component.is_symlink():
            raise ValueError('Symlink destination is not allowed')
    return resolved


def _new_owned_directory(destination: Path | str, allowed_parent: Path | str) -> Path:
    root = owned_destination(destination, allowed_parent)
    if root.exists() and any(root.iterdir()) and not (root / _MARKER).is_file():
        raise ValueError('Refusing a nonempty directory without this adapter ownership marker')
    root.mkdir(parents=True, exist_ok=True)
    marker = root / _MARKER
    if marker.exists():
        if marker.read_text(encoding='utf-8') != 'private builder resource directory\n':
            raise ValueError('Ownership marker mismatch')
    else:
        marker.write_text('private builder resource directory\n', encoding='utf-8')
    return root


def _asset_path(root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute() or '..' in Path(relative_path).parts:
        raise ValueError('Unsafe asset path')
    return owned_destination(root / relative_path, root)


def verify_resource(spec: ResourceFile, root: Path) -> Path:
    path = _asset_path(root, spec.relative_path)
    if not path.is_file() or path.stat().st_size > spec.max_bytes:
        raise ValueError(f'Missing or oversized resource: {spec.relative_path}')
    if spec.size is not None and path.stat().st_size != spec.size:
        raise ValueError(f'Resource size mismatch: {spec.relative_path}')
    if sha256_file(path) != spec.sha256:
        raise ValueError(f'Resource SHA256 mismatch: {spec.relative_path}')
    return path


def download_verified(spec: ResourceFile, root: Path, budget: DownloadBudget, *, timeout: float = 60) -> Path:
    """Download one explicit HTTPS resource; never overwrite an existing file."""
    path = _asset_path(root, spec.relative_path)
    if path.exists():
        verified = verify_resource(spec, root)
        budget.consume(verified.stat().st_size)
        return verified
    if urllib.parse.urlsplit(spec.url).scheme != 'https':
        raise ValueError('Only HTTPS resource URLs are allowed')
    if spec.size is not None and spec.size > budget.limit - budget.used:
        raise ValueError('Resource exceeds remaining aggregate download cap')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + '.', suffix='.part', dir=path.parent)
    temporary = Path(temporary_name)
    try:
        digest = hashlib.sha256()
        count = 0
        request = urllib.request.Request(spec.url, headers={'User-Agent': 'EEGFM-resource-audit/1.0'})
        with os.fdopen(fd, 'wb') as output, urllib.request.urlopen(request, timeout=timeout) as response:
            if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                raise ValueError('Non-HTTPS redirect refused')
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > min(spec.max_bytes, budget.limit - budget.used):
                raise ValueError('Resource Content-Length exceeds byte cap')
            while True:
                block = response.read(min(1024 * 1024, max(1, budget.limit - budget.used + 1)))
                if not block:
                    break
                budget.consume(len(block))
                count += len(block)
                if count > spec.max_bytes:
                    raise ValueError('Per-resource byte cap exceeded')
                digest.update(block)
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        if spec.size is not None and count != spec.size:
            raise ValueError('Downloaded resource size mismatch')
        if digest.hexdigest() != spec.sha256:
            raise ValueError('Downloaded resource SHA256 mismatch')
        # Link is atomic and refuses an existing destination (including racing writers).
        os.link(temporary, path)
        return path
    finally:
        temporary.unlink(missing_ok=True)


def _eegmat_specs(root: Path) -> tuple[ResourceFile, ...]:
    records = verify_resource(DATA_METADATA[0], root).read_text(encoding='ascii').splitlines()
    if tuple(records) != EXPECTED_RECORDS:
        raise ValueError('EEGMAT record inventory does not match the frozen 72-record list')
    sums: dict[str, str] = {}
    for line in verify_resource(DATA_METADATA[1], root).read_text(encoding='ascii').splitlines():
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r'[0-9a-f]{64}', parts[0]):
            raise ValueError('Malformed SHA256SUMS entry')
        if parts[1] in sums:
            raise ValueError('Duplicate SHA256SUMS entry')
        sums[parts[1]] = parts[0]
    if not set(EXPECTED_RECORDS).issubset(sums):
        raise ValueError('Missing EEGMAT hashes')
    return tuple(ResourceFile('eegmat/' + name, EEGMAT_URL + name, sums[name], None) for name in records)


def _atomic_json(path: Path, value: object) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f'Refusing changed metadata: {path}')
        return
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.part', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def acquire_resources(cache_dir: Path | str, *, allowed_parent: Path | str,
                      include_data: bool = True, max_download_bytes: int = 512 * 1024**2) -> dict[str, Any]:
    """Private Builder acquisition only. Fixed URLs, no recursive downloads."""
    if max_download_bytes <= 0 or max_download_bytes > 1024**3:
        raise ValueError('Download cap must be positive and no larger than 1 GiB')
    root = _new_owned_directory(cache_dir, allowed_parent)
    budget = DownloadBudget(max_download_bytes)
    resources = list(MODEL_RESOURCES)
    if include_data:
        resources.extend(DATA_METADATA)
    for spec in resources:
        download_verified(spec, root, budget)
    if include_data:
        data_specs = _eegmat_specs(root)
        for spec in data_specs:
            download_verified(spec, root, budget)
        resources.extend(data_specs)
    manifest = {
        'version': 1, 'private': True, 'cbramod_commit': CBRAMOD_COMMIT,
        'checkpoint_revision': CHECKPOINT_REVISION, 'dataset': 'eegmat/1.0.0' if include_data else None,
        'licenses': {'code': 'MIT', 'weights_model_card': 'Apache-2.0', 'eegmat': 'ODC-By-1.0'},
        'files': [{'path': spec.relative_path, 'source': spec.url, 'sha256': spec.sha256,
                   'bytes': (root / spec.relative_path).stat().st_size} for spec in resources],
    }
    if sum(item['bytes'] for item in manifest['files']) > max_download_bytes:
        raise ValueError('Total resource set exceeds byte cap, including existing files')
    _atomic_json(root / ('ACQUIRED_DATA.json' if include_data else 'ACQUIRED_MODEL.json'), manifest)
    return manifest


def subject_id(recording_or_window: str) -> str:
    match = re.fullmatch(r'(Subject\d{2})_[12](?:\.edf|-\d+)?', recording_or_window)
    if not match or not 0 <= int(match[1][7:]) < 36:
        raise ValueError(f'Invalid EEGMAT identifier: {recording_or_window}')
    return match[1]


def split_for_subject(subject: str) -> str:
    if not re.fullmatch(r'Subject\d{2}', subject) or not 0 <= int(subject[7:]) < 36:
        raise ValueError('Invalid participant identifier')
    number = int(subject[7:])
    return 'train' if number < 24 else ('validation' if number < 30 else 'test')


def window_indices(n_points: int, *, maximum: int = 12) -> list[int]:
    if n_points < 0 or not 1 <= maximum <= 12:
        raise ValueError('Invalid sample count or window cap; allowed maximum is 1..12')
    count = n_points // 1000
    if count <= maximum:
        return list(range(count))
    if maximum == 1:
        return [0]
    # Include first and last full window; integer arithmetic avoids platform rounding.
    return [(index * (count - 1)) // (maximum - 1) for index in range(maximum)]


def make_windows(signal: np.ndarray, *, unit: str, maximum: int = 12) -> tuple[np.ndarray, list[int]]:
    data = np.asarray(signal)
    if data.ndim != 2 or data.shape[0] != 20 or not np.isfinite(data).all():
        raise ValueError('Expected finite 20-channel signal')
    if unit not in ('V', 'uV'):
        raise ValueError('Unit must be explicitly V or uV')
    indices = window_indices(data.shape[-1], maximum=maximum)
    factor = 1e4 if unit == 'V' else .01
    windows = np.empty((len(indices), 20, 5, 200), dtype=np.float32)
    for row, index in enumerate(indices):
        windows[row] = (data[:, index * 1000:(index + 1) * 1000] * factor).reshape(20, 5, 200)
    if not np.isfinite(windows).all():
        raise ValueError('Non-finite float32 window after scaling')
    return windows, indices


def read_edf_header(path: Path | str) -> dict[str, Any]:
    """Read only EDF public technical fields, excluding patient/date identifiers."""
    source = Path(path)
    with source.open('rb') as stream:
        fixed = stream.read(256)
        if len(fixed) != 256 or fixed[:8].strip() != b'0':
            raise ValueError('Unsupported or truncated EDF header')
        header_bytes = int(fixed[184:192].decode('ascii').strip())
        records = int(fixed[236:244].decode('ascii').strip())
        duration = float(fixed[244:252].decode('ascii').strip())
        ns = int(fixed[252:256].decode('ascii').strip())
        if not 1 <= ns <= 256 or header_bytes != 256 * (1 + ns) or records <= 0 or duration <= 0:
            raise ValueError('Invalid EDF header dimensions')
        raw = stream.read(ns * 256)
        if len(raw) != ns * 256:
            raise ValueError('Truncated EDF signal headers')
    position = 0
    fields: dict[str, list[str]] = {}
    for name, width in [('labels', 16), ('transducer', 80), ('units', 8), ('physical_min', 8),
                        ('physical_max', 8), ('digital_min', 8), ('digital_max', 8),
                        ('prefilter', 80), ('samples_per_record', 8), ('reserved', 32)]:
        fields[name] = [raw[position + i * width:position + (i + 1) * width].decode('latin1').strip() for i in range(ns)]
        position += ns * width
    if len(set(fields['labels'])) != ns:
        raise ValueError('Duplicate EDF channel labels')
    selected: list[dict[str, Any]] = []
    for channel in CHANNELS:
        if channel not in fields['labels']:
            raise ValueError(f'Missing required EDF channel: {channel}')
        index = fields['labels'].index(channel)
        unit = fields['units'][index]
        if unit not in ('uV', 'µV', 'μV', 'V', 'mV'):
            raise ValueError(f'Unrecognized EDF voltage unit for {channel}: {unit}')
        values = [float(fields[name][index]) for name in ('physical_min', 'physical_max', 'digital_min', 'digital_max')]
        rate = int(fields['samples_per_record'][index]) / duration
        if not all(math.isfinite(value) for value in values) or values[1] <= values[0] or values[3] <= values[2] or rate < 200:
            raise ValueError(f'Invalid EDF calibration or sampling rate: {channel}')
        selected.append({'channel': channel, 'unit': unit, 'sample_rate': rate,
                         'physical_min': values[0], 'physical_max': values[1],
                         'digital_min': values[2], 'digital_max': values[3], 'prefilter': fields['prefilter'][index]})
    if len({item['sample_rate'] for item in selected}) != 1:
        raise ValueError('Mixed EEG channel sampling rates')
    expected_bytes = header_bytes + records * 2 * sum(int(v) for v in fields['samples_per_record'])
    if source.stat().st_size != expected_bytes:
        raise ValueError('EDF payload length disagrees with header')
    return {'n_records': records, 'record_seconds': duration, 'duration_seconds': records * duration,
            'original_sample_rate': selected[0]['sample_rate'], 'selected_channels': selected,
            'source_channel_names': fields['labels']}


def prepare_eegmat(cache_dir: Path | str, output_dir: Path | str, *, allowed_parent: Path | str,
                   splits: Sequence[str] = ('train', 'validation'), max_windows: int = 12,
                   allow_test: bool = False) -> dict[str, Path]:
    """Trusted preprocessing. Never mixes split rows; test requires explicit opt-in.

    The output directory still belongs outside Actor mounts. Export only specific
    permitted split NPZ files through the trusted task interface.
    """
    selected_splits = tuple(splits)
    if 'test' in selected_splits and not allow_test:
        raise PermissionError('Test preprocessing requires explicit trusted allow_test=True')
    if not selected_splits or len(set(selected_splits)) != len(selected_splits) or set(selected_splits) - set(SPLITS):
        raise ValueError('Invalid split selection')
    if not 1 <= max_windows <= 12:
        raise ValueError('Window cap must be 1..12')
    import mne
    cache = Path(cache_dir).resolve(strict=True)
    specs = _eegmat_specs(cache)
    output = _new_owned_directory(output_dir, allowed_parent)
    result: dict[str, Path] = {}
    for split in selected_splits:
        target = output / f'{split}.npz'
        if target.exists() or (output / f'{split}.json').exists():
            raise FileExistsError(f'Split output already exists: {split}')
        arrays: list[np.ndarray] = []
        labels: list[int] = []
        ids: list[str] = []
        subjects: list[str] = []
        recording_ids: list[str] = []
        source_windows: list[int] = []
        source_meta: list[dict[str, Any]] = []
        for spec in specs:
            name = Path(spec.relative_path).name
            participant = subject_id(name)
            if split_for_subject(participant) != split:
                continue
            path = verify_resource(spec, cache)
            header = read_edf_header(path)
            raw = mne.io.read_raw_edf(path, preload=True, verbose='ERROR')
            try:
                raw.pick(list(CHANNELS)).reorder_channels(list(CHANNELS))
                if tuple(raw.ch_names) != CHANNELS or not np.isclose(raw.info['sfreq'], header['original_sample_rate']):
                    raise ValueError('MNE channel/rate interpretation disagrees with EDF header')
                raw.resample(200, npad='auto', n_jobs=1, verbose='ERROR')
                windows, indices = make_windows(raw.get_data(units='uV'), unit='uV', maximum=max_windows)
            finally:
                raw.close()
            if len(indices) == 0:
                raise ValueError(f'No full 5-second windows: {name}')
            condition = int(name[-5]) - 1
            recording = name[:-4]
            arrays.append(windows)
            labels.extend([condition] * len(indices))
            ids.extend(f'{recording}-{index}' for index in indices)
            subjects.extend([participant] * len(indices))
            recording_ids.extend([recording] * len(indices))
            source_windows.extend(indices)
            source_meta.append({'recording_id': recording, 'subject_id': participant,
                                'sha256': spec.sha256, 'window_indices': indices, 'header': header})
        values = {'x': np.concatenate(arrays), 'y': np.asarray(labels, dtype=np.int64),
                  'sample_ids': np.asarray(ids), 'subject_ids': np.asarray(subjects),
                  'recording_ids': np.asarray(recording_ids), 'window_indices': np.asarray(source_windows, dtype=np.int64),
                  'split': np.asarray(split), 'channels': np.asarray(CHANNELS),
                  'sample_rate': np.asarray(200), 'input_unit': np.asarray('uV/100')}
        if len(set(ids)) != len(ids):
            raise ValueError('Duplicate sample identifiers')
        fd, temp_name = tempfile.mkstemp(prefix=split + '.', suffix='.part', dir=output)
        try:
            with os.fdopen(fd, 'wb') as stream:
                np.savez_compressed(stream, **values)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temp_name, target)
        finally:
            Path(temp_name).unlink(missing_ok=True)
        _atomic_json(output / f'{split}.json', {
            'version': 1, 'split': split, 'npz_sha256': sha256_file(target),
            'shape': list(values['x'].shape), 'input_unit': 'uV/100', 'sample_rate': 200,
            'max_windows_per_recording': max_windows, 'selection': 'evenly_spaced_full_5s_windows',
            'subject_range': {'train': [0, 23], 'validation': [24, 29], 'test': [30, 35]}[split],
            'reference': 'source linked-ear reference retained; no rereference or additional explicit filter',
            'mne_version': mne.__version__, 'numpy_version': np.__version__, 'records': source_meta,
            'quality': input_quality(values['x']),
        })
        result[split] = target
    return result


def _validate_x(x: np.ndarray) -> np.ndarray:
    values = np.asarray(x, dtype=np.float32)
    if values.ndim != 4 or values.shape[1:] != (20, 5, 200) or values.shape[0] < 1:
        raise ValueError('Expected shape (N,20,5,200), N >= 1')
    if not np.isfinite(values).all():
        raise ValueError('Input contains non-finite values')
    return values


def input_quality(x: np.ndarray) -> dict[str, int]:
    values = np.asarray(x)
    if values.ndim != 4:
        raise ValueError('Expected four-dimensional EEG windows')
    signal = values.reshape(values.shape[0], values.shape[1], -1)
    finite = np.isfinite(signal).all(axis=-1)
    variance = np.var(np.where(np.isfinite(signal), signal, 0), axis=-1)
    return {'nonfinite_values': int((~np.isfinite(values)).sum()),
            'zero_variance_channels': int(((variance <= 1e-12) & finite).sum()),
            'windows': int(values.shape[0])}


def compute_feature_panel(x: np.ndarray) -> np.ndarray:
    """Exact twelve registered generic features (62 columns), on uV/100 input.

    PyTorch float32 operators match the source median, quantile and FFT semantics.
    Missing/constant channels must be audited through input_quality separately.
    """
    import torch
    values = _validate_x(x)
    with torch.inference_mode():
        signal = torch.from_numpy(values).reshape(len(values), 20, 1000)

        def aggregate(value: Any) -> Any:
            value = torch.nan_to_num(value.float(), nan=0., posinf=0., neginf=0.)
            return torch.stack((value.mean(1), value.std(1, unbiased=False), value.median(1).values,
                                torch.quantile(value, .25, dim=1), torch.quantile(value, .75, dim=1),
                                value.max(1).values), dim=1)

        dx = signal[..., 1:] - signal[..., :-1]
        var = signal.var(-1, unbiased=False).clamp_min(_EPS)
        output = [aggregate(var), aggregate(torch.sqrt(dx.var(-1, unbiased=False).clamp_min(_EPS) / var))]
        frequencies = torch.fft.rfftfreq(1000, d=1 / 200)
        spectrum = torch.fft.rfft(signal, dim=-1)
        for low, high in ((.5, 4.), (4., 8.)):
            power = spectrum.abs().square()[..., (frequencies >= low) & (frequencies < high)].sum(-1).clamp_min(_EPS)
            output.append(aggregate(torch.log(power)))
        approximation = signal
        details = []
        for _ in range(5):
            if approximation.shape[-1] % 2:
                approximation = approximation[..., :-1]
            even, odd = approximation[..., 0::2], approximation[..., 1::2]
            details.append((even - odd) * (1.0 / math.sqrt(2)))
            approximation = (even + odd) * (1.0 / math.sqrt(2))
        energies = torch.stack([d.square().mean(-1).clamp_min(_EPS) for d in details] +
                               [approximation.square().mean(-1).clamp_min(_EPS)], dim=-1)
        probability = energies / energies.sum(-1, keepdim=True).clamp_min(_EPS)
        output.extend((aggregate(-(probability * probability.log()).sum(-1) / math.log(6)),
                       aggregate(details[0].var(-1, unbiased=False))))
        a, b, c = signal[..., :-2], signal[..., 1:-1], signal[..., 2:]
        pattern = torch.zeros_like(a, dtype=torch.long)
        for mask, code in (((a <= b) & (b <= c), 0), ((a <= c) & (c < b), 1),
                           ((b < a) & (a <= c), 2), ((b <= c) & (c < a), 3),
                           ((c < a) & (a <= b), 4), ((c < b) & (b < a), 5)):
            pattern = torch.where(mask, torch.full_like(pattern, code), pattern)
        probabilities = torch.stack([(pattern == index).float().mean(-1) for index in range(6)], -1).clamp_min(_EPS)
        probabilities /= probabilities.sum(-1, keepdim=True)
        output.append(aggregate(-(probabilities * probabilities.log()).sum(-1) / math.log(6)))
        radius = .2 * signal.std(-1, unbiased=False).clamp_min(1e-6)
        close1 = (dx.abs().mean(-1) / radius).clamp_min(_EPS)
        close2 = ((dx[..., 1:] - dx[..., :-1]).abs().mean(-1) / radius).clamp_min(_EPS)
        output.append(aggregate(torch.log1p(close2) - torch.log1p(close1)))

        def analytic_band(low: float, high: float) -> Any:
            mask = ((frequencies >= low) & (frequencies < high)).to(signal.dtype)
            filtered = torch.fft.irfft(spectrum * mask, n=1000, dim=-1)
            h = torch.zeros(1000, dtype=signal.dtype)
            h[0] = h[500] = 1
            h[1:500] = 2
            return torch.fft.ifft(torch.fft.fft(filtered, dim=-1) * h, dim=-1)

        for (phase_low, phase_high), (amp_low, amp_high) in (((.5, 4.), (13., 30.)), ((4., 8.), (30., 45.))):
            phase = torch.angle(analytic_band(phase_low, phase_high))
            amplitude = analytic_band(amp_low, amp_high).abs()
            edges = torch.linspace(-torch.pi, torch.pi, 19, dtype=signal.dtype)
            means = []
            for index in range(18):
                mask = (phase >= edges[index]) & (phase < edges[index + 1])
                means.append((amplitude * mask).sum(-1) / mask.sum(-1).clamp_min(1))
            weighted = torch.stack(means, dim=-1).clamp_min(_EPS)
            probability = weighted / weighted.sum(-1, keepdim=True).clamp_min(_EPS)
            output.append(aggregate((math.log(18) + (probability * probability.log()).sum(-1)) / math.log(18)))
        centered = signal - signal.mean(-1, keepdim=True)
        centered /= centered.std(-1, unbiased=False, keepdim=True).clamp_min(1e-6)
        correlation = (centered[:, :, None, :] * centered[:, None, :, :]).mean(-1).clamp(-1., 1.)
        rows, columns = torch.triu_indices(20, 20, offset=1)
        pairs = correlation.abs()[:, rows, columns]
        output.extend((pairs.mean(1, keepdim=True), pairs.std(1, unbiased=False, keepdim=True)))
        return torch.cat(output, dim=1).numpy().astype(np.float32)


def _load_strict_backbone(model: Any, checkpoint_path: Path) -> None:
    import torch
    state = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    model.load_state_dict(state, strict=True)
    model.proj_out = torch.nn.Identity()
    model.requires_grad_(False).cpu().eval()


class CBraModCPU:
    """CPU frozen backbone; all layer numbers are one-based, post-layer outputs.

    Full activations are returned on explicit request. Continue an intervention
    through the remaining layers before applying the separately frozen task head.
    """
    def __init__(self, model: Any) -> None:
        self.model = model.cpu().eval().requires_grad_(False)
        self.n_layers = len(model.encoder.layers)

    def activations(self, x: np.ndarray, *, layers: Sequence[int] | None = None) -> dict[int, np.ndarray]:
        import torch
        chosen = tuple(range(1, self.n_layers + 1)) if layers is None else tuple(layers)
        if not chosen or any(layer < 1 or layer > self.n_layers for layer in chosen):
            raise ValueError('Invalid one-based layer selection')
        with torch.inference_mode():
            activation = self.model.patch_embedding(torch.from_numpy(_validate_x(x)))
            result = {}
            for number, layer in enumerate(self.model.encoder.layers, start=1):
                activation = layer(activation)
                if number in chosen:
                    result[number] = activation.numpy().copy()
            return result

    def continue_from(self, activation: np.ndarray, *, layer: int) -> np.ndarray:
        import torch
        if not 1 <= layer <= self.n_layers:
            raise ValueError('Invalid one-based continuation layer')
        with torch.inference_mode():
            current = torch.from_numpy(_validate_x(activation).copy())
            for following in self.model.encoder.layers[layer:]:
                current = following(current)
            if self.model.encoder.norm is not None:
                current = self.model.encoder.norm(current)
            return self.model.proj_out(current).numpy().copy()

    def encode(self, x: np.ndarray) -> np.ndarray:
        last = self.activations(x, layers=(self.n_layers,))[self.n_layers]
        return self.continue_from(last, layer=self.n_layers).mean(axis=(1, 2))


def load_cbramod(cache_dir: Path | str, *, threads: int = 4) -> CBraModCPU:
    """Verify all official code/weight bytes, then import and strictly load on CPU."""
    import torch
    if not 1 <= threads <= 4:
        raise ValueError('CPU thread budget must be 1..4')
    torch.set_num_threads(threads)
    cache = Path(cache_dir).resolve(strict=True)
    for spec in MODEL_RESOURCES:
        verify_resource(spec, cache)
    # Isolated package avoids importing an unrelated generic `models` package.
    package_name = '_eegfm_cbramod_' + CBRAMOD_COMMIT[:12]
    transformer_name = package_name + '.criss_cross_transformer'
    package = types.ModuleType(package_name)
    package.__path__ = [str(cache / 'vendor/models')]
    sys.modules[package_name] = package
    transformer_spec = importlib.util.spec_from_file_location(transformer_name, cache / 'vendor/models/criss_cross_transformer.py')
    if transformer_spec is None or transformer_spec.loader is None:
        raise ImportError('Could not create CBraMod transformer import')
    transformer = importlib.util.module_from_spec(transformer_spec)
    sys.modules[transformer_name] = transformer
    transformer_spec.loader.exec_module(transformer)
    source = (cache / 'vendor/models/cbramod.py').read_text(encoding='utf-8')
    old_import = 'from models.criss_cross_transformer import TransformerEncoderLayer, TransformerEncoder'
    if source.count(old_import) != 1:
        raise ValueError('Unexpected pinned CBraMod import statement')
    # Sole source adaptation: namespaced import; verified original file remains unchanged.
    source = source.replace(old_import, f'from {transformer_name} import TransformerEncoderLayer, TransformerEncoder')
    module = types.ModuleType(package_name + '.cbramod')
    module.__file__ = str(cache / 'vendor/models/cbramod.py')
    module.__package__ = package_name
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    model = module.CBraMod()
    _load_strict_backbone(model, cache / 'pretrained_weights.pth')
    return CBraModCPU(model)
