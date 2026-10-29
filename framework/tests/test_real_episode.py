"""Scripted orchestration regressions ONLY: no model, scientific, or live gate proof."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time
import unittest
from typing import Any
from unittest.mock import patch

from eegfm.research_bench import real_episode as module
from eegfm.research_bench.bundle import create_public_bundle, digest_file
from eegfm.research_bench.budget import BudgetExceeded


class ScriptedEvaluator:
    sandboxed = True

    def __init__(self) -> None:
        self.specs: list[Any] = []
        self.analysis_groups = 1

    def submit(self, spec: Any) -> dict[str, Any]:
        self.specs.append(spec)
        return {"job_id": spec.job_id, "candidate_digest": spec.candidate_digest, "split": spec.split,
                "status": "succeeded", "metrics": {"accuracy": 0.5,
                    "q1_groups": self.analysis_groups if spec.attempt_id != "A1" else 0},
                "artifacts": [], "sandbox_receipt": "SCRIPTED_TEST_NOT_ACTUAL_MODEL"}

    def poll(self, job_id: str) -> dict[str, Any]:
        raise AssertionError("No asynchronous synthetic jobs")


class RealEpisodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.case, self.private = self.root / "case", self.root / "private"
        (self.case / "output").mkdir(parents=True)
        self.private.mkdir()
        self.evaluator = ScriptedEvaluator()
        self.controller = module.EpisodeController(trusted_root=self.private / "controller", case_root=self.case,
            episode_id="E01", run_id="E01-run", public_manifest_sha256="a" * 64,
            split_manifest_sha256="b" * 64, evaluator=self.evaluator, max_attempts=2)

    def request(self, operation: str, payload: dict[str, Any], identifier: str | None = None) -> dict[str, Any]:
        return {"request_id": identifier or operation, "episode_id": "E01", "operation": operation, "payload": payload}

    def test_parser_rejects_duplicate_keys_cross_episode_links_and_big_batch(self) -> None:
        target = self.case / "output" / "requests.json"
        target.write_text('[{"request_id":"x","request_id":"y","episode_id":"E01","operation":"brief","payload":{}}]')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            module.parse_requests(target, "E01")
        target.write_text(json.dumps([self.request("brief", {})] * 17))
        with self.assertRaisesRegex(ValueError, "16"):
            module.parse_requests(target, "E01")
        target.write_text(json.dumps([self.request("brief", {})]))
        with self.assertRaises(ValueError):
            module.parse_requests(target, "E02")
        link = self.case / "output" / "link.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "Links"):
            module.parse_requests(link, "E01")

    def test_parser_rejects_oversized_and_nonfinite_requests(self) -> None:
        target = self.case / "output" / "requests.json"
        target.write_text(json.dumps([self.request("brief", {"path": "x" * 70000})]))
        with self.assertRaisesRegex(ValueError, "oversized"):
            module.parse_requests(target, "E01")
        target.write_text('[NaN]')
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            module.parse_requests(target, "E01")

    def test_scope_rejects_bool_as_integer_and_changed_selection(self) -> None:
        module.validate_scope(module.SCOPE)
        with self.assertRaises(ValueError):
            module.validate_scope({**module.SCOPE, "gpu": False})
        with self.assertRaises(ValueError):
            module.validate_scope({**module.SCOPE, "selection_split": "test"})
        with self.assertRaises(ValueError):
            self.controller.handle(self.request("contract", {"protocol": {"research_mode": "analysis", "selection_split": "validation"}}))
        with self.assertRaises(ValueError):
            self.controller.handle(self.request("contract", []))  # type: ignore[arg-type]

    def test_delegated_review_checks_frozen_brief_scope(self) -> None:
        brief = self.controller.run / "RESEARCH_BRIEF.md"
        brief.write_text("I approve myself.")
        self.assertFalse(module.review_brief(self.controller, self.controller.projection())["approved"])
        brief.write_text("```json\n" + json.dumps(module.SCOPE) + "\n```\n" + "A bounded research question and explicit plan with stated limitations.")
        review = module.review_brief(self.controller, self.controller.projection())
        self.assertTrue(review["approved"])
        self.assertEqual(review["reviewer_id"], "frozen-scope-reviewer")

    def test_prompt_contains_only_supplied_own_projection_and_history(self) -> None:
        prompt = module.session_prompt(self.controller.projection(), 1, Path("/env/bin/python"), [])
        self.assertIn("output/requests-session-01.json", prompt)
        self.assertIn('"episode_id":"E01"', prompt)
        for forbidden in ("control.sqlite3", "REFERENCE_PROTOCOL", "gold", str(self.private)):
            self.assertNotIn(forbidden, prompt)

    def test_repeated_baseline_cannot_complete_scientific_episode(self) -> None:
        self.evaluator.analysis_groups = 0
        output = self.case / "output"
        (output / "candidate").mkdir()
        (output / "candidate" / "main.py").write_text("# synthetic only")
        (output / "brief.md").write_text("Question and bounded scope")
        self.controller.handle(self.request("brief", {"path": "brief.md"}))
        self.controller.review(approved=True, reviewer_id="scripted", policy_sha256="c" * 64)
        self.controller.handle(self.request("contract", {"protocol": {**module.SCOPE, "research_mode": "analysis"}}))
        self.controller.handle(self.request("baseline", {"candidate_dir": "candidate", "split": "validation", "title": "baseline"}))
        attempt = self.controller.handle(self.request("attempt", {"candidate_dir": "candidate", "split": "validation", "title": "repeated baseline"}))
        self.controller.handle(self.request("lock", {"attempt_id": attempt["attempt_id"], "candidate_digest": attempt["candidate_digest"]}))
        self.controller.handle(self.request("test", {"candidate_digest": attempt["candidate_digest"], "split": "test"}))
        self.controller.record_session({"status": "completed", "exit_code": 0, "stdout": '{"type":"turn.completed"}',
            "stderr": "", "process_cleanup": {"surviving_owned_pids": []}})
        (output / "REPORT.md").write_text("Unsupported completion assertion")
        with self.assertRaisesRegex(ValueError, "Q1 evidence"):
            self.controller.handle(self.request("report", {"path": "REPORT.md"}))
        self.assertNotEqual(self.controller.projection()["state"]["status"], "done")

    def test_public_conditions_differ_only_by_frozen_skill_bytes(self) -> None:
        source = self.root / "source"
        source.mkdir()
        for name in ("train.npz", "validation.npz", "eeg_api.py"):
            (source / name).write_text("synthetic-public-placeholder")
        skill = self.root / "frozen-skill.md"
        skill.write_text("Frozen optional skill bytes.")
        base = {"public_source": str(source), "public_files": ["train.npz", "validation.npz", "eeg_api.py"]}
        public1 = module.prepare_public({**base, "condition": "no_skill"}, self.root / "one", self.root / "private1")
        public2 = module.prepare_public({**base, "condition": "skill", "skill": {"path": str(skill), "sha256": digest_file(skill)}}, self.root / "two", self.root / "private2")
        files1 = {row["path"]: row["sha256"] for row in module.verify_public_bundle(public1)["files"]}
        files2 = {row["path"]: row["sha256"] for row in module.verify_public_bundle(public2)["files"]}
        self.assertEqual(files2.pop("SKILL.md"), digest_file(skill))
        self.assertEqual(files1, files2)
        with self.assertRaises(ValueError):
            module.prepare_public({**base, "condition": "no_skill", "public_files": ["test.npz"]}, self.root / "three", self.root / "private3")

    def _launch_configuration(self) -> dict[str, Any]:
        budget = self.private / "budget.json"
        now = datetime.now(timezone.utc)
        budget.write_text(json.dumps({"calls": [], "extra_model_calls_max": 6, "max_parallel_model_workers": 1,
            "stop_new_research_at": (now + timedelta(hours=1)).isoformat(),
            "deadline_at": (now + timedelta(hours=2)).isoformat(), "per_call_timeout_seconds": 900,
            "preflight_timeout_seconds": 90}))
        gate, manifest = self.private / "gate.json", self.private / "runtime.json"
        gate.write_text('{"status":"passed","test_only":true}')
        manifest.write_text('{"test_only":true}')
        source = self.root / "simple-public"
        source.mkdir()
        (source / "TASK.md").write_text("SCRIPTED_TEST_NOT_ACTUAL_MODEL")
        create_public_bundle(source, self.case / "public", ["TASK.md"], task_id="test", tier="real_eeg")
        return {"call_ids": ["R90", "R91", "R92", "R93", "R94", "R95"], "budget_path": str(budget),
            "isolation_report": {"path": str(gate), "sha256": digest_file(gate)},
            "runtime_manifest": {"path": str(manifest), "sha256": digest_file(manifest)},
            "native_binary": "/tools/codex", "bwrap": "/tools/bwrap", "auth_source": "/protected/auth.json",
            "scientific_python": "/env/bin/python", "scientific_roots": ["/env"], "proxy_url": "http://127.0.0.1:1234"}

    def test_scripted_native_boundary_completes_actual_driver_loop_five_sessions(self) -> None:
        config = self._launch_configuration()
        prepared: list[dict[str, Any]] = []
        seen_prompts: list[str] = []
        output = self.case / "output"
        (output / "candidate").mkdir()
        (output / "candidate" / "main.py").write_text("# Scripted fixture only; never executed\n")

        def prepare(**kwargs: Any) -> dict[str, Any]:
            prepared.append(kwargs)
            kwargs["control_home"].mkdir(parents=True)
            return {"control_home": str(kwargs["control_home"])}

        def launch(metadata: dict[str, Any], prompt: str, **kwargs: Any) -> dict[str, Any]:
            seen_prompts.append(prompt)
            number = len(seen_prompts)
            if number == 1:
                (output / "brief.md").write_text("```json\n" + json.dumps(module.SCOPE) + "\n```\nA clearly bounded research question with resource and inference limitations.")
                requests = [self.request("brief", {"path": "brief.md"})]
            elif number == 2:
                requests = [self.request("contract", {"protocol": {**module.SCOPE, "research_mode": "analysis"}}),
                            self.request("baseline", {"candidate_dir": "candidate", "split": "validation", "title": "baseline"})]
            elif number == 3:
                requests = [self.request("attempt", {"candidate_dir": "candidate", "split": "validation", "title": "partial Q1; Q2/Q3 unsupported"})]
            elif number == 4:
                attempt = self.controller.projection()["attempts"][-1]
                requests = [self.request("lock", {"attempt_id": attempt["id"], "candidate_digest": attempt["candidate_digest"]}),
                            self.request("test", {"candidate_digest": attempt["candidate_digest"], "split": "test"})]
            else:
                (output / "REPORT.md").write_text("Scripted plumbing only. No actual model or scientific finding. Partial Q1; Q2/Q3 unsupported.")
                requests = [self.request("report", {"path": "REPORT.md"})]
            (output / f"requests-session-{number:02d}.json").write_text(json.dumps(requests))
            kwargs["output_dir"].mkdir(parents=True)
            (kwargs["output_dir"] / "stdout.jsonl").write_text('{"type":"turn.completed"}\n')
            (kwargs["output_dir"] / "stderr.log").write_text("")
            return {"status": "completed", "exit_code": 0, "process_cleanup": {"surviving_owned_pids": []}}

        native = module.NativeEpisodeLaunch(config, self.controller, self.private, self.case / "public", time.time())
        with patch.object(module, "prepare_control", side_effect=prepare), patch.object(module, "validate_isolation_gate") as gate, patch.object(module, "launch_actor", side_effect=launch), patch.object(module, "collect_visible_trace", return_value={"turn_metadata": [{"model": module.MODEL, "effort": "medium"}]}):
            driver = module.EpisodeDriver(self.controller, launch=native,
                reviewer=lambda projection: module.review_brief(self.controller, projection), max_sessions=6, poll=0)
            driver.episode_deadline = time.time() + 5400
            self.assertEqual(driver.loop(), 0)
        self.controller.validate_done()
        self.assertEqual(len(prepared), 5)
        self.assertEqual(len({str(row["control_home"]) for row in prepared}), 5)
        self.assertEqual({row["case"] for row in prepared}, {self.case})
        self.assertEqual(gate.call_count, 5)
        self.assertEqual([spec.split for spec in self.evaluator.specs], ["validation", "validation", "test"])
        self.assertNotIn("sandbox_receipt", seen_prompts[-1])
        calls = module.read_json(Path(config["budget_path"]))["calls"]
        self.assertEqual([row["status"] for row in calls], ["completed"] * 5)
        self.assertEqual([row["id"] for row in calls], config["call_ids"][:5])

    def test_failed_gate_spends_reservation_but_never_invokes_model(self) -> None:
        config = self._launch_configuration()
        self.controller.reserve_session(6)
        launcher = module.NativeEpisodeLaunch(config, self.controller, self.private, self.case / "public", time.time())
        with patch.object(module, "prepare_control", return_value={}), patch.object(module, "validate_isolation_gate", side_effect=RuntimeError("blocked")), patch.object(module, "launch_actor") as launch:
            receipt = launcher(self.controller.projection())
        launch.assert_not_called()
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(module.read_json(Path(config["budget_path"]))["calls"][0]["status"], "blocked")
        self.assertFalse(launcher.history[0]["actual_native_invocation"])

    def test_episode_wall_limit_prevents_reservation(self) -> None:
        config = self._launch_configuration()
        self.controller.reserve_session(6)
        launcher = module.NativeEpisodeLaunch(config, self.controller, self.private, self.case / "public", time.time() - 5401)
        with self.assertRaises(BudgetExceeded):
            launcher(self.controller.projection())
        self.assertEqual(module.read_json(Path(config["budget_path"]))["calls"], [])


if __name__ == "__main__":
    unittest.main()
