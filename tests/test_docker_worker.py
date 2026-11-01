"""Docker boundary contracts plus explicitly enabled Linux execution canaries."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == 'linux', 'Linux Docker worker')
class DockerContractTests(unittest.TestCase):
    def backend(self):
        self.assertIsNotNone(importlib.util.find_spec("eegfm.evaluation.docker_worker"),
                             "Docker backend has not been implemented")
        from eegfm.evaluation.docker_worker import DockerBackend
        return DockerBackend(Path("/usr/bin/docker"), "sha256:" + "a" * 64,
                             "unix:///var/run/docker.sock", Path("/usr/local/bin/python"))

    def test_backend_rejects_mutable_image_or_remote_daemon(self):
        backend = self.backend()
        for image, host in (("python:latest", backend.host), (backend.image, "tcp://host:2375")):
            with self.assertRaises(ValueError):
                type(backend)(backend.client, image, host, backend.python)

    def test_command_has_only_selected_bindings_and_trusted_supervisor(self):
        backend = self.backend()
        command = backend.create_command(Path("/owned/job"), "f" * 64, "validation", 30)
        joined = " ".join(command)
        for flag in ("--network none", "--read-only", "--cap-drop ALL", "--security-opt no-new-privileges",
                     "--user 65534:65534"):
            self.assertIn(flag, joined)
        self.assertEqual(command[-4:], ['/opt/eegfm/docker_worker.py', '--supervise', '30', 'validation'])
        # Rootless daemon has no cgroups: flag acceptance cannot prove limits.
        self.assertNotIn('--memory', command)
        mounts = [command[i + 1] for i, word in enumerate(command) if word == "--mount"]
        self.assertEqual(len(mounts), 4)
        self.assertTrue(all("source=/owned/job/" in mount for mount in mounts))
        self.assertEqual(sum("readonly" in mount for mount in mounts), 3)
        self.assertNotIn("docker.sock", " ".join(mounts))
        self.assertNotIn("test.npz", joined)

    def test_image_without_matching_supervisor_is_rejected(self):
        backend = self.backend()
        image = {'Id':backend.image,'Architecture':'amd64','Config':{'Labels':{}}}
        with patch('eegfm.evaluation.docker_worker.subprocess.check_output', return_value=json.dumps([image]).encode()):
            with self.assertRaises(ValueError):
                backend.inspect_image()

    def test_cleanup_refuses_other_owner(self):
        backend = self.backend()
        other = {'Id':'b'*64,'Config':{'Labels':{'eegfm.worker.owner':'c'*64}}}
        with patch('eegfm.evaluation.docker_worker.subprocess.check_output', return_value=json.dumps([other]).encode()):
            with self.assertRaises(ValueError):
                backend.remove_owned('b'*64, 'd'*64)

    def test_cleanup_is_idempotent_after_verified_absence(self):
        backend = self.backend()
        import subprocess
        error = subprocess.CalledProcessError(1, ['docker'], stderr=b'Error: No such object: '+b'b'*64)
        with patch('eegfm.evaluation.docker_worker.subprocess.check_output', side_effect=error):
            backend.remove_owned('b'*64, 'd'*64)

    def test_runtime_rejects_host_environment_mounts_for_docker(self):
        self.backend()
        from eegfm.evaluation.worker import RuntimeConfig
        with self.assertRaises(ValueError):
            RuntimeConfig(bwrap=None, python=Path("/usr/local/bin/python"), backend="docker",
                          docker=Path("/usr/bin/docker"), docker_image="sha256:" + "a" * 64,
                          environment_roots=(Path("/owned/environment"),))


import hashlib
import os
import shutil
import subprocess
import tempfile
import time


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('EEGFM_DOCKER_IMAGE'), 'Explicit Linux image canary')
class DockerExecutionTests(unittest.TestCase):
    def setUp(self):
        from test_real_worker import WorkerTests
        from eegfm.evaluation.worker import RuntimeConfig
        self.fixture = WorkerTests()
        self.fixture.setUp()
        self.addCleanup(self.clean_fixture)
        self.runtime = RuntimeConfig(bwrap=None, python=Path('/usr/local/bin/python'), backend='docker',
            docker=Path('/usr/bin/docker'), docker_image=os.environ['EEGFM_DOCKER_IMAGE'])
        self.fixture.runtime = lambda: self.runtime

    def clean_fixture(self):
        # Only directories created by this test and owned by its UID need reset.
        for entry in self.fixture.root.rglob('*'):
            if not entry.is_symlink() and entry.is_dir() and entry.stat().st_uid == os.getuid():
                entry.chmod(0o700)
        self.fixture.doCleanups()

    def run_candidate(self, source, timeout=30):
        (self.fixture.candidate/'main.py').write_text(source)
        evaluator = self.fixture.evaluator()
        evaluator.timeout = timeout
        result = evaluator.submit(self.fixture.spec())
        return evaluator, result

    def assert_removed(self, evaluator):
        job = evaluator.job_directory('job-validation')
        identity = json.loads((job/'container.json').read_text())
        check = subprocess.run(evaluator.docker.command('inspect', identity['id']), capture_output=True)
        self.assertNotEqual(check.returncode, 0)
        self.assertIn(b'No such', check.stderr)
        return job

    def test_science_and_kernel_boundaries(self):
        hidden = self.fixture.root/'private-canary.txt'
        hidden.write_text('not mounted')
        source = '''import errno, json, mmap, os, pathlib, resource, socket, threading
import numpy as np, scipy, sklearn, torch, mne
from sklearn.linear_model import LogisticRegression
assert os.getuid() == 65534
assert len(os.sched_getaffinity(0)) == 4
assert resource.getrlimit(resource.RLIMIT_AS) == (12884901888, 12884901888)
assert resource.getrlimit(resource.RLIMIT_NPROC) == (128, 128)
assert not pathlib.Path(HIDDEN).exists()
assert not pathlib.Path('/var/run/docker.sock').exists()
assert not pathlib.Path('/inputs/test.npz').exists()
assert not any(k in os.environ for k in ['OPENAI_API_KEY','ANTHROPIC_API_KEY','AWS_SECRET_ACCESS_KEY'])
def denied(fn):
    try: fn()
    except (PermissionError, OSError, ValueError): return
    raise AssertionError('boundary allowed')
denied(lambda: os.fork())
denied(lambda: os.kill(1, 9))
denied(lambda: os.sched_setaffinity(0, os.sched_getaffinity(0)))
denied(lambda: resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY)))
denied(lambda: mmap.mmap(-1, 13*1024**3))
denied(lambda: pathlib.Path('/proc/1/mem').read_bytes())
for path in ['/candidate/probe','/public/probe','/inputs/train.npz','/root/probe']:
    denied(lambda: pathlib.Path(path).write_text('forbidden'))
denied(lambda: socket.socket())
denied(lambda: socket.socketpair())
if hasattr(os, 'pidfd_open'):
    import ctypes
    libc=ctypes.CDLL(None,use_errno=True)
    pidfd=os.pidfd_open(1)
    assert libc.syscall(424,pidfd,0,0,0) == -1 and ctypes.get_errno() == errno.EPERM
    os.close(pidfd)
threads = [threading.Thread(target=lambda: sum(range(100))) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
x=np.array([[-2.,0.],[-1.,1.],[1.,0.],[2.,1.]])
model=LogisticRegression().fit(x,np.array([0,0,1,1]))
assert model.score(x,[0,0,1,1]) == 1.
torch.set_num_threads(4)
assert torch.mm(torch.ones(4,4),torch.ones(4,4)).sum().item() == 64.
pathlib.Path('/out/proof.json').write_text(json.dumps({'numpy':np.__version__,'sklearn':sklearn.__version__,'torch':torch.__version__,'mne':mne.__version__}))
'''.replace('HIDDEN', repr(str(hidden)))
        evaluator, result = self.run_candidate(source)
        self.assertEqual(result['status'], 'succeeded', result)
        job = self.assert_removed(evaluator)
        proof = json.loads((job/'out/proof.json').read_text())
        self.assertEqual(proof['torch'], '2.6.0+cpu')
        self.assertNotEqual((job/'out/proof.json').stat().st_uid, os.getuid())
        self.assertEqual(hidden.read_text(), 'not mounted')
        status = json.loads((job/'execution/status.json').read_text())
        self.assertFalse(status['resource_enforcement']['cgroups'])
        self.assertEqual(status['container_cleanup'], 'verified_removed')

    def test_timeout_removes_container(self):
        evaluator, result = self.run_candidate('import time\ntime.sleep(30)\n', timeout=2)
        self.assertEqual(result['status'], 'failed')
        job = self.assert_removed(evaluator)
        status = json.loads((job/'execution/status.json').read_text())
        self.assertEqual(status['status'], 'timed_out')
        self.assertEqual(status['container_exit_code'], 124)

    def test_output_symlink_cannot_reach_aggregator(self):
        evaluator, result = self.run_candidate("import os\nos.symlink('/etc/passwd','/out/results.npz')\n")
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['metrics'], {})
        self.assert_removed(evaluator)

    def test_unreadable_candidate_output_fails_closed(self):
        evaluator, result = self.run_candidate("from pathlib import Path\np=Path('/out/results.npz')\np.write_bytes(b'not readable')\np.chmod(0)\n")
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['metrics'], {})
        self.assert_removed(evaluator)

    def test_independent_deadline_survives_attached_client_death(self):
        backend = self.fixture.evaluator().docker
        job = self.fixture.root/'detached-job'; job.mkdir(mode=0o700)
        for name in ['candidate','public','out','inputs']: (job/name).mkdir(mode=0o777)
        (job/'out').chmod(0o777)
        (job/'candidate/main.py').write_text('import time\ntime.sleep(30)\n')
        for name in ['train.npz','evaluation.npz']: (job/'inputs'/name).write_bytes(b'fixture')
        fingerprint = hashlib.sha256(str(job).encode()).hexdigest()
        container = subprocess.check_output(backend.create_command(job, fingerprint, 'validation', 2)).decode().strip()
        try:
            attached = subprocess.Popen(backend.command('start','--attach',container), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                state=json.loads(subprocess.check_output(backend.command('inspect',container)))[0]['State']
                if state['Running']: break
                time.sleep(.1)
            self.assertTrue(state['Running'])
            attached.kill(); attached.wait(timeout=5)
            while time.monotonic()<deadline:
                state=json.loads(subprocess.check_output(backend.command('inspect',container)))[0]['State']
                if not state['Running']: break
                time.sleep(.1)
            self.assertFalse(state['Running'])
            self.assertEqual(state['ExitCode'],124)
            self.assertEqual(state['Pid'],0)
        finally:
            backend.remove_owned(container,fingerprint)
