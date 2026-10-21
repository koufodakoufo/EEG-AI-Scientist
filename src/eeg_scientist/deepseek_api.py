"""Typed DeepSeek Flash client for Chat Completions, Search, and Fetch.

This is the adapter boundary: vendor JSON is parsed here into explicit models,
and upper layers never guess field names.  There is no fallback provider.

The client reserves budget before every paid attempt, settles against reported
usage, and preserves a reservation as UNKNOWN when a timeout makes billing
ambiguous.  Request headers are never logged or serialized.
"""

from __future__ import annotations

import json
import time
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .ledger import BudgetLedger, LedgerError
from .schema import ModelRequest, ProviderResponse
from .storage import redact


class DeepSeekError(RuntimeError):
    """API or protocol failure with a machine-readable kind."""

    def __init__(self, kind: str, message: str, *, status_code: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.retryable = retryable


class DeepSeekToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments: str


class DeepSeekUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    reported: bool = True
    valid: bool = True


class DeepSeekChatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = ""
    reasoning_content: str = ""
    tool_calls: list[DeepSeekToolCall] = Field(default_factory=list)
    finish_reason: str = ""
    requested_model: str
    returned_model: str = ""
    usage: DeepSeekUsage = Field(default_factory=DeepSeekUsage)
    request_id: str | None = None
    latency_ms: float = 0.0
    truncated: bool = False
    raw: dict[str, object] = Field(default_factory=dict)


class SearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    title: str = ""
    url: str
    snippet: str = ""
    summary: str = ""
    site_name: str | None = None
    date: str | None = None
    authority: int = -1
    rerank_score: float = 0.0
    content: str = ""


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    results: list[SearchItem]
    latency_ms: float = 0.0
    raw: dict[str, object] = Field(default_factory=dict)


class FetchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str = ""
    content: str = ""
    latency_ms: float = 0.0
    raw: dict[str, object] = Field(default_factory=dict)


class ModelChatClient(Protocol):
    model_name: str
    provider_name: str
    backend_status: str

    def chat(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]] | None = None,
        max_tokens: int = 16384,
        json_mode: bool = False,
        stage: str = "",
    ) -> DeepSeekChatResult: ...


class SearchFetchClient(Protocol):
    def search(self, query: str, *, count: int = 8, need_content: bool = False) -> SearchResponse: ...

    def fetch(self, url: str) -> FetchResponse: ...


class ChatClient(ModelChatClient, SearchFetchClient, Protocol):
    """Backward-compatible combined protocol for the original client."""


