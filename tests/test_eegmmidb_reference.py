"""Dataset identity, held-out access, and anonymous row-binding regressions."""
from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pytest



def module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        pytest.fail(f'Missing production boundary: {name}')


def fixture() -> tuple[dict, dict]:
    subjects = np.repeat([f'S{i:03d}' for i in range(31, 37)], 24)
    labels = np.tile(np.repeat([0, 1], 12), 6)
    windows = np.tile(np.arange(12), 12)
    recordings = np.asarray([f'{s}R{int(y)+1:02d}' for s, y in zip(subjects, labels)])
    samples = np.asarray([f'{r}-{w}' for r, w in zip(recordings, windows)])
    x = np.broadcast_to(np.arange(144, dtype=np.float32)[:, None, None, None], (144, 20, 5, 200)).copy()
    prepared = dict(x=x, y=labels, sample_ids=samples, subject_ids=subjects,
        recording_ids=recordings, window_indices=windows, split=np.asarray('test'),
        input_unit=np.asarray('uV/100'), sample_rate=np.asarray(200),
        channels=np.asarray(['Fp1','Fp2','F3','F4','F7','F8','T7','T8','C3','C4','P7','P8','P3','P4','O1','O2','Fz','Cz','Pz','FCz']))
    reps = {k: prepared[k].copy() for k in ('y','sample_ids','subject_ids','recording_ids','window_indices')}
    reps.update(features=np.repeat(np.arange(144, dtype=np.float32)[:,None],62,axis=1),
        layer_6=x.copy(), layer_12=x.copy(), embedding=np.zeros((144,200),np.float32))
    return prepared, reps


def test_true_source_identity_and_exact_rows() -> None:
    ref = module('eegfm.eeg.eegmmidb_reference')
    p, r = fixture()
    assert ref.validate_eegmmidb(p, r, 'test') == 144
    for key, bad in [('subject_ids', 'S030'), ('recording_ids', 'S031R02'), ('sample_ids', 'Subject30_1-0')]:
        pp, rr = copy.deepcopy(p), copy.deepcopy(r)
        pp[key][0] = bad
        rr[key][0] = bad
        with pytest.raises(ValueError):
            ref.validate_eegmmidb(pp, rr, 'test')
    r['features'][0, 0] = np.nan
    with pytest.raises(ValueError):
        ref.validate_eegmmidb(p, r, 'test')


def test_wrong_channels_or_reordered_cache_are_rejected() -> None:
    ref = module('eegfm.eeg.eegmmidb_reference')
    p, r = fixture()
    p['channels'][-1] = 'A2-A1'
    with pytest.raises(ValueError):
        ref.validate_eegmmidb(p, r, 'test')
    p['channels'][-1] = 'FCz'
    r['sample_ids'][[0,1]] = r['sample_ids'][[1,0]]
    with pytest.raises(ValueError):
        ref.validate_eegmmidb(p, r, 'test')


def test_one_shot_reservation_and_source_tamper(tmp_path: Path) -> None:
    ref = module('eegfm.eeg.eegmmidb_reference')
    source = tmp_path / 'source.txt'
    source.write_text('frozen')
    lock = {'schema':'eegmmidb_reference_lock_v1','files':[{'path':str(source),'sha256':ref.sha256_file(source)}]}
    (tmp_path / 'REFERENCE_LOCK.json').write_text(json.dumps(lock))
    source.write_text('changed')
    with pytest.raises(ValueError):
        ref.reserve_reference_test(tmp_path)
    assert not (tmp_path/'TEST_RESERVATION.json').exists()
    source.write_text('frozen')
    ref.reserve_reference_test(tmp_path)
    with pytest.raises(FileExistsError):
        ref.reserve_reference_test(tmp_path)


def test_test_export_is_private_and_row_bound(tmp_path: Path) -> None:
    ref, export = module('eegfm.eeg.eegmmidb_reference'), module('eegfm.eeg.eegmmidb_export')
    p, r = fixture()
    source, cache = tmp_path/'prepared.npz', tmp_path/'reps.npz'
    np.savez(source, **p)
    np.savez(cache, **r)
    private, public = tmp_path/'private', tmp_path/'public'
    args = dict(split='test', private_dir=private, target_npz=private/'evaluation/test.npz',
        run_id='eegmmidb-baseline-v1', public_root=public,
        expected_prepared_sha256=ref.sha256_file(source), expected_repr_sha256=ref.sha256_file(cache))
    with pytest.raises(PermissionError):
        export.build_split_view(source, cache, **args)
    receipt = export.build_split_view(source, cache, **args, allow_test=True, reference_freeze_sha256='a'*64)
    with np.load(receipt['target_npz']) as view, np.load(receipt['truth_npz']) as truth:
        assert set(view.files) == {'x','sample_ids','subject_ids'}
        assert all(str(s).startswith('s_') for s in view['sample_ids'])
        assert all(str(s).startswith('p_') for s in view['subject_ids'])
        assert np.array_equal(view['sample_ids'], truth['sample_ids'])
        assert np.array_equal(view['x'][:,0,0,0], truth['features'][:,0])
        original_rows = view['x'][:,0,0,0].astype(int)
        assert np.array_equal(truth['y'], p['y'][original_rows])
    assert not public.exists()
    with pytest.raises(FileExistsError):
        export.build_split_view(source, cache, **args, allow_test=True, reference_freeze_sha256='a'*64)
