"""Anthropic Messages adapter for the existing ResearchRunner tool loop."""

from __future__ import annotations

import json
import time
from typing import cast

import httpx

from .deepseek_api import DeepSeekChatResult, DeepSeekError, DeepSeekToolCall, DeepSeekUsage
from .ledger import BudgetLedger


class AnthropicClient:
    """Real Messages API client; no fallback provider and no hidden retries."""

    provider_name = "anthropic"
    backend = "real_llm"
    backend_status = "unverified"

    def __init__(
        self,
        *,
        api_key: str,
        ledger: BudgetLedger,
        model: str,
        base_url: str = "https://api.anthropic.com",
        timeout_seconds: int = 600,
        connect_timeout_seconds: int = 20,
        max_tokens: int = 16384,
        attribution: str = "",
        thinking: bool = True,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not model:
            raise ValueError("model is required")
        self.api_key = api_key
        self.ledger = ledger
        self.model_name = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self.max_tokens = max_tokens
        self.attribution = attribution
        self.thinking = thinking
        self.transport = transport
        self.call_count = 0

    def __repr__(self) -> str:
        return f"AnthropicClient(model={self.model_name!r}, status={self.backend_status!r})"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _client(self) -> httpx.Client:
        timeout = httpx.Timeout(self.timeout_seconds, connect=self.connect_timeout_seconds)
        return httpx.Client(timeout=timeout, transport=self.transport)

    @staticmethod
    def _tool_name_by_id(messages: list[dict[str, object]]) -> dict[str, str]:
        names: dict[str, str] = {}
        for message in messages:
            if message.get("role") != "assistant":
                continue
            calls = message.get("tool_calls")
            if not isinstance(calls, list):
                continue
            for call in calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function")
                if isinstance(function, dict):
                    name = function.get("name")
                    identifier = call.get("id")
                    if isinstance(name, str) and isinstance(identifier, str):
                        names[identifier] = name
        return names

    def _wire(self, messages: list[dict[str, object]], tools: list[dict[str, object]] | None) -> tuple[str, list[dict[str, object]]]:
        system_parts: list[str] = []
        wire: list[dict[str, object]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            if role == "system":
                system_parts.append(text)
                continue
            if role == "user":
                wire.append({"role": "user", "content": [{"type": "text", "text": text}]})
                continue
            if role == "tool":
                identifier = message.get("tool_call_id")
                if not isinstance(identifier, str) or not identifier:
                    raise DeepSeekError("bad_message", "tool message lacks tool_call_id")
                block: dict[str, object] = {
                    "type": "tool_result",
                    "tool_use_id": identifier,
                    "content": text,
                }
                if text.lstrip().startswith('{"status":"error"'):
                    block["is_error"] = True
                self._append_tool_result(wire, block)
                continue
            if role == "assistant":
                blocks = self._assistant_blocks(message, text)
                if blocks:
                    wire.append({"role": "assistant", "content": blocks})
                continue
            raise DeepSeekError("bad_message", f"unsupported message role {role!r}")
        if tools:
            # Anthropic tools are top-level objects, not OpenAI's function wrapper.
            converted: list[dict[str, object]] = []
            for tool in tools:
                function = tool.get("function") if isinstance(tool, dict) else None
                if not isinstance(function, dict):
                    raise DeepSeekError("bad_request", "tool lacks function object")
                converted.append(
                    {
                        "name": str(function.get("name", "")),
                        "description": str(function.get("description", "")),
                        "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
            self._converted_tools = converted
        else:
            self._converted_tools = []
        return "\n\n".join(system_parts), wire

    def _assistant_blocks(self, message: dict[str, object], text: str) -> list[dict[str, object]]:
        """Replay the vendor-native assistant content when available.

        Anthropic requires thinking/redacted_thinking blocks (including their
        original signature/data) to be sent back before the tool_result for a
        tool_use turn.  Rebuilding history from ``content``/``tool_calls`` loses
        that signature, so native blocks take precedence.
        """

        native = message.get("native_blocks")
        blocks: list[dict[str, object]] = []
        if isinstance(native, list) and native:
            for block in native:
                if not isinstance(block, dict):
                    continue
                if not self.thinking and block.get("type") in {"thinking", "redacted_thinking"}:
                    continue
                blocks.append(dict(block))
            return blocks
        if text:
            blocks.append({"type": "text", "text": text})
        calls = message.get("tool_calls")
        if isinstance(calls, list):
            for call in calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function")
                identifier = call.get("id")
                if not isinstance(function, dict) or not isinstance(identifier, str):
                    raise DeepSeekError("bad_message", "assistant tool_call is malformed")
                name = str(function.get("name", ""))
                arguments = str(function.get("arguments", "{}"))
                try:
                    parsed = json.loads(arguments) if arguments.strip() else {}
                except json.JSONDecodeError as error:
                    raise DeepSeekError("bad_message", f"tool arguments are not JSON: {error}") from error
                if not isinstance(parsed, dict):
                    raise DeepSeekError("bad_message", "tool arguments must be a JSON object")
                blocks.append({"type": "tool_use", "id": identifier, "name": name, "input": parsed})
        return blocks

    @staticmethod
    def _append_tool_result(wire: list[dict[str, object]], block: dict[str, object]) -> None:
        """Merge parallel tool results into one user turn, as the API expects."""

        if wire:
            last = wire[-1]
            last_content = last.get("content")
            if (
                last.get("role") == "user"
                and isinstance(last_content, list)
                and last_content
                and all(isinstance(item, dict) and item.get("type") == "tool_result" for item in last_content)
            ):
                last_content.append(block)
                return
        wire.append({"role": "user", "content": [block]})

    def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 16384,
        json_mode: bool = False,
        stage: str = "",
    ) -> DeepSeekChatResult:
        if not messages:
            raise DeepSeekError("bad_request", "messages must not be empty")
        system, wire = self._wire(messages, tools)
        payload: dict[str, object] = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "messages": wire,
        }
        if system:
            payload["system"] = system
        converted_tools = getattr(self, "_converted_tools", [])
        if converted_tools:
            payload["tools"] = converted_tools
        if self.thinking and max_tokens > 1024:
            # budget_tokens must be smaller than max_tokens; the API minimum is 1024.
            budget = min(4096, max_tokens - 1)
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
        reservation = self.ledger.reserve_model(
            json.dumps(payload, ensure_ascii=False, default=str),
            max_tokens,
            attribution=self.attribution,
        )
        self.call_count += 1
        started = time.perf_counter()
        try:
            with self._client() as client:
                response = client.post(f"{self.base_url}/v1/messages", headers=self._headers(), json=payload)
        except httpx.TimeoutException as error:
            self.ledger.mark_unknown(reservation.reservation_id, f"timeout: {type(error).__name__}")
            raise DeepSeekError("timeout", "Anthropic request timed out", retryable=True) from error
        except httpx.HTTPError as error:
            self.ledger.release(reservation.reservation_id, f"transport: {type(error).__name__}")
            raise DeepSeekError("network", f"Anthropic transport: {type(error).__name__}") from error
        if response.status_code != 200:
            self.ledger.release(reservation.reservation_id, f"HTTP {response.status_code}")
            raise DeepSeekError(
                "http_error",
                f"Anthropic HTTP {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
                retryable=response.status_code in {408, 429, 500, 502, 503, 504},
            )
        try:
            raw = response.json()
            result = self._parse(raw, started)
        except (ValueError, KeyError, TypeError) as error:
            self.ledger.mark_unknown(reservation.reservation_id, "unparseable Anthropic response")
            raise DeepSeekError("protocol", f"Anthropic parse: {type(error).__name__}") from error
        if not result.usage.valid:
            self.ledger.mark_unknown(reservation.reservation_id, "Anthropic usage missing/invalid")
            raise DeepSeekError("usage", "Anthropic response lacks valid input/output tokens")
        self.ledger.settle_model(
            reservation.reservation_id,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            returned_model=result.returned_model,
            finish_reason=result.finish_reason,
        )
        return result

    def _parse(self, raw: object, started: float) -> DeepSeekChatResult:
        if not isinstance(raw, dict):
            raise ValueError("response is not an object")
        blocks = raw.get("content", [])
        if not isinstance(blocks, list):
            raise ValueError("content is not a list")
        texts: list[str] = []
        thinking: list[str] = []
        calls: list[DeepSeekToolCall] = []
        native_blocks: list[dict[str, object]] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            native_blocks.append(dict(block))
            kind = block.get("type")
            if kind == "text":
                texts.append(str(block.get("text", "")))
            elif kind == "thinking":
                thinking.append(str(block.get("thinking", "")))
            elif kind == "tool_use":
                identifier = str(block.get("id", ""))
                name = str(block.get("name", ""))
                if not identifier or not name:
                    raise ValueError("tool_use block lacks id or name")
                if any(call.id == identifier for call in calls):
                    raise ValueError(f"duplicate tool_use id in one response: {identifier}")
                arguments = json.dumps(block.get("input", {}), ensure_ascii=False, separators=(",", ":"))
                calls.append(DeepSeekToolCall(id=identifier, name=name, arguments=arguments))
        usage_raw = raw.get("usage")
        usage = DeepSeekUsage(reported=False, valid=False)
        if isinstance(usage_raw, dict):
            def nonnegative_integer(value: object) -> int | None:
                if isinstance(value, bool) or not isinstance(value, int):
                    return None
                return value if value >= 0 else None

            prompt = nonnegative_integer(usage_raw.get("input_tokens"))
            completion = nonnegative_integer(usage_raw.get("output_tokens"))
            cache_creation = nonnegative_integer(usage_raw.get("cache_creation_input_tokens", 0))
            cache_read = nonnegative_integer(usage_raw.get("cache_read_input_tokens", 0))
            if prompt is None or completion is None or cache_creation is None or cache_read is None:
                usage = DeepSeekUsage(reported=True, valid=False)
            else:
                # Anthropic's input_tokens excludes cached prompt tokens; count
                # all prompt tokens so cost is not silently understated.
                total_prompt = prompt + cache_creation + cache_read
                usage = DeepSeekUsage(
                    prompt_tokens=total_prompt,
                    completion_tokens=completion,
                    total_tokens=total_prompt + completion,
                    prompt_cache_hit_tokens=cache_read,
                    prompt_cache_miss_tokens=prompt,
                    cache_creation_tokens=cache_creation,
                    cache_read_tokens=cache_read,
                    reported=True,
                    valid=True,
                )
        stop_reason = str(raw.get("stop_reason", ""))
        return DeepSeekChatResult(
            content="".join(texts),
            reasoning_content="".join(thinking),
            tool_calls=calls,
            finish_reason=stop_reason,
            requested_model=self.model_name,
            returned_model=str(raw.get("model", "")),
            usage=usage,
            request_id=str(raw.get("id", "")) or None,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            truncated=stop_reason in {"max_tokens", "model_context_window_exceeded"},
            native_blocks=native_blocks,
            raw=cast(dict[str, object], raw),
        )
