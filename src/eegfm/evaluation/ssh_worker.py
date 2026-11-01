"""Fixed SSH transport to the enrolled cloud scientific evaluator.

Only the trusted controller uses this module. SSH authentication stays outside
the scientific container. The RPC accepts no command, module, config or host
path from a request. Candidate bytes are ordinary files, never an archive.
"""
from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any

from eegfm.agent.controller import EvaluationSpec
from eegfm.evaluation.bundle import canonical_bytes, digest_file, safe_relative
from eegfm.evaluation.worker import (FileBinding, RuntimeConfig, SandboxedWorkerEvaluator,
                                     SplitInputs, _id, _path, _sha, _tree, candidate_digest)

MAX_CANDIDATE = 64 * 1024**2
MAX_REQUEST = 90 * 1024**2
SPEC_FIELDS = {'job_id', 'episode_id', 'run_id', 'attempt_id', 'split', 'candidate_digest',
               'split_manifest_sha256', 'public_manifest_sha256'}


class TransportUncertain(RuntimeError):
    """No authoritative response; the same job must only be polled."""


def encode_candidate(root: Path, digest: str) -> list[dict[str, str]]:
    if candidate_digest(root) != _sha(digest):
        raise ValueError('Candidate changed before SSH transfer')
    files = [{'path': item['path'], 'data': base64.b64encode((root / item['path']).read_bytes()).decode('ascii')}
             for item in _tree(root)]
    if candidate_digest(root) != digest:
        raise ValueError('Candidate changed during SSH transfer')
    return files


