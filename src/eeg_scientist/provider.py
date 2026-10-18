"""Model providers: local Ollama (primary), optional OpenAI-compatible cloud."""

from __future__ import annotations

import os
import time
from typing import Protocol

import httpx

from .schema import ModelRequest, ProviderResponse
from .storage import canonical_json, redact


class ScientistProvider(Protocol):
    backend: str
    provider_name: str
    model_name: str

    def decide(self, request: ModelRequest) -> ProviderResponse: ...


class OllamaProvider:
    backend = "real_llm"
    provider_name = "ollama_local"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3.5:9b",
        timeout_seconds: int = 120,
        max_retries: int = 2,
        max_output_tokens: int = 1500,
        temperature: float = 0.0,
        seed: int = 42,
        num_ctx: int = 8192,
        use_schema: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.seed = seed
        self.num_ctx = num_ctx
        self.use_schema = use_schema

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=httpx.Timeout(self.timeout_seconds))

    def health(self) -> dict[str, object]:
        try:
            with self._client() as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                return {"ok": True, "models": response.json().get("models", [])}
        except Exception as error:  # noqa: BLE001 - boundary report
            return {"ok": False, "error": str(error)}

    def describe(self) -> dict[str, object]:
        try:
            with self._client() as client:
                response = client.post(f"{self.base_url}/api/show", json={"model": self.model_name})
                response.raise_for_status()
                return response.json()
        except Exception as error:  # noqa: BLE001 - boundary report
            return {"error": str(error)}

    def _payload(self, request: ModelRequest) -> dict[str, object]:
        schema = request.model_settings.get("format_schema")
        if self.use_schema and isinstance(schema, dict):
            response_format: object = schema
        else:
            response_format = "json"
        return {
            "model": self.model_name,
            "messages": request.messages,
            "stream": False,
            "think": False,
            "format": response_format,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_output_tokens,
                "seed": self.seed,
                "num_ctx": self.num_ctx,
            },
        }

    def decide(self, request: ModelRequest) -> ProviderResponse:
        payload = self._payload(request)
        started = time.perf_counter()
        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                with self._client() as client:
                    response = client.post(f"{self.base_url}/api/chat", json=payload)
                latency = (time.perf_counter() - started) * 1000.0
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                    if response.status_code == 429 or 500 <= response.status_code < 600:
                        if attempt < self.max_retries:
                            time.sleep(2.0 ** attempt)
                            continue
                    return ProviderResponse(
                        status="http_error",
                        model_id=self.model_name,
                        latency_ms=latency,
                        error=redact(last_error, [os.environ.get("SCIENTIST_API_KEY", "")]),
                    )
                raw = response.json()
                message = raw.get("message", {}) if isinstance(raw, dict) else {}
                visible = str(message.get("content", "")) if isinstance(message, dict) else ""
                usage = {
                    "prompt_tokens": int(raw.get("prompt_eval_count", 0)),
                    "completion_tokens": int(raw.get("eval_count", 0)),
                    "total_tokens": int(raw.get("prompt_eval_count", 0)) + int(raw.get("eval_count", 0)),
                }
                return ProviderResponse(
                    status="ok",
                    visible_text=visible,
                    model_id=str(raw.get("model", self.model_name)),
                    usage=usage,
                    latency_ms=latency,
                    raw_response=raw,
                )
            except httpx.TimeoutException as error:
                latency = (time.perf_counter() - started) * 1000.0
                return ProviderResponse(
                    status="unknown_completion",
                    model_id=self.model_name,
                    latency_ms=latency,
                    error=redact(str(error), [os.environ.get("SCIENTIST_API_KEY", "")]),
                )
            except httpx.HTTPError as error:
                last_error = str(error)
                if attempt < self.max_retries:
                    time.sleep(2.0 ** attempt)
                    continue
                latency = (time.perf_counter() - started) * 1000.0
                return ProviderResponse(
                    status="unavailable",
                    model_id=self.model_name,
                    latency_ms=latency,
                    error=redact(last_error, [os.environ.get("SCIENTIST_API_KEY", "")]),
                )
        return ProviderResponse(status="unavailable", model_id=self.model_name, error=redact(last_error, []))


