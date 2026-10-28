from __future__ import annotations
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[3]/'scripts/overnight/prepare_evaluation.py'
spec=importlib.util.spec_from_file_location('overnight_evaluation',SCRIPT)
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class PartialSubmissionTests(unittest.TestCase):
    def test_bad_annex_does_not_erase_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'REPORT.md').write_text('Observed result with uncertainty.',encoding='utf-8')
            (root/'claims.json').write_text('{broken',encoding='utf-8')
            text,claims,meta=module.read_submission(root)
            self.assertEqual(text,'Observed result with uncertainty.')
            self.assertEqual(claims,[]); self.assertTrue(meta['annex_error']); self.assertFalse(meta['report_missing'])

    def test_absent_report_remains_explicit_empty_submission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text,claims,meta=module.read_submission(Path(tmp))
            self.assertEqual((text,claims),('',[])); self.assertTrue(meta['report_missing']); self.assertIsNone(meta['report_sha256'])


if __name__=='__main__': unittest.main()
