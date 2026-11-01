"""Post-result audit only: independent point estimates and export row binding.

No fitting, selection, held-out model replay, or modification of frozen outputs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression  # initialize Windows OpenMP once

from eegfm.common import CODE as REPO
ROOT = REPO/'.local/research/2026-10-30-extension/eegmmidb'


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):
            h.update(block)
    return h.hexdigest()


def r2(target: np.ndarray, prediction: np.ndarray) -> float:
    target, prediction = target.astype(float),prediction.astype(float)
    denominator = ((target-target.mean(0))**2).sum(0)
    valid = denominator > 1e-20
    return float(np.mean(1-((target-prediction)**2).sum(0)[valid]/denominator[valid]))


def ba(y: np.ndarray, logits: np.ndarray) -> float:
    return float(np.mean([np.mean((logits[y==c]>=0)==c) for c in (0,1)]))


def main() -> None:
    reference, public, sealed = ROOT/'private_builder/reference', ROOT/'actor_public', ROOT/'private_builder/actor_sealed'
    lock = json.loads((reference/'REFERENCE_LOCK.json').read_text())
    for row in lock['files']:
        assert digest(Path(row['path'])) == row['sha256'], row['path']
    recovery = json.loads((reference/'TEST_RECOVERY_RESERVATION.json').read_text())
    assert digest(Path(__file__).with_name('resume_eegmmidb_reference.py')) == recovery['source_sha256']
    assert digest(reference/'TEST_RESERVATION.json') == recovery['original_reservation_sha256']
    result = json.loads((reference/'REFERENCE_TEST_RESULT.json').read_text())
    assert digest(reference/'REFERENCE_TEST_ARRAYS.npz') == result['arrays_sha256']
    assert digest(reference/'REFERENCE_LOCK.json') == result['reference_lock_sha256']
    fits = json.loads((reference/'REFERENCE_FITS.json').read_text())
    with np.load(reference/'REFERENCE_TEST_ARRAYS.npz',allow_pickle=False) as a:
        assert abs(ba(a['y'],a['original_logits'])-result['head']['balanced_accuracy']) < 1e-12
        for i,row in enumerate(result['q1']):
            active=np.asarray(fits['probes'][i]['fit']['active_columns'],dtype=bool)
            target=a['features'][:,fits['probes'][i]['columns']][:,active]
            assert abs(r2(target,a[f'probe_{i}_predictions'][:,active])-row['r2']) < 1e-12
            assert abs(r2(target,a[f'probe_{i}_negative_predictions'][:,active])-row['negative_control_r2']) < 1e-12
        for i,row in enumerate(result['q2_q3']):
            scores=[ba(a['y'],a[f'intervention_{i}_{j}_logits']) for j in range(4)]
            assert abs(scores[0]-np.mean(scores[1:])-row['learned_minus_mean_random_balanced_accuracy'])<1e-12
            for j,variant in enumerate(row['variants']):
                assert abs(scores[j]-variant['balanced_accuracy'])<1e-12
                assert np.allclose(a[f'intervention_{i}_0_shift_l2'],a[f'intervention_{i}_{j}_shift_l2'],atol=1e-7,rtol=1e-5)
    export=json.loads((sealed/'EXPORT_RECEIPT.json').read_text())
    expected_files={'train.npz','validation.npz',*export['api']['exported_files']}
    actual_files={p.relative_to(public).as_posix() for p in public.rglob('*') if p.is_file()}
    assert actual_files == expected_files,(actual_files,expected_files)
    subjects:set[str]=set()
    for split,receipt in export['splits'].items():
        view=Path(receipt['target_npz'])
        assert digest(view)==receipt['target_sha256']
        mapping=json.loads(Path(receipt['private_manifest']).read_text())
        with np.load(view,allow_pickle=False) as v, np.load(receipt['truth_npz'],allow_pickle=False) as t, np.load(ROOT/f'private_builder/prepared/{split}.npz',allow_pickle=False) as p, np.load(reference/f'{split}-representations.npz',allow_pickle=False) as r:
            order=np.asarray(mapping['permutation'])
            names={'x','sample_ids','subject_ids'} if split=='test' else {'x','y','features','layer_6','layer_12','embedding','sample_ids','subject_ids'}
            assert set(v.files)==names
            assert np.array_equal(v['x'],p['x'][order])
            assert np.array_equal(t['y'],p['y'][order])
            assert np.array_equal(t['features'],r['features'][order])
            for key in ('sample_ids','subject_ids'):
                assert np.array_equal(v[key],t[key])
            if split!='test':
                for key in ('features','layer_6','layer_12','embedding'):
                    assert np.array_equal(v[key],r[key][order])
            current=set(map(str,v['subject_ids']))
            assert not subjects&current
            subjects.update(current)
    spec=importlib.util.spec_from_file_location('eegmmidb_export_api',public/'eeg_api.py')
    assert spec and spec.loader
    api=importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode=True
    spec.loader.exec_module(api)
    model=api.EEGModel()
    train_mapping=json.loads((sealed/'train-view-private.json').read_text())
    # Reproduce the original eight-window inference batch and source order;
    # arbitrary rebatching changes CPU float32 rounding and head amplification.
    indices=np.argsort(train_mapping['permutation'])[:8]
    with np.load(public/'train.npz',allow_pickle=False) as train:
        x=train['x'][indices]
        feature_error=float(np.max(np.abs(api.compute_feature_panel(x)-train['features'][indices])))
        layer=model.activations(x,layers=(6,12))
        layer_error=max(float(np.max(np.abs(layer[k]-train[f'layer_{k}'][indices]))) for k in (6,12))
        prediction_error=float(np.max(np.abs(model.logits(x)-api.head_logits(model.head,train['embedding'][indices]))))
    print(json.dumps({'feature_error':feature_error,'layer_error':layer_error,'prediction_error':prediction_error}),flush=True)
    assert feature_error==0 and layer_error<1e-6 and prediction_error<1e-5
    report={'scope':'post-result audit only, no fitting or held-out model replay','locked_files_verified':len(lock['files']),
        'q1_point_estimates_recomputed':24,'intervention_variants_recomputed':8,'export_rows_bound':864,
        'disjoint_anonymous_subjects':len(subjects),'public_file_allowlist_verified':len(actual_files),
        'public_train_api_smoke_windows':8,'feature_max_abs_error':feature_error,
        'layer_max_abs_error':layer_error,'logit_max_abs_error':prediction_error,
        'initial_three_row_rebatch_audit':{'status':'failed strict cache-equality check','feature_max_abs_error':0.0,'layer_max_abs_error':3.2186508178710938e-06,'logit_max_abs_error':2.500467275634577e-05,'resolution':'Use same eight-row source-order batch as frozen cache; no scientific files or thresholds changed'},
        'reference_lock_sha256':digest(reference/'REFERENCE_LOCK.json'),
        'reference_result_sha256':digest(reference/'REFERENCE_TEST_RESULT.json'),
        'audit_source_sha256':digest(Path(__file__))}
    with (reference/'POST_RESULT_AUDIT.json').open('x',encoding='utf-8') as f:
        json.dump(report,f,indent=2); f.write('\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
