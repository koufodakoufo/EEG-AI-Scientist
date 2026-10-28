from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from eegfm.research_bench.replay import freeze_submission,validate_commands


class ReplayContractTests(unittest.TestCase):
    def command(self) -> dict:
        return {'command_id':'c1','argv':['python3','output/analysis.py'],'artifacts':['metrics.json']}
    def test_no_shell_inline_or_parent_execution(self) -> None:
        for argv in [['sh','-c','true'],['python3','-c','print(1)'],['python3','../private/eval.py'],['python3','/private/eval.py']]:
            command=self.command(); command['argv']=argv
            with self.subTest(argv=argv),self.assertRaises(ValueError): validate_commands([command])
    def test_duplicate_and_escape_artifacts(self) -> None:
        command=self.command()
        with self.assertRaises(ValueError): validate_commands([command,command])
        command['artifacts']=['../private/gold.json']
        with self.assertRaises(ValueError): validate_commands([command])

    def test_second_command_cannot_claim_first_commands_old_output(self) -> None:
        first=self.command(); second={**self.command(),'command_id':'c2','argv':['python3','output/noop.py']}
        with self.assertRaisesRegex(ValueError,'multiple commands'):
            validate_commands([first,second])
    def test_freeze_preserves_and_cannot_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); output=root/'output'; output.mkdir()
            (output/'metrics.json').write_text('{"accuracy":0.5}')
            manifest=freeze_submission(output,root/'frozen')
            self.assertEqual(len(manifest['files']),1)
            self.assertEqual((root/'frozen/metrics.json').read_text(),(output/'metrics.json').read_text())
            with self.assertRaises(ValueError): freeze_submission(output,root/'frozen')


if __name__=='__main__': unittest.main()
