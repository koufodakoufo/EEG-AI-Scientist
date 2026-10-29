"""Trusted bridge regressions; synthetic callbacks do not certify live isolation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from typing import Any


class Evaluator:
    sandboxed = True

    def __init__(self) -> None:
        self.calls = []
        self.wait = False
        self.fail = False
        self.crash = False

    def result(self, spec: Any) -> dict[str, Any]:
        return {"job_id": spec.job_id, "candidate_digest": spec.candidate_digest,
                "split": spec.split, "status": "failed" if self.fail else "succeeded",
                "metrics": {"accuracy_delta": -0.25}, "artifacts": [],
                "sandbox_receipt": "synthetic-test-only"}

    def submit(self, spec: Any) -> dict[str, Any]:
        self.calls.append(spec)
        if self.crash:
            raise KeyboardInterrupt("crash after reservation")
        result = self.result(spec)
        if self.wait:
            result["status"] = "waiting"
        return result

    def poll(self, job_id: str) -> dict[str, Any]:
        return self.result(next(spec for spec in self.calls if spec.job_id == job_id))


class DriverBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        # A missing production module is an explicit RED assertion, not collection failure.
        self.assertIsNotNone(importlib.util.find_spec("eegfm.research_bench.driver_bridge"),
                             "trusted driver bridge is not implemented")
        self.mod = importlib.import_module("eegfm.research_bench.driver_bridge")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = self.root / "case"
        (self.case / "output" / "candidate").mkdir(parents=True)
        (self.case / "output" / "candidate" / "analysis.py").write_text("value = 1\n")
        self.evaluator = Evaluator()
        self.controller = self.mod.BridgeController(
            trusted_root=self.root / "trusted", case_root=self.case,
            episode_id="E01", run_id="run01", public_manifest_sha256="a" * 64,
            split_manifest_sha256="b" * 64, evaluator=self.evaluator, max_attempts=1)
        self.sequence = 0

    def request(self, operation: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
        self.sequence += 1
        return self.controller.handle({"request_id": request_id or f"r{self.sequence}",
                                       "episode_id": "E01", "operation": operation,
                                       "payload": payload})

    def ready(self) -> None:
        (self.case / "output" / "brief.md").write_text("Question, allowed scope and controls.\n")
        self.request("brief", {"path": "brief.md"})
        self.controller.review(approved=True, reviewer_id="protocol-reviewer", policy_sha256="c" * 64)
        self.request("contract", {"protocol": {"research_mode": "analysis", "selection_split": "validation"}})

    def candidate(self) -> dict[str, Any]:
        return self.request("baseline", {"candidate_dir": "candidate", "split": "validation",
                                         "title": "unmodified model"})

    def locked(self) -> dict[str, Any]:
        self.ready()
        result = self.candidate()
        self.request("attempt", {"candidate_dir": "candidate", "split": "validation", "title": "negative control"})
        self.request("lock", {"attempt_id": result["attempt_id"], "candidate_digest": result["candidate_digest"]})
        return result

    def test_request_identity_cannot_cross_episode_or_add_shell(self) -> None:
        with self.assertRaises(ValueError):
            self.controller.handle({"request_id": "x", "episode_id": "OTHER", "operation": "brief", "payload": {}})
        self.ready()
        with self.assertRaises(ValueError):
            self.request("baseline", {"candidate_dir": "candidate", "split": "validation", "title": "x", "command": "touch /tmp/escape"})

    def test_private_control_must_not_be_under_actor_case(self) -> None:
        with self.assertRaises(ValueError):
            self.mod.BridgeController(trusted_root=self.case / "control", case_root=self.case,
                episode_id="E02", run_id="run02", public_manifest_sha256="a" * 64,
                split_manifest_sha256="b" * 64, evaluator=self.evaluator)

    def test_review_is_delegated_and_actor_cannot_self_approve(self) -> None:
        self.ready()
        review = json.loads((self.controller.run / "review.json").read_text())
        self.assertEqual(review["approval_mode"], "delegated_protocol_review")
        self.assertEqual(review["reviewer_id"], "protocol-reviewer")
        with self.assertRaises(ValueError):
            self.request("approve", {})

    def test_duplicate_id_returns_original_and_changed_payload_rejected(self) -> None:
        self.ready()
        payload = {"candidate_dir": "candidate", "split": "validation", "title": "baseline"}
        result = self.request("baseline", payload, "same")
        self.assertEqual(result, self.request("baseline", payload, "same"))
        self.assertEqual(len(self.evaluator.calls), 1)
        with self.assertRaises(ValueError):
            self.request("baseline", {**payload, "title": "changed"}, "same")

    def test_negative_result_retained_and_attempts_bounded(self) -> None:
        self.ready()
        self.candidate()
        self.request("attempt", {"candidate_dir": "candidate", "split": "validation", "title": "negative"})
        projection = self.controller.projection()
        self.assertEqual(projection["attempts"][-1]["retention"], "retained_valid")
        self.assertEqual(projection["attempts"][-1]["metrics"]["accuracy_delta"], -0.25)
        with self.assertRaises(ValueError):
            self.request("attempt", {"candidate_dir": "candidate", "split": "validation", "title": "over budget"})

    def test_test_requires_lock_and_matching_digest(self) -> None:
        self.ready()
        result = self.candidate()
        with self.assertRaises(ValueError):
            self.request("test", {"candidate_digest": result["candidate_digest"], "split": "test"})
        self.request("lock", {"attempt_id": result["attempt_id"], "candidate_digest": result["candidate_digest"]})
        with self.assertRaises(ValueError):
            self.request("test", {"candidate_digest": "0" * 64, "split": "test"})

    def test_locked_candidate_tamper_prevents_test(self) -> None:
        result = self.locked()
        snapshot = self.evaluator.calls[0].candidate_dir
        (snapshot / "analysis.py").write_text("value = 2\n")
        with self.assertRaises(ValueError):
            self.request("test", {"candidate_digest": result["candidate_digest"], "split": "test"})

    def test_original_actor_copy_changes_do_not_change_locked_snapshot(self) -> None:
        result = self.locked()
        (self.case / "output" / "candidate" / "analysis.py").write_text("value = 99\n")
        self.request("test", {"candidate_digest": result["candidate_digest"], "split": "test"})
        self.assertEqual(self.evaluator.calls[-1].candidate_dir.joinpath("analysis.py").read_text(), "value = 1\n")

    def test_symlink_and_hardlink_candidates_rejected(self) -> None:
        self.ready()
        target = self.case / "output" / "candidate" / "link.py"
        target.symlink_to(self.case / "output" / "candidate" / "analysis.py")
        with self.assertRaises(ValueError):
            self.candidate()
        target.unlink()
        import os
        os.link(self.case / "output" / "candidate" / "analysis.py", target)
        with self.assertRaises(ValueError):
            self.candidate()

    def test_actor_cannot_redirect_output_root_to_host_directory(self) -> None:
        self.ready()
        (self.case / "output").rename(self.root / "outside")
        (self.case / "output").symlink_to(self.root / "outside", target_is_directory=True)
        with self.assertRaises(ValueError):
            self.candidate()

    def test_test_reserved_before_callback_and_never_reexecutes_after_crash(self) -> None:
        result = self.locked()
        self.evaluator.crash = True
        payload = {"candidate_digest": result["candidate_digest"], "split": "test"}
        with self.assertRaises(KeyboardInterrupt):
            self.request("test", payload, "one-shot")
        self.evaluator.crash = False
        calls = len(self.evaluator.calls)
        self.controller = self.mod.BridgeController(
            trusted_root=self.root / "trusted", case_root=self.case,
            episode_id="E01", run_id="run01", public_manifest_sha256="a" * 64,
            split_manifest_sha256="b" * 64, evaluator=self.evaluator, max_attempts=1)
        self.request("test", payload, "one-shot")
        with self.assertRaises(ValueError):
            self.request("test", payload, "new-test")
        self.assertEqual(len(self.evaluator.calls), calls)

    def test_concurrent_test_requests_start_one_job(self) -> None:
        result = self.locked()
        def invoke(index: int) -> dict[str, Any] | None:
            try:
                return self.controller.handle({"request_id": f"race{index}", "episode_id": "E01", "operation": "test",
                    "payload": {"candidate_digest": result["candidate_digest"], "split": "test"}})
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(invoke, range(2)))
        self.assertEqual(sum(response is not None for response in responses), 1)
        self.assertEqual(sum(spec.split == "test" for spec in self.evaluator.calls), 1)

    def test_waiting_job_recovers_without_resubmit(self) -> None:
        self.ready()
        self.evaluator.wait = True
        self.candidate()
        self.assertEqual(self.controller.projection()["state"]["status"], "waiting_job")
        self.controller.poll_jobs()
        self.assertEqual(self.controller.projection()["state"]["status"], "working")
        self.assertEqual(len(self.evaluator.calls), 1)

    def test_actor_state_tamper_does_not_override_private_state(self) -> None:
        (self.case / "STATE.json").write_text('{"status":"done"}')
        self.assertEqual(self.controller.projection()["state"]["status"], "brief")

    def test_failed_job_or_session_and_missing_report_cannot_be_done(self) -> None:
        result = self.locked()
        self.evaluator.fail = True
        self.request("test", {"candidate_digest": result["candidate_digest"], "split": "test"})
        with self.assertRaises(ValueError):
            self.request("report", {"path": "missing.md"})
        (self.case / "output" / "report.md").write_text("Results and limitations.\n")
        with self.assertRaises(ValueError):
            self.request("report", {"path": "report.md"})
        self.assertNotEqual(self.controller.projection()["state"]["status"], "done")

    def test_successful_negative_study_can_complete_after_real_session_receipt(self) -> None:
        result = self.locked()
        self.request("test", {"candidate_digest": result["candidate_digest"], "split": "test"})
        (self.case / "output" / "report.md").write_text("Negative finding and limitations.\n")
        with self.assertRaises(ValueError):
            self.request("report", {"path": "report.md"})
        self.controller.record_session({"status": "completed", "exit_code": 0,
            "stdout": '{"type":"turn.completed"}\n', "stderr": "",
            "process_cleanup": {"surviving_owned_pids": []}})
        self.request("report", {"path": "report.md"})
        self.assertEqual(self.controller.projection()["state"]["status"], "done")

    def test_exit_zero_capacity_error_is_not_completed_session(self) -> None:
        outcome = self.controller.record_session({"status": "completed", "exit_code": 0,
            "stdout": '{"type":"error","message":"rate limit"}\n', "stderr": "",
            "process_cleanup": {"surviving_owned_pids": []}})
        self.assertFalse(outcome["ok"])

    def test_real_driver_loop_waits_and_honors_blocked_without_legacy_argv(self) -> None:
        from eegfm.driver import Driver
        from unittest.mock import patch
        original_loop = Driver.loop
        calls = []
        def observed_loop(instance: Any) -> int:
            calls.append(instance)
            return original_loop(instance)
        self.ready()
        self.evaluator.wait = True
        self.candidate()
        def launch(projection: dict[str, Any]) -> dict[str, Any]:
            return {"status": "completed", "exit_code": 0, "stdout": '{"type":"turn.completed"}\n',
                    "stderr": "", "process_cleanup": {"surviving_owned_pids": []}, "requests": []}
        driver = self.mod.BridgeDriver(self.controller, launch=launch, max_sessions=1, once=True)
        with patch.object(Driver,'loop',observed_loop):
            self.assertEqual(driver.loop(), 0)
        self.assertEqual(calls,[driver])
        self.assertEqual(self.controller.projection()["state"]["status"], "working")

    def test_driver_session_budget_block_is_controller_owned(self) -> None:
        def launch(projection: dict[str, Any]) -> dict[str, Any]:
            return {"status": "completed", "exit_code": 0, "stdout": '{"type":"turn.completed"}\n',
                    "stderr": "", "process_cleanup": {"surviving_owned_pids": []}, "requests": []}
        driver = self.mod.BridgeDriver(self.controller, launch=launch, max_sessions=1)
        self.assertEqual(driver.loop(), 3)
        self.assertEqual(self.controller.projection()["state"]["status"], "blocked")

    def test_projected_feedback_never_contains_internal_worker_receipt(self) -> None:
        self.ready()
        self.candidate()
        serialized = json.dumps(self.controller.projection())
        self.assertNotIn("synthetic-test-only", serialized)
        self.assertNotIn(str(self.controller.run), serialized)

    def test_latest_failed_session_cannot_finish_after_earlier_success(self) -> None:
        result = self.locked()
        self.request("test", {"candidate_digest": result["candidate_digest"], "split": "test"})
        (self.case / "output" / "report.md").write_text("Findings.\n")
        self.controller.record_session({"status": "completed", "exit_code": 0,
            "stdout": '{"type":"turn.completed"}\n', "stderr": "",
            "process_cleanup": {"surviving_owned_pids": []}})
        self.controller.record_session({"status": "failed", "exit_code": 1, "stdout": "", "stderr": "failed",
            "process_cleanup": {"surviving_owned_pids": []}})
        with self.assertRaises(ValueError):
            self.request("report", {"path": "report.md"})

    def test_mismatched_worker_split_is_failed_not_trusted(self) -> None:
        self.ready()
        original = self.evaluator.result
        def mismatched(spec: Any) -> dict[str, Any]:
            return {**original(spec), "split": "test"}
        self.evaluator.result = mismatched
        self.candidate()
        self.assertEqual(self.controller.projection()["attempts"][0]["status"], "failed")

    def test_invalid_actor_request_has_immutable_safe_feedback(self) -> None:
        request = {"request_id": "bad-operation", "episode_id": "E01", "operation": "shell", "payload": {}}
        def launch(projection: dict[str, Any]) -> dict[str, Any]:
            return {"status": "completed", "exit_code": 0, "stdout": '{"type":"turn.completed"}\n',
                    "stderr": "", "process_cleanup": {"surviving_owned_pids": []}, "requests": [request]}
        self.mod.BridgeDriver(self.controller, launch=launch, once=True).loop()
        responses = self.controller.projection()["responses"]
        self.assertTrue(responses, "rejected requests must receive safe feedback")
        response = responses[-1]
        self.assertEqual(response["status"], "rejected")
        self.assertEqual(response, self.controller.handle(request))


    def test_malformed_paths_and_operations_fail_with_safe_schema_error(self) -> None:
        for invalid in (None, 3, [], {}):
            with self.assertRaises(ValueError):
                self.request('brief', {'path': invalid})
            with self.assertRaises(ValueError):
                self.request(invalid, {})

    def test_terminal_job_survives_stale_waiting_poll_and_failure_callback(self) -> None:
        self.ready()
        self.candidate()
        spec = self.evaluator.calls[0]
        self.controller._accept_result(spec.job_id,{**self.evaluator.result(spec),'status':'waiting'})
        self.controller._fail_job(spec.job_id,'stale_poll_exception')
        self.assertEqual(self.controller.projection()['jobs'][0]['status'],'succeeded')

    def test_driver_lifetime_lease_prevents_second_controller_launch(self) -> None:
        import fcntl
        called=[]
        with (self.controller.run/'bridge-driver.lock').open('a') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(RuntimeError):
                self.mod.BridgeDriver(self.controller,launch=lambda p:called.append(p),once=True).loop()
        self.assertEqual(called,[])

    def test_crashed_launch_consumes_durable_session_budget(self) -> None:
        calls=[]
        def crash(projection: dict[str,Any]) -> dict[str,Any]:
            calls.append(projection)
            raise OSError('crash after launching')
        with self.assertRaises(OSError):
            self.mod.BridgeDriver(self.controller,launch=crash,max_sessions=2,once=True).loop()
        result=self.mod.BridgeDriver(self.controller,launch=crash,max_sessions=2,once=True).loop()
        self.assertEqual(result,3)
        self.assertEqual(len(calls),1)


if __name__ == "__main__":
    unittest.main()
