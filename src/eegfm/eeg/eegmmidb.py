"""Independent, private Builder preparation of EEGMMIDB baseline EEG.

No training, inference, test outcomes, or changes to frozen EEGMAT adapters.
Official source: https://physionet.org/content/eegmmidb/1.0.0/ (ODC-By 1.0).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

BASE = 'https://physionet.org/files/eegmmidb/1.0.0/'
MARKER = '.eegmmidb-private-builder-v1'
MAX_FILE_BYTES = 4 * 1024**2
CHANNELS = ('Fp1', 'Fp2', 'F3', 'F4', 'F7', 'F8', 'T7', 'T8', 'C3', 'C4',
            'P7', 'P8', 'P3', 'P4', 'O1', 'O2', 'Fz', 'Cz', 'Pz', 'FCz')
SPLITS = ('train', 'validation', 'test')
METADATA = {
    'SHA256SUMS.txt': BASE + 'SHA256SUMS.txt',
    'RECORDS': BASE + 'RECORDS',
    'dataset.html': 'https://physionet.org/content/eegmmidb/1.0.0/',
    'protocol-original.html': 'https://archive.physionet.org/pn4/eegmmidb/',
    'license.html': 'https://physionet.org/content/eegmmidb/view-license/1.0.0/',
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_file(path: Path, expected: str) -> None:
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f'missing/oversized resource: {path.name}')
    if sha256_file(path) != expected:
        raise ValueError(f'hash mismatch; original preserved: {path.name}')


def publish_bytes(path: Path, data: bytes) -> None:
    """Atomic no-replace publication, including Windows and racing writers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def write_once_json(path: Path, value: Any) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f'Locked metadata changed; preserved: {path}')
        return
    publish_bytes(path, data)


def initialize_root(root: Path, parent: Path) -> Path:
    parent = parent.resolve(strict=True)
    original = root.absolute()
    root = root.resolve()
    if parent not in root.parents:
        raise ValueError('root must be a proper child of owned parent')
    for component in (original, *original.parents):
        if component == parent:
            break
        if component.is_symlink() or (hasattr(component, 'is_junction') and component.is_junction()):
            raise ValueError('symlink/junction ownership alias refused')
    marker = root / MARKER
    if root.exists() and any(root.iterdir()) and not marker.is_file():
        raise ValueError('ownership marker missing from nonempty directory')
    root.mkdir(parents=True, exist_ok=True)
    if marker.exists():
        if marker.read_text(encoding='utf-8') != 'private EEGMMIDB Builder resources\n':
            raise ValueError('ownership marker mismatch')
    else:
        publish_bytes(marker, b'private EEGMMIDB Builder resources\n')
    for name in ('resources', 'private_builder/prepared'):
        child = root / name
        child.mkdir(parents=True, exist_ok=True)
        if root not in child.resolve().parents:
            raise ValueError('child path escaped owned root')
    return root


def split_for_subject(number: int) -> str:
    if not 1 <= number <= 36:
        raise ValueError('participant outside frozen S001-S036 set')
    return 'train' if number <= 24 else ('validation' if number <= 30 else 'test')


def protocol() -> dict[str, Any]:
    return {
        'version': 'eegmmidb-baseline-v1', 'dataset': 'eegmmidb/1.0.0',
        'labels': {'R01': 0, 'R02': 1}, 'label_names': ['eyes_open', 'eyes_closed'],
        'participants': {s: [f'S{n:03d}' for n in range(1, 37) if split_for_subject(n) == s] for s in SPLITS},
        'channels': list(CHANNELS), 'missing_ear_channel_resolution': 'FCz measured, never A2-A1 fabricated',
        'native_hz': 160, 'target_hz': 200, 'seconds': 60, 'window_seconds': 5,
        'windows_per_record': 12, 'selection': 'first_60_seconds_nonoverlapping',
        'resample': 'mne.filter.resample up=5 down=4 npad=auto n_jobs=1 method=fft',
        'scale': 'uV/100', 'dtype': 'float32', 'reference': 'original retained; unspecified in official overview',
        'additional_filter': None, 'artifact_rejection': None, 'statistics_fit': False,
        'test_access': 'private_builder_preprocessing_only; no model fit, inference, outcomes',
        'exclusion_rule': 'fail closed on technical invalidity; no replacement subjects',
    }


