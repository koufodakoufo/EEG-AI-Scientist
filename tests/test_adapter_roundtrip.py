"""Two-request Claude/Gemini protocol roundtrips, checked at the wire boundary."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from eeg_scientist.anthropic_api import AnthropicClient
from eeg_scientist.evidence import EvidenceStore
from eeg_scientist.gemini_api import GeminiClient
from eeg_scientist.ledger import BudgetLedger
from eeg_scientist.research import ResearchConfig, ResearchRunner
from eeg_scientist.run_manifest import sha256_file


def _runner(tmp_path: Path, client: Any, *, name: str = "roundtrip") -> tuple[ResearchRunner, list[str], BudgetLedger]:
    materials = tmp_path / name / "materials"
    store = EvidenceStore(materials / "evidence")
    first = store.add_text(url="https://example.org/first", title="First", text="first evidence body " * 60)
    second = store.add_text(url="https://example.org/second", title="Second", text="second evidence body " * 60)
    manifest = materials / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "v1",
                "materials": [
                    {"evidence_id": first.evidence_id, "title": "First", "version": "v1"},
                    {"evidence_id": second.evidence_id, "title": "Second", "version": "v1"},
                ],
            }
        ),
        encoding="utf-8",
    )
    task = tmp_path / name / "task.md"
    task.write_text("# Task\n\nRead both sources and submit a proposal.\n", encoding="utf-8")
    system = tmp_path / name / "system.md"
    system.write_text("SYSTEM: use read_evidence and finish_study.\n", encoding="utf-8")
    ledger = BudgetLedger(
        tmp_path / name / "budget.json",
        run_id=name,
        cap_cny=10,
        wrap_up_reserve_cny=0,
        model_attempts_limit=20,
        input_tokens_limit=1_000_000,
        output_tokens_limit=100_000,
    )
    config = ResearchConfig(
        run_id=name,
        run_dir=str(tmp_path / name / "run"),
        question="metadata",
        deadline="2099-01-01T00:00:00+00:00",
        stop_new_at="2099-01-01T00:00:00+00:00",
        task_text_path=str(task),
        system_prompt_path=str(system),
        deliverables=["one proposal"],
        materials_manifest_path=str(manifest),
        material_evidence_dir=str(materials / "evidence"),
        material_version="v1",
        material_manifest_sha256=sha256_file(manifest),
        research_mode="materials_only",
        max_model_calls=8,
        max_tool_calls=8,
        max_turns=3,
        max_model_calls_per_turn=8,
        max_tool_calls_per_turn=8,
        max_output_tokens=12000,
        max_output_tokens_retry=24000,
        study_config={"study_id": "adapter_test"},
        model_info={"model": getattr(client, "model_name", ""), "status": "unverified"},
        ledger_path=str(tmp_path / name / "budget.json"),
        code_root=str(tmp_path),
    )
    runner = ResearchRunner(config, model_client=client, tool_client=None, ledger=ledger)
    if hasattr(client, "ledger"):
        # Keep one ledger for both the adapter's reservations and the runner's
        # final budget snapshot, matching production wiring.
        client.ledger = ledger
    return runner, [first.evidence_id, second.evidence_id], ledger


def _answer(evidence_ids: list[str]) -> str:
    return "Proposal " + ("z" * 240) + " " + " ".join(f"[{item}]" for item in evidence_ids)


def _anthropic_client(tmp_path: Path, responses: list[dict[str, object]], seen: list[dict[str, object]]) -> AnthropicClient:
    ledger = BudgetLedger(
        tmp_path / "anthropic_protocol_budget.json",
        run_id="anthropic_protocol",
        cap_cny=10,
        wrap_up_reserve_cny=0,
        model_attempts_limit=20,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        if len(seen) > len(responses):
            raise AssertionError("unexpected extra Anthropic request")
        return httpx.Response(200, json=responses[len(seen) - 1])

    return AnthropicClient(
        api_key="sk-ant-test-01234567890123456789",
        ledger=ledger,
        model="claude-test",
        transport=httpx.MockTransport(handler),
    )


def test_anthropic_two_requests_replay_thinking_signature_and_cache_usage(tmp_path: Path) -> None:
    seen: list[dict[str, object]] = []
    responses: list[dict[str, object]] = [
        {
            "id": "msg_1",
            "model": "claude-test",
            "content": [
                {"type": "thinking", "thinking": "opaque reasoning", "signature": "CLAUDE_SIGNATURE_ONE"},
                {"type": "redacted_thinking", "data": "ENCRYPTED_REDACTED_BLOCK"},
                {"type": "text", "text": "Reading the first source."},
                {"type": "tool_use", "id": "toolu_1", "name": "read_evidence", "input": {"evidence_id": "PLACEHOLDER", "max_chars": 100}},
            ],
            "stop_reason": "tool_use",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_input_tokens": 100,
                "cache_creation_input_tokens": 50,
            },
        },
        {
            "id": "msg_2",
            "model": "claude-test",
            "content": [
                {"type": "thinking", "thinking": "finish", "signature": "CLAUDE_SIGNATURE_TWO"},
                {"type": "tool_use", "id": "toolu_2", "name": "finish_study", "input": {"answer": "PLACEHOLDER", "evidence_ids": ["PLACEHOLDER"], "unresolved": []}},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 20, "output_tokens": 6},
        },
    ]
    client = _anthropic_client(tmp_path, responses, seen)
    runner, evidence_ids, ledger = _runner(tmp_path, client)
    responses[0]["content"][3]["input"]["evidence_id"] = evidence_ids[0]  # type: ignore[index]
    responses[1]["content"][1]["input"]["answer"] = _answer([evidence_ids[0]])  # type: ignore[index]
    responses[1]["content"][1]["input"]["evidence_ids"] = [evidence_ids[0]]  # type: ignore[index]
    summary = runner.run()
    assert summary.accepted is True
    assert client.call_count == 2
    assert len(seen) == 2
    first_request, second_request = seen
    assert first_request["thinking"] == {"type": "enabled", "budget_tokens": 4096}
    assistant = next(message for message in second_request["messages"] if message["role"] == "assistant")
    blocks = assistant["content"]
    assert blocks[0]["type"] == "thinking"
    assert blocks[0]["signature"] == "CLAUDE_SIGNATURE_ONE"
    assert blocks[1] == {"type": "redacted_thinking", "data": "ENCRYPTED_REDACTED_BLOCK"}
    assert any(block.get("type") == "tool_use" and block.get("id") == "toolu_1" for block in blocks)
    tool_message = next(message for message in second_request["messages"] if message["role"] == "user" and message["content"][0].get("type") == "tool_result")
    assert tool_message["content"][0]["tool_use_id"] == "toolu_1"
    # Cached tokens are included in prompt accounting, not dropped as zero.
    response_one = json.loads((tmp_path / "roundtrip" / "run" / "responses" / "response_001.json").read_text(encoding="utf-8"))
    assert response_one["usage"]["prompt_tokens"] == 160
    assert response_one["usage"]["cache_read_tokens"] == 100
    assert response_one["usage"]["cache_creation_tokens"] == 50
    assert ledger.snapshot()["input_tokens"] == 180


def test_anthropic_parallel_tool_results_are_merged_and_ids_stay_unique(tmp_path: Path) -> None:
    seen: list[dict[str, object]] = []
    responses: list[dict[str, object]] = [
        {
            "id": "msg_parallel_1",
            "model": "claude-test",
            "content": [
                {"type": "tool_use", "id": "toolu_a", "name": "read_evidence", "input": {"evidence_id": "PLACEHOLDER_A", "max_chars": 50}},
                {"type": "tool_use", "id": "toolu_b", "name": "read_evidence", "input": {"evidence_id": "PLACEHOLDER_B", "max_chars": 50}},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
        {
            "id": "msg_parallel_2",
            "model": "claude-test",
            "content": [{"type": "tool_use", "id": "toolu_finish", "name": "finish_study", "input": {}}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 20, "output_tokens": 6},
        },
    ]
    client = _anthropic_client(tmp_path, responses, seen)
    runner, evidence_ids, _ledger = _runner(tmp_path, client, name="parallel")
    responses[0]["content"][0]["input"]["evidence_id"] = evidence_ids[0]  # type: ignore[index]
    responses[0]["content"][1]["input"]["evidence_id"] = evidence_ids[1]  # type: ignore[index]
    responses[1]["content"][0]["input"] = {  # type: ignore[index]
        "answer": _answer(evidence_ids),
        "evidence_ids": evidence_ids,
        "unresolved": [],
    }
    summary = runner.run()
    assert summary.accepted is True
    second_request = seen[1]
    assistant = next(message for message in second_request["messages"] if message["role"] == "assistant")
    assert [block["id"] for block in assistant["content"]] == ["toolu_a", "toolu_b"]
    tool_messages = [
        message
        for message in second_request["messages"]
        if message["role"] == "user" and message["content"][0].get("type") == "tool_result"
    ]
    assert len(tool_messages) == 1
    assert [block["tool_use_id"] for block in tool_messages[0]["content"]] == ["toolu_a", "toolu_b"]


def test_anthropic_max_tokens_is_truncated_and_partial_tool_is_not_executed(tmp_path: Path) -> None:
    seen: list[dict[str, object]] = []
    responses: list[dict[str, object]] = [
        {
            "id": "msg_truncated",
            "model": "claude-test",
            "content": [
                {"type": "tool_use", "id": "toolu_partial", "name": "read_evidence", "input": {"evidence_id": "PLACEHOLDER", "max_chars": 100}}
            ],
            "stop_reason": "max_tokens",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
        {
            "id": "msg_retry",
            "model": "claude-test",
            "content": [
                {"type": "tool_use", "id": "toolu_still_partial", "name": "read_evidence", "input": {"evidence_id": "PLACEHOLDER", "max_chars": 100}}
            ],
            "stop_reason": "max_tokens",
            "usage": {"input_tokens": 12, "output_tokens": 6},
        },
    ]
    client = _anthropic_client(tmp_path, responses, seen)
    runner, evidence_ids, _ledger = _runner(tmp_path, client, name="truncated")
    responses[0]["content"][0]["input"]["evidence_id"] = evidence_ids[0]  # type: ignore[index]
    responses[1]["content"][0]["input"]["evidence_id"] = evidence_ids[0]  # type: ignore[index]
    summary = runner.run()
    assert client.call_count == 2
    assert seen[0]["max_tokens"] == 12000
    assert seen[1]["max_tokens"] == 24000
    assert all(message["role"] != "tool" for message in seen[1]["messages"])
    assert summary.accepted is False
    assert summary.phase == "failed"
    assert "truncated twice" in summary.stop_reason


def test_anthropic_parse_marks_truncation_and_cache_usage(tmp_path: Path) -> None:
    ledger = BudgetLedger(tmp_path / "parse_budget.json", run_id="parse", cap_cny=1, wrap_up_reserve_cny=0)
    client = AnthropicClient(api_key="offline", ledger=ledger, model="claude-test")
    raw = {
        "id": "msg_parse",
        "model": "claude-test",
        "content": [{"type": "thinking", "thinking": "why", "signature": "SIG"}],
        "stop_reason": "max_tokens",
        "usage": {"input_tokens": 10, "output_tokens": 4, "cache_read_input_tokens": 2, "cache_creation_input_tokens": 3},
    }
    result = client._parse(raw, time.perf_counter())
    assert result.truncated is True
    assert result.usage.prompt_tokens == 15
    assert result.usage.completion_tokens == 4
    assert result.usage.cache_read_tokens == 2
    assert result.native_blocks[0]["signature"] == "SIG"


def _gemini_client(tmp_path: Path, responses: list[dict[str, object]], seen: list[dict[str, object]]) -> GeminiClient:
    ledger = BudgetLedger(
        tmp_path / "gemini_protocol_budget.json",
        run_id="gemini_protocol",
        cap_cny=10,
        wrap_up_reserve_cny=0,
        model_attempts_limit=20,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        if len(seen) > len(responses):
            raise AssertionError("unexpected extra Gemini request")
        return httpx.Response(200, json=responses[len(seen) - 1])

    return GeminiClient(
        api_key="AIza-test-01234567890123456789",
        ledger=ledger,
        model="gemini-test",
        transport=httpx.MockTransport(handler),
    )


def _gemini_response(parts: list[dict[str, object]], *, finish: str = "STOP", prompt: int = 10, candidates: int = 4, thoughts: int = 6) -> dict[str, object]:
    return {
        "responseId": "resp_test",
        "modelVersion": "gemini-test",
        "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": finish}],
        "usageMetadata": {
            "promptTokenCount": prompt,
            "candidatesTokenCount": candidates,
            "thoughtsTokenCount": thoughts,
            "totalTokenCount": prompt + candidates + thoughts,
        },
    }


def test_gemini_two_requests_replay_signature_and_count_thoughts(tmp_path: Path) -> None:
    seen: list[dict[str, object]] = []
    first = _gemini_response(
        [
            {"text": "Reading both.", "thought": False},
            {"text": "internal reasoning", "thought": True},
            {"functionCall": {"name": "read_evidence", "args": {"evidence_id": "PLACEHOLDER_A", "max_chars": 80}}, "thoughtSignature": "GEMINI_SIG_A"},
            {"functionCall": {"name": "read_evidence", "args": {"evidence_id": "PLACEHOLDER_B", "max_chars": 80}}, "thoughtSignature": "GEMINI_SIG_B"},
        ]
    )
    second = _gemini_response(
        [{"functionCall": {"name": "finish_study", "args": {}}, "thoughtSignature": "GEMINI_SIG_FINISH"}],
        prompt=20,
        candidates=8,
        thoughts=2,
    )
    client = _gemini_client(tmp_path, [first, second], seen)
    runner, evidence_ids, ledger = _runner(tmp_path, client, name="gemini")
    first["candidates"][0]["content"]["parts"][2]["functionCall"]["args"]["evidence_id"] = evidence_ids[0]  # type: ignore[index]
    first["candidates"][0]["content"]["parts"][3]["functionCall"]["args"]["evidence_id"] = evidence_ids[1]  # type: ignore[index]
    second["candidates"][0]["content"]["parts"][0]["functionCall"]["args"] = {  # type: ignore[index]
        "answer": _answer(evidence_ids),
        "evidence_ids": evidence_ids,
        "unresolved": [],
    }
    summary = runner.run()
    assert summary.accepted is True
    assert client.call_count == 2
    second_request = seen[1]
    model_turn = next(content for content in second_request["contents"] if content["role"] == "model")
    signatures = [part.get("thoughtSignature") for part in model_turn["parts"] if "thoughtSignature" in part]
    assert signatures == ["GEMINI_SIG_A", "GEMINI_SIG_B"]
    model_response_turn = next(
        content
        for content in second_request["contents"]
        if content["role"] == "user" and all("functionResponse" in part for part in content["parts"])
    )
    assert [part["functionResponse"]["name"] for part in model_response_turn["parts"]] == ["read_evidence", "read_evidence"]
    assistant_messages = [
        message for message in json.loads((tmp_path / "gemini" / "run" / "messages.json").read_text(encoding="utf-8")) if message["role"] == "assistant"
    ]
    assert [call["id"] for call in assistant_messages[0]["tool_calls"]] == ["gcall_001", "gcall_002"]
    first_response = json.loads((tmp_path / "gemini" / "run" / "responses" / "response_001.json").read_text(encoding="utf-8"))
    assert first_response["usage"]["completion_tokens"] == 10
    assert first_response["usage"]["reasoning_tokens"] == 6
    assert first_response["usage"]["total_tokens"] == 20
    assert ledger.snapshot()["output_tokens"] == 20


def test_gemini_cross_turn_tool_ids_are_unique(tmp_path: Path) -> None:
    seen: list[dict[str, object]] = []
    responses = [
        _gemini_response(
            [{"functionCall": {"name": "read_evidence", "args": {"evidence_id": "PLACEHOLDER_A"}}, "thoughtSignature": "SIG_TURN_1"}]
        ),
        _gemini_response(
            [{"functionCall": {"name": "read_evidence", "args": {"evidence_id": "PLACEHOLDER_B"}}, "thoughtSignature": "SIG_TURN_2"}]
        ),
        _gemini_response([{"functionCall": {"name": "finish_study", "args": {}}, "thoughtSignature": "SIG_TURN_3"}]),
    ]
    client = _gemini_client(tmp_path, responses, seen)
    runner, evidence_ids, _ledger = _runner(tmp_path, client, name="gemini_turns")
    responses[0]["candidates"][0]["content"]["parts"][0]["functionCall"]["args"]["evidence_id"] = evidence_ids[0]  # type: ignore[index]
    responses[1]["candidates"][0]["content"]["parts"][0]["functionCall"]["args"]["evidence_id"] = evidence_ids[1]  # type: ignore[index]
    responses[2]["candidates"][0]["content"]["parts"][0]["functionCall"]["args"] = {  # type: ignore[index]
        "answer": _answer(evidence_ids),
        "evidence_ids": evidence_ids,
        "unresolved": [],
    }
    summary = runner.run()
    assert summary.accepted is True
    assert client.call_count == 3
    messages = json.loads((tmp_path / "gemini_turns" / "run" / "messages.json").read_text(encoding="utf-8"))
    assistant_ids = [
        call["id"] for message in messages if message["role"] == "assistant" for call in message.get("tool_calls", [])
    ]
    assert assistant_ids == ["gcall_001", "gcall_002", "gcall_003"]
    assert len(set(assistant_ids)) == len(assistant_ids)


def test_gemini_parse_marks_max_tokens_and_keeps_thought_usage(tmp_path: Path) -> None:
    ledger = BudgetLedger(tmp_path / "gemini_parse_budget.json", run_id="parse", cap_cny=1, wrap_up_reserve_cny=0)
    client = GeminiClient(api_key="offline", ledger=ledger, model="gemini-test")
    raw = _gemini_response(
        [{"functionCall": {"name": "read_evidence", "args": {}}, "thoughtSignature": "PARSE_SIG"}],
        finish="MAX_TOKENS",
    )
    result = client._parse(raw, time.perf_counter(), call_index_start=5)
    assert result.truncated is True
    assert result.tool_calls[0].id == "gcall_006"
    assert result.usage.completion_tokens == 10
    assert result.usage.reasoning_tokens == 6
    assert result.usage.total_tokens == 20
    assert result.native_blocks[0]["thoughtSignature"] == "PARSE_SIG"
