"""Worker boundary tests; local bwrap canary is separate from real EEG acceptance."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import patch
import zipfile


class WorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec("eegfm.research_bench.real_worker"), "sandbox worker missing")
        self.mod = importlib.import_module("eegfm.research_bench.real_worker")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.public = self.root / "public"
        self.public.mkdir()
        (self.public / "TASK.md").write_text("Read only public task")
        self.mod.write_atomic(self.public / "PUBLIC_MANIFEST.json", {
            "schema_version": "public_bundle_v1", "task_id": "test", "resource_tier": "real_eeg", "files": [
                {"path": "TASK.md", "bytes": (self.public / "TASK.md").stat().st_size,
                 "sha256": self.mod.digest_file(self.public / "TASK.md")} ]})
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        for name in ("train", "validation", "test"):
            with zipfile.ZipFile(self.inputs / f"{name}.npz", "w") as archive:
                archive.writestr("x.npy", b"trusted dummy input for stdlib canary")
                if name == "train": archive.writestr("y.npy", b"train labels allowed")
                else:
                    archive.writestr("sample_ids.npy", b"sample IDs for stdlib canary")
                    archive.writestr("subject_ids.npy", b"subject IDs for stdlib canary")
        self.split_manifest = self.root / "split.json"
        self.split_manifest.write_text('{"frozen":"fixture"}')
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        (self.candidate / "main.py").write_text("print('candidate')\n")

    @unittest.skipUnless(sys.platform == 'linux','Linux worker enrollment')
    def test_cached_job_refuses_changed_input_or_aggregation_enrollment(self) -> None:
        evaluator=self.evaluator()
        spec=self.spec()
        finished={'status':'completed','exit_code':0,'process_cleanup':{'surviving_owned_pids':[]}}
        with patch.object(self.mod,'run_bounded',return_value=finished) as execute:
            self.assertEqual(evaluator.submit(spec)['status'],'succeeded')
            with zipfile.ZipFile(self.inputs/'train.npz','a') as archive:
                archive.writestr('new_input.npy',b'new trusted input')
            changed=self.evaluator()
            with self.assertRaises(ValueError):
                changed.submit(spec)
            with self.assertRaises(ValueError):
                changed.poll(spec.job_id)
            self.assertEqual(execute.call_count,1)

    def binding(self, name: str) -> Any:
        path = self.inputs / f"{name}.npz"
        return self.mod.FileBinding(path, self.mod.digest_file(path))

    def runtime(self) -> Any:
        return self.mod.RuntimeConfig(bwrap=Path(shutil.which("bwrap") or "/usr/bin/bwrap"), python=Path("/usr/bin/python3"), environment_roots=())

    def evaluator(self, aggregate: Any = None) -> Any:
        return self.mod.SandboxedWorkerEvaluator(private_root=self.root / "private", public_root=self.public,
            public_manifest_sha256=self.mod.digest_file(self.public / "PUBLIC_MANIFEST.json"),
            split_manifest_path=self.split_manifest, split_manifest_sha256=self.mod.digest_file(self.split_manifest),
            inputs_by_split={split: self.mod.SplitInputs(self.binding("train"), self.binding(split)) for split in ("validation", "test")},
            runtime=self.runtime(), aggregate=aggregate or (lambda output, spec: {"metrics": {"accuracy": 0.5}, "artifacts": []}),
            released_metrics=frozenset({"accuracy"}), timeout_seconds=30, minimum_free_bytes=0)

    def spec(self, split: str = "validation") -> Any:
        return SimpleNamespace(job_id=f"job-{split}", episode_id="E01", run_id="run01", attempt_id="A1",
            split=split, candidate_dir=self.candidate, candidate_digest=self.mod.candidate_digest(self.candidate),
            split_manifest_sha256=self.mod.digest_file(self.split_manifest),
            public_manifest_sha256=self.mod.digest_file(self.public / "PUBLIC_MANIFEST.json"))

    @unittest.skipUnless(sys.platform == "linux", "Linux bwrap boundary")
    def test_command_mounts_only_selected_files_and_has_no_network_or_host_root(self) -> None:
        evaluator = self.evaluator()
        job = self.root / "job"
        job.mkdir()
        (job / "out").mkdir()
        command = evaluator.build_command(self.spec(), self.candidate, job / "out")
        self.assertIn("--unshare-all", command)
        self.assertIn("--die-with-parent", command)
        self.assertIn("--new-session", command)
        self.assertIn("--clearenv", command)
        self.assertNotIn(str(self.inputs), command)
        self.assertNotIn(str(self.inputs / "test.npz"), command)
        self.assertIn(str(self.inputs / "validation.npz"), command)
        self.assertNotIn("--share-net", command)
        # Server bwrap 0.6.1 has no --size. Scratch must be a private owned
        # directory included in the sampled job storage cap, never host /tmp.
        self.assertNotIn("--size", command)
        self.assertIn(str(job / "tmp"), command)
        self.assertIn(["--bind", str(job / "tmp"), "/tmp"],
                      [command[i:i+3] for i in range(len(command)-2)])
        self.assertEqual(command[-10:], ["--split", "validation", "--input", "/inputs/evaluation.npz", "--train", "/inputs/train.npz", "--public", "/public", "--output", "/out"])

    @unittest.skipUnless(sys.platform == "linux", "Linux runtime identity")
    def test_changed_candidate_public_input_or_split_fails_before_execution(self) -> None:
        evaluator = self.evaluator()
        for target in (self.candidate / "main.py", self.public / "TASK.md", self.inputs / "validation.npz", self.split_manifest):
            spec = self.spec()
            saved = target.read_bytes()
            target.write_bytes(saved + b"tamper")
            with self.assertRaises(ValueError):
                evaluator.submit(spec)
            target.write_bytes(saved)

    @unittest.skipUnless(sys.platform == "linux", "Linux runtime identity")
    def test_invalid_split_or_broad_environment_mount_rejected(self) -> None:
        evaluator = self.evaluator()
        with self.assertRaises(ValueError): evaluator.submit(self.spec("train"))
        with self.assertRaises(ValueError):
            self.mod.RuntimeConfig(bwrap=Path(shutil.which("bwrap") or "/usr/bin/bwrap"), python=Path("/usr/bin/python3"), environment_roots=(Path("/"),))

    @unittest.skipUnless(sys.platform == "linux", "Linux runtime identity")
    def test_evaluation_input_cannot_contain_labels_or_feature_targets(self) -> None:
        for key in ("y", "labels", "feature_targets"):
            with zipfile.ZipFile(self.inputs / "validation.npz", "w") as archive:
                archive.writestr(f"{key}.npy", b"hidden")
            evaluator = self.evaluator()
            with self.assertRaises(ValueError): evaluator.submit(self.spec())

    @unittest.skipUnless(sys.platform == "linux", "Linux runtime identity")
    def test_input_symlink_and_output_symlink_fail_closed(self) -> None:
        evaluator = self.evaluator()
        target = self.inputs / "validation.npz"
        original = self.root / "saved.npz"
        target.rename(original)
        target.symlink_to(original)
        with self.assertRaises(ValueError): evaluator.submit(self.spec())

    @unittest.skipUnless(sys.platform == "linux", "Linux runtime identity")
    def test_poll_never_submits_unknown_job(self) -> None:
        evaluator = self.evaluator()
        with patch.object(self.mod, "run_bounded", side_effect=AssertionError("poll must never execute")):
            with self.assertRaises(ValueError): evaluator.poll("missing")

    @unittest.skipUnless(sys.platform == "linux", "Linux runtime identity")
    def test_existing_unregistered_evidence_is_never_overwritten(self) -> None:
        evaluator = self.evaluator()
        spec = self.spec()
        job = evaluator.job_directory(spec.job_id)
        job.mkdir()
        receipt = job / "receipt.json"
        receipt.write_text("old evidence")
        with self.assertRaises(FileExistsError): evaluator.submit(spec)
        self.assertEqual(receipt.read_text(), "old evidence")

    @unittest.skipUnless(sys.platform == "linux", "Linux runtime identity")
    def test_crash_consumes_job_and_poll_does_not_reexecute(self) -> None:
        evaluator = self.evaluator()
        spec = self.spec()
        with patch.object(self.mod, "run_bounded", side_effect=KeyboardInterrupt("crash")):
            with self.assertRaises(KeyboardInterrupt): evaluator.submit(spec)
        with patch.object(self.mod, "run_bounded", side_effect=AssertionError("must not execute again")):
            result = evaluator.submit(spec)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(evaluator.poll(spec.job_id), result)

    @unittest.skipUnless(sys.platform == "linux", "Linux worker enrollment")
    def test_missing_output_or_rejected_aggregation_releases_only_finite_diagnostic(self) -> None:
        def aggregate(output: Path, spec: Any) -> dict[str, Any]:
            (output / "results.npz").read_bytes()
            raise AssertionError("Missing output must fail before this line")
        evaluator = self.evaluator(aggregate)
        finished = {"status": "completed", "exit_code": 0, "process_cleanup": {"surviving_owned_pids": []}}
        with patch.object(self.mod, "run_bounded", return_value=finished):
            result = evaluator.submit(self.spec())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result.get("diagnostic_code"), "candidate_outputs_rejected")
        self.assertEqual(result["metrics"], {})
        self.assertEqual(result["artifacts"], [])
        self.assertNotIn("secret labels", json.dumps(result))
        self.assertEqual(evaluator.poll(self.spec().job_id), result)

    @unittest.skipUnless(sys.platform == "linux", "Linux worker enrollment")
    def test_invalid_trusted_aggregation_response_is_not_recoverable(self) -> None:
        evaluator = self.evaluator(lambda output, spec: {"metrics": {"secret": 77}, "artifacts": []})
        finished = {"status": "completed", "exit_code": 0, "process_cleanup": {"surviving_owned_pids": []}}
        with patch.object(self.mod, "run_bounded", return_value=finished):
            result = evaluator.submit(self.spec())
        self.assertEqual(result.get("diagnostic_code"), "evaluation_integrity_failed")
        self.assertNotIn("secret", json.dumps(result))

    @unittest.skipUnless(sys.platform == "linux", "Linux worker enrollment")
    def test_unclean_execution_has_distinct_safe_diagnostic(self) -> None:
        evaluator = self.evaluator()
        failed = {"status": "timed_out", "exit_code": -9, "process_cleanup": {"surviving_owned_pids": []}}
        with patch.object(self.mod, "run_bounded", return_value=failed):
            result = evaluator.submit(self.spec())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result.get("diagnostic_code"), "candidate_execution_failed")

    @unittest.skipUnless(sys.platform == "linux", "Linux worker enrollment")
    def test_surviving_worker_or_unexpected_aggregator_error_is_not_recoverable(self) -> None:
        evaluator = self.evaluator()
        unfinished = {"status": "completed", "exit_code": 0, "process_cleanup": {"surviving_owned_pids": [123]}}
        with patch.object(self.mod, "run_bounded", return_value=unfinished):
            result = evaluator.submit(self.spec())
        self.assertEqual(result.get("diagnostic_code"), "evaluation_integrity_failed")
        def broken(output: Path, spec: Any) -> dict[str, Any]:
            raise RuntimeError("unexpected controller defect /private/path")
        # A distinct job preserves the first failure receipt.
        evaluator = self.evaluator(broken)
        finished = {"status": "completed", "exit_code": 0, "process_cleanup": {"surviving_owned_pids": []}}
        with patch.object(self.mod, "run_bounded", return_value=finished):
            result = evaluator.submit(self.spec("test"))
        self.assertEqual(result.get("diagnostic_code"), "evaluation_integrity_failed")

    @unittest.skipUnless(sys.platform == "linux", "Linux worker enrollment")
    def test_fixed_validator_diagnostics_distinguish_strength_from_direction_span(self) -> None:
        cases = [("validation", "Control strength must match each individual window", "intervention_strength_mismatch"),
                 ("test", "Recorded shifts do not lie in the recorded direction spans", "direction_span_mismatch")]
        for split, message, expected in cases:
            with self.subTest(code=expected):
                def rejected(output: Path, spec: Any) -> dict[str, Any]:
                    raise ValueError(message)
                evaluator = self.evaluator(rejected)
                finished = {"status": "completed", "exit_code": 0, "process_cleanup": {"surviving_owned_pids": []}}
                with patch.object(self.mod, "run_bounded", return_value=finished):
                    result = evaluator.submit(self.spec(split))
                self.assertEqual(result.get("diagnostic_code"), expected)
                self.assertNotIn(message, json.dumps(result))

    @unittest.skipUnless(sys.platform == "linux", "Linux runtime identity")
    def test_unapproved_metrics_and_forged_artifact_hash_rejected(self) -> None:
        evaluator = self.evaluator()
        output = self.root / "output"
        output.mkdir()
        (output / "results.npz").write_bytes(b"result")
        with self.assertRaises(ValueError):
            evaluator.validate_aggregate(output, {"metrics": {"secret": 42}, "artifacts": []})
        with self.assertRaises(ValueError):
            evaluator.validate_aggregate(output, {"metrics": {"accuracy": float("nan")}, "artifacts": []})
        with self.assertRaises(ValueError):
            evaluator.validate_aggregate(output, {"metrics": {"accuracy": 0.5}, "artifacts": [{"path": "results.npz", "sha256": "0" * 64}]})

    @unittest.skipUnless(sys.platform == "linux" and Path(shutil.which("bwrap") or "/usr/bin/bwrap").exists(), "local bwrap unavailable")
    def test_live_stdlib_canary_denies_private_network_writes_and_duplicate_execution(self) -> None:
        secret = self.root / "private-sentinel.txt"
        secret.write_text("hidden")
        code = '''import argparse,json,os,pathlib,socket
p=argparse.ArgumentParser()
for name in ('split','input','train','public','output'): p.add_argument('--'+name)
a=p.parse_args(); out=pathlib.Path(a.output)
def writable(path):
 try: pathlib.Path(path).write_text('bad'); return True
 except OSError: return False
sock=socket.socket(); sock.settimeout(0.1)
try: sock.connect(('1.1.1.1',443)); network=True
except OSError: network=False
result={'private':pathlib.Path(SECRET).exists(),'network':network,'public_write':writable('/public/TASK.md'),'input_write':writable('/inputs/evaluation.npz'),'candidate_write':writable('/candidate/main.py'),'proxy':any('proxy' in k.lower() for k in os.environ),'test_visible':pathlib.Path('/inputs/test.npz').exists(),'own_write':writable('/out/owned.txt'),'root_write':writable('/escape.txt'),'dev_write':writable('/dev/escape')}
(out/'canary.json').write_text(json.dumps(result))
counter=out/'counter.txt'; counter.write_text(str(int(counter.read_text())+1) if counter.exists() else '1')
print('PRIVATE_WORKER_STDOUT')
'''.replace("SECRET", repr(str(secret)))
        (self.candidate / "main.py").write_text(code)
        def aggregate(output: Path, spec: Any) -> dict[str, Any]:
            flags = json.loads((output / "canary.json").read_text())
            self.assertEqual(flags, {"private": False, "network": False, "public_write": False,
                "input_write": False, "candidate_write": False, "proxy": False, "test_visible": False, "own_write": True,
                "root_write": False, "dev_write": False})
            return {"metrics": {"accuracy": 1.0}, "artifacts": []}
        evaluator = self.evaluator(aggregate)
        spec = self.spec()
        result = evaluator.submit(spec)
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(evaluator.submit(spec), result)
        self.assertEqual(evaluator.poll(spec.job_id), result)
        self.assertEqual((evaluator.job_directory(spec.job_id) / "out" / "counter.txt").read_text(), "1")
        self.assertNotIn("PRIVATE_WORKER_STDOUT", json.dumps(result))
        self.assertNotIn("canary.json", json.dumps(result))

    @unittest.skipUnless(sys.platform == "linux" and Path(shutil.which("bwrap") or "/usr/bin/bwrap").exists(), "local bwrap unavailable")
    def test_actual_timeout_and_output_link_cannot_produce_success(self) -> None:
        (self.candidate / "main.py").write_text("import pathlib; pathlib.Path('/out/results.npz').symlink_to('/public/TASK.md')\n")
        evaluator = self.evaluator()
        self.assertEqual(evaluator.submit(self.spec())["status"], "failed")
        (self.candidate / "main.py").write_text("import time; time.sleep(30)\n")
        evaluator.timeout = 1
        spec = self.spec("test")
        self.assertEqual(evaluator.submit(spec)["status"], "failed")
        status = json.loads((evaluator.job_directory(spec.job_id) / "execution" / "status.json").read_text())
        self.assertEqual(status["status"], "timed_out")
        self.assertEqual(status["process_cleanup"]["surviving_owned_pids"], [])


class DiagnosticTests(unittest.TestCase):
    def test_unknown_values_and_private_missing_files_fail_closed(self) -> None:
        from eegfm.research_bench import real_worker as module
        classify = getattr(module, "_output_failure_diagnostic", None)
        self.assertIsNotNone(classify, "Output diagnostics need a closed classification boundary")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "out"
            output.mkdir()
            errors = [ValueError("Bound input changed"), ValueError("Unknown validator defect"),
                      ValueError("Only predeclared metrics may be released"),
                      ValueError("Control strength must match each individual window: private detail"),
                      FileNotFoundError("Missing unlocated output"),
                      FileNotFoundError(2, "missing", str(root / "truth.npz")),
                      FileNotFoundError(2, "missing", str(output / "unknown.npz"))]
            for error in errors:
                with self.subTest(error=repr(error)):
                    self.assertEqual(classify(error, output), "evaluation_integrity_failed")

    def test_known_candidate_constraints_and_exact_missing_outputs_are_recoverable(self) -> None:
        from eegfm.research_bench import real_worker as module
        classify = getattr(module, "_output_failure_diagnostic", None)
        self.assertIsNotNone(classify, "Output diagnostics need a closed classification boundary")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(classify(ValueError("Control strength must match each individual window"), output),
                             "intervention_strength_mismatch")
            self.assertEqual(classify(ValueError("Interventions require Q1 evidence"), output),
                             "candidate_outputs_rejected")
            for name in ("results.npz", "analysis.npz", "interventions.npz"):
                self.assertEqual(classify(FileNotFoundError(2, "missing", str(output / name)), output),
                                 "candidate_outputs_rejected")


@unittest.skipUnless(importlib.util.find_spec("numpy") is not None, "NumPy unavailable")
class NpzTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec("eegfm.research_bench.real_worker"), "sandbox worker missing")
        self.mod = importlib.import_module("eegfm.research_bench.real_worker")
        import numpy as np
        self.np = np
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / "out"
        self.output.mkdir()
        self.truth = self.root / "truth.npz"
        np.savez(self.truth, sample_ids=np.array(["s1", "s2"]), y=np.array([0, 1]))

    def test_default_aggregate_uses_trusted_labels_and_rejects_row_reordering(self) -> None:
        np = self.np
        np.savez(self.output / "results.npz", sample_ids=np.array(["s1", "s2"]), logits=np.array([-1.0, 2.0]))
        aggregator = self.mod.NpzClassificationAggregator({"validation": self.mod.FileBinding(self.truth, self.mod.digest_file(self.truth))})
        result = aggregator(self.output, SimpleNamespace(split="validation"))
        self.assertEqual(result["metrics"], {"accuracy": 1.0, "balanced_accuracy": 1.0})
        np.savez(self.output / "results.npz", sample_ids=np.array(["s2", "s1"]), logits=np.array([-1.0, 2.0]))
        with self.assertRaises(ValueError): aggregator(self.output, SimpleNamespace(split="validation"))

    def test_pickle_nonfinite_wrongshape_and_candidate_labels_rejected(self) -> None:
        np = self.np
        cases = [dict(logits=np.array([float("nan"), 2.])), dict(logits=np.array([[1.], [2.]])),
                 dict(logits=np.array([object(), object()], dtype=object)),
                 dict(logits=np.array([1., 2.]), y=np.array([0, 1])),
                 dict(logits=np.array([1., 2.]), target_predictions=np.ones((2, 61)))]
        for arrays in cases:
            np.savez(self.output / "results.npz", sample_ids=np.array(["s1", "s2"]), **arrays)
            with self.assertRaises(ValueError): self.mod.validate_prediction_npz(self.output / "results.npz", self.truth)


if __name__ == "__main__": unittest.main()
