"""Regression tests: the task and rule text must reach the actual model request."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from eeg_scientist.deepseek_api import DeepSeekChatResult, DeepSeekToolCall, DeepSeekUsage
from eeg_scientist.evidence import EvidenceStore
from eeg_scientist.ledger import BudgetLedger
from eeg_scientist.research import ResearchConfig, ResearchError, ResearchRunner
from eeg_scientist.run_manifest import sha256_file, sha256_text

TASK_ALPHA = "TASK_SENTINEL_ALPHA_0123456789"
TASK_BETA = "TASK_SENTINEL_BETA_9876543210"
RULE_ALPHA = "RULE_SENTINEL_ALPHA_ABCDEF"
RULE_BETA = "RULE_SENTINEL_BETA_FEDCBA"


class RecordingModel:
    """Two-call offline model: read_evidence, then finish_study."""

    model_name = "offline-recorder"
    provider_name = "offline"
    backend_status = "unverified"

    def __init__(self, evidence_id: str) -> None:
        self.evidence_id = evidence_id
        self.requests: list[list[dict[str, object]]] = []

    def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 16384,
        json_mode: bool = False,
        stage: str = "",
    ) -> DeepSeekChatResult:
        self.requests.append(copy.deepcopy(messages))
        if not any(message.get("role") == "tool" for message in messages):
            return DeepSeekChatResult(
                tool_calls=[
                    DeepSeekToolCall(
                        id="call_read_1",
                        name="read_evidence",
                        arguments=json.dumps({"evidence_id": self.evidence_id, "max_chars": 200}),
                    )
                ],
                finish_reason="tool_calls",
                requested_model=self.model_name,
                usage=DeepSeekUsage(prompt_tokens=100, completion_tokens=10, total_tokens=110),
            )
        answer = "Proposal " + ("x" * 240) + f" [{self.evidence_id}]"
        return DeepSeekChatResult(
            tool_calls=[
                DeepSeekToolCall(
                    id="call_finish_1",
                    name="finish_study",
                    arguments=json.dumps(
                        {"answer": answer, "evidence_ids": [self.evidence_id], "unresolved": ["offline test gap"]}
                    ),
                )
            ],
            finish_reason="tool_calls",
            requested_model=self.model_name,
            usage=DeepSeekUsage(prompt_tokens=120, completion_tokens=20, total_tokens=140),
        )


def _config(
    root: Path,
    *,
    task_text: str = TASK_ALPHA,
    rule_text: str | None = RULE_ALPHA,
    name: str = "run",
    rule_version: str = "rule_v1",
) -> tuple[ResearchConfig, str]:
    materials = root / name / "materials"
    store = EvidenceStore(materials / "evidence")
    record = store.add_text(url="https://example.org/source", title="Source", text="evidence body " * 40)
    manifest = materials / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "v1",
                "materials": [{"evidence_id": record.evidence_id, "title": "Source", "version": "v1"}],
            }
        ),
        encoding="utf-8",
    )
    task = root / name / "task.md"
    task.write_text(task_text + "\n\nRead the evidence and answer.\n", encoding="utf-8")
    system = root / name / "system.md"
    system.write_text("SYSTEM_BASE_SENTINEL\n", encoding="utf-8")
    rule_path: Path | None = None
    if rule_text is not None:
        rule_path = root / name / "rule.md"
        rule_path.write_text(rule_text + "\nAlways cite the source.\n", encoding="utf-8")
    ledger = BudgetLedger(
        root / name / "budget.json",
        run_id=name,
        cap_cny=10,
        wrap_up_reserve_cny=0,
        model_attempts_limit=6,
    )
    config = ResearchConfig(
        run_id=name,
        run_dir=str(root / name / "run"),
        question="short metadata label",
        deadline="2099-01-01T00:00:00+00:00",
        stop_new_at="2099-01-01T00:00:00+00:00",
        task_text_path=str(task),
        study_id="test_study",
        arm="baseline",
        repeat=1,
        system_prompt_path=str(system),
        deliverables=["one proposal"],
        materials_manifest_path=str(manifest),
        material_evidence_dir=str(materials / "evidence"),
        material_version="v1",
        material_manifest_sha256=sha256_file(manifest),
        rule_text_path=str(rule_path) if rule_path is not None else None,
        rule_version=rule_version,
        research_mode="materials_only",
        max_model_calls=6,
        max_tool_calls=6,
        max_turns=2,
        max_model_calls_per_turn=6,
        max_tool_calls_per_turn=6,
        max_output_tokens=2048,
        study_config={"study_id": "test_study"},
        model_info={"model": "offline-recorder", "status": "unverified"},
        ledger_path=str(root / name / "budget.json"),
        code_root=str(root),
    )
    return config, record.evidence_id


def _normalized_user(text: str, task_marker: str, task_path: str) -> str:
    text = text.replace(task_path, "<TASK_PATH>").replace(task_marker, "<TASK>")
    return re.sub(r"Current local time: [^.]*\.", "Current local time: <TIME>.", text)


def _normalized_system(text: str, rule_marker: str) -> str:
    return text.replace(rule_marker, "<RULE>")


def test_task_and_rule_are_in_the_actual_request(tmp_path: Path) -> None:
    config_a, evidence_a = _config(tmp_path, task_text=TASK_ALPHA, rule_text=RULE_ALPHA, name="alpha")
    model_a = RecordingModel(evidence_a)
    summary_a = ResearchRunner(config_a, model_client=model_a, ledger=BudgetLedger(
        tmp_path / "alpha" / "budget.json", run_id="alpha", cap_cny=10, wrap_up_reserve_cny=0, model_attempts_limit=6
    )).run()
    assert summary_a.phase == "completed"

    config_b, evidence_b = _config(tmp_path, task_text=TASK_BETA, rule_text=RULE_BETA, name="beta")
    model_b = RecordingModel(evidence_b)
    summary_b = ResearchRunner(config_b, model_client=model_b, ledger=BudgetLedger(
        tmp_path / "beta" / "budget.json", run_id="beta", cap_cny=10, wrap_up_reserve_cny=0, model_attempts_limit=6
    )).run()
    assert summary_b.phase == "completed"

    first_a = model_a.requests[0]
    first_b = model_b.requests[0]
    system_a = str(first_a[0]["content"])
    system_b = str(first_b[0]["content"])
    user_a = str(first_a[1]["content"])
    user_b = str(first_b[1]["content"])
    assert RULE_ALPHA in system_a and TASK_ALPHA in user_a
    assert RULE_ALPHA not in system_b and TASK_ALPHA not in user_b
    assert RULE_BETA in system_b and TASK_BETA in user_b
    # The only controlled differences are the task marker and rule marker.
    assert _normalized_user(user_a, TASK_ALPHA, str(config_a.task_text_path)) == _normalized_user(
        user_b, TASK_BETA, str(config_b.task_text_path)
    )
    assert _normalized_system(system_a, RULE_ALPHA) == _normalized_system(system_b, RULE_BETA)

    run_a = tmp_path / "alpha" / "run"
    run_b = tmp_path / "beta" / "run"
    snapshot_a = json.loads((run_a / "input_snapshot.json").read_text(encoding="utf-8"))
    manifest_a = json.loads((run_a / "run_manifest.json").read_text(encoding="utf-8"))
    rule_file = run_a / "rules" / "rule_v1.md"
    assert snapshot_a["rule"]["injected_into"] == "system"
    assert snapshot_a["rule"]["snapshot_sha256"] == sha256_file(rule_file)
    assert manifest_a["rule"]["sha256"] == sha256_file(rule_file)
    assert manifest_a["inputs"]["rule"]["text"] == rule_file.read_text(encoding="utf-8")
    assert snapshot_a["request"]["system_sha256"] == sha256_text(system_a)
    assert snapshot_a["request"]["user_sha256"] == sha256_text(user_a)
    task_file_text = Path(str(config_a.task_text_path)).read_text(encoding="utf-8")
    assert snapshot_a["task"]["sha256"] == sha256_text(task_file_text)
    assert RULE_ALPHA in (run_a / "scientist_input.md").read_text(encoding="utf-8")
    assert TASK_ALPHA in (run_a / "scientist_input.md").read_text(encoding="utf-8")

    request_a = json.loads((run_a / "requests" / "request_001.json").read_text(encoding="utf-8"))
    assert request_a["message_count"] == 2
    assert request_a["tool_specs"] == snapshot_a["tools"]["specs"]
    assert {tool["function"]["name"] for tool in request_a["tool_specs"]} == {"read_evidence", "finish_study"}
    assert RULE_ALPHA in request_a["messages"][0]["content"]
    assert TASK_ALPHA in request_a["messages"][1]["content"]
    assert run_a != run_b


def test_missing_configured_rule_fails_before_any_model_call(tmp_path: Path) -> None:
    config, evidence = _config(tmp_path, name="missing_rule")
    object.__setattr__(config, "rule_text_path", str(tmp_path / "missing_rule" / "no_such_rule.md"))
    model = RecordingModel(evidence)
    runner = ResearchRunner(
        config,
        model_client=model,
        ledger=BudgetLedger(tmp_path / "missing_rule" / "budget.json", run_id="missing_rule", cap_cny=10, wrap_up_reserve_cny=0),
    )
    with pytest.raises(ResearchError, match="rule file is configured but missing"):
        runner.run()
    assert model.requests == []


def test_changed_rule_or_task_after_freeze_is_refused(tmp_path: Path) -> None:
    config, evidence = _config(tmp_path, name="frozen")
    ledger = BudgetLedger(tmp_path / "frozen" / "budget.json", run_id="frozen", cap_cny=10, wrap_up_reserve_cny=0)
    model = RecordingModel(evidence)
    ResearchRunner(config, model_client=model, ledger=ledger).run()
    calls = len(model.requests)

    rule_path = tmp_path / "frozen" / "rule.md"
    rule_path.write_text("DIFFERENT_RULE_AFTER_FREEZE\n", encoding="utf-8")
    with pytest.raises(ResearchError, match="rule source changed"):
        ResearchRunner(config, model_client=model, ledger=ledger).run()
    assert len(model.requests) == calls

    rule_path.write_text(RULE_ALPHA + "\nAlways cite the source.\n", encoding="utf-8")
    task_path = tmp_path / "frozen" / "task.md"
    task_path.write_text("DIFFERENT_TASK_AFTER_FREEZE\n", encoding="utf-8")
    with pytest.raises(ResearchError, match="task file differs"):
        ResearchRunner(config, model_client=model, ledger=ledger).run()
    assert len(model.requests) == calls


def test_legacy_run_without_rule_cannot_gain_one_on_resume(tmp_path: Path) -> None:
    config, evidence = _config(tmp_path, rule_text=None, name="legacy")
    ledger = BudgetLedger(tmp_path / "legacy" / "budget.json", run_id="legacy", cap_cny=10, wrap_up_reserve_cny=0)
    model = RecordingModel(evidence)
    ResearchRunner(config, model_client=model, ledger=ledger).run()
    calls = len(model.requests)
    new_rule = tmp_path / "legacy" / "late_rule.md"
    new_rule.write_text("LATE_RULE_MUST_NOT_APPEAR\n", encoding="utf-8")
    object.__setattr__(config, "rule_text_path", str(new_rule))
    with pytest.raises(ResearchError, match="rule source changed"):
        ResearchRunner(config, model_client=model, ledger=ledger).run()
    assert len(model.requests) == calls
