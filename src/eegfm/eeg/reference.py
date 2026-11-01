"""Private deterministic reference preparation for the real EEG study.

Not part of the Actor public package. The test entrypoint verifies a fitted,
hashed development snapshot before touching any held-out EEG.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

import numpy as np

from eegfm.eeg.data import FEATURE_IDS
from eegfm.eeg.data import FEATURE_COLUMNS
from eegfm.eeg.data import MODEL_RESOURCES
from eegfm.eeg.data import compute_feature_panel
from eegfm.eeg.data import load_cbramod
from eegfm.eeg.data import prepare_eegmat
from eegfm.eeg.data import sha256_file
from eegfm.eeg.statistics import classification_metrics
from eegfm.eeg.statistics import fit_head
from eegfm.eeg.statistics import fit_probe
from eegfm.eeg.statistics import head_logits
from eegfm.eeg.statistics import interval
from eegfm.eeg.statistics import perturb
from eegfm.eeg.statistics import predict_probe
from eegfm.eeg.statistics import r2_columns
from eegfm.eeg.statistics import subspace
from eegfm.eeg.statistics import permute_subject_blocks
from eegfm.eeg.statistics import cluster_bootstrap_indices
from eegfm.eeg.statistics import validate_partitions


def plain(value: Any) -> Any:
    if isinstance(value,np.ndarray):
        return plain(value.tolist())
    if isinstance(value,np.generic):
        return plain(value.item())
    if isinstance(value,dict):
        return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):
        return [plain(v) for v in value]
    if isinstance(value,float) and not np.isfinite(value):
        return None
    return value


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(plain(value),stream,sort_keys=True,indent=2,allow_nan=False)
        stream.write('\n')


def array_fit(value: dict[str,Any]) -> dict[str,Any]:
    return {k:np.asarray(v) if isinstance(v,list) and k not in {'selection_grid'} else v for k,v in value.items()}


def cache_provenance(resources: Path) -> dict[str,Any]:
    import torch
    return {'code_sha256':{name:sha256_file(Path(__file__).with_name(name))
                           for name in ('reference.py','data.py','statistics.py')},
            'model_files':{item.relative_path:sha256_file(resources/item.relative_path) for item in MODEL_RESOURCES},
            'numpy':np.__version__,'torch':torch.__version__,'device':'cpu','dtype':'float32'}


def cache_split(resources: Path, prepared: Path, output: Path, split: str, *, batch_size: int = 8) -> Path:
    """Caller must authorize test separately before this private helper is used."""
    target = output/f'{split}-representations.npz'
    producer = cache_provenance(resources)
    if target.exists():
        receipt = json.loads((output/f'{split}-representations.json').read_text(encoding='utf-8'))
        if receipt.get('producer') != producer:
            raise ValueError('Cached representation producer/model/runtime changed')
        if receipt['sha256'] != sha256_file(target) or receipt['input_sha256'] != sha256_file(prepared/f'{split}.npz'):
            raise ValueError('Cached representations changed')
        return target
    model = load_cbramod(resources,threads=4)
    with np.load(prepared/f'{split}.npz',allow_pickle=False) as data:
        x = data['x']
        saved = {name:data[name] for name in ('y','sample_ids','subject_ids','recording_ids','window_indices')}
    activations: dict[int,list[np.ndarray]] = {6:[],12:[]}
    features: list[np.ndarray] = []
    embeddings: list[np.ndarray] = []
    start = time.monotonic()
    for offset in range(0,len(x),batch_size):
        batch = x[offset:offset+batch_size]
        acts = model.activations(batch,layers=(6,12))
        for layer in activations:
            activations[layer].append(acts[layer])
        embeddings.append(model.continue_from(acts[12],layer=12).mean((1,2)))
        features.append(compute_feature_panel(batch))
    for layer, values in activations.items():
        saved[f'layer_{layer}'] = np.concatenate(values)
    saved['embedding'] = np.concatenate(embeddings)
    saved['features'] = np.concatenate(features)
    if any(not np.isfinite(saved[name]).all() for name in ('layer_6','layer_12','embedding','features')):
        raise ValueError('Nonfinite scientific cache')
    output.mkdir(parents=True,exist_ok=True)
    np.savez(target,**saved)
    save_json(output/f'{split}-representations.json',{'split':split,'sha256':sha256_file(target),
        'input_sha256':sha256_file(prepared/f'{split}.npz'),'samples':len(x),'seconds':time.monotonic()-start,
        'layers':[6,12],'feature_columns':FEATURE_COLUMNS,'model_device':'cpu','threads':4,'producer':producer})
    return target


def choose_probe(train: np.ndarray, targets: np.ndarray, validation: np.ndarray, val_targets: np.ndarray) -> tuple[dict[str,Any],float]:
    fits = [fit_probe(train,targets,alpha=alpha) for alpha in (1.,10.,100.)]
    scores = [float(np.nanmean(r2_columns(val_targets,predict_probe(fit,validation))[fit['active_columns']]))
              if fit['active_columns'].any() else float('-inf') for fit in fits]
    best = int(np.argmax(scores))
    return fits[best],scores[best]


def prepare_reference(resources: Path, prepared: Path, output: Path, protocol: Path) -> dict[str,Any]:
    if (output/'REFERENCE_LOCK.json').exists():
        raise FileExistsError('Reference is already frozen')
    output.mkdir(parents=True,exist_ok=True)
    for split in ('train','validation'):
        cache_split(resources,prepared,output,split)
    with np.load(output/'train-representations.npz',allow_pickle=False) as data:
        train = dict(data)
    with np.load(output/'validation-representations.npz',allow_pickle=False) as data:
        val = dict(data)
    validate_partitions({'train':train['subject_ids'],'validation':val['subject_ids']})
    head = fit_head(train['embedding'],train['y'],val['embedding'],val['y'])
    save_json(output/'FROZEN_HEAD.json',head)
    probes: list[dict[str,Any]] = []
    permutation = permute_subject_blocks(train['subject_ids'],seed=20261029)
    for layer in (6,12):
        tx, vx = train[f'layer_{layer}'].mean((1,2)), val[f'layer_{layer}'].mean((1,2))
        for feature in FEATURE_IDS:
            columns = [index for index,name in enumerate(FEATURE_COLUMNS) if name == feature or name.startswith(feature+':')]
            fit, score = choose_probe(tx,train['features'][:,columns],vx,val['features'][:,columns])
            changed = np.any(train['features'][permutation][:,columns] != train['features'][:,columns],axis=0)
            if not np.all(changed[fit['active_columns']]):
                raise ValueError('An active target column was unchanged by diagnostic randomization')
            control = fit_probe(tx,train['features'][permutation][:,columns],alpha=fit['alpha'])
            probes.append({'feature':feature,'layer':layer,'columns':columns,'fit':fit,
                           'negative_fit':control,'validation_r2':score})
    ranked = sorted(probes,key=lambda item:(-item['validation_r2'],item['feature'],item['layer']))
    selected: list[dict[str,Any]] = []
    for item in ranked:
        if item['feature'] in {p['feature'] for p in selected} or not np.isfinite(item['validation_r2']):
            continue
        selected.append(item)
        if len(selected) == 2:
            break
    interventions: list[dict[str,Any]] = []
    for item in selected:
        layer, columns, fit = item['layer'],item['columns'],item['fit']
        basis = subspace(fit['directions'][:,fit['active_columns']])
        variants: list[dict[str,Any]] = []
        for seed in (None,1301,1302,1303):
            tx, tm = perturb(train[f'layer_{layer}'],basis,fit['x_mean'],random_seed=seed)
            vx, vm = perturb(val[f'layer_{layer}'],basis,fit['x_mean'],random_seed=seed)
            residual, score = choose_probe(tx.mean((1,2)),train['features'][:,columns],vx.mean((1,2)),val['features'][:,columns])
            variants.append({'random_seed':seed,'residual_fit':residual,'residual_validation_r2':score,
                'train_shift_l2_mean':float(np.mean(tm['pooled_shift_l2'])),'validation_shift_l2_mean':float(np.mean(vm['pooled_shift_l2']))})
        interventions.append({'feature':item['feature'],'layer':layer,'columns':columns,'basis':basis,
                              'center':fit['x_mean'],'rank':basis.shape[1],'variants':variants})
    save_json(output/'REFERENCE_FITS.json',{'probes':probes,'interventions':interventions,
        'permutation_indices':permutation,'selection_split':'validation','test_accessed':False})
    save_json(output/'DEVELOPMENT_RESULT.json',{'head':classification_metrics(val['y'],head_logits(head,val['embedding'])),
        'head_C':head['C'],'selected_features':[{'feature':p['feature'],'layer':p['layer'],'rank':p['rank']} for p in interventions],
        'q1_validation':[{'feature':p['feature'],'layer':p['layer'],'r2':p['validation_r2'],'alpha':p['fit']['alpha']} for p in probes]})
    locked = [output/'FROZEN_HEAD.json',output/'REFERENCE_FITS.json',output/'DEVELOPMENT_RESULT.json',
              protocol,Path(__file__),Path(__file__).resolve().parents[1]/'arguments.py',Path(__file__).with_name('statistics.py'),Path(__file__).with_name('data.py')]
    locked += [prepared/f'{split}.npz' for split in ('train','validation')]
    locked += [output/f'{split}-representations.{suffix}' for split in ('train','validation') for suffix in ('npz','json')]
    locked += [resources/item.relative_path for item in MODEL_RESOURCES]
    receipt = {'schema':'real_reference_lock_v1','test_accessed':False,'files':[
        {'path':str(path.resolve()),'sha256':sha256_file(path)} for path in locked],
        'protocol_sha256':sha256_file(protocol),'frozen_at_unix':time.time()}
    save_json(output/'REFERENCE_LOCK.json',receipt)
    return {'status':'reference_frozen','output':str(output),'test_accessed':False}


def reserve_reference_test(output: Path) -> dict[str,Any]:
    lock_path = output/'REFERENCE_LOCK.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if lock.get('schema') != 'real_reference_lock_v1' or not lock.get('files'):
        raise ValueError('Invalid reference lock')
    for item in lock['files']:
        path = Path(item['path'])
        if path.is_symlink() or not path.is_file() or sha256_file(path) != item['sha256']:
            raise ValueError('Frozen reference bytes changed: '+path.name)
    reservation = {'reference_lock_sha256':sha256_file(lock_path),'reserved_at_unix':time.time(),
                   'status':'reserved_before_test_access','one_shot':True}
    save_json(output/'TEST_RESERVATION.json',reservation)
    return reservation


def balanced_accuracy(y: np.ndarray, logits: np.ndarray) -> float:
    prediction = np.asarray(logits) >= 0
    return float(np.mean([np.mean(prediction[y == label] == label) for label in (0,1)]))


def reference_coverage(q1: list[dict[str,Any]], q2: list[dict[str,Any]]) -> dict[str,Any]:
    recoverable = sum(isinstance(row.get('r2'),(float,int)) and np.isfinite(row['r2']) for row in q1)
    interventions = sum(row.get('rank',0) > 0 for row in q2)
    complete = recoverable == 24 and interventions == 2
    scope = 'Q1-Q3' if recoverable and interventions else 'Q1 only' if recoverable else 'not estimable'
    return {'status':'real_reference_complete' if complete else 'real_reference_partial','scope':scope,
            'estimable_feature_layer_groups':int(recoverable),'nonzero_rank_interventions':int(interventions),
            'coverage_reason':'all predeclared analyses estimable' if complete else
                'Some target groups or interventions were not estimable; do not infer completed Q2/Q3 from lifecycle completion'}


def evaluate_reference(resources: Path, prepared: Path, output: Path) -> dict[str,Any]:
    reservation = reserve_reference_test(output)
    # These private views are only made AFTER the fitted protocol reservation.
    if not (prepared/'test.npz').exists():
        prepare_eegmat(resources,prepared,allowed_parent=prepared.parent,splits=('test',),allow_test=True)
    cache_split(resources,prepared,output,'test')
    with np.load(output/'test-representations.npz',allow_pickle=False) as data:
        test = dict(data)
    other_subjects: dict[str,np.ndarray] = {}
    for split in ('train','validation'):
        with np.load(output/f'{split}-representations.npz',allow_pickle=False) as data:
            other_subjects[split] = data['subject_ids']
    validate_partitions({**other_subjects,'test':test['subject_ids']})
    head = array_fit(json.loads((output/'FROZEN_HEAD.json').read_text(encoding='utf-8')))
    fits = json.loads((output/'REFERENCE_FITS.json').read_text(encoding='utf-8'))
    original_logits = head_logits(head,test['embedding'])
    model = load_cbramod(resources,threads=4)
    samples = cluster_bootstrap_indices(test['subject_ids'],resamples=2000,seed=20261029)
    q1: list[dict[str,Any]] = []
    saved: dict[str,np.ndarray] = {name:test[name] for name in ('y','sample_ids','subject_ids','features')}
    saved['original_logits'] = original_logits
    for index,item in enumerate(fits['probes']):
        fit, negative = array_fit(item['fit']),array_fit(item['negative_fit'])
        targets = test['features'][:,item['columns']]
        z = test[f"layer_{item['layer']}"].mean((1,2))
        prediction, control = predict_probe(fit,z),predict_probe(negative,z)
        active = fit['active_columns'].astype(bool)
        def r2_mean(rows: np.ndarray, prediction: np.ndarray = prediction) -> float:
            values = r2_columns(targets[rows],prediction[rows])[active]
            return float(np.nanmean(values)) if np.isfinite(values).any() else float('nan')
        all_rows = np.arange(len(targets))
        bootstrap = np.asarray([r2_mean(rows) for rows in samples])
        control_r2 = r2_mean(all_rows,control)
        differences = np.asarray([r2_mean(rows)-r2_mean(rows,control) for rows in samples])
        q1.append({'feature':item['feature'],'layer':item['layer'],'alpha':fit['alpha'],
            'r2':r2_mean(all_rows),'negative_control_r2':control_r2,
            'r2_ci95':interval(bootstrap),'r2_family_adjusted_ci':interval(bootstrap,confidence=1-.05/24),
            'r2_minus_negative_ci95':interval(differences),'active_train_columns':int(active.sum()),
            'test_constant_columns':int(np.sum(np.var(targets,axis=0) <= 1e-20)),
            'columns':[FEATURE_COLUMNS[i] for i in item['columns']]})
        saved[f'probe_{index}_predictions'] = prediction
        saved[f'probe_{index}_negative_predictions'] = control
    q2: list[dict[str,Any]] = []
    for index,item in enumerate(fits['interventions']):
        layer, basis, center = item['layer'],np.asarray(item['basis']),np.asarray(item['center'])
        original_activation = test[f'layer_{layer}']
        variants: list[dict[str,Any]] = []
        all_logits: list[np.ndarray] = []
        for number,variant in enumerate(item['variants']):
            changed, metadata = perturb(original_activation,basis,center,random_seed=variant['random_seed'])
            applied = changed.astype(np.float32)
            logits_parts: list[np.ndarray] = []
            for offset in range(0,len(changed),8):
                embedding = model.continue_from(applied[offset:offset+8],layer=layer).mean((1,2))
                logits_parts.append(head_logits(head,embedding))
            logits = np.concatenate(logits_parts)
            all_logits.append(logits)
            residual = predict_probe(array_fit(variant['residual_fit']),applied.mean((1,2)))
            targets = test['features'][:,item['columns']]
            active = np.asarray(variant['residual_fit']['active_columns'],dtype=bool)
            r2_values = r2_columns(targets,residual)[active]
            delta_samples = [balanced_accuracy(test['y'][rows],logits[rows])-balanced_accuracy(test['y'][rows],original_logits[rows]) for rows in samples]
            actual_shift = np.linalg.norm((original_activation-applied).mean((1,2)),axis=1)
            variants.append({'random_seed':variant['random_seed'],'rank':item['rank'],
                **classification_metrics(test['y'],logits),
                'delta_balanced_accuracy':balanced_accuracy(test['y'],logits)-balanced_accuracy(test['y'],original_logits),
                'delta_balanced_accuracy_ci95':interval(np.asarray(delta_samples)),
                'prediction_flip_rate':float(np.mean((logits>=0)!=(original_logits>=0))),
                'mean_abs_logit_change':float(np.mean(np.abs(logits-original_logits))),
                'residual_r2':float(np.nanmean(r2_values)) if np.isfinite(r2_values).any() else None,
                'actual_shift_l2_mean':float(actual_shift.mean()),
                'maximum_float32_shift_norm_error':float(np.max(np.abs(actual_shift-metadata['pooled_shift_l2'])))})
            saved[f'intervention_{index}_{number}_logits'] = logits
            saved[f'intervention_{index}_{number}_residual_predictions'] = residual
            saved[f'intervention_{index}_{number}_shift_l2'] = actual_shift
        contrast = balanced_accuracy(test['y'],all_logits[0])-np.mean([balanced_accuracy(test['y'],v) for v in all_logits[1:]])
        contrast_samples = [balanced_accuracy(test['y'][rows],all_logits[0][rows])-np.mean([
            balanced_accuracy(test['y'][rows],v[rows]) for v in all_logits[1:]]) for rows in samples]
        q2.append({'feature':item['feature'],'layer':layer,'rank':item['rank'],'variants':variants,
            'learned_minus_mean_random_balanced_accuracy':float(contrast),
            'contrast_ci95':interval(np.asarray(contrast_samples)),
            'contrast_family_adjusted_ci':interval(np.asarray(contrast_samples),confidence=.975)})
    np.savez(output/'REFERENCE_TEST_ARRAYS.npz',**saved)
    result = {**reference_coverage(q1,q2),'study_identity':'new EEGMAT adaptation',
        'execution':'private reference implementation, not Actor',
        'test_subjects':len(np.unique(test['subject_ids'])),'test_windows':len(test['y']),
        'head':classification_metrics(test['y'],original_logits),'q1':q1,'q2_q3':q2,
        'bootstrap':{'unit':'subject','resamples':2000,'marginal_confidence':.95,'seed':20261029},
        'arrays_sha256':sha256_file(output/'REFERENCE_TEST_ARRAYS.npz'),
        'split_npz_sha256':sha256_file(prepared/'test.npz'),
        'reference_lock_sha256':reservation['reference_lock_sha256'],
        'interpretation':'Representation sensitivity, not physiological causation; small held-out cohort, fixed acquisition order and possible condition/session confounds.'}
    save_json(output/'REFERENCE_TEST_RESULT.json',result)
    return {'status':result['status'],'scope':result['scope'],'subjects':result['test_subjects'],'windows':result['test_windows']}


def main() -> None:
    from eegfm.arguments import task_parser
    parser = task_parser('reference', description=__doc__)
    args = parser.parse_args()
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key] = '4'
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    if args.command == 'prepare':
        if args.protocol is None:
            parser.error('--protocol is required for prepare')
        result = prepare_reference(args.resources,args.prepared,args.output,args.protocol)
    else:
        result = evaluate_reference(args.resources,args.prepared,args.output)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