class OpenAICompatibleProvider:
    backend = "real_llm"
    provider_name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: int = 120,
        max_retries: int = 2,
        max_output_tokens: int = 1500,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.seed = seed

    def decide(self, request: ModelRequest) -> ProviderResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model_name,
            "messages": request.messages,
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
            "seed": self.seed,
        }
        started = time.perf_counter()
        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                    response = client.post(url, headers=headers, json=payload)
                latency = (time.perf_counter() - started) * 1000.0
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                    if response.status_code == 429 or 500 <= response.status_code < 600:
                        if attempt < self.max_retries:
                            time.sleep(2.0 ** attempt)
                            continue
                    return ProviderResponse(
                        status="http_error",
                        model_id=self.model_name,
                        latency_ms=latency,
                        error=redact(last_error, [self.api_key]),
                    )
                raw = response.json()
                choice = raw.get("choices", [{}])[0] if raw.get("choices") else {}
                message = choice.get("message", {}) if isinstance(choice, dict) else {}
                visible = str(message.get("content", "")) if isinstance(message, dict) else ""
                usage_raw = raw.get("usage", {}) if isinstance(raw, dict) else {}
                usage = {
                    "prompt_tokens": int(usage_raw.get("prompt_tokens", 0)),
                    "completion_tokens": int(usage_raw.get("completion_tokens", 0)),
                    "total_tokens": int(usage_raw.get("total_tokens", 0)),
                }
                return ProviderResponse(
                    status="ok",
                    visible_text=visible,
                    model_id=str(raw.get("model", self.model_name)),
                    usage=usage,
                    latency_ms=latency,
                    raw_response=raw,
                )
            except httpx.TimeoutException as error:
                return ProviderResponse(
                    status="unknown_completion",
                    model_id=self.model_name,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    error=redact(str(error), [self.api_key]),
                )
            except httpx.HTTPError as error:
                last_error = str(error)
                if attempt < self.max_retries:
                    time.sleep(2.0 ** attempt)
                    continue
                return ProviderResponse(
                    status="unavailable",
                    model_id=self.model_name,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    error=redact(last_error, [self.api_key]),
                )
        return ProviderResponse(status="unavailable", model_id=self.model_name, error=redact(last_error, [self.api_key]))


class ScriptedProvider:
    """Deterministic provider for tests and non-research state-machine checks."""

    backend = "scripted"
    provider_name = "scripted"

    def __init__(self, responses: list[ProviderResponse], model_name: str = "scripted") -> None:
        self.responses = responses
        self.model_name = model_name
        self.requests: list[ModelRequest] = []
        self.calls = 0

    def decide(self, request: ModelRequest) -> ProviderResponse:
        self.requests.append(request)
        if self.calls >= len(self.responses):
            return ProviderResponse(status="unavailable", model_id=self.model_name, error="script exhausted")
        response = self.responses[self.calls]
        self.calls += 1
        return response


class UnavailableProvider:
    backend = "real_llm"
    provider_name = "unavailable"
    model_name = "unavailable"

    def decide(self, request: ModelRequest) -> ProviderResponse:
        return ProviderResponse(status="unavailable", model_id=self.model_name, error="provider unavailable")


def provider_from_config(config: dict[str, object]) -> ScientistProvider:
    kind = str(config.get("kind", "ollama_native"))
    if kind == "auto":
        key = os.environ.get("SCIENTIST_API_KEY", "")
        base = os.environ.get("SCIENTIST_BASE_URL", "")
        model = os.environ.get("SCIENTIST_MODEL", "")
        if key and base and model:
            return OpenAICompatibleProvider(
                base_url=base,
                model=model,
                api_key=key,
                timeout_seconds=int(config.get("timeout_seconds", 120)),
                max_retries=int(config.get("max_retries", 2)),
                max_output_tokens=int(config.get("max_output_tokens", 1500)),
                temperature=float(config.get("temperature", 0.0)),
                seed=int(config.get("seed", 42)),
            )
        kind = "ollama_native"
    if kind == "openai_compatible":
        key = os.environ.get("SCIENTIST_API_KEY", "")
        base = os.environ.get("SCIENTIST_BASE_URL", "")
        model = os.environ.get("SCIENTIST_MODEL", "")
        if not (key and base and model):
            raise RuntimeError("cloud provider requested but SCIENTIST_* is incomplete")
        return OpenAICompatibleProvider(
            base_url=base,
            model=model,
            api_key=key,
            timeout_seconds=int(config.get("timeout_seconds", 120)),
            max_retries=int(config.get("max_retries", 2)),
            max_output_tokens=int(config.get("max_output_tokens", 1500)),
            temperature=float(config.get("temperature", 0.0)),
            seed=int(config.get("seed", 42)),
        )
    if kind == "ollama_native":
        return OllamaProvider(
            base_url=str(config.get("base_url", "http://127.0.0.1:11434")),
            model=str(config.get("model", "qwen3.5:9b")),
            timeout_seconds=int(config.get("timeout_seconds", 120)),
            max_retries=int(config.get("max_retries", 2)),
            max_output_tokens=int(config.get("max_output_tokens", 1500)),
            temperature=float(config.get("temperature", 0.0)),
            seed=int(config.get("seed", 42)),
            num_ctx=int(config.get("num_ctx", 8192)),
            use_schema=bool(config.get("use_schema", False)),
        )
    raise RuntimeError(f"unknown provider kind {kind}")