def _message_wire(message: dict[str, object]) -> dict[str, object]:
    """Normalize one internal message to the Chat Completions wire shape."""

    role = message.get("role")
    if role not in {"system", "user", "assistant", "tool"}:
        raise DeepSeekError("bad_message", f"unsupported message role {role!r}")
    wire: dict[str, object] = {"role": role}
    content = message.get("content", "")
    wire["content"] = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    if role == "assistant":
        reasoning = message.get("reasoning_content", "")
        if isinstance(reasoning, str) and reasoning:
            wire["reasoning_content"] = reasoning
        tool_calls = message.get("tool_calls", [])
        if isinstance(tool_calls, list) and tool_calls:
            serialized: list[dict[str, object]] = []
            for item in tool_calls:
                if not isinstance(item, dict):
                    raise DeepSeekError("bad_message", "assistant tool_calls must be objects")
                function = item.get("function")
                if not isinstance(function, dict):
                    raise DeepSeekError("bad_message", "tool call lacks function object")
                serialized.append(
                    {
                        "id": str(item.get("id", "")),
                        "type": "function",
                        "function": {
                            "name": str(function.get("name", "")),
                            "arguments": str(function.get("arguments", "{}")),
                        },
                    }
                )
            wire["tool_calls"] = serialized
    if role == "tool":
        tool_call_id = message.get("tool_call_id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            raise DeepSeekError("bad_message", "tool message lacks tool_call_id")
        wire["tool_call_id"] = tool_call_id
    return wire


def _usage_from(raw_usage: object) -> DeepSeekUsage:
    """Parse vendor usage without turning missing/invalid values into zero cost."""

    if not isinstance(raw_usage, dict):
        return DeepSeekUsage(reported=False, valid=False)
    required = ("prompt_tokens", "completion_tokens")
    if any(name not in raw_usage for name in required):
        return DeepSeekUsage(reported=True, valid=False)

    def nonnegative_integer(value: object) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if isinstance(value, float) and not value.is_integer():
            return None
        number = int(value)
        return number if number >= 0 else None

    prompt_tokens = nonnegative_integer(raw_usage.get("prompt_tokens"))
    completion_tokens = nonnegative_integer(raw_usage.get("completion_tokens"))
    if prompt_tokens is None or completion_tokens is None:
        return DeepSeekUsage(reported=True, valid=False)

    optional: dict[str, int] = {}
    for name in ("total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
        if name not in raw_usage:
            optional[name] = 0
            continue
        value = nonnegative_integer(raw_usage.get(name))
        if value is None:
            return DeepSeekUsage(reported=True, valid=False)
        optional[name] = value

    return DeepSeekUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=optional["total_tokens"] or prompt_tokens + completion_tokens,
        prompt_cache_hit_tokens=optional["prompt_cache_hit_tokens"],
        prompt_cache_miss_tokens=optional["prompt_cache_miss_tokens"],
        reported=True,
        valid=True,
    )


class DeepSeekClient:
    """Official DeepSeek client used by this project's Scientist."""

    provider_name = "deepseek_official"
    backend = "real_llm"

    def __init__(
        self,
        *,
        api_key: str,
        ledger: BudgetLedger,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-flash",
        timeout_seconds: int = 600,
        connect_timeout_seconds: int = 20,
        search_timeout_seconds: int = 60,
        fetch_timeout_seconds: int = 60,
        max_retries: int = 2,
        retry_wait_seconds: tuple[float, ...] = (2.0, 8.0),
        transport: httpx.BaseTransport | None = None,
        attribution: str = "",
        provider_name: str = "deepseek_official",
        backend_status: str = "verified",
    ) -> None:
        if not api_key:
            raise DeepSeekError("credential", "empty API key")
        self._api_key = api_key
        self.ledger = ledger
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.provider_name = provider_name
        self.backend_status = backend_status
        self.attribution = attribution
        self.timeout_seconds = timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self.search_timeout_seconds = search_timeout_seconds
        self.fetch_timeout_seconds = fetch_timeout_seconds
        self.max_retries = max_retries
        self.retry_wait_seconds = retry_wait_seconds
        self._transport = transport
        self._call_count = 0

    def __repr__(self) -> str:
        return f"DeepSeekClient(base_url={self.base_url!r}, model={self.model_name!r})"

    # --------------------------------------------------------------- helpers
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _redact(self, text: str) -> str:
        return redact(text, [self._api_key])

    def _client(self, timeout: httpx.Timeout) -> httpx.Client:
        return httpx.Client(timeout=timeout, transport=self._transport, follow_redirects=False)

    @staticmethod
    def _timeout(total: int, connect: int) -> httpx.Timeout:
        return httpx.Timeout(total, connect=min(connect, total), write=min(total, 60), pool=min(connect, 20))

    def _error_from_response(self, response: httpx.Response, *, operation: str) -> DeepSeekError:
        status = response.status_code
        try:
            payload = response.json()
            error_object = payload.get("error", {}) if isinstance(payload, dict) else {}
            message = str(error_object.get("message", "")) if isinstance(error_object, dict) else ""
        except Exception:  # noqa: BLE001 - error body may not be JSON
            message = ""
        if not message:
            message = f"HTTP {status}"
        kind = "auth" if status in {401, 403} else "payment" if status == 402 else "http"
        retryable = status in {408, 429} or 500 <= status < 600
        return DeepSeekError(
            kind,
            self._redact(f"{operation}: HTTP {status}: {message[:500]}"),
            status_code=status,
            retryable=retryable,
        )

    def _sleep_before_retry(self, attempt: int, response: httpx.Response | None = None) -> None:
        wait = 0.0
        if response is not None:
            header = response.headers.get("Retry-After", "")
            if header.strip().isdigit():
                requested = float(header.strip())
                if requested > 60:
                    raise DeepSeekError("retry_after", f"server requested a wait longer than 60s: {requested}")
                wait = requested
        if wait <= 0:
            index = min(attempt, len(self.retry_wait_seconds) - 1)
            wait = self.retry_wait_seconds[index]
        if wait > 60:
            raise DeepSeekError("retry_after", f"server requested a wait longer than 60s: {wait}")
        time.sleep(wait)

    def list_models(self) -> dict[str, object]:
        """Free metadata call used by preflight/capability checks."""

        try:
            with self._client(self._timeout(60, 20)) as client:
                response = client.get(f"{self.base_url}/models", headers=self._headers())
        except httpx.HTTPError as error:
            raise DeepSeekError("network", self._redact(f"list_models: {type(error).__name__}")) from error
        if response.status_code != 200:
            raise self._error_from_response(response, operation="list_models")
        payload = response.json()
        return payload if isinstance(payload, dict) else {"raw": payload}

    # ------------------------------------------------------------------- chat
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
        wire_messages = [_message_wire(message) for message in messages]
        payload: dict[str, object] = {
            "model": self.model_name,
            "messages": wire_messages,
            "max_tokens": max_tokens,
            "stream": False,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
        }
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        reservation_payload = json.dumps(
            {"messages": wire_messages, "tools": tools, "max_tokens": max_tokens, "json_mode": json_mode},
            ensure_ascii=False,
            default=str,
        )
        started = time.perf_counter()
        last_error: DeepSeekError | None = None
        for attempt in range(self.max_retries + 1):
            reservation = self.ledger.reserve_model(
                reservation_payload, max_tokens, attribution=self.attribution
            )
            self._call_count += 1
            try:
                with self._client(self._timeout(self.timeout_seconds, self.connect_timeout_seconds)) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
            except httpx.ConnectError as error:
                self.ledger.release(reservation.reservation_id, f"connect error: {type(error).__name__}")
                raise DeepSeekError("network", self._redact(f"chat connect: {type(error).__name__}")) from error
            except httpx.TimeoutException as error:
                self.ledger.mark_unknown(reservation.reservation_id, f"timeout: {type(error).__name__}")
                raise DeepSeekError(
                    "timeout",
                    self._redact(f"chat timeout after {self.timeout_seconds}s"),
                    retryable=True,
                ) from error
            except httpx.HTTPError as error:
                self.ledger.mark_unknown(reservation.reservation_id, f"transport: {type(error).__name__}")
                last_error = DeepSeekError("network", self._redact(f"chat transport: {type(error).__name__}"))
                if attempt < self.max_retries:
                    self._sleep_before_retry(attempt)
                    continue
                raise last_error from error

            if response.status_code != 200:
                error = self._error_from_response(response, operation="chat")
                if error.retryable and error.status_code == 408:
                    self.ledger.mark_unknown(reservation.reservation_id, f"HTTP {error.status_code}")
                else:
                    self.ledger.release(reservation.reservation_id, f"HTTP {error.status_code}")
                last_error = error
                if error.retryable and attempt < self.max_retries:
                    self._sleep_before_retry(attempt, response)
                    continue
                raise error

            try:
                raw = response.json()
                result = self._parse_chat(raw, requested_model=self.model_name, latency_ms=(time.perf_counter() - started) * 1000.0)
            except (ValueError, KeyError, TypeError, ValidationError) as error:
                self.ledger.mark_unknown(reservation.reservation_id, "unparseable 200 response")
                raise DeepSeekError("protocol", self._redact(f"chat response parse: {type(error).__name__}")) from error

            if not result.usage.valid:
                self.ledger.mark_unknown(reservation.reservation_id, "usage missing or invalid")
                raise DeepSeekError(
                    "usage",
                    "HTTP 200 response has missing or invalid token usage; "
                    "the reservation is retained as UNKNOWN spend, not settled as zero",
                )
            self.ledger.settle_model(
                reservation.reservation_id,
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                returned_model=result.returned_model,
                finish_reason=result.finish_reason,
            )
            return result
        raise last_error or DeepSeekError("network", "chat failed without a specific error")

    @staticmethod
    def _parse_chat(raw: object, *, requested_model: str, latency_ms: float) -> DeepSeekChatResult:
        if not isinstance(raw, dict):
            raise ValueError("response is not an object")
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("response has no choices")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError("choice is not an object")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("choice has no message")
        content_value = message.get("content", "")
        content = content_value if isinstance(content_value, str) else json.dumps(content_value, ensure_ascii=False)
        reasoning_value = message.get("reasoning_content", "")
        reasoning = reasoning_value if isinstance(reasoning_value, str) else ""
        raw_tool_calls = message.get("tool_calls", [])
        tool_calls: list[DeepSeekToolCall] = []
        if isinstance(raw_tool_calls, list):
            for item in raw_tool_calls:
                if not isinstance(item, dict):
                    raise ValueError("tool call is not an object")
                identifier = str(item.get("id", ""))
                function = item.get("function", {})
                if not isinstance(function, dict):
                    raise ValueError("tool call function is not an object")
                name = str(function.get("name", ""))
                arguments_value = function.get("arguments", "{}")
                arguments = (
                    arguments_value
                    if isinstance(arguments_value, str)
                    else json.dumps(arguments_value, ensure_ascii=False)
                )
                if not identifier or not name:
                    raise ValueError("tool call lacks id or name")
                tool_calls.append(DeepSeekToolCall(id=identifier, name=name, arguments=arguments))
        finish_reason = str(choice.get("finish_reason", ""))
        usage = _usage_from(raw.get("usage"))
        returned_model = str(raw.get("model", ""))
        request_id_value = raw.get("id")
        return DeepSeekChatResult(
            content=content,
            reasoning_content=reasoning,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            requested_model=requested_model,
            returned_model=returned_model,
            usage=usage,
            request_id=request_id_value if isinstance(request_id_value, str) else None,
            latency_ms=latency_ms,
            truncated=finish_reason == "length",
            raw=raw,
        )

    # ----------------------------------------------------------------- search
    def search(self, query: str, *, count: int = 8, need_content: bool = False) -> SearchResponse:
        query = query.strip()
        if not query or len(query) > 128:
            raise DeepSeekError("bad_request", "query must contain 1-128 characters")
        if not 1 <= count <= 50:
            raise DeepSeekError("bad_request", "count must be between 1 and 50")
        payload = {"query": query, "count": count, "need_content": need_content}
        started = time.perf_counter()
        raw = self._tool_post("/v1/tools/search", payload, kind="search", timeout=self.search_timeout_seconds)
        results_raw = raw.get("results", [])
        if not isinstance(results_raw, list):
            raise DeepSeekError("protocol", "search response has no results list")
        results: list[SearchItem] = []
        for index, item in enumerate(results_raw):
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            results.append(
                SearchItem(
                    result_id=f"sr_{index + 1:02d}",
                    title=str(item.get("title", "")),
                    url=url,
                    snippet=str(item.get("snippet", "")),
                    summary=str(item.get("summary", "")),
                    site_name=item.get("site_name") if isinstance(item.get("site_name"), str) else None,
                    date=item.get("date") if isinstance(item.get("date"), str) else None,
                    authority=int(item.get("authority", -1)) if isinstance(item.get("authority", -1), int) else -1,
                    rerank_score=float(item.get("rerank_score", 0.0))
                    if isinstance(item.get("rerank_score", 0.0), (int, float))
                    else 0.0,
                    content=str(item.get("content", "")),
                )
            )
        return SearchResponse(
            query=query,
            results=results,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            raw=raw,
        )

    # ------------------------------------------------------------------ fetch
    def fetch(self, url: str) -> FetchResponse:
        if not url.startswith(("http://", "https://")) or len(url) > 8192:
            raise DeepSeekError("bad_request", "fetch URL must be a public HTTP(S) URL under 8192 chars")
        started = time.perf_counter()
        raw = self._tool_post("/v1/tools/fetch", {"url": url}, kind="fetch", timeout=self.fetch_timeout_seconds)
        content = raw.get("content")
        if not isinstance(content, str):
            raise DeepSeekError("protocol", "fetch response has no string content")
        return FetchResponse(
            url=url,
            title=str(raw.get("title", "")),
            content=content,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            raw=raw,
        )

    def _tool_post(
        self,
        path: str,
        payload: dict[str, object],
        *,
        kind: Literal["search", "fetch"],
        timeout: int,
    ) -> dict[str, object]:
        last_error: DeepSeekError | None = None
        for attempt in range(self.max_retries + 1):
            reservation = self.ledger.reserve_tool(kind, attribution=self.attribution)
            try:
                with self._client(self._timeout(timeout, 20)) as client:
                    response = client.post(
                        f"{self.base_url}{path}",
                        headers=self._headers(),
                        json=payload,
                    )
            except httpx.ConnectError as error:
                self.ledger.settle_tool(reservation.reservation_id, succeeded=False, note="connect error")
                raise DeepSeekError("network", self._redact(f"{kind} connect: {type(error).__name__}")) from error
            except httpx.TimeoutException as error:
                self.ledger.mark_unknown(reservation.reservation_id, f"{kind} timeout")
                raise DeepSeekError("timeout", self._redact(f"{kind} timeout after {timeout}s"), retryable=True) from error
            except httpx.HTTPError as error:
                self.ledger.mark_unknown(reservation.reservation_id, f"{kind} transport")
                last_error = DeepSeekError("network", self._redact(f"{kind} transport: {type(error).__name__}"))
                if attempt < self.max_retries:
                    self._sleep_before_retry(attempt)
                    continue
                raise last_error from error

            if response.status_code == 200:
                try:
                    raw = response.json()
                except ValueError as error:
                    self.ledger.mark_unknown(reservation.reservation_id, f"{kind} unparseable 200")
                    raise DeepSeekError("protocol", f"{kind} response is not JSON") from error
                self.ledger.settle_tool(reservation.reservation_id, succeeded=True)
                if not isinstance(raw, dict):
                    raise DeepSeekError("protocol", f"{kind} response is not an object")
                return raw

            error = self._error_from_response(response, operation=kind)
            self.ledger.settle_tool(reservation.reservation_id, succeeded=False, note=f"HTTP {error.status_code}")
            last_error = error
            if error.retryable and attempt < self.max_retries:
                self._sleep_before_retry(attempt, response)
                continue
            raise error
        raise last_error or DeepSeekError("network", f"{kind} failed without a specific error")


class DeepSeekDecisionProvider:
    """Adapter for the existing ``decide(ModelRequest) -> ProviderResponse`` loop.

    The old synthetic-case runner expects one JSON decision per call.  This
    adapter keeps that boundary while sending the request to DeepSeek Flash.
    It is used only for the Task C diagnostics, not for the literature loop.
    """

    backend = "real_llm"
    provider_name = "deepseek_flash"
    model_name = "deepseek-flash"

    def __init__(
        self,
        client: DeepSeekClient,
        *,
        max_output_tokens: int = 8000,
        model_name: str = "deepseek-flash",
    ) -> None:
        self.client = client
        self.max_output_tokens = max_output_tokens
        self.model_name = model_name

    def decide(self, request: ModelRequest) -> ProviderResponse:
        messages: list[dict[str, object]] = []
        for message in request.messages:
            messages.append({"role": message.get("role", "user"), "content": message.get("content", "")})
        started = time.perf_counter()
        try:
            result = self.client.chat(
                messages,
                tools=None,
                max_tokens=self.max_output_tokens,
                json_mode=True,
                stage=request.stage,
            )
        except LedgerError as error:
            return ProviderResponse(
                status="unavailable",
                model_id=self.model_name,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error=f"budget ledger: {error}",
            )
        except DeepSeekError as error:
            status = "unknown_completion" if error.kind == "timeout" else "http_error" if error.kind in {"http", "auth", "payment"} else "unavailable"
            return ProviderResponse(
                status=status,
                model_id=self.model_name,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error=f"{error.kind}: {error}",
            )
        return ProviderResponse(
            status="ok",
            visible_text=result.content,
            model_id=result.returned_model or result.requested_model,
            usage={
                "prompt_tokens": result.usage.prompt_tokens,
                "completion_tokens": result.usage.completion_tokens,
                "total_tokens": result.usage.total_tokens,
            },
            latency_ms=result.latency_ms,
            raw_response={
                "request_id": result.request_id,
                "finish_reason": result.finish_reason,
                "truncated": result.truncated,
                "reasoning_chars": len(result.reasoning_content),
            },
        )
