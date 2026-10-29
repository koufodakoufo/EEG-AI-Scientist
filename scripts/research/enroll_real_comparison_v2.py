"""Enroll fresh episodes after disclosed development corrections; preserve v1."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from eegfm.research_bench.bundle import canonical_bytes, digest_file
from eegfm.research_bench.real_episode import run_episode

BASE = Path('/data/duandh/eegfm-stage-a-20261028')
WORK = BASE / 'brainpec-real-20261029'
REPO = BASE / 'overnight-20261029/integration'
DOCS = REPO / 'docs/research/2026-10-30-extension'
CONTROLLER = WORK / 'controller/comparison-v2'


def bind(path: Path) -> dict[str, str]:
    return {'path': str(path), 'sha256': digest_file(path)}


def save_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(canonical_bytes(value))


def verify(records: list[dict[str, str]]) -> None:
    for record in records:
        if digest_file(Path(record['path'])) != record['sha256']:
            raise ValueError('Frozen comparison binding changed')


def enroll() -> None:
    if CONTROLLER.exists():
        raise FileExistsError('Comparison enrollment is exclusive')
    protocol_path = DOCS / 'COMPARISON_PROTOCOL_V2.json'
    protocol = json.loads(protocol_path.read_text())
    if (protocol['sessions_per_episode'] != 6 or protocol['seconds_per_session'] != 900
            or protocol['episode_wall_seconds'] != 5400 or protocol['cpu_threads'] != 4
            or protocol['memory_bytes'] != 12 * 1024**3 or protocol['gpu'] != 0):
        raise ValueError('Protocol differs from runner/runtime comparison limits')
    base = json.loads((WORK / 'controller/E01.json').read_text())
    predecessor = json.loads((WORK / 'episodes/E01/EPISODE_RESULT.json').read_text())
    if predecessor['state']['status'] != 'blocked':
        raise ValueError('Expected preserved v1 development outcome')
    skill = REPO / 'framework/benchmarks/brainpec_pilot/skills/distinguish-recovery-response-and-causation/SKILL.md'
    if digest_file(skill) != protocol['skill']['sha256']:
        raise ValueError('M15 treatment bytes changed')
    configurations: list[dict[str, str]] = []
    for row in protocol['condition_order']:
        episode = row['episode_id']
        if (WORK / 'cases' / episode).exists() or (WORK / 'episodes' / episode).exists():
            raise FileExistsError('Fresh episode paths required')
        config = {**base, 'episode_id': episode, 'run_id': 'real-' + episode,
            'condition': row['condition'], 'call_ids': row['call_ids'],
            'case_root': str(WORK / 'cases' / episode), 'trusted_root': str(WORK / 'episodes' / episode),
            'task_id': protocol['task_id'], 'recovery_policy': protocol['recovery_policy'],
            'skill_delivery': protocol['skill_delivery'],
            'max_attempts': protocol['max_iterations_excluding_baseline'],
            'model': protocol['model'], 'reasoning_effort': protocol['reasoning_effort'],
            'bootstrap_resamples': protocol['bootstrap_resamples'],
            'worker_timeout_seconds': protocol['worker_seconds'],
            'proxy_url': os.environ['HTTPS_PROXY']}
        if len(config['call_ids']) != protocol['sessions_per_episode']:
            raise ValueError('Episode call allocation differs from protocol')
        config.pop('skill', None)
        if row['condition'] == 'skill':
            config['skill'] = bind(skill)
        path = CONTROLLER / (episode + '.json')
        save_new(path, config)
        configurations.append(bind(path))
    source = Path(base['public_source'])
    docs = REPO / 'framework/benchmarks/brainpec_real'
    input_records = [base[name] for name in ('train_input', 'validation_input', 'test_input',
        'train_truth', 'split_manifest', 'runtime_manifest', 'isolation_report')]
    input_records.extend(base['truth_by_split'].values())
    records = [bind(protocol_path), bind(skill), *configurations,
        *[bind(source / name) for name in base['public_files']],
        *[bind(docs / name) for name in ('TASK.md','INTERFACE.md','API_README.md','PUBLIC_RESULT_SCHEMA.md')],
        *[bind(path) for path in sorted((REPO / 'framework/eegfm').rglob('*.py'))],
        bind(Path(__file__)), *input_records]
    verify(records)
    seal = {'version': 'real-comparison-seal-v2', 'protocol': protocol,
        'bindings': records, 'previous_seal': bind(WORK / 'controller/EXPERIMENT_FREEZE.json'),
        'previous_result': bind(WORK / 'episodes/E01/EPISODE_RESULT.json'),
        'reference_unchanged': True, 'actor_started': False,
        'semantic_calibration': 'pending'}
    save_new(CONTROLLER / 'EXPERIMENT_FREEZE.json', seal)
    print(json.dumps({'status': 'enrolled', 'seal_sha256': digest_file(CONTROLLER / 'EXPERIMENT_FREEZE.json')}))


def run(episode: str) -> None:
    seal = json.loads((CONTROLLER / 'EXPERIMENT_FREEZE.json').read_text())
    verify(seal['bindings'])
    rows = seal['protocol']['condition_order']
    if episode not in [row['episode_id'] for row in rows]:
        raise ValueError('Episode is not enrolled')
    position = [row['episode_id'] for row in rows].index(episode)
    if position:
        prior = json.loads((WORK / 'episodes' / rows[position - 1]['episode_id'] / 'EPISODE_RESULT.json').read_text())
        if prior['state']['status'] not in {'done', 'blocked'}:
            raise ValueError('Predeclared condition order not satisfied')
    if episode != 'E05':
        baseline = json.loads((WORK / 'episodes/E05/EPISODE_RESULT.json').read_text())
        if baseline['state']['status'] != 'done':
            raise ValueError('E05 real lifecycle admission not satisfied')
    config = json.loads((CONTROLLER / (episode + '.json')).read_text())
    budget = json.loads(Path(config['budget_path']).read_text())
    required = (2 if episode == 'E07' else 1) * seal['protocol']['episode_wall_seconds']
    remaining = (datetime.fromisoformat(budget['stop_new_research_at']) - datetime.now(timezone.utc)).total_seconds()
    if remaining < required and not (Path(config['trusted_root']) / 'ENROLLMENT.json').exists():
        raise ValueError('Insufficient worst-case time for admitted episode/pair before closeout')
    print(json.dumps(run_episode(config)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('enroll', 'run'))
    parser.add_argument('--episode')
    args = parser.parse_args()
    if args.action == 'enroll':
        enroll()
    elif args.episode:
        run(args.episode)
    else:
        parser.error('--episode is required for run')


if __name__ == '__main__':
    main()
