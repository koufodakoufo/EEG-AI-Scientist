"""Evidence feedback boundaries; scripted fixtures are not scientific evidence."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time

import pytest

from eegfm.eeg import episode
from eegfm.eeg import evidence_policy as policy


TASK = "eegmat-attribute-dependence-v2"
POLICY = {"schema_version": "scientific_evidence_policy_v1",
          "policy_id": "attribute-dependence-evidence-v1",
          "obligations": [
              {"id": "recoverability", "metric": "q1_groups", "minimum": 24},
              {"id": "matched_intervention", "metric": "q2_interventions", "minimum": 2},
              {"id": "residual_refit", "metric": "q3_residual_groups", "minimum": 2}],
          "lock_policy": "advisory", "partial_reports_allowed": True}


def projection() -> dict:
    return {"state": {"status": "working"}, "lock": None, "attempts": [
        {"id": "A1", "kind": "baseline", "status": "evaluated", "candidate_digest": "b" * 64,
         "jobs": ["J1"], "metrics": {"q1_groups": 24}},
        {"id": "A2", "kind": "iteration", "status": "evaluated", "candidate_digest": "c" * 64,
         "jobs": ["J2"], "metrics": {"q1_groups": 99}}],
        "jobs": [{"job_id": "J2", "attempt_id": "A2", "split": "validation",
                  "candidate_digest": "c" * 64, "status": "succeeded",
                  "result": {"job_id": "J2", "attempt_id": "A2", "split": "validation",
                             "candidate_digest": "c" * 64, "status": "succeeded",
                             "metrics": {"q1_groups": 24., "q2_interventions": 0.}}}]}


@pytest.mark.parametrize("minimum", [True, 0, -1, 2.0, float("nan"), float("inf"), "2"])
def test_policy_rejects_nonpositive_or_noninteger_minima(minimum: object) -> None:
    value = deepcopy(POLICY)
    value["obligations"][0]["minimum"] = minimum
    with pytest.raises(ValueError):
        policy.validate_policy(value)


@pytest.mark.parametrize("mutation", ["test_metric", "duplicate", "extra", "mandatory"])
def test_policy_rejects_unreviewed_executable_requirements(mutation: str) -> None:
    value = deepcopy(POLICY)
    if mutation == "test_metric":
        value["obligations"][0]["metric"] = "test_accuracy"
    elif mutation == "duplicate":
        value["obligations"].append(value["obligations"][0])
    elif mutation == "extra":
        value["obligations"][0]["execute"] = "arbitrary code"
    else:
        value["lock_policy"] = "mandatory"
    with pytest.raises(ValueError):
        policy.validate_policy(value)


def test_feedback_uses_validation_job_counts_and_distinguishes_absent_from_zero() -> None:
    result = policy.validation_evidence_status(POLICY, projection(), max_iterations=2)
    assert result["source_attempt_id"] == "A2"
    assert result["source_split"] == "validation"
    assert result["source_status"] == "succeeded"
    assert [(r["observed"], r["status"]) for r in result["requirements"]] == [
        (24, "present"), (0, "missing"), (None, "not_assessed")]
    assert result["remaining_iterations"] == 1
    assert result["next_action"] == "consider_revision_before_lock"
    assert result["scientific_validity"] == "not_assessed"


@pytest.mark.parametrize("wrong", ["failed_attempt", "failed_job", "test_split", "other_attempt", "other_digest", "failed_result", "other_result_split"])
def test_untrusted_current_attempt_does_not_inherit_older_or_test_success(wrong: str) -> None:
    value = projection()
    if wrong == "failed_attempt":
        value["attempts"][-1]["status"] = "failed"
    elif wrong == "failed_job":
        value["jobs"][0]["status"] = "failed"
    elif wrong == "test_split":
        value["jobs"][0]["split"] = "test"
    elif wrong == "other_attempt":
        value["jobs"][0]["attempt_id"] = "A1"
    elif wrong == "other_digest":
        value["jobs"][0]["candidate_digest"] = "d" * 64
    elif wrong == "failed_result":
        value["jobs"][0]["result"]["status"] = "failed"
    else:
        value["jobs"][0]["result"]["split"] = "test"
    result = policy.validation_evidence_status(POLICY, value, max_iterations=2)
    assert result["source_attempt_id"] == "A2"
    assert all(row["observed"] is None for row in result["requirements"])
    if wrong in {"failed_attempt", "failed_job", "failed_result"}:
        assert result["source_status"] == "failed"


def test_baseline_does_not_certify_iteration_and_latest_failed_attempt_remains_failed() -> None:
    value = projection()
    value["attempts"] = value["attempts"][:1]
    result = policy.validation_evidence_status(POLICY, value, max_iterations=2)
    assert result["source_attempt_id"] is None
    assert result["remaining_iterations"] == 2
    assert all(row["observed"] is None for row in result["requirements"])
    value = projection()
    value["attempts"].append({"id": "A3", "kind": "iteration", "status": "failed", "jobs": [],
                              "candidate_digest": "d" * 64, "metrics": {"q1_groups": 24}})
    result = policy.validation_evidence_status(POLICY, value, max_iterations=2)
    assert result["source_attempt_id"] == "A3"
    assert result["source_status"] == "failed"
    assert result["remaining_iterations"] == 0
    assert all(row["observed"] is None for row in result["requirements"])
    assert result["next_action"] == "report_failed_attempt_and_limitations"


@pytest.mark.parametrize("observed", [True, -1, 0.5, float("nan"), float("inf"), "24"])
def test_invalid_count_never_certifies_coverage(observed: object) -> None:
    value = projection()
    value["jobs"][0]["result"]["metrics"]["q1_groups"] = observed
    result = policy.validation_evidence_status(POLICY, value, max_iterations=2)
    assert result["requirements"][0]["observed"] is None
    assert result["requirements"][0]["status"] == "not_assessed"


def test_after_lock_feedback_stays_validation_only_and_directs_reporting() -> None:
    value = projection()
    value["lock"] = {"attempt_id": "A2"}
    before = policy.validation_evidence_status(POLICY, value, max_iterations=2)
    value["jobs"].append({"job_id": "JT", "attempt_id": "A2", "split": "test", "status": "succeeded",
                          "result": {"metrics": {"q1_groups": 999, "q2_interventions": 999, "q3_residual_groups": 999}}})
    after = policy.validation_evidence_status(POLICY, value, max_iterations=2)
    assert before == after
    assert after["next_action"] == "complete_frozen_lifecycle_and_report_limitations"


def test_adaptive_prompt_after_lock_only_advises_frozen_completion() -> None:
    value = projection()
    value["lock"] = {"attempt_id": "A2"}
    prompt = episode.session_prompt(value, 5, Path("python"), [], task_id=TASK,
                                    session_guidance="adaptive_evidence_v1")
    guidance = prompt.split("TRUSTED_OWN_EPISODE_PROJECTION_JSON", 1)[0].lower()
    assert "consider a useful revision" not in guidance
    assert "without changing scientific choices" in guidance


class NoExecutionEvaluator:
    sandboxed = True


def controller(tmp_path: Path, guidance: str = "adaptive_evidence_v1", task: str = TASK) -> episode.EpisodeController:
    case = tmp_path / "case"
    (case / "output").mkdir(parents=True, exist_ok=True)
    return episode.EpisodeController(trusted_root=tmp_path / "trusted", case_root=case,
        episode_id="evidence", run_id="evidence", public_manifest_sha256="a" * 64,
        split_manifest_sha256="b" * 64, evaluator=NoExecutionEvaluator(), max_attempts=2,
        task_id=task, session_guidance=guidance)


def test_only_adaptive_projection_exposes_evidence_and_legacy_prompt_keeps_recipe(tmp_path: Path) -> None:
    adaptive = controller(tmp_path / "adaptive")
    fixed = controller(tmp_path / "fixed", "fixed_stages_v1")
    legacy = controller(tmp_path / "legacy", "fixed_stages_v1", episode.DEFAULT_TASK)
    assert "evidence_status" in adaptive.projection()
    assert "evidence_status" not in fixed.projection()
    assert "evidence_status" not in legacy.projection()
    assert "five-stage flow" in episode.session_prompt(legacy.projection(), 1, Path("python"), [])
    text = episode.session_prompt(adaptive.projection(), 1, Path("python"), [], task_id=TASK,
                                  session_guidance="adaptive_evidence_v1")
    assert "public/EVIDENCE_POLICY.json" in text
    assert "five-stage flow" not in text
    assert "after lock" in text.lower()


def test_resume_rejects_guidance_or_policy_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    controller(tmp_path)
    with pytest.raises(ValueError, match="guidance|identity"):
        controller(tmp_path, "fixed_stages_v1")
    changed = deepcopy(POLICY)
    changed["obligations"][0]["minimum"] = 25
    monkeypatch.setattr(episode, "task_evidence_policy", lambda task_id: changed)
    with pytest.raises(ValueError, match="guidance|identity"):
        controller(tmp_path)


@pytest.mark.parametrize("task,guidance", [(TASK, "unknown"), (episode.DEFAULT_TASK, "adaptive_evidence_v1")])
def test_invalid_guidance_rejected_before_controller_creation(tmp_path: Path, task: str, guidance: str) -> None:
    with pytest.raises(ValueError, match="guidance"):
        controller(tmp_path, guidance, task)
    assert not (tmp_path / "trusted").exists()


def test_v2_controller_enforces_declared_iteration_cap(tmp_path: Path) -> None:
    case = tmp_path / "case"
    (case / "output").mkdir(parents=True)
    with pytest.raises(ValueError, match="iteration|attempt"):
        episode.EpisodeController(trusted_root=tmp_path / "trusted", case_root=case,
            episode_id="too-many", run_id="too-many", public_manifest_sha256="a" * 64,
            split_manifest_sha256="b" * 64, evaluator=NoExecutionEvaluator(), max_attempts=3, task_id=TASK)
    assert not (tmp_path / "trusted").exists()


def test_v2_recovery_matches_public_contract_while_legacy_default_stays_strict(tmp_path: Path) -> None:
    assert controller(tmp_path / "v2").recovery_policy == "validation-recovery-v1"
    assert controller(tmp_path / "legacy", "fixed_stages_v1", episode.DEFAULT_TASK).recovery_policy == "strict-v1"
    with pytest.raises(ValueError, match="recovery"):
        episode.evidence_guidance_identity({"task_id": TASK, "recovery_policy": "strict-v1"})


@pytest.mark.parametrize("task", [TASK, "eegmmidb-attribute-dependence-v2"])
def test_public_export_and_enrollment_bind_same_policy_for_both_arms(tmp_path: Path, task: str) -> None:
    source = tmp_path / "source"
    source.mkdir()
    names = ["train.npz", "validation.npz", "eeg_api.py"]
    for name in names:
        (source / name).write_text("synthetic public fixture")
    base = {"public_source": str(source), "public_files": names, "condition": "no_skill", "task_id": task}
    identities, bundles = [], []
    for index, guidance in enumerate(("fixed_stages_v1", "adaptive_evidence_v1")):
        config = {**base, "session_guidance": guidance}
        public = episode.prepare_public(config, tmp_path / f"case{index}", tmp_path / f"trusted{index}")
        bundles.append(episode.verify_public_bundle(public)["files"])
        assert json.loads((public / "EVIDENCE_POLICY.json").read_text()) == POLICY
        identities.append(episode.evidence_guidance_identity(config, public))
    assert bundles[0] == bundles[1]
    assert identities[0]["evidence_policy_sha256"] == identities[1]["evidence_policy_sha256"]
    assert identities[0] != identities[1]
    (public / "EVIDENCE_POLICY.json").write_text(json.dumps({**POLICY, "policy_id": "changed"}))
    with pytest.raises(ValueError, match="policy|bundle"):
        episode.evidence_guidance_identity(config, public)


def test_review_policy_binds_guidance_and_obligations_without_changing_v1_hash() -> None:
    assert episode.review_policy_hash() == episode.POLICY_HASH
    fixed = episode.review_policy_hash(TASK)
    adaptive = episode.review_policy_hash(TASK, session_guidance="adaptive_evidence_v1")
    assert fixed != adaptive
    assert fixed != episode.POLICY_HASH


def test_enrollment_binds_feedback_implementation_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(episode, "__file__", str(tmp_path / "episode.py"))
    source = tmp_path / "evidence_policy.py"
    source.write_text("# first frozen implementation")
    before = episode.evidence_guidance_identity({"task_id": TASK})
    source.write_text("# changed feedback semantics")
    after = episode.evidence_guidance_identity({"task_id": TASK})
    assert before != after
    assert before["evidence_policy_sha256"] == after["evidence_policy_sha256"]


def test_native_launcher_uses_adaptive_condition_in_actual_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from eegfm.evaluation.bundle import digest_file

    actor = controller(tmp_path)
    private = tmp_path / "private"
    private.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    names = ["train.npz", "validation.npz", "eeg_api.py"]
    for name in names:
        (source / name).write_text("synthetic public fixture")
    base = {"public_source": str(source), "public_files": names, "condition": "no_skill", "task_id": TASK,
            "session_guidance": "adaptive_evidence_v1"}
    public = episode.prepare_public(base, actor.case, private)
    now = datetime.now(timezone.utc)
    budget = private / "budget.json"
    budget.write_text(json.dumps({"calls": [], "extra_model_calls_max": 6, "max_parallel_model_workers": 1,
        "stop_new_research_at": (now + timedelta(hours=1)).isoformat(),
        "deadline_at": (now + timedelta(hours=2)).isoformat(), "per_call_timeout_seconds": 900,
        "preflight_timeout_seconds": 90}))
    gate, runtime = private / "gate.json", private / "runtime.json"
    gate.write_text('{"test_only":true}')
    runtime.write_text('{"test_only":true}')
    config = {**base, "call_ids": ["R90"], "budget_path": str(budget),
        "isolation_report": {"path": str(gate), "sha256": digest_file(gate)},
        "runtime_manifest": {"path": str(runtime), "sha256": digest_file(runtime)},
        "native_binary": "/tools/codex", "bwrap": "/tools/bwrap", "auth_source": "/protected/auth.json",
        "scientific_python": "/env/bin/python", "scientific_roots": ["/env"], "proxy_url": "http://localhost:1234"}
    seen = []

    def launch(metadata: dict, prompt: str, **kwargs: object) -> dict:
        seen.append(prompt)
        output = kwargs["output_dir"]
        output.mkdir(parents=True)
        (output / "stdout.jsonl").write_text('{"type":"turn.completed"}\n')
        (output / "stderr.log").write_text("")
        (actor.case / "output" / "requests-session-01.json").write_text("[]")
        return {"status": "completed", "exit_code": 0, "process_cleanup": {"surviving_owned_pids": []}}

    monkeypatch.setattr(episode, "prepare_control", lambda **kwargs: {"control_home": str(private / "home")})
    monkeypatch.setattr(episode, "validate_isolation_gate", lambda *args: None)
    monkeypatch.setattr(episode, "launch_actor", launch)
    monkeypatch.setattr(episode, "collect_visible_trace", lambda *args: {
        "turn_metadata": [{"model": episode.MODEL, "effort": "medium"}]})
    actor.reserve_session(6)
    receipt = episode.NativeEpisodeLaunch(config, actor, private, public, time.time())(actor.projection())
    assert receipt["status"] == "completed"
    assert len(seen) == 1
    assert '"evidence_status"' in seen[0]
    assert "five-stage flow" not in seen[0]


class PartialEvidenceEvaluator:
    sandboxed = True

    def __init__(self, *, fail_iteration: bool = False) -> None:
        self.fail_iteration = fail_iteration

    def submit(self, spec: object) -> dict:
        if self.fail_iteration and spec.attempt_id == "A2" and spec.split == "validation":
            return {"job_id": spec.job_id, "candidate_digest": spec.candidate_digest, "split": spec.split,
                    "status": "failed", "metrics": {}, "artifacts": [],
                    "sandbox_receipt": "SCRIPTED_BOUNDARY_ONLY", "diagnostic_code": "candidate_outputs_rejected"}
        return {"job_id": spec.job_id, "candidate_digest": spec.candidate_digest, "split": spec.split,
                "status": "succeeded", "metrics": {"q1_groups": 1. if spec.attempt_id != "A1" else 0.},
                "artifacts": [], "sandbox_receipt": "SCRIPTED_BOUNDARY_ONLY"}


@pytest.mark.parametrize("guidance", ["fixed_stages_v1", "adaptive_evidence_v1"])
@pytest.mark.parametrize("revise_failure", [False, True])
def test_advisory_policy_allows_honest_partial_report_in_both_arms(tmp_path: Path, guidance: str,
                                                               revise_failure: bool) -> None:
    case = tmp_path / "case"
    output = case / "output"
    (output / "candidate").mkdir(parents=True)
    (output / "candidate" / "main.py").write_text("# scripted fixture, not executed")
    (output / "brief.md").write_text("```json\n" + json.dumps(episode.task_scope(TASK)) + "\n```\n"
        "Measure recoverability and dependence with explicit limits on incomplete evidence.")
    actor = episode.EpisodeController(trusted_root=tmp_path / "trusted", case_root=case,
        episode_id="partial", run_id="partial", public_manifest_sha256="a" * 64,
        split_manifest_sha256="b" * 64, evaluator=PartialEvidenceEvaluator(fail_iteration=revise_failure), max_attempts=2,
        task_id=TASK, session_guidance=guidance)

    def request(operation: str, payload: dict, request_id: str | None = None) -> dict:
        return actor.handle({"request_id": request_id or operation, "episode_id": "partial", "operation": operation,
                             "payload": payload})

    request("brief", {"path": "brief.md"})
    actor.review(**episode.review_brief(actor, actor.projection()))
    request("contract", {"protocol": {**episode.task_scope(TASK), "research_mode": "analysis"}})
    request("baseline", {"candidate_dir": "candidate", "split": "validation", "title": "baseline"})
    request("attempt", {"candidate_dir": "candidate", "split": "validation", "title": "partial Q1"})
    if revise_failure:
        failed = actor.projection()
        assert failed["attempts"][-1]["status"] == "failed"
        if guidance == "adaptive_evidence_v1":
            assert failed["evidence_status"]["source_status"] == "failed"
        request("attempt", {"candidate_dir": "candidate", "split": "validation", "title": "corrected partial Q1"}, "revision")
    current = actor.projection()["attempts"][-1]
    if guidance == "adaptive_evidence_v1":
        status = actor.projection()["evidence_status"]
        assert status["source_attempt_id"] == current["id"]
        assert status["requirements"][0]["observed"] == 1
        assert status["requirements"][0]["status"] == "missing"
    request("lock", {"attempt_id": current["id"], "candidate_digest": current["candidate_digest"]})
    request("test", {"split": "test", "candidate_digest": current["candidate_digest"]})
    actor.record_session({"status": "completed", "exit_code": 0, "stdout": '{"type":"turn.completed"}',
                          "stderr": "", "process_cleanup": {"surviving_owned_pids": []}})
    (output / "REPORT.md").write_text("Partial Q1 only. Q2 and Q3 unsupported. No scientific validity claim.")
    request("report", {"path": "REPORT.md"})
    actor.validate_done()
    assert actor.projection()["state"]["status"] == "done"
    if revise_failure:
        assert actor.projection()["attempts"][-2]["status"] == "failed"
        assert actor.projection()["attempts"][-2]["metrics"] == {}
    with pytest.raises(ValueError):
        request("attempt", {"candidate_dir": "candidate", "split": "validation", "title": "post-test revision"})
