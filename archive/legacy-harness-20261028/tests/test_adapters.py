"""Offline contract tests for Claude/Gemini adapters and credential loading."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from eeg_scientist.anthropic_api import AnthropicClient
from eeg_scientist.credentials import load_secret
from eeg_scientist.gemini_api import GeminiClient
from eeg_scientist.ledger import BudgetLedger


def _ledger(tmp_path: Path, name: str) -> BudgetLedger:
    return BudgetLedger(
        tmp_path / f"{name}.json",
        run_id=name,
        cap_cny=10,
        wrap_up_reserve_cny=0,
        model_attempts_limit=4,
        input_tokens_limit=1_000_000,
        output_tokens_limit=100_000,
    )


def test_anthropic_messages_tool_roundtrip(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("x-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "model": "claude-test",
                "content": [
                    {"type": "text", "text": "Use the evidence."},
                    {"type": "tool_use", "id": "toolu_1", "name": "read_evidence", "input": {"evidence_id": "ev_test"}},
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 12, "output_tokens": 5},
            },
        )

    client = AnthropicClient(
        api_key="sk-ant-test-01234567890123456789",
        ledger=_ledger(tmp_path, "claude"),
        model="claude-test",
        transport=httpx.MockTransport(handler),
    )
    result = client.chat(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "question"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "read_evidence",
                    "description": "read",
                    "parameters": {"type": "object", "properties": {"evidence_id": {"type": "string"}}},
                },
            }
        ],
    )
    assert seen["path"] == "/v1/messages"
    assert seen["key"] == "sk-ant-test-01234567890123456789"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["tools"][0]["input_schema"]["properties"]["evidence_id"]["type"] == "string"
    assert result.content == "Use the evidence."
    assert result.tool_calls[0].name == "read_evidence"
    assert result.usage.prompt_tokens == 12
    assert result.usage.completion_tokens == 5
    assert client.call_count == 1


def test_gemini_generate_content_tool_roundtrip(tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "responseId": "resp_test",
                "modelVersion": "gemini-test",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "Read the source."},
                                {"functionCall": {"name": "read_evidence", "args": {"evidence_id": "ev_test"}}},
                            ]
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4},
            },
        )

    client = GeminiClient(
        api_key="AIza-test-01234567890123456789",
        ledger=_ledger(tmp_path, "gemini"),
        model="gemini-test",
        transport=httpx.MockTransport(handler),
    )
    result = client.chat(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "question"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "read_evidence",
                    "description": "read",
                    "parameters": {"type": "object", "properties": {"evidence_id": {"type": "string"}}},
                },
            }
        ],
    )
    assert seen["path"] == "/v1beta/models/gemini-test:generateContent"
    assert seen["key"] == "AIza-test-01234567890123456789"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["tools"][0]["functionDeclarations"][0]["name"] == "read_evidence"
    assert result.content == "Read the source."
    assert result.tool_calls[0].name == "read_evidence"
    assert result.usage.total_tokens == 14


def test_gemini_requires_usage_and_keeps_unknown(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "no usage"}]}}]})

    client = GeminiClient(
        api_key="AIza-test-01234567890123456789",
        ledger=_ledger(tmp_path, "gemini_unknown"),
        model="gemini-test",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(Exception, match="usage"):
        client.chat([{"role": "user", "content": "q"}])
    snapshot = client.ledger.snapshot()
    assert snapshot["unknown_cny"] > 0


def test_load_secret_accepts_plain_and_dotenv(tmp_path: Path) -> None:
    plain = tmp_path / "gemini.txt"
    plain.write_text("AIza-test-01234567890123456789\n", encoding="utf-8")
    key, report = load_secret(plain, "GEMINI_API_KEY", allowed_prefixes=("AIza",))
    assert key.startswith("AIza")
    assert report.key_present is True
    dotenv = tmp_path / "claude.env"
    dotenv.write_text("ANTHROPIC_API_KEY=sk-ant-test-01234567890123456789\n", encoding="utf-8")
    key2, _ = load_secret(dotenv, "ANTHROPIC_API_KEY", allowed_prefixes=("sk-ant-",))
    assert key2.startswith("sk-ant-")
