#!/usr/bin/env python3
"""Trusted Builder CLI for the bounded EEGMAT / official CBraMod adapter.

Examples (owned paths only):
  python scripts/research/acquire-real-resources.py acquire --parent OWNED --cache OWNED/cache
  python scripts/research/acquire-real-resources.py prepare --parent OWNED --cache OWNED/cache --output OWNED/prepared --splits train
  python scripts/research/acquire-real-resources.py profile --cache OWNED/cache --train OWNED/prepared/train.npz

Do not grant this acquisition/preprocessing CLI or the complete cache to Actors.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

# Set before loading numerical runtimes; the process remains within four threads.
for variable in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[variable] = '4'
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'framework'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='command', required=True)
    acquire = subcommands.add_parser('acquire', help='Download fixed official files, with SHA256 and byte caps')
    acquire.add_argument('--parent', type=Path, required=True)
    acquire.add_argument('--cache', type=Path, required=True)
    acquire.add_argument('--model-only', action='store_true')
    acquire.add_argument('--max-bytes', type=int, default=512 * 1024**2)
    prepare = subcommands.add_parser('prepare', help='Create separate private split NPZ files')
    prepare.add_argument('--parent', type=Path, required=True)
    prepare.add_argument('--cache', type=Path, required=True)
    prepare.add_argument('--output', type=Path, required=True)
    prepare.add_argument('--splits', nargs='+', choices=('train', 'validation', 'test'), default=['train', 'validation'])
    prepare.add_argument('--max-windows', type=int, default=12)
    prepare.add_argument('--allow-test', action='store_true', help='Trusted preparation only; never export test files to Actors')
    profile = subcommands.add_parser('profile', help='Profile the first training batch; no task-model fitting')
    profile.add_argument('--cache', type=Path, required=True)
    profile.add_argument('--train', type=Path, required=True)
    profile.add_argument('--batch-size', type=int, default=1)
    args = parser.parse_args()

    from eegfm.research_bench import real_data as rd

    if args.command == 'acquire':
        manifest = rd.acquire_resources(args.cache, allowed_parent=args.parent,
                                        include_data=not args.model_only, max_download_bytes=args.max_bytes)
        print(json.dumps({'cache': str(args.cache), 'verified_files': len(manifest['files']),
                          'verified_bytes': sum(item['bytes'] for item in manifest['files'])}))
    elif args.command == 'prepare':
        paths = rd.prepare_eegmat(args.cache, args.output, allowed_parent=args.parent,
                                  splits=args.splits, max_windows=args.max_windows, allow_test=args.allow_test)
        print(json.dumps({split: str(path) for split, path in paths.items()}))
    else:
        import numpy as np
        import torch
        if args.train.name != 'train.npz' or not 1 <= args.batch_size <= 4:
            raise ValueError('Profile accepts train.npz and batch size 1..4 only')
        manifest_path = args.train.with_suffix('.json')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['split'] != 'train' or rd.sha256_file(args.train) != manifest['npz_sha256']:
            raise ValueError('Training split provenance mismatch')
        with np.load(args.train, allow_pickle=False) as data:
            if str(data['split']) != 'train' or any(rd.split_for_subject(str(s)) != 'train' for s in data['subject_ids']):
                raise ValueError('Unexpected participants or split')
            x = data['x'][:args.batch_size].copy()
        started = time.perf_counter()
        model = rd.load_cbramod(args.cache)
        loaded = time.perf_counter()
        encoded = model.encode(x)
        forwarded = time.perf_counter()
        features = rd.compute_feature_panel(x)
        featured = time.perf_counter()
        print(json.dumps({'input_shape': list(x.shape), 'encoding_shape': list(encoded.shape),
                          'feature_shape': list(features.shape), 'load_seconds': loaded - started,
                          'forward_seconds': forwarded - loaded, 'feature_seconds': featured - forwarded,
                          'finite_encoding': bool(np.isfinite(encoded).all()),
                          'finite_features': bool(np.isfinite(features).all()),
                          'torch_version': torch.__version__, 'numpy_version': np.__version__,
                          'quality': rd.input_quality(x), 'checkpoint_sha256': rd.CHECKPOINT_SHA256}))


if __name__ == '__main__':
    main()
