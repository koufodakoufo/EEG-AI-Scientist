from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from eegfm.evaluation.bundle import create_public_bundle
from eegfm.evaluation.bundle import freeze_experiment
from eegfm.evaluation.bundle import verify_public_bundle
from eegfm.evaluation.bundle import verify_seal
from eegfm.agent.budget import BudgetExceeded
from eegfm.agent.budget import mark_call
from eegfm.agent.budget import reserve_call
from eegfm.agent.budget import run_bounded
from eegfm.agent.budget import tree_bytes


class BundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'TASK_PUBLIC.md').write_text('Compare hypotheses using the supplied observations.')
        (self.source / 'REFERENCE_PRIVATE.json').write_text('{"private":"hidden"}')

    def export(self) -> Path:
        target = self.root / 'public'
        create_public_bundle(self.source, target, ['TASK_PUBLIC.md'], task_id='fixture', tier='synthetic_mechanism')
        return target

    def test_allowlist_excludes_private_and_checks_mutations(self) -> None:
        target = self.export()
        self.assertFalse((target / 'REFERENCE_PRIVATE.json').exists())
        verify_public_bundle(target)
        (target / 'TASK_PUBLIC.md').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Changed'):
            verify_public_bundle(target)

    def test_private_control_path_and_parent_traversal_rejected(self) -> None:
        for name in ['REFERENCE_PRIVATE.json', '../source/TASK_PUBLIC.md', '.codex/config.toml', 'C:/auth.json']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                create_public_bundle(self.source, self.root / 'public', [name], task_id='x', tier='synthetic_mechanism')

    def test_unlisted_file_and_symlink_rejected(self) -> None:
        target = self.export()
        (target / 'extra.txt').write_text('not frozen')
        with self.assertRaisesRegex(ValueError, 'Unmanifested'):
            verify_public_bundle(target)
        try:
            (self.source / 'alias.txt').symlink_to(self.source / 'TASK_PUBLIC.md')
        except OSError:
            return
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            create_public_bundle(self.source, self.root / 'other', ['alias.txt'], task_id='x', tier='synthetic_mechanism')

    def test_reference_and_policy_freeze_cannot_be_replaced(self) -> None:
        target = self.export()
        reference = self.source / 'REFERENCE_PRIVATE.json'
        seal = self.root / 'trusted/seal.json'
        freeze_experiment(target, reference, {'version':'fire_inspired_v1'}, {'seconds':60}, ['synthetic_mechanism'], seal)
        verify_seal(target, reference, seal)
        with self.assertRaises(FileExistsError):
            freeze_experiment(target, reference, {'version':'changed'}, {'seconds':60}, ['synthetic_mechanism'], seal)
        reference.write_text('{"private":"retrofit"}')
        with self.assertRaisesRegex(ValueError, 'reference changed'):
            verify_seal(target, reference, seal)

    def test_seal_inside_public_rejected(self) -> None:
        target = self.export()
        with self.assertRaisesRegex(ValueError, 'outside'):
            freeze_experiment(target, self.source/'REFERENCE_PRIVATE.json', {'v':1}, {'s':60}, ['synthetic_mechanism'], target/'seal.json')


class BudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root/'budget.json'
        later = (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
        self.path.write_text(json.dumps({'extra_model_calls_max':2,'max_parallel_model_workers':1,
                                        'stop_new_research_at':later,'deadline_at':later,
                                        'per_call_timeout_seconds':1800,'preflight_timeout_seconds':90,'calls':[]}))

    def test_reservations_prevent_duplicate_parallel_and_overbudget(self) -> None:
        reserve_call(self.path,'one','preflight',90)
        with self.assertRaises(BudgetExceeded): reserve_call(self.path,'two','actor',60)
        mark_call(self.path,'one','running')
        mark_call(self.path,'one','completed')
        with self.assertRaises(BudgetExceeded): reserve_call(self.path,'one','actor',60)
        reserve_call(self.path,'two','actor',60)
        mark_call(self.path,'two','blocked',reason='isolation')
        with self.assertRaises(BudgetExceeded): reserve_call(self.path,'three','actor',60)
        self.assertEqual(len(json.loads(self.path.read_text())['calls']),2)

    def test_no_silent_resume_or_timeout_override(self) -> None:
        with self.assertRaises(BudgetExceeded): reserve_call(self.path,'one','preflight',91)
        reserve_call(self.path,'one','actor',60)
        with self.assertRaises(BudgetExceeded): mark_call(self.path,'one','completed')
        with self.assertRaises(ValueError): mark_call(self.path,'one','running',timeout_seconds=9999)

    def test_new_work_deadline(self) -> None:
        state=json.loads(self.path.read_text()); state['stop_new_research_at']='2000-01-01T00:00:00+00:00'
        self.path.write_text(json.dumps(state))
        with self.assertRaises(BudgetExceeded): reserve_call(self.path,'one','actor',60)

    def test_storage_accounting_and_early_stop(self) -> None:
        owned=self.root/'owned'; owned.mkdir()
        (owned/'one').write_bytes(b'1'*32)
        (owned/'two').write_bytes(b'2'*32)
        self.assertEqual(tree_bytes(owned),64)
        self.assertGreater(tree_bytes(owned,stop_above=20),20)

    @unittest.skipUnless(sys.platform=='linux','Linux launcher fault injection')
    def test_output_and_storage_faults(self) -> None:
        output=run_bounded([sys.executable,'-c','import time; print("x"*4096,flush=True); time.sleep(5)'],cwd=self.root,
                           output_dir=self.root/'noisy',timeout_seconds=3,stdout_limit_bytes=1024,minimum_free_bytes=0)
        self.assertEqual(output['status'],'output_exceeded')
        scope=self.root/'scope'; scope.mkdir()
        storage=run_bounded([sys.executable,'-c','from pathlib import Path; import time; Path("large").write_bytes(b"x"*4096); time.sleep(5)'],cwd=scope,
                            output_dir=self.root/'storage',timeout_seconds=3,storage_scope=scope,storage_limit_bytes=1024,minimum_free_bytes=0)
        self.assertEqual(storage['status'],'storage_exceeded')

    @unittest.skipUnless(sys.platform=='linux','Linux bounded stdin transport')
    def test_stdin_large_prompt_is_not_argv(self) -> None:
        source=self.root/'input.txt'; source.write_text('prompt-data-'*20000)
        result=run_bounded([sys.executable,'-c','import sys; print(len(sys.stdin.read()))'],cwd=self.root,
                           output_dir=self.root/'stdin-run',timeout_seconds=2,minimum_free_bytes=0,stdin_path=source)
        self.assertEqual(result['status'],'completed')
        self.assertEqual((self.root/'stdin-run/stdout.jsonl').read_text().strip(),'240000')

    @unittest.skipUnless(sys.platform=='linux','Linux supervisor race regression')
    def test_limit_reason_survives_child_exit_race(self) -> None:
        from unittest.mock import Mock,patch
        child=Mock(pid=123,returncode=0); child.poll.side_effect=[None,0]
        tree=Mock(); tree.rss_bytes.return_value=0; tree.terminate.return_value={'surviving_owned_pids':[]}
        with patch('eegfm.agent.budget.subprocess.Popen',return_value=child), \
             patch('eegfm.agent.processes.OwnedProcessTree',return_value=tree), \
             patch('eegfm.agent.processes.affinity_lock',return_value=lambda:None), \
             patch('eegfm.agent.budget.time.monotonic',side_effect=[0,2,3]):
            report=run_bounded(['fixture'],cwd=self.root,output_dir=self.root/'race',timeout_seconds=1,minimum_free_bytes=0)
        self.assertEqual(report['status'],'timed_out')
        self.assertEqual(report['exit_code'],0)

    @unittest.skipUnless(sys.platform=='linux','Linux launcher enforcement test')
    def test_hard_timeout_and_affinity(self) -> None:
        report=run_bounded([sys.executable,'-c','import time; time.sleep(20)'],cwd=self.root,output_dir=self.root/'run',timeout_seconds=0.4,minimum_free_bytes=0)
        self.assertEqual(report['status'],'timed_out')
        self.assertLess(report['elapsed_seconds'],3)
        self.assertLessEqual(len(report['affinity_cpus']),4)
        with self.assertRaises(FileExistsError):
            run_bounded([sys.executable,'-c','pass'],cwd=self.root,output_dir=self.root/'run',timeout_seconds=1)

    @unittest.skipUnless(sys.platform=='linux','Linux process group test')
    def test_background_children_collected_after_success(self) -> None:
        script='import subprocess,sys; p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"],start_new_session=True); print(p.pid,flush=True)'
        report=run_bounded([sys.executable,'-c',script],cwd=self.root,output_dir=self.root/'children',timeout_seconds=2,minimum_free_bytes=0)
        self.assertEqual(report['status'],'completed')
        self.assertFalse(report['process_cleanup']['surviving_owned_pids'])
        child_pid=int((self.root/'children/stdout.jsonl').read_text())
        status=Path(f'/proc/{child_pid}/stat')
        if status.exists():
            self.assertEqual(status.read_text().rsplit(')',1)[1].split()[0],'Z')

    @unittest.skipUnless(sys.platform=='linux','Linux process-tree RAM monitor')
    def test_new_process_group_memory_is_counted_and_stopped(self) -> None:
        child='import time; x=bytearray(80*1024*1024); time.sleep(20)'
        parent='import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",'+repr(child)+'],start_new_session=True); time.sleep(20)'
        report=run_bounded([sys.executable,'-c',parent],cwd=self.root,output_dir=self.root/'memory',timeout_seconds=3,
                           memory_limit_bytes=64*1024**2,limit_address_space=False,minimum_free_bytes=0)
        self.assertEqual(report['status'],'memory_exceeded')
        self.assertFalse(report['process_cleanup']['surviving_owned_pids'])

    @unittest.skipUnless(sys.platform=='linux','Linux launch disk floor')
    def test_disk_floor_rejects_before_spawn(self) -> None:
        with self.assertRaises(BudgetExceeded):
            run_bounded([sys.executable,'-c','pass'],cwd=self.root,output_dir=self.root/'disk',timeout_seconds=1,minimum_free_bytes=2**100)
        self.assertFalse((self.root/'disk').exists())

    @unittest.skipUnless(sys.platform=='linux','Linux affinity enforcement')
    def test_child_cannot_widen_own_cpu_affinity(self) -> None:
        script='import os,json\ntry:\n os.sched_setaffinity(0,set(range(os.cpu_count()))); denied=False\nexcept PermissionError:\n denied=True\nprint(json.dumps({"denied":denied,"cpus":list(os.sched_getaffinity(0))}))'
        report=run_bounded([sys.executable,'-c',script],cwd=self.root,output_dir=self.root/'cpu',timeout_seconds=2,minimum_free_bytes=0)
        result=json.loads((self.root/'cpu/stdout.jsonl').read_text())
        self.assertTrue(result['denied'])
        self.assertLessEqual(len(result['cpus']),4)
        self.assertEqual(report['status'],'completed')


if __name__ == '__main__':
    unittest.main()
