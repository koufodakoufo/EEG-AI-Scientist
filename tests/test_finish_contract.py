"""Regression tests for strict finish_study validation and truncation retry limits."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eeg_scientist.deepseek_api import DeepSeekChatResult, DeepSeekToolCall, DeepSeekUsage
from eeg_scientist.ledger import BudgetLedger
from eeg_scientist.research import ResearchConfig, ResearchError, ResearchRunner


class _SilentModel:
    model_name = "offline"
    provider_name = "offline"
    backend_status = "unverified"

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, *, tools=None, max_tokens=16384, json_mode=False, stage=""):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise AssertionError("model must not be called in these tests")


class _TruncatingModel:
    model_name = "offline-truncating"
    provider_name = "offline"
    backend_status = "unverified"

    def __init__(self) -> None:
        self.calls = 0
        self.max_tokens_seen: list[int] = []

    def chat(self, messages, *, tools=None, max_tokens=16384, json_mode=False, stage=""):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.max_tokens_seen.append(max_tokens)
        return DeepSeekChatResult(
            tool_calls=[
                DeepSeekToolCall(
                    id="truncated_call",
                    name="finish_study",
                    arguments=json.dumps({"answer": "partial", "evidence_ids": [], "unresolved": []}),
                )
            ],
            finish_reason="max_tokens",
            requested_model=self.model_name,
            usage=DeepSeekUsage(prompt_tokens=10, completion_tokens=2, total_tokens=12),
            truncated=True,
        )


def _config(tmp_path: Path, *, max_model_calls: int = 4) -> ResearchConfig:
    return ResearchConfig(
        run_id="finish_contract",
        run_dir=str(tmp_path / "run"),
        question="Does finish_study validate required fields?",
        deadline="2099-01-01T00:00:00+00:00",
        stop_new_at="2099-01-01T00:00:00+00:00",
        max_model_calls=max_model_calls,
        max_tool_calls=4,
        max_turns=2,
        max_model_calls_per_turn=4,
        max_tool_calls_per_turn=4,
        max_output_tokens=2048,
        max_output_tokens_retry=4096,
        research_mode="materials_only",
    )


def _runner(tmp_path: Path) -> tuple[ResearchRunner, str]:
    ledger = BudgetLedger(tmp_path / "budget.json", run_id="finish_contract", cap_cny=10, wrap_up_reserve_cny=0)
    runner = ResearchRunner(_config(tmp_path), model_client=_SilentModel(), ledger=ledger)
    record = runner.evidence.add_text(url="https://example.org/f", title="F", text="source text " * 40)
    runner.evidence.read(record.evidence_id, max_chars=50)
    return runner, record.evidence_id


def _call() -> DeepSeekToolCall:
    return DeepSeekToolCall(id="finish_call", name="finish_study", arguments="{}")


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"evidence_ids": ["ev_x"], "unresolved": []}, "requires a string 'answer'"),
        ({"answer": "x" * 250, "unresolved": []}, "requires an 'evidence_ids' list"),
        ({"answer": "x" * 250, "evidence_ids": ["ev_x"]}, "requires an 'unresolved' list"),
        ({"answer": 123, "evidence_ids": ["ev_x"], "unresolved": []}, "'answer' must be a string"),
        ({"answer": "x" * 250, "evidence_ids": "ev_x", "unresolved": []}, "evidence_ids must be a list"),
        ({"answer": "x" * 250, "evidence_ids": ["ev_x"], "unresolved": "gap"}, "unresolved must be a list"),
        ({"answer": "x" * 250, "evidence_ids": ["ev_x"], "unresolved": [""]}, "unresolved entries must be non-empty"),
        ({"answer": "short", "evidence_ids": ["ev_x"], "unresolved": []}, "implausibly short"),
    ],
)
def test_finish_rejects_missing_or_wrongly_typed_arguments(
    tmp_path: Path, arguments: dict[str, object], message: str
) -> None:
    runner, _evidence_id = _runner(tmp_path)
    with pytest.raises(ResearchError, match=message):
        runner._tool_finish(arguments, _call())
    assert runner.state.accepted is False


def test_finish_accepts_explicit_empty_unresolved(tmp_path: Path) -> None:
    runner, evidence_id = _runner(tmp_path)
    result = runner._tool_finish(
        {"answer": "Proposal " + "y" * 240 + f" [{evidence_id}]", "evidence_ids": [evidence_id], "unresolved": []},
        _call(),
    )
    assert result["status"] == "completed"
    final = json.loads((tmp_path / "run" / "final.json").read_text(encoding="utf-8"))
    assert final["unresolved"] == []
    assert final["accepted"] is True


def test_truncated_tool_arguments_are_not_executed_and_retry_is_bounded(tmp_path: Path) -> None:
    model = _TruncatingModel()
    ledger = BudgetLedger(tmp_path / "budget.json", run_id="finish_contract", cap_cny=10, wrap_up_reserve_cny=0)
    runner = ResearchRunner(_config(tmp_path, max_model_calls=1), model_client=model, ledger=ledger)
    summary = runner.run()
    assert summary.phase == "failed"
    assert model.calls == 1
    assert model.max_tokens_seen == [2048]
    assert not (tmp_path / "run" / "final.json").exists()
    messages = json.loads((tmp_path / "run" / "messages.json").read_text(encoding="utf-8"))
    assert all(message.get("role") != "tool" for message in messages)


def test_two_truncations_fail_without_executing_partial_tool_call(tmp_path: Path) -> None:
    model = _TruncatingModel()
    ledger = BudgetLedger(tmp_path / "budget.json", run_id="finish_contract", cap_cny=10, wrap_up_reserve_cny=0)
    runner = ResearchRunner(_config(tmp_path, max_model_calls=4), model_client=model, ledger=ledger)
    summary = runner.run()
    assert summary.phase == "failed"
    assert "truncated twice" in summary.stop_reason
    assert model.max_tokens_seen == [2048, 4096]
    assert not (tmp_path / "run" / "final.json").exists()
    messages = json.loads((tmp_path / "run" / "messages.json").read_text(encoding="utf-8"))
    assert all(message.get("role") != "tool" for message in messages)
