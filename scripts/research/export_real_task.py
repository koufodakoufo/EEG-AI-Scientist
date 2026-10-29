"""Builder-only export of a frozen reference into anonymous Actor inputs."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any

from eegfm.research_bench.real_data import sha256_file
from eegfm.research_bench.real_public import build_split_view, export_api_resources, make_evaluation_view


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ('resources', 'prepared', 'reference', 'public', 'private'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    lock_path = args.reference / 'REFERENCE_LOCK.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
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
        receipt = build_split_view(prepared, representations, split=split, run_id='real-eegmat-v1',
            private_dir=args.private, public_root=args.public, target_npz=destination,
            expected_prepared_sha256=prepared_hash, expected_repr_sha256=representation_hash,
            allow_test=split == 'test', reference_freeze_sha256=sha256_file(lock_path))
        if split == 'validation':
            receipt['evaluation'] = make_evaluation_view(destination, args.private / 'evaluation/validation.npz',
                expected_sha256=receipt['target_sha256'])
        receipts[split] = receipt
    combined: dict[str, Any] = {'schema_version': 'split_manifest_v3', 'run_id': 'real-eegmat-v1', 'samples': {}}
    for receipt in receipts.values():
        manifest = json.loads(Path(receipt['split_manifest']).read_text(encoding='utf-8'))
        if combined['samples'].keys() & manifest['samples'].keys():
            raise ValueError('Repeated opaque sample identity')
        combined['samples'].update(manifest['samples'])
    combined_path = args.private / 'split-manifest.json'
    combined_path.write_text(json.dumps(combined, sort_keys=True, separators=(',', ':')), encoding='utf-8')
    head = args.reference / 'FROZEN_HEAD.json'
    api = export_api_resources(args.resources, head, args.public, expected_head_sha256=expected[str(head.resolve())])
    report = {'schema': 'real_task_export_v1', 'reference_lock_sha256': sha256_file(lock_path),
        'reference_result_sha256': sha256_file(args.reference / 'REFERENCE_TEST_RESULT.json'),
        'splits': receipts, 'api': api, 'split_manifest_sha256': sha256_file(combined_path)}
    (args.private / 'EXPORT_RECEIPT.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'exported', 'public_files': len(list(args.public.rglob('*'))),
        'reference_lock_sha256': report['reference_lock_sha256']}))


if __name__ == '__main__':
    main()
