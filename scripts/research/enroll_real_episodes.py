"""Builder-only enrollment and a scripted validation smoke, never an Actor."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
from typing import Any

from eegfm.research_bench.bundle import canonical_bytes, create_public_bundle, digest_file
from eegfm.research_bench.driver_bridge import EvaluationSpec
from eegfm.research_bench.real_worker import (FileBinding, RuntimeConfig, SplitInputs,
    SandboxedWorkerEvaluator, NpzClassificationAggregator, candidate_digest)

BASE = Path('/data/duandh/eegfm-stage-a-20261028')
WORK = BASE / 'brainpec-real-20261029'
RUNTIME = BASE / 'overnight-20261029'
REPO = RUNTIME / 'integration'
DOCS = REPO / 'docs/research/2026-10-29-brainpec-real'


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(canonical_bytes(value))


def bind(path: Path) -> dict[str, str]:
    return {'path': str(path), 'sha256': digest_file(path)}


def enroll() -> None:
    if shutil.disk_usage('/home/duandh').free < 4 * 1024**3 or shutil.disk_usage(WORK).free < 20 * 1024**3:
        raise RuntimeError('Disk admission floor')
    source, private = WORK / 'task-v2/public-source', WORK / 'private/task-v2'
    receipt = json.loads((private / 'EXPORT_RECEIPT.json').read_text())
    names = ['train.npz', 'validation.npz', *receipt['api']['exported_files']]
    expected = {source / 'eeg_api.py': receipt['api']['api_sha256'],
                private / 'split-manifest.json': receipt['split_manifest_sha256']}
    for split, record in receipt['splits'].items():
        target = private / 'evaluation/test.npz' if split == 'test' else source / (split + '.npz')
        expected[target] = record['target_sha256']
        expected[private / (split + '-truth.npz')] = record['truth_sha256']
        if split == 'validation':
            expected[private / 'evaluation/validation.npz'] = record['evaluation']['sha256']
    if any(digest_file(path) != digest for path, digest in expected.items()):
        raise ValueError('Transferred task bytes differ from the local frozen export')
    packages = ('numpy','scipy','torch','scikit-learn','mne','pandas','PyWavelets','einops','matplotlib','psutil')
    manifest = {'version': 1, 'packages': {name: importlib.metadata.version(name) for name in packages},
        'files': [bind(WORK / 'venv/pyvenv.cfg'), bind(WORK / 'evidence/requirements.lock.txt'),
                  bind((WORK / 'venv/bin/python').resolve())],
        'python_link': os.readlink(WORK / 'venv/bin/python'),
        'restriction': 'Owned runtime frozen for this comparison; Actor/worker mounts are read-only; no dependency mutation permitted.'}
    runtime_file = WORK / 'controller/frozen-runtime.json'
    save(runtime_file, manifest)
    budget = WORK / 'controller/BUDGET.json'
    if budget.exists():
        raise FileExistsError('Budget authority already transferred')
    save(budget, json.loads((DOCS / 'BUDGET.json').read_text()))
    comparison = json.loads((DOCS / 'COMPARISON_PROTOCOL.json').read_text())
    skill = REPO / 'framework/benchmarks/brainpec_pilot/skills/distinguish-recovery-response-and-causation/SKILL.md'
    if digest_file(skill) != comparison['skill']['sha256']:
        raise ValueError('Frozen M15 skill bytes changed')
    configs = []
    for row in comparison['condition_order']:
        episode = row['episode_id']
        config = {'schema_version': 'real_episode_config_v1', 'episode_id': episode, 'run_id': 'real-' + episode,
            'condition': row['condition'], 'case_root': str(WORK / 'cases' / episode),
            'trusted_root': str(WORK / 'episodes' / episode), 'public_source': str(source), 'public_files': names,
            'model': comparison['model'], 'reasoning_effort': comparison['reasoning_effort'],
            'native_binary': str(RUNTIME / 'tools/runtime-review/bin/codex'),
            'bwrap': str(RUNTIME / 'tools/bubblewrap/usr/bin/bwrap'),
            'scientific_python': str(WORK / 'venv/bin/python'), 'scientific_roots': [str(WORK / 'venv')],
            'runtime_manifest': bind(runtime_file), 'auth_source': str(BASE / 'codex-home/auth.json'),
            'proxy_url': os.environ['HTTPS_PROXY'], 'isolation_report': bind(WORK / 'evidence/ISOLATION_REPORT.json'),
            'budget_path': str(budget), 'call_ids': row['call_ids'], 'train_input': bind(source / 'train.npz'),
            'validation_input': bind(private / 'evaluation/validation.npz'),
            'test_input': bind(private / 'evaluation/test.npz'), 'split_manifest': bind(private / 'split-manifest.json'),
            'train_truth': bind(private / 'train-truth.npz'),
            'truth_by_split': {s: bind(private / (s + '-truth.npz')) for s in ('validation', 'test')},
            'bootstrap_resamples': 2000, 'worker_timeout_seconds': 900, 'max_attempts': 2}
        if row['condition'] == 'skill':
            config['skill'] = bind(skill)
        path = WORK / 'controller' / (episode + '.json')
        save(path, config)
        configs.append(bind(path))
    source_files = list((REPO / 'framework/eegfm').rglob('*.py'))
    public_docs = [REPO / 'framework/benchmarks/brainpec_real' / name for name in
                  ('TASK.md', 'INTERFACE.md', 'API_README.md', 'PUBLIC_RESULT_SCHEMA.md')]
    seal = {'version': 'real-comparison-seal-v1', 'condition_order': comparison['condition_order'],
            'configurations': configs, 'public_sources': [bind(source / name) for name in names],
            'public_documents': [bind(path) for path in public_docs],
            'controller_source': [bind(path) for path in sorted(source_files)],
            'protocols': [bind(DOCS / name) for name in ('REFERENCE_PROTOCOL.json', 'COMPARISON_PROTOCOL.json', 'SCORING_PROTOCOL_V3.md')],
            'reference_lock_sha256': receipt['reference_lock_sha256'],
            'reference_result_sha256': receipt['reference_result_sha256'],
            'semantic_calibration': 'pending; no accepted semantic score',
            'execution': 'not started; no Actor outcome used for this seal'}
    save(WORK / 'controller/EXPERIMENT_FREEZE.json', seal)
    print(json.dumps({'status': 'enrolled', 'episodes': 4, 'budget_authority': str(budget),
                      'seal_sha256': digest_file(WORK / 'controller/EXPERIMENT_FREEZE.json')}))


def smoke() -> None:
    """Validation only, frozen classifier; this is not a scientific Actor attempt."""
    config = json.loads((WORK / 'controller/E01.json').read_text())
    root = WORK / 'diagnostics/D01-real-validation-worker'
    root.mkdir(parents=True, exist_ok=False)
    public = root / 'public'
    create_public_bundle(Path(config['public_source']), public, config['public_files'], task_id='D01-validation-smoke', tier='real_eeg')
    candidate = root / 'candidate'
    candidate.mkdir()
    (candidate / 'main.py').write_text('''import argparse,sys,numpy as np
p=argparse.ArgumentParser()
for name in ('split','input','train','public','output'):p.add_argument('--'+name)
a=p.parse_args();sys.path.insert(0,a.public)
from eeg_api import EEGModel
m=EEGModel()
with np.load(a.input,allow_pickle=False) as d:x=d['x'];ids=d['sample_ids']
logits=np.concatenate([m.logits(x[i:i+8]) for i in range(0,len(x),8)])
np.savez(a.output+'/results.npz',sample_ids=ids,logits=logits)
''')
    fb = lambda value: FileBinding(Path(value['path']), value['sha256'])
    truth = {s: fb(v) for s, v in config['truth_by_split'].items()}
    aggregate = NpzClassificationAggregator(truth)
    worker = SandboxedWorkerEvaluator(private_root=root / 'worker', public_root=public,
        public_manifest_sha256=digest_file(public / 'PUBLIC_MANIFEST.json'),
        split_manifest_path=Path(config['split_manifest']['path']), split_manifest_sha256=config['split_manifest']['sha256'],
        inputs_by_split={s: SplitInputs(fb(config['train_input']), fb(config[s + '_input'])) for s in ('validation','test')},
        runtime=RuntimeConfig(Path(config['bwrap']), Path(config['scientific_python']),
            tuple(Path(p) for p in config['scientific_roots']), fb(config['runtime_manifest'])),
        aggregate=aggregate, aggregate_bindings=tuple(truth.values()),
        released_metrics=frozenset({'accuracy','balanced_accuracy'}), timeout_seconds=300)
    spec = EvaluationSpec(job_id='D01-validation', episode_id='D01', run_id='diagnostic-D01', attempt_id='A1',
        split='validation', candidate_dir=candidate, candidate_digest=candidate_digest(candidate),
        public_manifest_sha256=digest_file(public / 'PUBLIC_MANIFEST.json'), split_manifest_sha256=config['split_manifest']['sha256'])
    result = worker.submit(spec)
    save(root / 'RESULT.json', {'execution_subject': 'Builder-scripted validation smoke; not Actor', 'result': result})
    print(json.dumps({'status': result['status'], 'metrics': result['metrics']}))
    if result['status'] != 'succeeded':
        raise RuntimeError('Actual scientific worker validation smoke failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('enroll', 'smoke'))
    args = parser.parse_args()
    enroll() if args.command == 'enroll' else smoke()
