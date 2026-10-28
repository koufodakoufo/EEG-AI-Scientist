from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from eegfm.research_bench.bundle import create_public_bundle, freeze_experiment, verify_public_bundle, verify_seal
from eegfm.research_bench.budget import BudgetExceeded, mark_call, reserve_call, run_bounded, tree_bytes


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

    @unittest.skipUnless(sys.platform=='linux','Linux launcher enforcement test')
    def test_hard_timeout_and_affinity(self) -> None:
        report=run_bounded([sys.executable,'-c','import time; time.sleep(20)'],cwd=self.root,output_dir=self.root/'run',timeout_seconds=0.4)
        self.assertEqual(report['status'],'timed_out')
        self.assertLess(report['elapsed_seconds'],3)
        self.assertLessEqual(len(report['affinity_cpus']),4)
        with self.assertRaises(FileExistsError):
            run_bounded([sys.executable,'-c','pass'],cwd=self.root,output_dir=self.root/'run',timeout_seconds=1)

    @unittest.skipUnless(sys.platform=='linux','Linux process group test')
    def test_background_children_collected_after_success(self) -> None:
        script='import subprocess,sys; p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"]); print(p.pid,flush=True)'
        report=run_bounded([sys.executable,'-c',script],cwd=self.root,output_dir=self.root/'children',timeout_seconds=2)
        self.assertEqual(report['status'],'completed')
        child_pid=int((self.root/'children/stdout.jsonl').read_text())
        status=Path(f'/proc/{child_pid}/stat')
        if status.exists():
            self.assertEqual(status.read_text().rsplit(')',1)[1].split()[0],'Z')


if __name__ == '__main__':
    unittest.main()
