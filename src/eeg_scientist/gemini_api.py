"""Google Gemini generateContent adapter for the existing tool loop."""

from __future__ import annotations

import json
import time
from typing import cast

import httpx

from .deepseek_api import DeepSeekChatResult, DeepSeekError, DeepSeekToolCall, DeepSeekUsage
from .ledger import BudgetLedger


class GeminiClient:
    """Real Gemini API client; tool calls are mapped to the internal neutral shape."""

    provider_name = "google"
    backend = "real_llm"
    backend_status = "unverified"

    def __init__(
        self,
        *,
        api_key: str,
        ledger: BudgetLedger,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com",
        timeout_seconds: int = 600,
        connect_timeout_seconds: int = 20,
        max_tokens: int = 16384,
        attribution: str = "",
        thinking: bool = True,
        thinking_level: str | None = None,
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
        self.thinking_level = thinking_level
        self.transport = transport
        self.call_count = 0

    def __repr__(self) -> str:
        return f"GeminiClient(model={self.model_name!r}, status={self.backend_status!r})"

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.api_key, "content-type": "application/json"}

    def _client(self) -> httpx.Client:
        timeout = httpx.Timeout(self.timeout_seconds, connect=self.connect_timeout_seconds)
        return httpx.Client(timeout=timeout, transport=self.transport)

    @staticmethod
    def _tool_names(messages: list[dict[str, object]]) -> dict[str, str]:
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
                identifier = call.get("id")
                function = call.get("function")
                if isinstance(identifier, str) and isinstance(function, dict):
                    name = function.get("name")
                    if isinstance(name, str):
                        names[identifier] = name
        return names

    @staticmethod
    def _existing_tool_ids(messages: list[dict[str, object]]) -> set[str]:
        identifiers: set[str] = set()
        for message in messages:
            calls = message.get("tool_calls")
            if not isinstance(calls, list):
                continue
            for call in calls:
                if isinstance(call, dict) and isinstance(call.get("id"), str):
                    identifiers.add(str(call["id"]))
        return identifiers

    def _wire(self, messages: list[dict[str, object]], tools: list[dict[str, object]] | None) -> tuple[str, list[dict[str, object]]]:
        system_parts: list[str] = []
        contents: list[dict[str, object]] = []
        names = self._tool_names(messages)
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            if role == "system":
                system_parts.append(text)
                continue
            if role == "user":
                contents.append({"role": "user", "parts": [{"text": text}]})
                continue
            if role == "tool":
                identifier = message.get("tool_call_id")
                if not isinstance(identifier, str) or not identifier:
                    raise DeepSeekError("bad_message", "tool message lacks tool_call_id")
                name = names.get(identifier, "tool")
                try:
                    payload = json.loads(text) if text.strip() else {}
                except json.JSONDecodeError:
                    payload = {"result": text}
                self._append_function_response(contents, name, payload)
                continue
            if role == "assistant":
                parts = self._assistant_parts(message, text)
                if parts:
                    contents.append({"role": "model", "parts": parts})
                continue
            raise DeepSeekError("bad_message", f"unsupported message role {role!r}")
        if tools:
            declarations: list[dict[str, object]] = []
            for tool in tools:
                function = tool.get("function") if isinstance(tool, dict) else None
                if not isinstance(function, dict):
                    raise DeepSeekError("bad_request", "tool lacks function object")
                declarations.append(
                    {
                        "name": str(function.get("name", "")),
                        "description": str(function.get("description", "")),
                        "parameters": function.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
            self._converted_tools = [{"functionDeclarations": declarations}]
        else:
            self._converted_tools = []
        return "\n\n".join(system_parts), contents

    def _assistant_parts(self, message: dict[str, object], text: str) -> list[dict[str, object]]:
        """Replay the vendor-native parts (including thoughtSignature) verbatim."""

        native = message.get("native_blocks")
        parts: list[dict[str, object]] = []
        if isinstance(native, list) and native:
            for part in native:
                if isinstance(part, dict):
                    parts.append(dict(part))
            return parts
        if text:
            parts.append({"text": text})
        calls = message.get("tool_calls")
        if isinstance(calls, list):
            for call in calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function")
                if not isinstance(function, dict):
                    raise DeepSeekError("bad_message", "assistant tool_call lacks function")
                arguments = str(function.get("arguments", "{}"))
                try:
                    args = json.loads(arguments) if arguments.strip() else {}
                except json.JSONDecodeError as error:
                    raise DeepSeekError("bad_message", f"tool arguments are not JSON: {error}") from error
                parts.append(
                    {
                        "functionCall": {
                            "name": str(function.get("name", "")),
                            "args": args if isinstance(args, dict) else {},
                        }
                    }
                )
        return parts

    @staticmethod
    def _append_function_response(
        contents: list[dict[str, object]],
        name: str,
        payload: dict[str, object],
    ) -> None:
        response_part: dict[str, object] = {
            "functionResponse": {
                "name": name,
                "response": payload if isinstance(payload, dict) else {"result": payload},
            }
        }
        if contents:
            last = contents[-1]
            last_parts = last.get("parts")
            if (
                last.get("role") == "user"
                and isinstance(last_parts, list)
                and last_parts
                and all(isinstance(item, dict) and "functionResponse" in item for item in last_parts)
            ):
                last_parts.append(response_part)
                return
        contents.append({"role": "user", "parts": [response_part]})

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
        system, contents = self._wire(messages, tools)
        generation_config: dict[str, object] = {"maxOutputTokens": max_tokens}
        payload: dict[str, object] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        converted_tools = getattr(self, "_converted_tools", [])
        if converted_tools:
            payload["tools"] = converted_tools
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        if self.thinking and max_tokens > 1024:
            if self.thinking_level:
                # Gemini 3-style control; verify against the chosen model before a real run.
                generation_config["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
            else:
                generation_config["thinkingConfig"] = {"thinkingBudget": min(4096, max_tokens - 1)}
        reservation = self.ledger.reserve_model(
            json.dumps(payload, ensure_ascii=False, default=str),
            max_tokens,
            attribution=self.attribution,
        )
        self.call_count += 1
        started = time.perf_counter()
        try:
            with self._client() as client:
                response = client.post(
                    f"{self.base_url}/v1beta/models/{self.model_name}:generateContent",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.TimeoutException as error:
            self.ledger.mark_unknown(reservation.reservation_id, f"timeout: {type(error).__name__}")
            raise DeepSeekError("timeout", "Gemini request timed out", retryable=True) from error
        except httpx.HTTPError as error:
            self.ledger.release(reservation.reservation_id, f"transport: {type(error).__name__}")
            raise DeepSeekError("network", f"Gemini transport: {type(error).__name__}") from error
        if response.status_code != 200:
            self.ledger.release(reservation.reservation_id, f"HTTP {response.status_code}")
            raise DeepSeekError(
                "http_error",
                f"Gemini HTTP {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
                retryable=response.status_code in {408, 429, 500, 502, 503, 504},
            )
        try:
            raw = response.json()
            existing_ids = self._existing_tool_ids(messages)
            result = self._parse(raw, started, call_index_start=len(existing_ids), reserved_ids=existing_ids)
        except (ValueError, KeyError, TypeError) as error:
            self.ledger.mark_unknown(reservation.reservation_id, "unparseable Gemini response")
            raise DeepSeekError("protocol", f"Gemini parse: {type(error).__name__}") from error
        if not result.usage.valid:
            self.ledger.mark_unknown(reservation.reservation_id, "Gemini usage missing/invalid")
            raise DeepSeekError("usage", "Gemini response lacks valid usage (prompt/candidate tokens)")
        self.ledger.settle_model(
            reservation.reservation_id,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            returned_model=result.returned_model,
            finish_reason=result.finish_reason,
        )
        return result

    def _parse(
        self,
        raw: object,
        started: float,
        *,
        call_index_start: int = 0,
        reserved_ids: set[str] | None = None,
    ) -> DeepSeekChatResult:
        if not isinstance(raw, dict):
            raise ValueError("response is not an object")
        candidates = raw.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("no candidates")
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise ValueError("candidate is not an object")
        content = candidate.get("content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else []
        texts: list[str] = []
        thinking: list[str] = []
        calls: list[DeepSeekToolCall] = []
        native_blocks: list[dict[str, object]] = []
        used_ids: set[str] = set(reserved_ids or set())
        next_index = call_index_start
        if isinstance(parts, list):
            for part in parts:
                if not isinstance(part, dict):
                    continue
                native_blocks.append(dict(part))
                if part.get("thought") is True:
                    thinking.append(str(part.get("text", "")))
                    continue
                if "text" in part:
                    texts.append(str(part.get("text", "")))
                call = part.get("functionCall")
                if isinstance(call, dict):
                    name = str(call.get("name", ""))
                    if not name:
                        raise ValueError("functionCall lacks a name")
                    args = call.get("args", {})
                    provider_id = call.get("id")
                    identifier = provider_id if isinstance(provider_id, str) and provider_id else ""
                    if not identifier or identifier in used_ids:
                        while True:
                            next_index += 1
                            candidate_id = f"gcall_{next_index:03d}"
                            if candidate_id not in used_ids:
                                identifier = candidate_id
                                break
                    used_ids.add(identifier)
                    calls.append(
                        DeepSeekToolCall(
                            id=identifier,
                            name=name,
                            arguments=json.dumps(args if isinstance(args, dict) else {}, ensure_ascii=False, separators=(",", ":")),
                        )
                    )
        usage_raw = raw.get("usageMetadata")
        usage = DeepSeekUsage(reported=False, valid=False)
        if isinstance(usage_raw, dict):
            def nonnegative_integer(value: object) -> int | None:
                if isinstance(value, bool) or not isinstance(value, int):
                    return None
                return value if value >= 0 else None

            prompt = nonnegative_integer(usage_raw.get("promptTokenCount"))
            candidates_tokens = nonnegative_integer(usage_raw.get("candidatesTokenCount"))
            thoughts = nonnegative_integer(usage_raw.get("thoughtsTokenCount", 0))
            cached = nonnegative_integer(usage_raw.get("cachedContentTokenCount", 0))
            reported_total = nonnegative_integer(usage_raw.get("totalTokenCount", 0))
            if (
                prompt is None
                or candidates_tokens is None
                or thoughts is None
                or cached is None
                or reported_total is None
            ):
                usage = DeepSeekUsage(reported=True, valid=False)
            else:
                completion = candidates_tokens + thoughts
                total = reported_total or (prompt + completion)
                usage = DeepSeekUsage(
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    reasoning_tokens=thoughts,
                    cache_read_tokens=cached,
                    reported=True,
                    valid=total >= prompt + completion,
                )
        finish_reason = str(candidate.get("finishReason", ""))
        return DeepSeekChatResult(
            content="".join(texts),
            reasoning_content="".join(thinking),
            tool_calls=calls,
            finish_reason=finish_reason,
            requested_model=self.model_name,
            returned_model=str(raw.get("modelVersion", "")),
            usage=usage,
            request_id=str(raw.get("responseId", "")) or None,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            truncated=finish_reason == "MAX_TOKENS",
            native_blocks=native_blocks,
            raw=cast(dict[str, object], raw),
        )
