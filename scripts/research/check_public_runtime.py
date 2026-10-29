"""Read-only compatibility check of public train caches and the CPU API."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path

for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '2'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'


def main() -> None:
    import numpy as np
    import psutil
    import torch
    parser = argparse.ArgumentParser()
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve previous runtime evidence')
    process = psutil.Process()
    process.cpu_affinity(process.cpu_affinity()[:2])
    spec = importlib.util.spec_from_file_location('public_eeg_api', args.public / 'eeg_api.py')
    assert spec is not None and spec.loader is not None
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    model = api.EEGModel(args.public / 'resources')
    torch.set_num_threads(2)
    with np.load(args.public / 'train.npz', allow_pickle=False) as archive:
        x = archive['x'][:4]
        expected = {k: archive[k][:4] for k in ('layer_6', 'layer_12', 'embedding', 'features')}
    activations = model.activations(x, layers=(6, 12))
    embedding = model.continue_from(activations[12], layer=12).mean((1, 2))
    actual = {'layer_6': activations[6], 'layer_12': activations[12], 'embedding': embedding,
              'features': api.compute_feature_panel(x)}
    errors = {key: float(np.max(np.abs(actual[key] - expected[key]))) for key in actual}
    logits_error = float(np.max(np.abs(model.logits(x) - model.head_logits(expected['embedding']))))
    passed = all(np.allclose(actual[key], expected[key], rtol=1e-4, atol=1e-5) for key in actual) and logits_error < 1e-3
    result = {'status': 'passed' if passed else 'failed', 'scope': 'four public training windows; no test access',
              'max_absolute_errors': errors, 'max_logit_error': logits_error,
              'runtime': {'torch': torch.__version__, 'numpy': np.__version__, 'device': 'cpu', 'cpu_affinity': process.cpu_affinity()},
              'tolerance': {'rtol': 1e-4, 'atol': 1e-5, 'logit_atol': 1e-3}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    if not passed:
        raise RuntimeError('Public cache and runtime numerical compatibility failed')


if __name__ == '__main__':
    main()
