"""Finite controlled CPU validation; never launches research or publishes requests."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import time
import unittest

import torch
import yaml


def main():
    root=Path(__file__).resolve().parent
    started=time.monotonic()
    torch.set_num_threads(1)
    task=yaml.safe_load((root/"task.yaml").read_text())
    for name in task["research"]["source_files"]:
        if name.endswith(".py"):
            ast.parse((root/name).read_text(),filename=name)
    import validate_core
    import test_package
    import test_hparam
    suite=unittest.TestSuite()
    for module in (validate_core,test_package,test_hparam):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"passed":result.wasSuccessful(),"tests_run":result.testsRun,
                      "elapsed_seconds":time.monotonic()-started,"evidence_level":"E0_smoke",
                      "controlled_inputs":True,"real_data_opened":False,"official_weights_loaded":False,
                      "cuda_smoke_completed":False,"jobs_submitted":0,"test_evaluations":0,
                      "scheduler_builder_test":"actual supplied source body on virtual filesystem",
                      "candidate_execution_certified":False},separators=(",",":")))
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=="__main__":
    main()