def stage_candidate(root: Path, digest: str, files: list[dict[str, str]]) -> Path:
    _sha(digest)
    if not isinstance(files, list) or not 1 <= len(files) <= 256:
        raise ValueError('Candidate file count exceeded')
    root = root.absolute()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    _path(root, directory=True)
    decoded: dict[str, bytes] = {}
    total = 0
    for item in files:
        if not isinstance(item, dict) or set(item) != {'path', 'data'}:
            raise ValueError('Unexpected candidate file fields')
        name = item['path']
        relative = safe_relative(name)
        if (name in decoded or any(part.startswith('.') for part in relative.parts)
                or not isinstance(item['data'], str) or len(item['data']) > MAX_REQUEST):
            raise ValueError('Invalid candidate path/content')
        try:
            raw = base64.b64decode(item['data'], validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError('Invalid candidate encoding') from error
        total += len(raw)
        if total > MAX_CANDIDATE:
            raise ValueError('Candidate byte budget exceeded')
        decoded[name] = raw
    if 'main.py' not in decoded:
        raise ValueError('Missing candidate entrypoint')
    target = root / digest
    if target.exists() or target.is_symlink():
        if candidate_digest(target) != digest:
            raise ValueError('Existing sealed candidate changed')
        # Even duplicate requests must bind their submitted bytes to the digest.
        manifest = [{'path': name, 'bytes': len(decoded[name]), 'sha256': hashlib.sha256(decoded[name]).hexdigest()}
                    for name in sorted(decoded, key=Path)]
        if hashlib.sha256(canonical_bytes(manifest)).hexdigest() != digest:
            raise ValueError('Duplicate candidate differs')
        return target
    stage = Path(tempfile.mkdtemp(prefix='.upload-', dir=root))
    try:
        for name, raw in decoded.items():
            path = stage / safe_relative(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as handle:
                handle.write(raw)
        if candidate_digest(stage) != digest:
            raise ValueError('Transferred candidate digest mismatch')
        try:
            stage.rename(target)
        except FileExistsError:
            if candidate_digest(target) != digest:
                raise ValueError('Concurrent candidate differs')
        return target
    finally:
        if stage.exists():
            shutil.rmtree(stage)  # Newly created private upload directory only.


def ssh_command(*, host: str, port: int, user: str, known_hosts: Path,
                python: Path, code: Path, config: Path, config_sha256: str,
                ssh: Path = Path('/usr/bin/ssh')) -> list[str]:
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host)
            or not re.fullmatch(r'[a-z_][a-z0-9_-]*', user)
            or type(port) is not int or not 1 <= port <= 65535):
        raise ValueError('Invalid fixed SSH endpoint')
    for path in (python, code, config, known_hosts, ssh):
        if not PurePosixPath(str(path)).is_absolute() or any(char in str(path) for char in '\n\r\x00'):
            raise ValueError('Explicit absolute trusted SSH paths required')
    remote = ['env', 'PYTHONPATH=' + str(code / 'src'), str(python), '-B', '-m',
              'eegfm.evaluation.ssh_worker', '--config', str(config), '--config-sha256', _sha(config_sha256)]
    return [str(ssh), '-T', '-p', str(port), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
            '-o', 'ForwardAgent=no', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=' + str(known_hosts), user + '@' + host, shlex.join(remote)]


class SshWorkerEvaluator:
    sandboxed = True

    def __init__(self, *, host: str, port: int, user: str, known_hosts: FileBinding,
                 remote_python: Path, remote_code: Path, remote_config: FileBinding,
                 journal_root: Path,
                 ssh: Path = Path('/usr/bin/ssh')) -> None:
        self.known_hosts, self.ssh = known_hosts, ssh
        self.deadline_epoch: float | None = None
        known_hosts.verify()
        self.ssh_sha256 = digest_file(ssh.resolve(strict=True))
        self.command = ssh_command(host=host, port=port, user=user, known_hosts=known_hosts.path,
            python=remote_python, code=remote_code, config=remote_config.path,
            config_sha256=remote_config.sha256, ssh=ssh)
        self.identity = self._rpc({'operation': 'enrollment'}, timeout=60)
        self.timeout = self.identity['timeout_seconds']
        if type(self.timeout) is not int or not 0 < self.timeout <= 1800:
            raise ValueError('Invalid remote worker deadline')
        self.operation_timeout_seconds = self.timeout + 180
        if not journal_root.is_absolute():
            raise ValueError('Absolute local worker journal required')
        journal_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        _path(journal_root, directory=True)
        self.database = journal_root / 'jobs.sqlite3'
        self.identity_hash = hashlib.sha256(canonical_bytes(self.identity)).hexdigest()
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, spec TEXT NOT NULL, enrollment TEXT NOT NULL, result TEXT)')

    def _rpc(self, request: dict[str, Any], *, timeout: int) -> dict[str, Any]:
        self.known_hosts.verify()
        if digest_file(self.ssh.resolve(strict=True)) != self.ssh_sha256:
            raise ValueError('SSH binary changed')
        payload = canonical_bytes(request)
        if len(payload) > MAX_REQUEST:
            raise ValueError('SSH request byte budget exceeded')
        if self.deadline_epoch is not None:
            timeout = min(timeout, self.deadline_epoch - time.time())
            if timeout <= 0:
                raise TransportUncertain('Episode deadline reached; remote outcome remains unconfirmed')
        try:
            response = subprocess.run(self.command, input=payload, capture_output=True, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError) as error:
            raise TransportUncertain('Cloud worker response unavailable') from error
        if response.returncode != 0 or len(response.stdout) > 8 * 1024**2:
            raise TransportUncertain('Trusted cloud worker RPC response unavailable')
        try:
            value = json.loads(response.stdout)
        except (ValueError, UnicodeError) as error:
            raise TransportUncertain('Cloud worker response incomplete') from error
        if not isinstance(value, dict):
            raise TransportUncertain('Invalid cloud worker response')
        return value

    def _enrollment(self) -> dict[str, Any]:
        if self._rpc({'operation': 'enrollment'}, timeout=60) != self.identity:
            raise ValueError('Cloud worker enrollment changed')
        return {'transport': 'ssh-scientific-worker-v1', 'command': self.command,
                'ssh_sha256': self.ssh_sha256, 'known_hosts_sha256': self.known_hosts.sha256,
                'client_source_sha256': digest_file(Path(__file__)), 'remote': self.identity}

    def submit(self, spec: EvaluationSpec) -> dict[str, Any]:
        record = {name: getattr(spec, name) for name in SPEC_FIELDS}
        files = encode_candidate(spec.candidate_dir, spec.candidate_digest)
        _id(spec.job_id)
        # Commit the single submission opportunity before any network activity.
        # A crash before delivery is conservative: unknown remote jobs stay
        # uncertain until the enclosing episode deadline; never resubmit them.
        with closing(sqlite3.connect(self.database, timeout=30)) as db, db:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT spec,enrollment FROM jobs WHERE id=?', (spec.job_id,)).fetchone()
            if previous:
                if json.loads(previous[0]) != record or previous[1] != self.identity_hash:
                    raise ValueError('SSH job identity reused')
            else:
                db.execute('INSERT INTO jobs VALUES(?,?,?,NULL)',
                           (spec.job_id, canonical_bytes(record).decode(), self.identity_hash))
        if previous:
            return self.poll(spec.job_id)
        try:
            self._enrollment()
            result = self._rpc({'operation': 'submit', 'spec': record, 'files': files}, timeout=self.timeout + 120)
        except TransportUncertain:
            return self._waiting(record)
        return self._accept(record, result)

    def poll(self, job_id: str) -> dict[str, Any]:
        with closing(sqlite3.connect(self.database)) as db:
            row = db.execute('SELECT spec,enrollment,result FROM jobs WHERE id=?', (_id(job_id),)).fetchone()
        if row is None:
            raise ValueError('Unknown local SSH worker job')
        if row[1] != self.identity_hash:
            raise ValueError('SSH job enrollment changed')
        record = json.loads(row[0])
        try:
            self._enrollment()
            if row[2] is not None:
                return json.loads(row[2])
            result = self._rpc({'operation': 'poll', 'job_id': job_id}, timeout=60)
        except TransportUncertain:
            return json.loads(row[2]) if row[2] is not None else self._waiting(record)
        if result == {'rpc_status': 'unknown_job', 'job_id': job_id}:
            return self._waiting(record)
        return self._accept(record, result)

    @staticmethod
    def _waiting(record: dict[str, Any]) -> dict[str, Any]:
        return {'job_id': record['job_id'], 'candidate_digest': record['candidate_digest'],
                'split': record['split'], 'status': 'waiting', 'metrics': {}, 'artifacts': [],
                'sandbox_receipt': 'ssh:awaiting-authoritative-result:' + record['job_id']}

    def _accept(self, record: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        if (any(result.get(key) != record[key] for key in ('job_id', 'candidate_digest', 'split'))
                or result.get('status') not in {'waiting', 'succeeded', 'failed'}):
            raise ValueError('Cloud worker result identity changed')
        if result['status'] != 'waiting':
            with closing(sqlite3.connect(self.database, timeout=30)) as db, db:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('BEGIN IMMEDIATE')
                prior = db.execute('SELECT result FROM jobs WHERE id=?', (record['job_id'],)).fetchone()[0]
                if prior is not None and json.loads(prior) != result:
                    raise ValueError('Cloud worker terminal result changed')
                db.execute('UPDATE jobs SET result=? WHERE id=?', (canonical_bytes(result).decode(), record['job_id']))
        return result


def scientific_identity(config: dict[str, Any], *, aggregate: Any,
                        public_manifest_sha256: str, split_manifest_sha256: str) -> dict[str, Any]:
    """Bind roles and scoring semantics across machines, independently of paths."""
    from eegfm.eeg.aggregation import LAYERS, FEATURE_COLUMNS
    return {'episode_id': config['episode_id'], 'run_id': config['run_id'],
            'public_manifest_sha256': public_manifest_sha256, 'split_manifest_sha256': split_manifest_sha256,
            'truth_roles': {'train_truth': aggregate.train_truth.sha256,
                'truth_by_split': {name: binding.sha256 for name, binding in sorted(aggregate.truth.items())}},
            'scoring_policy': {'schema': 'scientific_aggregate_v1',
                'bootstrap_resamples': aggregate.bootstrap_resamples, 'seed': 20261029,
                'layers': list(LAYERS), 'feature_columns': list(FEATURE_COLUMNS),
                'released_metrics': sorted(aggregate.released_metrics),
                'selection_candidates': sorted(aggregate.selection)}}


def load_worker(config_binding: FileBinding) -> tuple[dict[str, Any], SandboxedWorkerEvaluator]:
    """Config is fixed by trusted CLI arguments and independently hash-bound."""
    from eegfm.eeg.aggregation import ScientificAggregator
    path = config_binding.verify()
    if path.stat().st_size > 1024**2:
        raise ValueError('Cloud config byte limit exceeded')
    config = json.loads(path.read_text())
    if config.get('schema_version') != 'ssh_scientific_worker_v1':
        raise ValueError('Unknown cloud worker configuration')
    for key in ('episode_id', 'run_id'):
        _id(config[key])
    def binding(value: dict[str, str]) -> FileBinding:
        if set(value) != {'path', 'sha256'} or not Path(value['path']).is_absolute():
            raise ValueError('Explicit cloud binding required')
        result = FileBinding(Path(value['path']), _sha(value['sha256']))
        result.verify()
        return result
    for key in ('staging_root', 'private_root', 'public_root'):
        if not Path(config[key]).is_absolute():
            raise ValueError('Absolute cloud root required')
    truth = {name: binding(value) for name, value in config['truth_by_split'].items()}
    aggregate = ScientificAggregator(truth, binding(config['train_truth']),
                                    bootstrap_resamples=config.get('bootstrap_resamples', 2000))
    runtime = config['runtime']
    split = binding(config['split_manifest'])
    worker = SandboxedWorkerEvaluator(private_root=Path(config['private_root']), public_root=Path(config['public_root']),
        public_manifest_sha256=config['public_manifest_sha256'], split_manifest_path=split.path, split_manifest_sha256=split.sha256,
        inputs_by_split={name: SplitInputs(binding(pair['train']), binding(pair['evaluation']))
                        for name, pair in config['inputs_by_split'].items()},
        runtime=RuntimeConfig(bwrap=None, python=Path(runtime['python']), backend='docker',
            docker=Path(runtime['docker']), docker_image=runtime['image'], docker_host=runtime['host']),
        aggregate=aggregate, released_metrics=aggregate.released_metrics, aggregate_bindings=aggregate.bindings,
        aggregate_policy_sha256=aggregate.policy_sha256, timeout_seconds=config.get('timeout_seconds', 900),
        minimum_free_bytes=config.get('minimum_free_bytes', 20 * 1024**3))
    return config, worker


def handle_request(config_binding: FileBinding, request: dict[str, Any]) -> dict[str, Any]:
    config, worker = load_worker(config_binding)
    operation = request.get('operation')
    if operation == 'enrollment' and set(request) == {'operation'}:
        return {'config_sha256': config_binding.sha256, 'rpc_source_sha256': digest_file(Path(__file__)),
                'timeout_seconds': worker.timeout, 'worker': worker._enrollment(),
                **scientific_identity(config, aggregate=worker.aggregate,
                    public_manifest_sha256=worker.public_hash, split_manifest_sha256=worker.split_hash)}
    if operation == 'poll' and set(request) == {'operation', 'job_id'}:
        try:
            return worker.poll(_id(request['job_id']))
        except ValueError as error:
            if str(error) == 'Unknown worker job':
                return {'rpc_status': 'unknown_job', 'job_id': request['job_id']}
            raise
    if operation != 'submit' or set(request) != {'operation', 'spec', 'files'}:
        raise ValueError('Only fixed enrollment, submit and poll RPC operations exist')
    record = request['spec']
    if not isinstance(record, dict) or set(record) != SPEC_FIELDS:
        raise ValueError('Unexpected evaluation specification fields')
    for name in ('job_id', 'episode_id', 'run_id', 'attempt_id'):
        _id(record[name])
    if record['episode_id'] != config['episode_id'] or record['run_id'] != config['run_id']:
        raise ValueError('Evaluation belongs to a different enrolled episode')
    if (record['split'] not in {'validation', 'test'}
            or record['public_manifest_sha256'] != worker.public_hash
            or record['split_manifest_sha256'] != worker.split_hash):
        raise ValueError('Evaluation differs from fixed cloud data binding')
    candidate = stage_candidate(Path(config['staging_root']), record['candidate_digest'], request['files'])
    return worker.submit(EvaluationSpec(candidate_dir=candidate, **record))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--config-sha256', required=True)
    args = parser.parse_args()
    raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
    if len(raw) > MAX_REQUEST:
        raise ValueError('RPC request too large')
    result = handle_request(FileBinding(args.config, _sha(args.config_sha256)), json.loads(raw))
    sys.stdout.buffer.write(canonical_bytes(result))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('Trusted cloud worker request rejected', file=sys.stderr)
        raise SystemExit(2)