def log_event(root: Path, event: str, **details: Any) -> None:
    with (root / 'preparation_events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'event': event, **details}, sort_keys=True) + '\n')


def opener(proxy: str | None) -> urllib.request.OpenerDirector:
    handler = urllib.request.ProxyHandler({'https': proxy, 'http': proxy} if proxy else {})
    return urllib.request.build_opener(handler)


def fetch_metadata(root: Path, proxy: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, url in METADATA.items():
        target = root / 'resources' / name
        if not target.exists():
            request = urllib.request.Request(url, headers={'User-Agent': 'EEGFM-public-resource-audit/1.0'})
            with opener(proxy).open(request, timeout=45) as response:
                data = response.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES or urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                    raise ValueError('metadata size or HTTPS check failed')
            publish_bytes(target, data)
        result[name] = {'url': url, 'sha256': sha256_file(target), 'bytes': target.stat().st_size}
    write_once_json(root / 'METADATA.lock.json', result)
    return result


def freeze(root: Path, proxy: str | None) -> list[dict[str, Any]]:
    write_once_json(root / 'PROTOCOL.lock.json', protocol())
    log_event(root, 'protocol_locked', sha256=sha256_file(root / 'PROTOCOL.lock.json'))
    fetch_metadata(root, proxy)
    checksums: dict[str, str] = {}
    for line in (root / 'resources/SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r'[0-9a-f]{64}', parts[0]) or parts[1] in checksums:
            raise ValueError('Malformed or duplicate official checksum entry')
        checksums[parts[1]] = parts[0]
    records = set((root / 'resources/RECORDS').read_text(encoding='ascii').splitlines())
    manifest: list[dict[str, Any]] = []
    for number in range(1, 37):
        for run in (1, 2):
            subject = f'S{number:03d}'
            relative = f'{subject}/{subject}R{run:02d}.edf'
            if relative not in checksums or relative not in records:
                raise ValueError(f'Official record inventory missing {relative}')
            manifest.append({'path': relative, 'url': BASE + relative, 'sha256': checksums[relative],
                             'subject': subject, 'split': split_for_subject(number), 'label': run - 1})
    write_once_json(root / 'RECORDS.lock.json', manifest)
    log_event(root, 'record_inventory_locked', records=len(manifest), signal_read=False)
    return manifest


def load_locked(root: Path) -> list[dict[str, Any]]:
    if json.loads((root / 'PROTOCOL.lock.json').read_text(encoding='utf-8')) != protocol():
        raise ValueError('Current adapter does not match frozen protocol')
    metadata = json.loads((root / 'METADATA.lock.json').read_text(encoding='utf-8'))
    for name, item in metadata.items():
        verify_file(root / 'resources' / name, item['sha256'])
    return json.loads((root / 'RECORDS.lock.json').read_text(encoding='utf-8'))


def download_record(root: Path, item: dict[str, Any], proxy: str | None) -> dict[str, Any]:
    target = root / 'resources' / item['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    if root not in target.resolve().parents:
        raise ValueError('resource escaped owned root')
    if target.exists():
        verify_file(target, item['sha256'])
        return {**item, 'bytes': target.stat().st_size, 'state': 'verified_existing'}
    part = target.with_suffix(target.suffix + '.part')
    for attempt in range(3):
        if part.exists() and sha256_file(part) == item['sha256']:
            break
        offset = part.stat().st_size if part.exists() else 0
        if offset > MAX_FILE_BYTES:
            raise ValueError('partial download exceeds frozen byte cap')
        headers = {'User-Agent': 'EEGFM-public-resource-audit/1.0'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        try:
            with opener(proxy).open(urllib.request.Request(item['url'], headers=headers), timeout=45) as response:
                if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                    raise ValueError('Non-HTTPS redirect refused')
                if offset and response.status == 206:
                    if not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                        raise ValueError('Unexpected Content-Range')
                    mode = 'ab'
                else:
                    # Only our incomplete .part is restarted when Range is unsupported.
                    mode, offset = 'wb', 0
                if int(response.headers.get('Content-Length', '0')) + offset > MAX_FILE_BYTES:
                    raise ValueError('Content-Length exceeds frozen byte cap')
                with part.open(mode) as stream:
                    count = offset
                    while block := response.read(256 * 1024):
                        count += len(block)
                        if count > MAX_FILE_BYTES:
                            raise ValueError('download exceeds frozen byte cap')
                        stream.write(block)
                    stream.flush()
                    os.fsync(stream.fileno())
            verify_file(part, item['sha256'])
            break
        except (OSError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    verify_file(part, item['sha256'])
    os.link(part, target)
    part.unlink()
    return {**item, 'bytes': target.stat().st_size, 'state': 'downloaded_verified'}


def acquire(root: Path, records: list[dict[str, Any]], proxy: str | None, workers: int) -> list[dict[str, Any]]:
    if not 1 <= workers <= 4:
        raise ValueError('workers must be 1..4')
    result: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(download_record, root, item, proxy): item for item in records}
        for future in as_completed(futures):
            item = future.result()
            result.append(item)
            log_event(root, 'resource_verified', path=item['path'], bytes=item['bytes'], sha256=item['sha256'])
            print(json.dumps({'downloaded': len(result), 'of': len(records), 'path': item['path']}), flush=True)
    return sorted(result, key=lambda item: item['path'])


def select_channels(source: list[str]) -> list[str]:
    canonical: dict[str, str] = {}
    for name in source:
        key = name.strip().strip('.').lower()
        if key in canonical:
            raise ValueError(f'duplicate normalized channel: {name}')
        canonical[key] = name
    missing = [name for name in CHANNELS if name.lower() not in canonical]
    if missing:
        raise ValueError(f'missing measured channels: {missing}')
    return [canonical[name.lower()] for name in CHANNELS]


def read_header(path: Path) -> dict[str, Any]:
    """Technical EDF fields only; never emits patient/date fields."""
    with path.open('rb') as stream:
        fixed = stream.read(256)
        if len(fixed) != 256 or fixed[:8].strip() != b'0':
            raise ValueError('Unsupported EDF header')
        header_size = int(fixed[184:192])
        records = int(fixed[236:244])
        seconds = float(fixed[244:252])
        ns = int(fixed[252:256])
        if ns != 65 or header_size != 256 * (ns + 1) or records <= 0 or seconds <= 0:
            raise ValueError('Unexpected baseline EDF dimensions')
        raw = stream.read(ns * 256)
    fields: dict[str, list[str]] = {}
    position = 0
    for name, width in [('labels', 16), ('transducer', 80), ('units', 8), ('physical_min', 8),
                        ('physical_max', 8), ('digital_min', 8), ('digital_max', 8), ('prefilter', 80),
                        ('samples_per_record', 8), ('reserved', 32)]:
        fields[name] = [raw[position + i * width:position + (i + 1) * width].decode('latin1').strip() for i in range(ns)]
        position += width * ns
    selected = select_channels(fields['labels'])
    channels: list[dict[str, Any]] = []
    for label in selected:
        index = fields['labels'].index(label)
        rate = int(fields['samples_per_record'][index]) / seconds
        calibration = [float(fields[key][index]) for key in ('physical_min', 'physical_max', 'digital_min', 'digital_max')]
        if rate != 160 or fields['units'][index] not in ('uV', 'µV', 'μV'):
            raise ValueError('Unexpected sampling rate/unit')
        if not all(map(math.isfinite, calibration)) or calibration[1] <= calibration[0] or calibration[3] <= calibration[2]:
            raise ValueError('Invalid calibration')
        channels.append({'source_label': label, 'unit': fields['units'][index], 'hz': rate,
                         'calibration': calibration, 'prefilter': fields['prefilter'][index]})
    if records * seconds < 60:
        raise ValueError('Record shorter than precommitted 60 seconds')
    expected_size = header_size + 2 * records * sum(int(n) for n in fields['samples_per_record'])
    if path.stat().st_size != expected_size:
        raise ValueError('EDF byte length differs from header')
    return {'duration_seconds': records * seconds, 'eeg_channels': 64, 'annotation_channels': 1,
            'selected': channels, 'source_labels': fields['labels'], 'bytes': expected_size}


def to_windows(signal_uv: np.ndarray) -> np.ndarray:
    data = np.asarray(signal_uv)
    if data.shape != (20, 12000):
        raise ValueError('Require exactly 20 channels and 60 seconds at 200 Hz')
    if not np.isfinite(data).all():
        raise ValueError('Nonfinite EEG signal')
    return (data.reshape(20, 12, 5, 200).transpose(1, 0, 2, 3) / 100.0).astype(np.float32)


def read_windows(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    import mne
    header = read_header(path)
    raw = mne.io.read_raw_edf(path, preload=False, verbose='ERROR')
    try:
        labels = select_channels(raw.ch_names)
        if raw.info['sfreq'] != 160:
            raise ValueError('MNE and header sampling interpretation disagree')
        signal = raw.get_data(picks=labels, start=0, stop=9600, units='uV')
        signal = mne.filter.resample(signal, up=5, down=4, npad='auto', n_jobs=1, verbose='ERROR')
    finally:
        raw.close()
    return to_windows(signal), header


def probe_train(root: Path, records: list[dict[str, Any]]) -> None:
    results: list[dict[str, Any]] = []
    for item in records[:2]:
        if item['split'] != 'train' or item['subject'] != 'S001':
            raise ValueError('Initial probe must be train-only S001')
        path = root / 'resources' / item['path']
        verify_file(path, item['sha256'])
        windows, header = read_windows(path)
        results.append({'path': item['path'], 'shape': list(windows.shape), 'header': header,
                        'finite': bool(np.isfinite(windows).all())})
    write_once_json(root / 'TRAIN_PROBE.json', results)
    log_event(root, 'train_probe_complete', records=2, model_fit=False)
    print(json.dumps({'train_probe': 'passed', 'records': 2, 'windows_per_record': 12}), flush=True)


def prepare_split(root: Path, records: list[dict[str, Any]], split: str, allow_test: bool) -> dict[str, Any]:
    import mne
    if split not in SPLITS or (split == 'test' and not allow_test):
        raise PermissionError('Test mechanical preprocessing requires --allow-test')
    output = root / 'private_builder/prepared'
    target, metadata_path = output / f'{split}.npz', output / f'{split}.json'
    if target.exists() or metadata_path.exists():
        if not target.exists() or not metadata_path.exists():
            raise FileExistsError('Incomplete prior publication; preserve and inspect')
        meta = json.loads(metadata_path.read_text(encoding='utf-8'))
        if sha256_file(target) != meta['npz_sha256'] or meta['protocol_sha256'] != sha256_file(root / 'PROTOCOL.lock.json'):
            raise ValueError('Existing prepared split hash mismatch')
        return meta
    rows: list[np.ndarray] = []
    sample_ids: list[str] = []
    subject_ids: list[str] = []
    recording_ids: list[str] = []
    labels: list[int] = []
    source: list[dict[str, Any]] = []
    for item in records:
        if item['split'] != split:
            continue
        path = root / 'resources' / item['path']
        verify_file(path, item['sha256'])
        windows, header = read_windows(path)
        recording = Path(item['path']).stem
        rows.append(windows)
        labels.extend([item['label']] * 12)
        sample_ids.extend(f'{recording}-{i}' for i in range(12))
        subject_ids.extend([item['subject']] * 12)
        recording_ids.extend([recording] * 12)
        source.append({'path': item['path'], 'sha256': item['sha256'], 'header': header})
    values = {'x': np.concatenate(rows), 'y': np.asarray(labels, dtype=np.int64),
              'sample_ids': np.asarray(sample_ids), 'subject_ids': np.asarray(subject_ids),
              'recording_ids': np.asarray(recording_ids), 'window_indices': np.tile(np.arange(12), len(rows)),
              'split': np.asarray(split), 'channels': np.asarray(CHANNELS), 'sample_rate': np.asarray(200),
              'input_unit': np.asarray('uV/100')}
    expected = {'train': 576, 'validation': 144, 'test': 144}[split]
    if values['x'].shape != (expected, 20, 5, 200) or len(set(sample_ids)) != expected:
        raise ValueError('Prepared split differs from frozen cardinality')
    fd, name = tempfile.mkstemp(prefix=split + '.', suffix='.part', dir=output)
    try:
        with os.fdopen(fd, 'wb') as stream:
            np.savez_compressed(stream, **values)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, target)
    finally:
        Path(name).unlink(missing_ok=True)
    meta = {'split': split, 'shape': list(values['x'].shape), 'npz_sha256': sha256_file(target),
            'protocol_sha256': sha256_file(root / 'PROTOCOL.lock.json'), 'adapter_sha256': sha256_file(Path(__file__)),
            'mne_version': mne.__version__, 'numpy_version': np.__version__, 'records': source,
            'scientific_results_computed': False, 'model_fit': False, 'private_builder_only': True}
    write_once_json(metadata_path, meta)
    log_event(root, 'split_prepared', split=split, shape=meta['shape'], npz_sha256=meta['npz_sha256'], model_fit=False)
    print(json.dumps({'prepared': split, 'shape': meta['shape'], 'sha256': meta['npz_sha256']}), flush=True)
    return meta


def feature_smoke(root: Path) -> dict[str, Any]:
    """Only one train window; interface check, no feature ranking or model."""
    import torch
    torch.set_num_threads(4)
    from eegfm.eeg.data import compute_feature_panel
    from eegfm.eeg.data import FEATURE_COLUMNS
    with np.load(root / 'private_builder/prepared/train.npz', allow_pickle=False) as data:
        panel = compute_feature_panel(data['x'][:1])
    if panel.shape != (1, 62) or not np.isfinite(panel).all() or len(FEATURE_COLUMNS) != 62:
        raise ValueError('Frozen 62-column feature interface smoke failed')
    result = {'split': 'train', 'windows': 1, 'feature_shape': list(panel.shape),
              'finite': True, 'model_fit': False, 'scientific_results_computed': False,
              'feature_adapter_sha256': sha256_file(Path(__file__).with_name('data.py'))}
    write_once_json(root / 'FEATURE_INTERFACE_SMOKE.json', result)
    return result


def verify(root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    for item in records:
        verify_file(root / 'resources' / item['path'], item['sha256'])
    prepared: dict[str, Any] = {}
    for split in SPLITS:
        meta_path = root / 'private_builder/prepared' / f'{split}.json'
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            path = meta_path.with_suffix('.npz')
            if sha256_file(path) != meta['npz_sha256']:
                raise ValueError('Prepared output checksum mismatch')
            prepared[split] = {'shape': meta['shape'], 'sha256': meta['npz_sha256'], 'bytes': path.stat().st_size}
    result = {'records_verified': len(records),
              'edf_bytes': sum((root / 'resources' / item['path']).stat().st_size for item in records),
              'protocol_sha256': sha256_file(root / 'PROTOCOL.lock.json'),
              'record_manifest_sha256': sha256_file(root / 'RECORDS.lock.json'), 'prepared': prepared,
              'model_fit': False, 'scientific_results_computed': False, 'test_npz_opened_for_analysis': False}
    log_event(root, 'verification_complete', **result)
    return result


def main() -> None:
    from eegfm.arguments import task_parser
    parser = task_parser('prepare-eegmmidb', description=__doc__)
    args = parser.parse_args()
    for variable in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[variable] = '4'
    root = initialize_root(args.root, args.parent)
    if args.phase in ('freeze', 'all'):
        records = freeze(root, args.proxy)
        if args.phase == 'freeze':
            print(json.dumps({'frozen': len(records), 'protocol_sha256': sha256_file(root / 'PROTOCOL.lock.json')}))
            return
    else:
        records = load_locked(root)
    if args.phase in ('probe', 'all'):
        acquire(root, records[:2], args.proxy, args.workers)
        probe_train(root, records)
    if args.phase in ('download', 'all'):
        if not (root / 'TRAIN_PROBE.json').is_file():
            raise ValueError('Run train-only technical probe before full acquisition')
        acquired = acquire(root, records, args.proxy, args.workers)
        write_once_json(root / 'ACQUIRED.json', [{k: v for k, v in item.items() if k != 'state'} for item in acquired])
    if args.phase in ('prepare', 'all'):
        if not (root / 'TRAIN_PROBE.json').is_file():
            raise ValueError('Initial train-only probe required')
        for split in SPLITS if args.allow_test else SPLITS[:2]:
            prepare_split(root, records, split, args.allow_test)
    if args.phase == 'feature-smoke':
        print(json.dumps(feature_smoke(root)), flush=True)
    if args.phase in ('verify', 'all'):
        print(json.dumps(verify(root, records), indent=2), flush=True)


if __name__ == '__main__':
    main()
