"""Narrow scientific SSH worker contracts; no model or private data involved."""
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
import base64
import importlib.util
import tempfile
import unittest

class SshWorkerBoundaryTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('eegfm.evaluation.ssh_worker'))
        import eegfm.evaluation.ssh_worker as mod
        return mod

    def test_candidate_roundtrip_preserves_digest_and_is_idempotent(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);candidate=root/'candidate';candidate.mkdir()
            (candidate/'main.py').write_text('print("bounded")\n')
            (candidate/'main').mkdir()
            (candidate/'main/helper.py').write_text('value=1\n')
            digest=mod.candidate_digest(candidate)
            files=mod.encode_candidate(candidate,digest)
            target=mod.stage_candidate(root/'staging',digest,files)
            self.assertEqual(mod.candidate_digest(target),digest)
            self.assertEqual(mod.stage_candidate(root/'staging',digest,files),target)
            (target/'main.py').write_text('tampered')
            with self.assertRaises(ValueError):mod.stage_candidate(root/'staging',digest,files)

    def test_paths_duplicates_and_digest_mismatch_rejected(self):
        mod=self.module()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'stage'
            good={'path':'main.py','data':base64.b64encode(b'pass').decode()}
            for files in ([{**good,'path':'../escape'}],[{**good,'path':'/escape'}],[good,good],[good]):
                with self.subTest(files=files),self.assertRaises(ValueError):
                    mod.stage_candidate(root,'a'*64,files)
            self.assertFalse((root.parent/'escape').exists())

    def test_remote_command_is_fixed_and_agent_not_forwarded(self):
        mod=self.module()
        command=mod.ssh_command(host='127.0.0.1',port=10022,user='duandh',
            known_hosts=PurePosixPath('/owned/known_hosts'),python=PurePosixPath('/owned/python'),
            code=PurePosixPath('/owned/code'),config=PurePosixPath('/owned/config.json'),config_sha256='a'*64,
            ssh=PurePosixPath('/usr/bin/ssh'))
        self.assertIn('ForwardAgent=no',command)
        self.assertIn('StrictHostKeyChecking=yes',command)
        self.assertTrue(command[-1].endswith('--config-sha256 '+'a'*64))
        for host in ('-oProxyCommand=oops','host;uname','host\nother'):
            with self.assertRaises(ValueError):
                mod.ssh_command(host=host,port=22,user='duandh',known_hosts=PurePosixPath('/owned/known_hosts'),
                    python=PurePosixPath('/owned/python'),code=PurePosixPath('/owned/code'),config=PurePosixPath('/owned/config'),
                    config_sha256='a'*64,ssh=PurePosixPath('/usr/bin/ssh'))

import json
import os
import uuid

