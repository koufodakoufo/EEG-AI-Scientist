"""Complete synthetic transport/lifecycle; no model, SSH, Docker or EEG run.

The existing production scientific worker/scorer and qualification fixture are
used. Container predictions are fixtures. Public fits/refit execute tiny
deterministic fixture source locally, not a scientific candidate or algorithm.
"""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

from eegfm.agent import provider
from eegfm.agent.controller import ResearchDriver
from eegfm.eeg import episode
from eegfm.evaluation import public_workbench
from eegfm.evaluation.bundle import canonical_bytes, digest_file
from eegfm.evaluation.worker import candidate_digest
from test_agent_provider import setup_provider, open_session, call, complete_trace
from test_public_workbench import FakeWorker
from test_residual_recovery_aggregation import _method
from test_residual_recovery_episode import worker_fixture


def test_synthetic_full_path_keeps_two_fits_three_jobs_and_two_replays(tmp_path, monkeypatch, setup_provider):
    worker_root = tmp_path / 'qualified-worker'
    worker_root.mkdir()
    worker, spec = worker_fixture(worker_root, monkeypatch, bundled_text=True)
    qualification_before = digest_file(worker.aggregate.qualification.path)
    with np.load(worker_root / 'output/results.npz', allow_pickle=False) as archive:
        baseline_predictions = archive['predictions'].copy()
    science_jobs = []
    def execute(job, fingerprint, split, *args):
        phase = json.loads((job / 'candidate/method.json').read_text())['phase']
        predictions = baseline_predictions if phase == 'baseline' else np.concatenate([baseline_predictions] * 2, axis=2)
        with np.load(worker.aggregate.inference[split].path, allow_pickle=False) as archive:
            np.savez_compressed(job / 'out/results.npz', predictions=predictions, sample_ids=archive['sample_ids'])
        science_jobs.append(job.name)
        return {'status': 'completed', 'exit_code': 0, 'process_cleanup': {'surviving_owned_pids': []},
                'container_cleanup': 'verified_removed'}
    worker.docker.execute = execute
    case = tmp_path / 'author-case'
    (case / 'output').mkdir(parents=True)
    controller = episode.EpisodeController(trusted_root=tmp_path / 'control', case_root=case,
        episode_id='episode', run_id='run', evaluator=worker, task_id=episode.RESIDUAL_RECOVERY_TASK,
        public_manifest_sha256=worker.public_hash, split_manifest_sha256=worker.split_hash)
    fit_source = '''import argparse, json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--public');p.add_argument('--output');a=p.parse_args()
root=Path(__file__).parent
assert not list(root.rglob('parameters.npz'))
with np.load(Path(a.public)/'train.npz',allow_pickle=False) as z: assert len(z['x']) > 0
values={'linear__selected':np.zeros(5,dtype=np.int64),'linear__coef':np.ones((2,3)),'linear_shuffled__coef':np.zeros((2,3))}
if json.loads((root/'method.json').read_text())['phase']=='final':
    values.update(flexible__selected=np.zeros(5,dtype=np.int64),flexible_shuffled__coef=np.zeros((2,3)))
np.savez(Path(a.output)/'parameters.npz',**values)
'''
    class SyntheticFitWorker(FakeWorker):
        def submit(self, item):
            self.submissions += 1
            assert not list(item.candidate_dir.rglob('parameters.npz'))
            out = tmp_path / item.job_id
            out.mkdir()
            subprocess.run([sys.executable, '-B', str(item.candidate_dir / 'authored/fit.py'),
                '--public', str(worker.public), '--output', str(out)], check=True, capture_output=True, timeout=10)
            return {'job_id': item.job_id, 'candidate_digest': item.candidate_digest, 'split': 'validation',
                    'status': 'succeeded', 'public_artifacts': [public_workbench.encode_parameters(out / 'parameters.npz')]}
    fit_worker = SyntheticFitWorker(worker.public_hash)
    def workbench(staged_case):
        return public_workbench.PublicWorkbench(evaluator=fit_worker, private_root=tmp_path / 'fit-journal' / staged_case.parent.name,
            case_root=staged_case, episode_id='episode', run_id='run', public_manifest_sha256=worker.public_hash,
            split_manifest_sha256=worker.split_hash)
    enrollment = {**setup_provider[2], 'session_timeout_seconds': 1200,
                  'public_resource_delivery': 'manifest_text_bundle_v1'}
    box = provider.ProviderMailbox(root=controller.run / 'provider', case_root=case, public_root=worker.public,
                                   enrollment=enrollment, workbench_factory=workbench)
    stages = []
    def launch(projection):
        sid = projection['provider_session']['reservation_id']
        number = int(sid[-2:])
        stages.append(number)
        open_session(box, timeout=1200, projection=projection, session_id=sid, context_id=f'fresh-{number}')
        def rpc(operation, payload=None):
            result = call(box, operation, payload, session_id=sid)
            assert result['status'] == 'ok', result
            return result['result']
        task = rpc('task')
        assert len(task['public_resource_bundle']['files']) == 7
        def write(path, text):
            offset = 0
            for start in range(0, len(text), 2000):
                part = text[start:start+2000]
                value = rpc('write_chunk', {'path': path, 'offset': offset, 'text': part})
                offset += len(part.encode())
            rpc('seal_file', {'path': path, 'sha256': value['sha256']})
        requests = []
        def request(operation, payload):
            requests.append({'request_id': f'{sid}-{operation}', 'episode_id': 'episode',
                             'operation': operation, 'payload': payload})
        if number == 1:
            write('brief.md', '```json\n' + json.dumps(episode.task_scope(episode.RESIDUAL_RECOVERY_TASK))
                  + '\n```\nSynthetic transport exercise with fixture data; no scientific inference is being tested.\n')
            request('brief', {'path': 'brief.md'})
        elif number in (2, 4):
            phase = 'baseline' if number == 2 else 'final'
            if number == 2:
                request('contract', {'protocol': {**episode.task_scope(episode.RESIDUAL_RECOVERY_TASK), 'research_mode': 'analysis'}})
            method, _ = _method(phase)
            write(f'{phase}/method.json', canonical_bytes(method).decode())
            write(f'{phase}/linear.py', (spec.candidate_dir / 'linear.py').read_text())
            write(f'{phase}/main.py', '# synthetic container output supplied by fixture\n')
            write(f'{phase}/fit.py', fit_source)
            assert rpc('fit_submit', {'job_id': 'public-fit', 'candidate_dir': phase})['status'] == 'succeeded'
            request('baseline' if number == 2 else 'attempt', {'candidate_dir': phase, 'split': 'validation', 'title': phase})
        elif number == 3:
            write('checkpoint.md', 'Continue from the accepted baseline; this clean checkpoint grants no new fit.\n')
        elif number == 5:
            selected = projection['attempts'][-1]
            request('lock', {'attempt_id': selected['id'], 'candidate_digest': selected['candidate_digest']})
            request('test', {'candidate_digest': selected['candidate_digest'], 'split': 'test'})
        elif number == 6:
            assert (box._pending_root(sid) / 'checkpoint.md').exists()
            write('REPORT.md', 'Synthetic full-path fixture report; no scientific conclusions.\n')
            request('report', {'path': 'REPORT.md'})
        else:
            raise AssertionError('No seventh session')
        rpc('seal_session', {'requests': requests})
        return box.accept_trace(sid, complete_trace(box, session_id=sid))
    driver = ResearchDriver(controller, launch=launch, session_provider=provider.PROVIDER,
        provider_model=enrollment['model'], provider_timeout_seconds=1200,
        reviewer=lambda projection: episode.review_brief(controller, projection))
    from eegfm.agent.driver import Driver
    assert Driver.loop(driver) == 0  # portable shared loop; no Linux lease or model is invoked
    assert stages == list(range(1, 7)) and fit_worker.submissions == 2 and len(science_jobs) == 3
    assert controller.projection()['state']['status'] == 'done'
    assert (controller.run / 'FINAL_REPORT.md').read_text().startswith('Synthetic full-path')
    with box.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM fits').fetchone()[0] == 2
    # Two separate replay fixtures: refit from text-only source, then forward
    # through the same production worker/scorer using rebuilt parameters.
    rebuilt = tmp_path / 'replay-candidate'
    shutil.copytree(case / 'output/final', rebuilt, ignore=shutil.ignore_patterns('parameters.npz'))
    refit = tmp_path / 'replay-refit'
    refit.mkdir()
    subprocess.run([sys.executable, '-B', str(rebuilt / 'fit.py'), '--public', str(worker.public),
                    '--output', str(refit)], check=True, capture_output=True, timeout=10)
    with np.load(refit / 'parameters.npz', allow_pickle=False) as actual, np.load(case / 'output/final/parameters.npz', allow_pickle=False) as original:
        assert actual.files == original.files
        assert all(np.array_equal(actual[name], original[name]) for name in actual.files)
    shutil.copyfile(refit / 'parameters.npz', rebuilt / 'parameters.npz')
    replay = replace(spec, job_id='independent-rebuilt-forward', attempt_id='replay', split='test',
                     candidate_dir=rebuilt, candidate_digest=candidate_digest(rebuilt))
    assert worker.submit(replay)['status'] == 'succeeded'
    assert len(science_jobs) == 4 and fit_worker.submissions == 2
    assert digest_file(worker.aggregate.qualification.path) == qualification_before
