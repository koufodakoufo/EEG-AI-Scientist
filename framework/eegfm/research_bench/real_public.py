"""Trusted sanitization/export boundary. This module itself is never Actor-visible.

Fresh cryptographic IDs and row order are frozen privately. No source recording
names, condition suffixes, original window indices, or RNG seed enter a view.
Filesystem isolation is still required: do not mount private_dir or source roots.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
from typing import Any, Mapping
import zipfile

import numpy as np

from .real_data import MODEL_RESOURCES, sha256_file, split_for_subject, subject_id, verify_resource

_SHARED = ('sample_ids','subject_ids')
_PUBLIC_TRAIN = ('x','y','features','layer_6','layer_12','embedding',*_SHARED)
_PUBLIC_TEST = ('x',*_SHARED)
_TRUTH = ('y','features',*_SHARED)
_MARKER = '.private-eeg-view-directory-v1'
_MAX_ARCHIVE_BYTES = 1024**3


def _sha(value: str) -> str:
    if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{64}',value):
        raise ValueError('Expected lowercase SHA256')
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def _path(path: Path | str, *, existing: bool = False) -> Path:
    original = Path(path).absolute()
    for item in (original,*original.parents):
        if not item.exists() and not item.is_symlink():
            continue
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):
            raise ValueError('Symlinks and reparse points are forbidden')
    if existing:
        info = original.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Input must be a single-link regular file')
    return original.resolve()


def _input(path: Path | str, expected_sha256: str) -> Path:
    value = _path(path,existing=True)
    if sha256_file(value) != _sha(expected_sha256):
        raise ValueError('Source SHA256 mismatch')
    return value


def _arrays(path: Path, names: tuple[str,...]) -> dict[str,np.ndarray]:
    if path.stat().st_size > _MAX_ARCHIVE_BYTES:
        raise ValueError('NPZ file byte cap exceeded')
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members)>64 or len({entry.filename for entry in members})!=len(members) or sum(entry.file_size for entry in members)>_MAX_ARCHIVE_BYTES:
            raise ValueError('NPZ member count/uncompressed byte cap exceeded')
    with np.load(path,allow_pickle=False) as archive:
        if not set(names) <= set(archive.files):
            raise ValueError('Missing required source arrays')
        return {name:np.array(archive[name],copy=True) for name in names}


def _atomic_bytes(path: Path, data: bytes) -> None:
    path = _path(path)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name = tempfile.mkstemp(prefix='.publish-',suffix='.part',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.link(name,path)
    finally:
        Path(name).unlink(missing_ok=True)


def _atomic_npz(path: Path, arrays: Mapping[str,np.ndarray]) -> None:
    path = _path(path)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name = tempfile.mkstemp(prefix='.publish-',suffix='.part',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            np.savez(stream,**arrays); stream.flush(); os.fsync(stream.fileno())
        os.link(name,path)
    finally:
        Path(name).unlink(missing_ok=True)


def _private_directory(path: Path) -> None:
    if path.exists() and any(path.iterdir()) and not (path/_MARKER).is_file():
        raise ValueError('Private output directory is not owned by this adapter')
    path.mkdir(parents=True,exist_ok=True)
    marker = path/_MARKER
    if marker.exists():
        _path(marker,existing=True)
        if marker.read_bytes() != b'private mapping and truth; never mount to Actor\n':
            raise ValueError('Private directory marker mismatch')
    else:
        _atomic_bytes(marker,b'private mapping and truth; never mount to Actor\n')


def _validate_sources(prepared: dict[str,np.ndarray], representations: dict[str,np.ndarray], split: str) -> int:
    if prepared['split'].shape != () or str(prepared['split']) != split or str(prepared['input_unit']) != 'uV/100' or int(prepared['sample_rate']) != 200:
        raise ValueError('Prepared split/unit/sample-rate mismatch')
    n = len(prepared['sample_ids'])
    if n < 2 or prepared['x'].shape != (n,20,5,200):
        raise ValueError('Expected N>=2 EEG windows with shape (N,20,5,200)')
    for name in ('sample_ids','subject_ids','y','recording_ids','window_indices'):
        if prepared[name].shape != (n,) or not np.array_equal(prepared[name],representations[name]):
            raise ValueError(f'Prepared/representation alignment mismatch: {name}')
    if len(set(prepared['sample_ids'].tolist())) != n:
        raise ValueError('Duplicate source sample ID')
    if not np.issubdtype(prepared['y'].dtype,np.integer) or set(np.unique(prepared['y'])) != {0,1}:
        raise ValueError('Expected binary condition labels')
    if not np.issubdtype(prepared['window_indices'].dtype,np.integer) or np.any(prepared['window_indices']<0):
        raise ValueError('Source window indices must be nonnegative integers')
    for sample,subject,recording,window,label in zip(prepared['sample_ids'],prepared['subject_ids'],prepared['recording_ids'],prepared['window_indices'],prepared['y']):
        if subject_id(str(sample)) != str(subject) or split_for_subject(str(subject)) != split:
            raise ValueError('Source participant or participant partition mismatch')
        if str(sample) != f'{recording}-{int(window)}' or not str(recording).endswith('_'+str(int(label)+1)):
            raise ValueError('Source recording/window/condition metadata mismatch')
    for name,shape in (('features',(n,62)),('layer_6',(n,20,5,200)),('layer_12',(n,20,5,200)),('embedding',(n,200))):
        if representations[name].shape != shape or not np.issubdtype(representations[name].dtype,np.floating) or not np.isfinite(representations[name]).all():
            raise ValueError(f'Invalid representation array: {name}')
    if not np.issubdtype(prepared['x'].dtype,np.floating) or not np.isfinite(prepared['x']).all():
        raise ValueError('EEG samples must be finite floats')
    return n


def _permutation(labels: np.ndarray) -> list[int]:
    """System entropy only. Reject identity and visibly class-blocked permutations."""
    rng = secrets.SystemRandom()
    for _ in range(128):
        result = list(range(len(labels))); rng.shuffle(result)
        if result == list(range(len(labels))):
            continue
        if len(labels)>=4 and min(np.bincount(labels.astype(int)))>=2 and np.count_nonzero(np.diff(labels[result]))<2:
            continue
        return result
    raise RuntimeError('Could not generate a nontrivial private row permutation')


def build_split_view(prepared_npz: Path | str, repr_npz: Path | str, *, split: str,
                     private_dir: Path | str, target_npz: Path | str, run_id: str,
                     expected_prepared_sha256: str, expected_repr_sha256: str,
                     allow_test: bool = False, reference_freeze_sha256: str | None = None,
                     public_root: Path | str | None = None) -> dict[str,Any]:
    """One explicit split only; never discover/open another split's EEG source.

    For test, the controller must already have frozen the reference protocol and
    pass its hash plus explicit authorization. This function does not grant that
    authorization or release a test view to an Actor outside the trusted worker.
    For a nested public target, pass public_root as the complete Actor mount root;
    otherwise its immediate parent is assumed to be that boundary.
    """
    if split not in {'train','validation','test'}:
        raise ValueError('Unknown split')
    if split=='test' and (not allow_test or reference_freeze_sha256 is None):
        raise PermissionError('Test view requires explicit authorization and prior reference freeze hash')
    if reference_freeze_sha256 is not None:
        _sha(reference_freeze_sha256)
    if not isinstance(run_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',run_id):
        raise ValueError('Invalid run ID')
    target = _path(target_npz)
    private = _path(private_dir)
    actor_root = _path(public_root) if public_root is not None else target.parent
    if target.exists():
        raise FileExistsError(target)
    # A private mapping directory may not be inside the public file's mounted parent.
    if split!='test' and (not target.is_relative_to(actor_root) or private==actor_root or private.is_relative_to(actor_root) or actor_root.is_relative_to(private)):
        raise ValueError('Train/validation target and private directory must be disjoint')
    if split=='test' and public_root is not None and (target.is_relative_to(actor_root) or private.is_relative_to(actor_root)):
        raise ValueError('Test data and private mapping cannot be inside the Actor mount root')
    if split=='test' and not target.is_relative_to(private):
        raise ValueError('Test input must remain inside the private directory for trusted-worker mounting')
    output_paths = {name:private/f'{split}-{suffix}' for name,suffix in (
        ('truth_npz','truth.npz'),('private_manifest','view-private.json'),('split_manifest','split-manifest.json'))}
    if target in output_paths.values():
        raise ValueError('Input view and truth/manifest destinations must differ')
    if any(path.exists() for path in output_paths.values()):
        raise FileExistsError('Split export is immutable and already has private outputs')
    source = _input(prepared_npz,expected_prepared_sha256)
    cache = _input(repr_npz,expected_repr_sha256)
    prepared = _arrays(source,('x','y','sample_ids','subject_ids','recording_ids','window_indices','split','input_unit','sample_rate'))
    reps = _arrays(cache,('y','sample_ids','subject_ids','recording_ids','window_indices','features','layer_6','layer_12','embedding'))
    n = _validate_sources(prepared,reps,split)
    if sha256_file(source)!=expected_prepared_sha256 or sha256_file(cache)!=expected_repr_sha256:
        raise ValueError('Source changed while creating sanitized view')
    previous_subjects: set[str] = set()
    previous_tokens: set[str] = set()
    if private.exists():
        for other in ('train','validation','test'):
            path = private/f'{other}-view-private.json'
            if path.exists():
                previous = json.loads(_path(path,existing=True).read_text(encoding='utf-8'))
                if previous['run_id'] != run_id:
                    raise ValueError('Cannot mix run identities in private mapping directory')
                previous_subjects.update(previous['subject_mapping'])
                previous_tokens.update(previous['subject_mapping'].values())
                previous_tokens.update(item['opaque_sample_id'] for item in previous['source_mapping'])
    source_subjects = set(map(str,prepared['subject_ids']))
    if source_subjects & previous_subjects:
        raise ValueError('Participant appears in more than one exported split')
    used = set(previous_tokens)

    def token(prefix: str) -> str:
        while True:
            value = prefix+secrets.token_hex(16)
            if value not in used:
                used.add(value); return value

    subject_mapping = {s:token('p_') for s in sorted(source_subjects)}
    opaque_samples = np.asarray([token('s_') for _ in range(n)])
    opaque_subjects = np.asarray([subject_mapping[str(s)] for s in prepared['subject_ids']])
    permutation = _permutation(prepared['y'])
    all_arrays = {'x':prepared['x'], 'y':prepared['y'], 'sample_ids':opaque_samples, 'subject_ids':opaque_subjects,
                  **{name:reps[name] for name in ('features','layer_6','layer_12','embedding')}}
    public_arrays = {name:all_arrays[name][permutation] for name in (_PUBLIC_TEST if split=='test' else _PUBLIC_TRAIN)}
    truth_arrays = {name:all_arrays[name][permutation] for name in _TRUTH}
    split_manifest = {'schema_version':'split_manifest_v3','run_id':run_id,'samples':{
        str(sample):{'subject_id':str(subject),'split':split}
        for sample,subject in zip(public_arrays['sample_ids'],public_arrays['subject_ids'])}}
    mapping = [{'view_row':row,'source_row':index,'source_sample_id':str(prepared['sample_ids'][index]),
                'source_subject_id':str(prepared['subject_ids'][index]),'opaque_sample_id':str(opaque_samples[index]),
                'opaque_subject_id':str(opaque_subjects[index])} for row,index in enumerate(permutation)]
    _private_directory(private)
    _atomic_npz(output_paths['truth_npz'],truth_arrays)
    _atomic_bytes(output_paths['split_manifest'],_canonical(split_manifest))
    _atomic_npz(target,public_arrays)
    manifest = {'schema_version':'private_view_manifest_v1','run_id':run_id,'split':split,
                'prepared_sha256':expected_prepared_sha256,'representations_sha256':expected_repr_sha256,
                'target_sha256':sha256_file(target),'truth_sha256':sha256_file(output_paths['truth_npz']),
                'split_manifest_sha256':sha256_file(output_paths['split_manifest']),
                'reference_freeze_sha256':reference_freeze_sha256,'source_mapping':mapping,
                'subject_mapping':subject_mapping,'permutation':permutation,
                'randomness':'OS cryptographic entropy; no public or reproducible seed',
                'public_array_names':list(public_arrays),'rows':n}
    _atomic_bytes(output_paths['private_manifest'],_canonical(manifest))
    return {'target_npz':str(target),**{key:str(path) for key,path in output_paths.items()},
            'target_sha256':manifest['target_sha256'],'truth_sha256':manifest['truth_sha256'],
            'split_manifest_sha256':manifest['split_manifest_sha256'],
            'private_manifest_sha256':sha256_file(output_paths['private_manifest'])}


def make_evaluation_view(split_view: Path | str, destination: Path | str, *,
                         expected_sha256: str) -> dict[str,Any]:
    """Strip public validation truth for the trusted worker without changing rows.

    Mount only the returned file. The controller owns destination and must keep
    source truth/public validation labels out of the worker's evaluation mount.
    """
    target = _path(destination)
    if target.exists():
        raise FileExistsError(target)
    source = _input(split_view,expected_sha256)
    arrays = _arrays(source,_PUBLIC_TEST)
    n = len(arrays['sample_ids'])
    if n<1 or arrays['x'].shape!=(n,20,5,200) or not np.issubdtype(arrays['x'].dtype,np.floating) or not np.isfinite(arrays['x']).all():
        raise ValueError('Expected finite EEG input with shape (N,20,5,200)')
    for name,prefix in (('sample_ids','s_'),('subject_ids','p_')):
        if arrays[name].shape!=(n,) or any(not re.fullmatch(prefix+r'[0-9a-f]{32}',str(value)) for value in arrays[name]):
            raise ValueError('Evaluation IDs must already be opaque')
    if len(set(arrays['sample_ids'].tolist()))!=n:
        raise ValueError('Duplicate opaque sample ID')
    if sha256_file(source)!=expected_sha256:
        raise ValueError('Source changed during evaluation-view conversion')
    _atomic_npz(target,arrays)
    return {'path':str(target),'sha256':sha256_file(target),'source_sha256':expected_sha256,'rows':n,
            'sample_ids_sha256':hashlib.sha256(_canonical(arrays['sample_ids'].tolist())).hexdigest(),
            'subject_ids_sha256':hashlib.sha256(_canonical(arrays['subject_ids'].tolist())).hexdigest()}


def sanitize_head(value: Mapping[str,Any]) -> dict[str,Any]:
    """Export necessary prediction parameters only; discard scores and selection grids."""
    result: dict[str,Any] = {'schema_version':'frozen_linear_head_v1'}
    for name in ('x_mean','x_scale','coefficient'):
        array = np.asarray(value[name],dtype=np.float64)
        if array.shape!=(200,) or not np.isfinite(array).all() or (name=='x_scale' and np.any(array<=0)):
            raise ValueError('Frozen head vectors require 200 finite values and positive scales')
        result[name] = array.tolist()
    intercept = float(value['intercept'])
    if not np.isfinite(intercept):
        raise ValueError('Frozen head intercept must be finite')
    result['intercept'] = intercept
    return result


def export_api_resources(resource_cache: Path | str, frozen_head_json: Path | str,
                         public_root: Path | str, *, expected_head_sha256: str) -> dict[str,Any]:
    """Explicit allowlist export, without acquiring files or copying a source tree."""
    cache = _path(resource_cache)
    root = _path(public_root)
    source_head = _input(frozen_head_json,expected_head_sha256)
    head = sanitize_head(json.loads(source_head.read_text(encoding='utf-8')))
    if cache==root or cache.is_relative_to(root) or source_head.is_relative_to(root):
        raise ValueError('Private cache and source head cannot reside inside the Actor mount root')
    if sha256_file(source_head)!=expected_head_sha256:
        raise ValueError('Frozen head source changed during export')
    template = Path(__file__).resolve().parents[2]/'benchmarks/brainpec_real/eeg_api.py'
    _path(template,existing=True)
    targets = [root/'resources'/spec.relative_path for spec in MODEL_RESOURCES]
    targets += [root/'resources/FROZEN_HEAD.json',root/'resources/API_RESOURCES.json',root/'eeg_api.py']
    if any(_path(path).exists() for path in targets):
        raise FileExistsError('Public API/resource exports are immutable')
    checked = []
    for spec in MODEL_RESOURCES:
        source = _path(verify_resource(spec,cache),existing=True)
        checked.append((spec,source))
    resources: dict[str,Any] = {}
    for spec,source in checked:
        target = root/'resources'/spec.relative_path
        _atomic_bytes(target,source.read_bytes())
        if sha256_file(target) != spec.sha256:
            raise ValueError('Source changed during explicit resource export')
        resources[spec.relative_path] = {'sha256':spec.sha256,'bytes':target.stat().st_size}
    head_path = root/'resources/FROZEN_HEAD.json'
    _atomic_bytes(head_path,_canonical(head))
    resources['FROZEN_HEAD.json'] = {'sha256':sha256_file(head_path),'bytes':head_path.stat().st_size}
    api = root/'eeg_api.py'
    _atomic_bytes(api,template.read_bytes())
    manifest = {'schema_version':'public_eeg_resources_v1','files':resources}
    resource_manifest = root/'resources/API_RESOURCES.json'
    _atomic_bytes(resource_manifest,_canonical(manifest))
    return {'api_sha256':sha256_file(api),'resource_manifest_sha256':sha256_file(resource_manifest),
            'public_head_sha256':resources['FROZEN_HEAD.json']['sha256'],
            'private_source_head_sha256':expected_head_sha256,
            'exported_files':['eeg_api.py','resources/API_RESOURCES.json',*[f'resources/{name}' for name in resources]]}
