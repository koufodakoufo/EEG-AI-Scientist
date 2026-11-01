"""Independent EEGMMIDB anonymous export; no EEGMAT identity conversion."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import secrets
import sys
from typing import Any
import numpy as np
from eegfm.eeg.eegmmidb_reference import validate_eegmmidb
from eegfm.eeg.data import sha256_file
from eegfm.eeg.public import _sha
from eegfm.eeg.public import _path
from eegfm.eeg.public import _input
from eegfm.eeg.public import _arrays
from eegfm.eeg.public import _permutation
from eegfm.eeg.public import _private_directory
from eegfm.eeg.public import _atomic_npz
from eegfm.eeg.public import _atomic_bytes
from eegfm.eeg.public import _canonical
from eegfm.eeg.public import _PUBLIC_TEST
from eegfm.eeg.public import _PUBLIC_TRAIN
from eegfm.eeg.public import _TRUTH
from eegfm.eeg.public import export_api_resources
from eegfm.eeg.public import make_evaluation_view


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
    prepared = _arrays(source,('x','y','sample_ids','subject_ids','recording_ids','window_indices','split','input_unit','sample_rate','channels'))
    reps = _arrays(cache,('y','sample_ids','subject_ids','recording_ids','window_indices','features','layer_6','layer_12','embedding'))
    n = validate_eegmmidb(prepared,reps,split)
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



def main() -> None:
    from eegfm.arguments import task_parser
    parser = task_parser('eegmmidb-export', description=__doc__)
    args = parser.parse_args()
    lock_path = args.reference / 'REFERENCE_LOCK.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if lock.get('schema') != 'eegmmidb_reference_lock_v1':
        raise ValueError('Not an EEGMMIDB reference freeze')
    expected = {str(Path(row['path']).resolve()): row['sha256'] for row in lock['files']}
    for path, digest in expected.items():
        if sha256_file(Path(path)) != digest:
            raise ValueError('Frozen reference input changed')
    final = json.loads((args.reference / 'REFERENCE_TEST_RESULT.json').read_text(encoding='utf-8'))
    if final['reference_lock_sha256'] != sha256_file(lock_path):
        raise ValueError('Test result does not bind the reference freeze')
    if args.public.exists() or args.private.exists():
        raise FileExistsError('Task export destinations must be fresh')
    receipts: dict[str, Any] = {}
    for split in ('train', 'validation', 'test'):
        prepared = args.prepared / (split + '.npz')
        representations = args.reference / (split + '-representations.npz')
        cache_receipt = json.loads((args.reference / (split + '-representations.json')).read_text(encoding='utf-8'))
        prepared_hash = final['split_npz_sha256'] if split == 'test' else expected[str(prepared.resolve())]
        representation_hash = cache_receipt['sha256'] if split == 'test' else expected[str(representations.resolve())]
        if cache_receipt['input_sha256'] != prepared_hash:
            raise ValueError('Prepared/cache lineage mismatch')
        destination = args.private / 'evaluation/test.npz' if split == 'test' else args.public / (split + '.npz')
        receipt = build_split_view(prepared, representations, split=split, run_id='eegmmidb-baseline-v1',
            private_dir=args.private, public_root=args.public, target_npz=destination,
            expected_prepared_sha256=prepared_hash, expected_repr_sha256=representation_hash,
            allow_test=split == 'test', reference_freeze_sha256=sha256_file(lock_path))
        if split == 'validation':
            receipt['evaluation'] = make_evaluation_view(destination, args.private / 'evaluation/validation.npz',
                expected_sha256=receipt['target_sha256'])
        receipts[split] = receipt
    combined: dict[str, Any] = {'schema_version': 'split_manifest_v3', 'run_id': 'eegmmidb-baseline-v1', 'samples': {}}
    for receipt in receipts.values():
        manifest = json.loads(Path(receipt['split_manifest']).read_text(encoding='utf-8'))
        if combined['samples'].keys() & manifest['samples'].keys():
            raise ValueError('Repeated opaque sample identity')
        combined['samples'].update(manifest['samples'])
    combined_path = args.private / 'split-manifest.json'
    combined_path.write_text(json.dumps(combined, sort_keys=True, separators=(',', ':')), encoding='utf-8')
    head = args.reference / 'FROZEN_HEAD.json'
    api = export_api_resources(args.resources, head, args.public, expected_head_sha256=expected[str(head.resolve())])
    report = {'schema': 'eegmmidb_task_export_v1', 'reference_lock_sha256': sha256_file(lock_path),
        'reference_result_sha256': sha256_file(args.reference / 'REFERENCE_TEST_RESULT.json'),
        'splits': receipts, 'api': api, 'split_manifest_sha256': sha256_file(combined_path)}
    (args.private / 'EXPORT_RECEIPT.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'exported', 'public_files': len(list(args.public.rglob('*'))),
        'reference_lock_sha256': report['reference_lock_sha256']}))


if __name__ == '__main__':
    main()