@unittest.skipUnless(os.environ.get('EEGFM_SSH_CANARY'), 'Explicit trusted SSH canary')
class LiveSshWorkerTests(unittest.TestCase):
    def test_roundtrip_cache_poll_and_fixed_identity(self):
        from eegfm.evaluation.ssh_worker import SshWorkerEvaluator, encode_candidate
        from eegfm.evaluation.worker import FileBinding, candidate_digest
        from eegfm.evaluation.bundle import digest_file, canonical_bytes
        from eegfm.agent.controller import EvaluationSpec
        meta=json.loads(Path(os.environ['EEGFM_SSH_CANARY']).read_text())
        host_keys=Path(meta['known_hosts'])
        journal=tempfile.TemporaryDirectory()
        self.addCleanup(journal.cleanup)
        worker=SshWorkerEvaluator(host='124.174.8.252',port=10022,user='duandh',
            known_hosts=FileBinding(host_keys,digest_file(host_keys)),
            remote_python=Path('/home/duandh/projects/EEG-AI-Scientist/envs/cpu/bin/python'),
            remote_code=Path('/vePFS-0x0d/home/duandh/projects/EEG-AI-Scientist/code'),
            remote_config=FileBinding(Path(meta['remote_config']['path']),meta['remote_config']['sha256']),
            journal_root=Path(journal.name))
        with tempfile.TemporaryDirectory() as temp:
            candidate=Path(temp)
            (candidate/'main.py').write_text("import numpy as np\na=np.load('/inputs/evaluation.npz',allow_pickle=False)\nnp.savez('/out/results.npz',sample_ids=a['sample_ids'],logits=a['x'][:,0])\n")
            spec=EvaluationSpec(job_id='rpc-'+uuid.uuid4().hex,episode_id='transport-canary',run_id='cpu-rpc',attempt_id='baseline',
                split='validation',candidate_dir=candidate,candidate_digest=candidate_digest(candidate),
                public_manifest_sha256=meta['public_manifest_sha256'],split_manifest_sha256=meta['split_manifest_sha256'])
            first=worker.submit(spec)
            self.assertEqual(first['status'],'succeeded',first)
            self.assertEqual(first['metrics']['accuracy'],1.)
            self.assertEqual(first['metrics']['baseline_only'],1.)
            self.assertEqual(worker.submit(spec),first)
            self.assertEqual(worker.poll(spec.job_id),first)
            with self.assertRaises(RuntimeError):
                worker._rpc({'operation':'shell','command':'true'},timeout=60)
            record={name:getattr(spec,name) for name in ['job_id','episode_id','run_id','attempt_id','split','candidate_digest','public_manifest_sha256','split_manifest_sha256']}
            record['episode_id']='different-episode'
            with self.assertRaises(RuntimeError):
                worker._rpc({'operation':'submit','spec':record,'files':encode_candidate(candidate,spec.candidate_digest)},timeout=60)
            if meta.get('report_path'):
                Path(meta['report_path']).write_bytes(canonical_bytes({'purpose':'synthetic infrastructure canary, no model call','result':first,'repeat_submit_identical':True,'poll_identical':True,'arbitrary_operation_rejected':True,'cross_episode_rejected':True,'enrollment':worker._enrollment()}))

class ScientificEnrollmentTests(unittest.TestCase):
    def test_truth_roles_and_path_independent_scoring_policy_are_explicit(self):
        from eegfm.evaluation import ssh_worker as mod
        from eegfm.eeg.aggregation import ScientificAggregator
        from eegfm.evaluation.worker import FileBinding
        self.assertTrue(hasattr(mod,'scientific_identity'),'Role-keyed scientific identity is missing')
        roles={name:FileBinding(Path('/private')/name, digest*64) for name,digest in [('train','a'),('validation','b'),('test','c')]}
        aggregate=ScientificAggregator({'validation':roles['validation'],'test':roles['test']},roles['train'],bootstrap_resamples=7)
        identity=mod.scientific_identity({'episode_id':'episode','run_id':'run'},aggregate=aggregate,
            public_manifest_sha256='d'*64,split_manifest_sha256='e'*64)
        self.assertEqual(identity['truth_roles'],{'train_truth':'a'*64,'truth_by_split':{'validation':'b'*64,'test':'c'*64}})
        self.assertEqual(identity['scoring_policy']['bootstrap_resamples'],7)
        self.assertNotIn('/private',json.dumps(identity['scoring_policy']))
        swapped=ScientificAggregator({'validation':roles['test'],'test':roles['validation']},roles['train'],bootstrap_resamples=8)
        other=mod.scientific_identity({'episode_id':'episode','run_id':'run'},aggregate=swapped,
            public_manifest_sha256='d'*64,split_manifest_sha256='e'*64)
        self.assertNotEqual(identity['truth_roles'],other['truth_roles'])
        self.assertNotEqual(identity['scoring_policy'],other['scoring_policy'])


