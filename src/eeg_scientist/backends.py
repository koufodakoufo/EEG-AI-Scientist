"""Backend registry: separate chat models from public search/fetch tools.

Only `deepseek_flash` and `deepseek_search_fetch` are marked verified in this
round.  DeepSeek Pro, Claude Opus/Sonnet, and Gemini are configuration entries
only; attempting to use them raises an explicit unverified-backend error.  No
fake client or silent fallback exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .anthropic_api import AnthropicClient
from .credentials import load_deepseek_key, load_secret
from .deepseek_api import DeepSeekClient, ModelChatClient
from .gemini_api import GeminiClient
from .ledger import BudgetLedger


class BackendError(RuntimeError):
    """Backend configuration or availability problem."""


class UnverifiedBackendError(BackendError):
    """The backend entry exists but has not been validated in this project."""


class PriceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_cache_miss_peak_cny_per_mtok: float
    output_peak_cny_per_mtok: float
    input_cache_miss_offpeak_cny_per_mtok: float
    output_offpeak_cny_per_mtok: float
    search_cny_per_success: float = 0.005
    fetch_cny_per_success: float = 0.005
    source: str
    checked_at: str


class ChatBackend(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    id: str
    provider: str
    protocol: str
    model_name: str | None = None
    model_version: str = ""
    status: str  # verified | unverified | disabled
    reason: str = ""
    base_url: str = ""
    credential_file: str = ""
    credential_variable: str = "DEEPSEEK_API_KEY"
    max_output_tokens: int = 16384
    thinking: bool = True
    thinking_level: str | None = None
    reasoning_effort: str = "high"
    price: PriceConfig | None = None


class ToolBackend(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    id: str
    provider: str
    protocol: str
    status: str
    reason: str = ""
    base_url: str = ""
    credential_file: str = ""
    credential_variable: str = "DEEPSEEK_API_KEY"
    price: PriceConfig | None = None


class BackendRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    checked_at: str = ""
    chat_backends: list[ChatBackend] = Field(default_factory=list)
    tool_backends: list[ToolBackend] = Field(default_factory=list)

    def chat(self, backend_id: str) -> ChatBackend:
        for item in self.chat_backends:
            if item.id == backend_id:
                return item
        raise BackendError(f"unknown chat backend {backend_id!r}")

    def tool(self, backend_id: str) -> ToolBackend:
        for item in self.tool_backends:
            if item.id == backend_id:
                return item
        raise BackendError(f"unknown tool backend {backend_id!r}")


def load_registry(path: Path | str) -> BackendRegistry:
    return BackendRegistry.model_validate_json(Path(path).read_text(encoding="utf-8"))


def require_verified(backend: ChatBackend | ToolBackend) -> None:
    if backend.status != "verified":
        raise UnverifiedBackendError(
            f"backend {backend.id!r} is marked {backend.status!r}, not 'verified': {backend.reason}"
        )


def _build_chat_client(
    *,
    backend: ChatBackend,
    ledger: BudgetLedger,
    attribution: str,
) -> ModelChatClient:
    require_verified(backend)
    model = backend.model_name
    if not model:
        raise BackendError(f"backend {backend.id!r} has no model_name; set a real model ID first")
    if backend.provider == "deepseek":
        key, _report = load_deepseek_key(Path(backend.credential_file), backend.credential_variable)
        return DeepSeekClient(
            api_key=key,
            ledger=ledger,
            base_url=backend.base_url or "https://api.deepseek.com",
            model=model,
            timeout_seconds=600,
            connect_timeout_seconds=20,
            search_timeout_seconds=60,
            fetch_timeout_seconds=60,
            max_retries=2,
            attribution=attribution,
            provider_name=backend.provider,
            backend_status=backend.status,
        )
    if backend.provider == "anthropic":
        if not backend.credential_file:
            raise BackendError("Claude backend has no credential_file configured")
        key, _report = load_secret(
            Path(backend.credential_file),
            backend.credential_variable,
            allowed_prefixes=("sk-ant-",),
        )
        anthropic_client = AnthropicClient(
            api_key=key,
            ledger=ledger,
            model=model,
            base_url=backend.base_url or "https://api.anthropic.com",
            max_tokens=backend.max_output_tokens,
            attribution=attribution,
            thinking=backend.thinking,
        )
        anthropic_client.backend_status = backend.status
        return anthropic_client
    if backend.provider == "google":
        if not backend.credential_file:
            raise BackendError("Gemini backend has no credential_file configured")
        key, _report = load_secret(
            Path(backend.credential_file),
            backend.credential_variable,
            allowed_prefixes=("AIza",),
        )
        gemini_client = GeminiClient(
            api_key=key,
            ledger=ledger,
            model=model,
            base_url=backend.base_url or "https://generativelanguage.googleapis.com",
            max_tokens=backend.max_output_tokens,
            attribution=attribution,
            thinking=backend.thinking,
            thinking_level=backend.thinking_level,
        )
        gemini_client.backend_status = backend.status
        return gemini_client
    raise BackendError(f"no real chat adapter for provider {backend.provider!r}")


def _build_deepseek_client(
    *,
    backend: ChatBackend | ToolBackend,
    ledger: BudgetLedger,
    attribution: str,
    model_override: str | None = None,
) -> DeepSeekClient:
    require_verified(backend)
    if backend.provider != "deepseek" or not backend.credential_file:
        raise UnverifiedBackendError(f"no real client implementation for provider {backend.provider!r}")
    key, _report = load_deepseek_key(Path(backend.credential_file), backend.credential_variable)
    model = model_override or getattr(backend, "model_name", None) or "deepseek-flash"
    return DeepSeekClient(
        api_key=key,
        ledger=ledger,
        base_url=backend.base_url or "https://api.deepseek.com",
        model=model,
        timeout_seconds=600,
        connect_timeout_seconds=20,
        search_timeout_seconds=60,
        fetch_timeout_seconds=60,
        max_retries=2,
        attribution=attribution,
        provider_name=backend.provider,
        backend_status=backend.status,
    )


def create_chat_client(
    registry: BackendRegistry,
    backend_id: str,
    *,
    ledger: BudgetLedger,
    attribution: str,
) -> ModelChatClient:
    backend = registry.chat(backend_id)
    return _build_chat_client(backend=backend, ledger=ledger, attribution=attribution)


def create_tool_client(
    registry: BackendRegistry,
    backend_id: str,
    *,
    ledger: BudgetLedger,
    attribution: str,
) -> DeepSeekClient:
    backend = registry.tool(backend_id)
    return _build_deepseek_client(
        backend=backend,
        ledger=ledger,
        attribution=attribution,
        model_override=backend.model_name if hasattr(backend, "model_name") else None,
    )


def backend_public_info(backend: ChatBackend | ToolBackend) -> dict[str, object]:
    return {
        "id": backend.id,
        "provider": backend.provider,
        "protocol": backend.protocol,
        "status": backend.status,
        "reason": backend.reason,
        "model_name": getattr(backend, "model_name", None),
        "model_version": getattr(backend, "model_version", ""),
        "base_url": backend.base_url,
        "price": backend.price.model_dump(mode="json") if backend.price else None,
        "verified_in_this_project": backend.status == "verified",
    }
