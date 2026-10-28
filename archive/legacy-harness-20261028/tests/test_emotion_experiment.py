"""Offline tests for the controlled emotion study and backend boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eeg_scientist.backends import UnverifiedBackendError, create_chat_client, load_registry
from eeg_scientist.deepseek_api import DeepSeekChatResult, DeepSeekToolCall, DeepSeekUsage
from eeg_scientist.emotion_experiment import _assert_lock, load_study
from eeg_scientist.evidence import EvidenceStore
from eeg_scientist.ledger import BudgetLedger
from eeg_scientist.meta import build_meta_messages
from eeg_scientist.research import ResearchConfig, ResearchRunner
from eeg_scientist.run_manifest import sha256_file, snapshot_code


def _ledger(tmp_path: Path, *, input_price: float = 2.0, output_price: float = 8.0) -> BudgetLedger:
    return BudgetLedger(
        tmp_path / "budget.json",
        run_id="test_emotion",
        cap_cny=10.0,
        wrap_up_reserve_cny=0.0,
        input_price_cny_per_mtok=input_price,
        output_price_cny_per_mtok=output_price,
        price_source="test",
        price_checked_at="2026-10-21",
    )


def _material_config(tmp_path: Path, evidence_id: str) -> ResearchConfig:
    material_root = tmp_path / "materials" / "evidence"
    store = EvidenceStore(material_root)
    store.add_text(url="https://example.org/paper", title="Paper", text="methods and results " * 40)
    manifest = tmp_path / "materials" / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "test_v1",
                "materials": [
                    {
                        "evidence_id": evidence_id,
                        "title": "Paper",
                        "version": "html",
                        "read_scope": "methods/results",
                        "extraction_limits": "tables not extracted",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rule = tmp_path / "rule.md"
    rule.write_text("Baseline rule: cite evidence.\n", encoding="utf-8")
    system = tmp_path / "system.md"
    system.write_text("You are a test scientist. Use read_evidence and finish_study.\n", encoding="utf-8")
    return ResearchConfig(
        run_id="test_material_run",
        run_dir=str(tmp_path / "run"),
        question="Test question?",
        deadline="2099-01-01T00:00:00+00:00",
        stop_new_at="2099-01-01T00:00:00+00:00",
        system_prompt_path=str(system),
        deliverables=["one proposal"],
        materials_manifest_path=str(manifest),
        material_evidence_dir=str(material_root),
        material_version="test_v1",
        material_manifest_sha256=sha256_file(manifest),
        rule_text_path=str(rule),
        rule_version="test_rule_v1",
        research_mode="materials_only",
        max_model_calls=4,
        max_tool_calls=4,
        max_turns=2,
        max_model_calls_per_turn=4,
        max_tool_calls_per_turn=4,
        max_output_tokens=2048,
        study_config={"study_id": "test_study"},
        model_info={"model_name": "fake", "provider": "fake", "status": "verified"},
        tool_info={},
        ledger_path=str(tmp_path / "budget.json"),
        code_root=".",
    )


class _MaterialModel:
    model_name = "fake-flash"
    provider_name = "fake"
    backend_status = "verified"

    def __init__(self, evidence_id: str) -> None:
        self.evidence_id = evidence_id
        self.calls = 0

    def chat(self, messages, *, tools=None, max_tokens=16384, json_mode=False, stage=""):  # type: ignore[no-untyped-def]
        self.calls += 1
        if not any(message.get("role") == "tool" for message in messages):
            return DeepSeekChatResult(
                content="",
                reasoning_content="read the material",
                tool_calls=[
                    DeepSeekToolCall(
                        id="c1",
                        name="read_evidence",
                        arguments=json.dumps({"evidence_id": self.evidence_id, "max_chars": 200}),
                    )
                ],
                finish_reason="tool_calls",
                requested_model="fake-flash",
                returned_model="fake-flash",
                usage=DeepSeekUsage(prompt_tokens=100, completion_tokens=10, total_tokens=110),
            )
        answer = "Proposal " + ("x" * 260) + f" [{self.evidence_id}]"
        return DeepSeekChatResult(
            content="",
            reasoning_content="finish",
            tool_calls=[
                DeepSeekToolCall(
                    id="c2",
                    name="finish_study",
                    arguments=json.dumps({"answer": answer, "evidence_ids": [self.evidence_id], "unresolved": []}),
                )
            ],
            finish_reason="tool_calls",
            requested_model="fake-flash",
            returned_model="fake-flash",
            usage=DeepSeekUsage(prompt_tokens=120, completion_tokens=20, total_tokens=140),
        )


def test_material_only_run_is_accepted_and_writes_manifest(tmp_path: Path) -> None:
    evidence_id = "ev_" + "a" * 12
    config = _material_config(tmp_path, evidence_id)
    # The manifest uses the content-derived ID; fix the temp store record to match.
    store = EvidenceStore(tmp_path / "materials" / "evidence")
    record = store.list_meta()[0]
    manifest_path = Path(str(config.materials_manifest_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["materials"][0]["evidence_id"] = record.evidence_id
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config.material_manifest_sha256 = sha256_file(manifest_path)
    model = _MaterialModel(record.evidence_id)
    runner = ResearchRunner(config, model_client=model, tool_client=None, ledger=_ledger(tmp_path))
    summary = runner.run()
    assert summary.accepted is True
    assert summary.acceptance == "accepted"
    assert summary.phase == "completed"
    final = json.loads((tmp_path / "run" / "final.json").read_text(encoding="utf-8"))
    assert final["accepted"] is True
    manifest_out = json.loads((tmp_path / "run" / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest_out["material"]["version"] == "test_v1"
    assert manifest_out["rule"]["version"] == "test_rule_v1"
    assert (tmp_path / "run" / "evidence" / "sources" / f"{record.evidence_id}.json").exists()
    assert not (tmp_path / "run" / "searches").exists()


def test_prose_finish_is_unverified_not_accepted(tmp_path: Path) -> None:
    evidence_id = "ev_" + "b" * 12
    config = _material_config(tmp_path, evidence_id)
    runner = ResearchRunner(config, model_client=_MaterialModel(evidence_id), tool_client=None, ledger=_ledger(tmp_path))
    runner._finish_without_tool("A prose answer " * 40)
    assert runner.state.phase == "completed_unverified"
    assert runner.state.accepted is False
    assert runner.state.acceptance == "unverified"
    final = json.loads((tmp_path / "run" / "final.json").read_text(encoding="utf-8"))
    assert final["accepted"] is False
    assert final["acceptance"] == "unverified"


def test_unverified_backend_is_refused_before_any_call(tmp_path: Path) -> None:
    registry = load_registry("configs/models/backends_20261021.json")
    ledger = _ledger(tmp_path)
    with pytest.raises(UnverifiedBackendError):
        create_chat_client(registry, "claude_opus", ledger=ledger, attribution="test")


def test_ledger_uses_configured_prices_and_attribution(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path, input_price=9.0, output_price=27.0)
    reservation = ledger.reserve_model("x" * 1000, 1000, attribution="runA")
    ledger.settle_model(reservation.reservation_id, prompt_tokens=1000, completion_tokens=1000)
    assert ledger.state.spent_cny == pytest.approx(0.036)
    snapshot = ledger.snapshot()
    assert snapshot["input_price_cny_per_mtok"] == 9.0
    assert snapshot["output_price_cny_per_mtok"] == 27.0
    assert snapshot["cost_by_attribution"]["runA"] == pytest.approx(0.036)


def test_meta_messages_do_not_contain_the_new_question(tmp_path: Path) -> None:
    old = tmp_path / "old"
    old.mkdir()
    (old / "final.json").write_text(json.dumps({"run_id": "old_run", "evidence_ids": []}), encoding="utf-8")
    (old / "final_answer.md").write_text("old answer", encoding="utf-8")
    review = tmp_path / "REVIEW.md"
    review.write_text("review finding with source label", encoding="utf-8")
    messages, provenance = build_meta_messages(
        old_run_dir=old,
        review_files=[review],
        allowed_source_ids=["literature_v1:final_answer", "literature_v1:final_json", "review:REVIEW"],
    )
    user_text = str(messages[1]["content"])
    assert "state-vs-trait" not in user_text.lower()
    assert "emotion_state_trait" not in user_text
    assert "old_run" in user_text
    assert "review:REVIEW" in provenance["allowed_source_ids"]


def test_study_lock_matches_frozen_artifacts() -> None:
    _assert_lock(load_study())


def test_code_snapshot_copies_executable_sources(tmp_path: Path) -> None:
    result = snapshot_code(Path("."), tmp_path / "run")
    assert result["files"] > 10
    assert (tmp_path / "run" / "code_snapshot" / "src" / "eeg_scientist" / "scientist.py").exists()
    manifest = json.loads(
        (tmp_path / "run" / "code_snapshot" / "MANIFEST.json").read_text(encoding="utf-8")
    )
    assert manifest["aggregate_sha256"] == result["aggregate_sha256"]
    assert any(item["path"] == "pyproject.toml" for item in manifest["files"])
