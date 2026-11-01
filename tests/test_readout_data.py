"""Synthetic checks for immutable, opaque new-cohort cached-readout preparation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest


def adapter() -> Any:
    from eegfm.eeg import readout_data
    return readout_data


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return dict(archive)


@pytest.fixture
def sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """Replace only raw-signal decoding and model/feature computation with arrays."""
    module = adapter()
    raw, public, output = (tmp_path / name for name in ('raw', 'model', 'output'))
    raw.mkdir()
    public.mkdir()
    checksums, records = [], []
    for subject in range(37, 109):
        directory = raw / f'S{subject:03d}'
        directory.mkdir()
        for run in (1, 2):
            path = directory / f'S{subject:03d}R{run:02d}.edf'
            path.write_bytes(f'synthetic {subject} {run}'.encode())
            relative = path.relative_to(raw).as_posix()
            checksums.append(f'{digest(path)}  {relative}')
            records.append(relative)
    (raw / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='ascii')
    (raw / 'RECORDS').write_text('\n'.join(records) + '\n', encoding='ascii')
    monkeypatch.setattr(module, '_CHECKSUMS_SHA256', digest(raw / 'SHA256SUMS.txt'))
    from eegfm.eeg import api
    (public / 'eeg_api.py').write_bytes(Path(api.__file__).read_bytes())
    files: dict[str, dict[str, Any]] = {}
    official: dict[str, tuple[str, int]] = {}
    for name in api._OFFICIAL_FILES:
        path = public / 'resources' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('synthetic ' + name).encode())
        official[name] = (digest(path), path.stat().st_size)
        files[name] = {'sha256': digest(path), 'bytes': path.stat().st_size}
    monkeypatch.setattr(api, '_OFFICIAL_FILES', official)
    head = {'schema_version': 'frozen_linear_head_v1', 'x_mean': [0.] * 200,
            'x_scale': [1.] * 200, 'coefficient': [1.] + [0.] * 199, 'intercept': -.5}
    head_path = public / 'resources/FROZEN_HEAD.json'
    head_path.write_text(json.dumps(head), encoding='utf-8')
    files['FROZEN_HEAD.json'] = {'sha256': digest(head_path), 'bytes': head_path.stat().st_size}
    (public / 'resources/API_RESOURCES.json').write_text(json.dumps({
        'schema_version': 'public_eeg_resources_v1', 'files': files}), encoding='utf-8')

    def read_windows(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
        subject, run = int(path.stem[1:4]), int(path.stem[-2:])
        values = subject * 100 + run * 20 + np.arange(12, dtype=np.float32)
        return np.broadcast_to(values[:, None, None, None], (12, 20, 5, 200)), {'synthetic': True}

    class SyntheticModel:
        def __init__(self, resource_dir: Path) -> None:
            self.head = json.loads((resource_dir / 'FROZEN_HEAD.json').read_text())
            # Input hashes and private randomization must already be recorded.
            assert (output / 'private/RESOURCES.json').is_file()
            assert (output / 'private/RANDOMIZATION.json').is_file()

        def encode(self, windows: np.ndarray) -> np.ndarray:
            return np.repeat(windows[:, 0, 0, :1], 200, axis=1)

        def head_logits(self, embedding: np.ndarray) -> np.ndarray:
            return api.head_logits(self.head, embedding)

    helper = SimpleNamespace(EEGModel=SyntheticModel, FEATURE_COLUMNS=api.FEATURE_COLUMNS,
                             compute_feature_panel=lambda x: np.repeat(x[:, 0, 0, :1] + .25, 62, axis=1))
    monkeypatch.setattr(module, 'read_windows', read_windows)
    monkeypatch.setattr(module, '_load_helper', lambda path: helper)
    return raw, public, output


def test_frozen_cohorts_are_deterministic_disjoint_and_exclude_old_participants() -> None:
    module = adapter()
    splits = module.cohort_splits()
    assert splits['validation'] == (62, 42, 53, 66, 56, 46)
    assert splits['test'] == (70, 44, 43, 55, 54, 49)
    assert splits['confirmation'] == tuple(range(73, 109))
    assert len(splits['train']) == 24
    all_subjects = [subject for values in splits.values() for subject in values]
    assert len(all_subjects) == len(set(all_subjects)) == 72
    assert set(all_subjects) == set(range(37, 109))
    splits['train'] = ()
    assert len(module.cohort_splits()['train']) == 24


def test_cached_rows_align_with_private_truth_and_safe_inference(sources: tuple[Path, Path, Path]) -> None:
    module = adapter()
    raw, public, output = sources
    receipt = module.prepare_task(raw, public, output)
    assert receipt['status'] == 'prepared'
    all_samples, all_subjects = set(), set()
    mapping = json.loads((output / 'private/MAPPINGS.json').read_text())
    for split, expected in [('train', 576), ('validation', 144), ('test', 144), ('confirmation', 864)]:
        view = load(output / 'private/inference' / f'{split}.npz')
        truth = load(output / 'private/truth' / f'{split}.npz')
        cache = load(output / 'private/cache' / f'{split}.npz')
        prepared = load(output / 'private/prepared' / f'{split}.npz')
        assert set(view) == {'x', 'sample_ids', 'subject_ids'}
        assert set(truth) == {'y', 'sample_ids', 'subject_ids'}
        assert view['x'].shape == (expected, 325)
        assert np.isfinite(view['x']).all()
        assert all(re.fullmatch(r's_[0-9a-f]{32}', value) for value in view['sample_ids'])
        assert all(re.fullmatch(r'p_[0-9a-f]{32}', value) for value in view['subject_ids'])
        assert len(set(view['sample_ids'])) == expected
        assert not all_samples.intersection(view['sample_ids'])
        assert not all_subjects.intersection(view['subject_ids'])
        all_samples.update(view['sample_ids'])
        all_subjects.update(view['subject_ids'])
        for name in ('sample_ids', 'subject_ids'):
            np.testing.assert_array_equal(view[name], truth[name])
        rows = mapping['splits'][split]
        assert [row['source_row'] for row in rows] != list(range(expected))
        assert np.count_nonzero(np.diff(truth['y'])) > 2
        for index, row in enumerate(rows):
            source = row['source_row']
            assert row['opaque_sample_id'] == view['sample_ids'][index]
            assert row['opaque_subject_id'] == view['subject_ids'][index]
            assert row['source_sample_id'] == prepared['sample_ids'][source]
            assert row['source_subject_id'] == prepared['subject_ids'][source]
            value = prepared['x'][source, 0, 0, 0]
            np.testing.assert_array_equal(view['x'][index, :200], np.full(200, value))
            np.testing.assert_array_equal(view['x'][index, 200:262], np.full(62, value + .25))
            assert view['x'][index, 262] == value - .5
            assert truth['y'][index] == prepared['y'][source]
            np.testing.assert_array_equal(view['x'][index], cache['x'][source])
        if split in ('train', 'validation'):
            published = load(output / 'public' / f'{split}.npz')
            assert set(published) == {'x', 'y', 'sample_ids', 'subject_ids'}
            np.testing.assert_array_equal(published['y'], truth['y'])
            np.testing.assert_array_equal(published['x'], view['x'])
    assert {path.name for path in (output / 'public').iterdir()} == {'train.npz', 'validation.npz', 'CACHE_SCHEMA.json'}
    resources = json.loads((output / 'private/RESOURCES.json').read_text())
    assert len(resources['records']) == 144
    assert resources['model_files']['eeg_api.py']['sha256'] == digest(public / 'eeg_api.py')
    assert resources['model_files']['resources/FROZEN_HEAD.json']['sha256'] == digest(public / 'resources/FROZEN_HEAD.json')
    for row in resources['records']:
        assert digest(raw / row['path']) == row['sha256']
    final = json.loads((output / 'private/PREPARATION.json').read_text())
    for relative, expected_hash in final['artifacts'].items():
        assert digest(output / relative) == expected_hash


def test_random_control_is_bound_to_opaque_sample_not_source_order() -> None:
    module = adapter()
    ids = np.asarray(['s_' + 'a' * 32, 's_' + 'b' * 32, 's_' + 'c' * 32])
    values = module._random_columns(ids)
    assert values.shape == (3, 62)
    np.testing.assert_array_equal(module._random_columns(ids[::-1]), values[::-1])
    assert not np.array_equal(values[0], values[1])
    assert np.std(values) > .5


def test_existing_output_is_never_resumed_or_overwritten(sources: tuple[Path, Path, Path]) -> None:
    module = adapter()
    raw, public, output = sources
    output.mkdir()
    sentinel = output / 'sentinel'
    sentinel.write_bytes(b'preserve')
    with pytest.raises(FileExistsError):
        module.prepare_task(raw, public, output)
    assert sentinel.read_bytes() == b'preserve'
    assert list(output.iterdir()) == [sentinel]


@pytest.mark.parametrize('corruption', ['missing', 'changed', 'duplicate'])
def test_invalid_raw_resource_fails_without_replacement(sources: tuple[Path, Path, Path], corruption: str) -> None:
    module = adapter()
    raw, public, output = sources
    target = raw / 'S073/S073R01.edf'
    if corruption == 'missing':
        target.unlink()
    elif corruption == 'changed':
        target.write_bytes(b'changed original')
    else:
        target.write_bytes((raw / 'S073/S073R02.edf').read_bytes())
    before = target.read_bytes() if target.exists() else None
    with pytest.raises((FileNotFoundError, ValueError)):
        module.prepare_task(raw, public, output)
    assert not output.exists()
    assert (target.read_bytes() if target.exists() else None) == before


@pytest.mark.parametrize('relative', ['eeg_api.py', 'resources/FROZEN_HEAD.json', 'resources/pretrained_weights.pth'])
def test_model_helper_and_head_drift_fail_before_signal_access(sources: tuple[Path, Path, Path], relative: str) -> None:
    module = adapter()
    raw, public, output = sources
    target = public / relative
    original = target.read_bytes()
    target.write_bytes(original + b' ')
    with pytest.raises(ValueError, match='hash|identity|size|helper'):
        module.prepare_task(raw, public, output)
    assert target.read_bytes() == original + b' '
    assert not output.exists()


def test_outputs_cannot_be_written_under_input_roots(sources: tuple[Path, Path, Path]) -> None:
    module = adapter()
    raw, public, _ = sources
    for output in (raw / 'outputs', public / 'outputs'):
        with pytest.raises(ValueError, match='disjoint|overlap|input'):
            module.prepare_task(raw, public, output)
        assert not output.exists()


def test_bad_window_count_fails_closed_without_replacing_subject(sources: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    module = adapter()
    raw, public, output = sources
    monkeypatch.setattr(module, 'read_windows', lambda path: (np.zeros((11, 20, 5, 200), dtype=np.float32), {}))
    with pytest.raises(ValueError, match='window'):
        module.prepare_task(raw, public, output)
    assert not (output / 'private/PREPARATION.json').exists()
    assert not (output / 'public/train.npz').exists()