class SshTransportRecoveryTests(unittest.TestCase):
    def test_real_subprocess_timeout_and_lost_poll_response_preserve_controller_job(self):
        import subprocess,sys
        from unittest.mock import patch
        from test_driver_bridge import DriverBridgeTests
        from eegfm.evaluation.ssh_worker import SshWorkerEvaluator
        from eegfm.evaluation.worker import FileBinding
        from eegfm.evaluation.bundle import digest_file
        fixture=DriverBridgeTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        (fixture.case/'output/candidate/main.py').write_text('pass\n')
        root=fixture.root
        host_keys=root/'known_hosts';host_keys.write_text('fixture public host key')
        server=root/'server.py'
        server.write_text('''import json,sys,time
from pathlib import Path
root=Path(sys.argv[1]);request=json.load(sys.stdin)
op=request['operation']
with (root/'calls.jsonl').open('a') as f:f.write(json.dumps(request)+'\\n')
if op=='enrollment': result={'timeout_seconds':2,'fixture':'fixed'}
elif op=='submit':
 s=request['spec'];result={k:s[k] for k in ['job_id','candidate_digest','split']}
 result.update(status='succeeded',metrics={'accuracy_delta':.5},artifacts=[],sandbox_receipt='fixture-authority')
 (root/'remote-result.json').write_text(json.dumps(result))
 time.sleep(1)
else:
 if (root/'unknown').exists():result={'rpc_status':'unknown_job','job_id':request['job_id']}
 else:result=json.loads((root/'remote-result.json').read_text())
print(json.dumps(result))
''')
        options=dict(host='localhost',port=22,user='test',known_hosts=FileBinding(host_keys,digest_file(host_keys)),
            remote_python=PurePosixPath('/python'),remote_code=PurePosixPath('/code'),
            remote_config=FileBinding(PurePosixPath('/config'),'a'*64),ssh=Path(sys.executable),journal_root=root/'transport-journal')
        command=[sys.executable,str(server),str(root)]
        real_run=subprocess.run
        def interrupted(command,**kwargs):
            operation=json.loads(kwargs['input'])['operation']
            if operation=='submit':kwargs['timeout']=.2
            response=real_run(command,**kwargs)
            if operation=='poll':return subprocess.CompletedProcess(command,0,b'',b'')
            return response
        with patch('eegfm.evaluation.ssh_worker.ssh_command',return_value=command):
            worker=SshWorkerEvaluator(**options)
            fixture.controller.evaluator=worker
            fixture.ready()
            with patch('eegfm.evaluation.ssh_worker.subprocess.run',side_effect=interrupted):
                fixture.candidate()
                self.assertEqual(fixture.controller.projection()['state']['status'],'waiting_job')
                jobs=fixture.controller.poll_jobs()
                self.assertEqual(jobs[0]['status'],'waiting')
                self.assertEqual(fixture.controller.projection()['state']['status'],'waiting_job')
            # A fresh client reconstructs pending identity from its local journal.
            resumed=SshWorkerEvaluator(**options)
            fixture.controller.evaluator=resumed
            import time
            resumed.deadline_epoch=time.time()-1
            before=(root/'calls.jsonl').read_bytes()
            self.assertEqual(fixture.controller.poll_jobs()[0]['status'],'waiting')
            self.assertEqual((root/'calls.jsonl').read_bytes(),before)
            resumed.deadline_epoch=None
            (root/'unknown').touch()
            self.assertEqual(fixture.controller.poll_jobs()[0]['status'],'waiting')
            (root/'unknown').unlink()
            final=fixture.controller.poll_jobs()[0]
            self.assertEqual(final['status'],'succeeded')
            self.assertEqual(final['result']['metrics']['accuracy_delta'],.5)
            with fixture.controller._transaction() as db:
                state=fixture.controller._load(db)
                spec=fixture.controller._spec(state,state['jobs'][final['job_id']])
            self.assertEqual(resumed.submit(spec),final['result'])
        calls=[json.loads(line) for line in (root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(sum(call['operation']=='submit' for call in calls),1)

@unittest.skipUnless(os.environ.get('EEGFM_SSH_CANARY'), 'Explicit trusted SSH recovery canary')
class LiveSshRecoveryTests(unittest.TestCase):
    def test_lost_real_ssh_response_is_reconciled_by_controller(self):
        import subprocess
        from unittest.mock import patch
        from eegfm.agent.controller import ResearchController
        from eegfm.evaluation.ssh_worker import SshWorkerEvaluator
        from eegfm.evaluation.worker import FileBinding
        from eegfm.evaluation.bundle import digest_file, canonical_bytes
        meta=json.loads(Path(os.environ['EEGFM_SSH_CANARY']).read_text())
        host_keys=Path(meta['known_hosts'])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);case=root/'case';candidate=case/'output/candidate';candidate.mkdir(parents=True)
            (candidate/'main.py').write_text("import numpy as np\na=np.load('/inputs/evaluation.npz',allow_pickle=False)\nnp.savez('/out/results.npz',sample_ids=a['sample_ids'],logits=a['x'][:,0])\n")
            worker=SshWorkerEvaluator(host='124.174.8.252',port=10022,user='duandh',
                known_hosts=FileBinding(host_keys,digest_file(host_keys)),
                remote_python=Path('/home/duandh/projects/EEG-AI-Scientist/envs/cpu/bin/python'),
                remote_code=Path('/vePFS-0x0d/home/duandh/projects/EEG-AI-Scientist/code'),
                remote_config=FileBinding(Path(meta['remote_config']['path']),meta['remote_config']['sha256']),
                journal_root=root/'transport-journal')
            controller=ResearchController(trusted_root=root/'controller',case_root=case,
                episode_id='transport-canary',run_id='cpu-rpc',public_manifest_sha256=meta['public_manifest_sha256'],
                split_manifest_sha256=meta['split_manifest_sha256'],evaluator=worker,max_attempts=1)
            def request(name,payload):
                return controller.handle({'request_id':name,'episode_id':'transport-canary','operation':name,'payload':payload})
            (case/'output/brief.md').write_text('Synthetic connection-recovery check; no model or EEG claim.')
            request('brief',{'path':'brief.md'})
            controller.review(approved=True,reviewer_id='fixture-review',policy_sha256='a'*64)
            request('contract',{'protocol':{'research_mode':'analysis','selection_split':'validation'}})
            real_run=subprocess.run;operations=[]
            def lose_response(command,**kwargs):
                operation=json.loads(kwargs['input'])['operation'];operations.append(operation)
                response=real_run(command,**kwargs)
                if operation in {'submit','poll'}:
                    self.assertEqual(response.returncode,0,response.stderr)
                    self.assertEqual(json.loads(response.stdout)['status'],'succeeded')
                    return subprocess.CompletedProcess(command,255,b'',b'synthetic dropped reply after real remote completion')
                return response
            with patch('eegfm.evaluation.ssh_worker.subprocess.run',side_effect=lose_response):
                request('baseline',{'candidate_dir':'candidate','split':'validation','title':'synthetic transport'})
                self.assertEqual(controller.projection()['state']['status'],'waiting_job')
                self.assertEqual(controller.poll_jobs()[0]['status'],'waiting')
            final=controller.poll_jobs()[0]
            self.assertEqual(final['status'],'succeeded')
            self.assertEqual(final['result']['metrics']['accuracy'],1.)
            self.assertEqual(operations.count('submit'),1)
            unknown=worker._rpc({'operation':'poll','job_id':'never-submitted-canary'},timeout=60)
            self.assertEqual(unknown,{'rpc_status':'unknown_job','job_id':'never-submitted-canary'})
            if meta.get('report_path'):
                Path(meta['report_path']).with_name('ssh-worker-loss-report.json').write_bytes(canonical_bytes({
                    'purpose':'real SSH response-loss engineering canary, no model call',
                    'submit_requests':operations.count('submit'),'controller_waited_after_submit_loss':True,
                    'controller_waited_after_poll_loss':True,'authoritative_final_result':final['result'],
                    'unknown_remote_job_remains_unknown':True,'enrollment':worker._enrollment()}))
