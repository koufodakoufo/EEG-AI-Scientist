"""Persistent spend/attempt/token ledger for the Flash overnight run.

The ledger is deliberately conservative:

* every paid request is reserved at peak prices **before** the HTTP call;
* a successful response settles against reported usage;
* a timeout or ambiguous server failure keeps the reservation as UNKNOWN spend;
* a resumed process sees the same counters and never resets them.

Search/Fetch are counted per successful request at the documented price.  The
ledger is a JSON file replaced atomically after every mutation.
"""

from __future__ import annotations

import math
import time
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .storage import atomic_write_json, ensure_dir, utc_now


class LedgerError(RuntimeError):
    """Base error for the budget ledger."""


class BudgetExceeded(LedgerError):
    """A new paid request would violate the configured cap."""


class LedgerState(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    run_id: str
    cap_cny: float = 20.0
    wrap_up_reserve_cny: float = 2.0
    spent_cny: float = 0.0
    unknown_cny: float = 0.0
    reserved_cny: float = 0.0
    model_attempts: int = 0
    search_attempts: int = 0
    fetch_attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model_attempts_limit: int = 120
    model_attempts_reserved_for_wrap_up: int = 10
    search_attempts_limit: int = 60
    fetch_attempts_limit: int = 90
    input_tokens_limit: int = 2_000_000
    output_tokens_limit: int = 500_000
    input_price_cny_per_mtok: float = 2.0
    output_price_cny_per_mtok: float = 8.0
    tool_price_cny_per_request: float = 0.005
    price_source: str = ""
    price_checked_at: str = ""
    pending: dict[str, dict[str, object]] = Field(default_factory=dict)
    history: list[dict[str, object]] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


def _number(payload: dict[str, object], key: str, default: float = 0.0) -> float:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


class Reservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: str
    kind: str
    reserved_cny: float
    created_at: str


class BudgetLedger:
    """Single-process ledger shared by capability, diagnostics, and research."""

    def __init__(
        self,
        path: Path | str,
        *,
        run_id: str,
        cap_cny: float = 20.0,
        wrap_up_reserve_cny: float = 2.0,
        model_attempts_limit: int = 120,
        search_attempts_limit: int = 60,
        fetch_attempts_limit: int = 90,
        input_tokens_limit: int = 2_000_000,
        output_tokens_limit: int = 500_000,
        input_price_cny_per_mtok: float = 2.0,
        output_price_cny_per_mtok: float = 8.0,
        tool_price_cny_per_request: float = 0.005,
        price_source: str = "",
        price_checked_at: str = "",
    ) -> None:
        self.path = Path(path)
        ensure_dir(self.path.parent)
        if self.path.exists():
            try:
                self.state = LedgerState.model_validate_json(self.path.read_text(encoding="utf-8"))
            except Exception as error:  # noqa: BLE001 - corrupt ledger must stop paid calls
                raise LedgerError(f"ledger unreadable: {error}") from error
            if self.state.run_id != run_id:
                raise LedgerError(
                    f"ledger belongs to run {self.state.run_id!r}, not {run_id!r}; refusing to reset"
                )
        else:
            self.state = LedgerState(
                run_id=run_id,
                cap_cny=cap_cny,
                wrap_up_reserve_cny=wrap_up_reserve_cny,
                model_attempts_limit=model_attempts_limit,
                search_attempts_limit=search_attempts_limit,
                fetch_attempts_limit=fetch_attempts_limit,
                input_tokens_limit=input_tokens_limit,
                output_tokens_limit=output_tokens_limit,
                input_price_cny_per_mtok=input_price_cny_per_mtok,
                output_price_cny_per_mtok=output_price_cny_per_mtok,
                tool_price_cny_per_request=tool_price_cny_per_request,
                price_source=price_source,
                price_checked_at=price_checked_at,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            self._save()

    # ------------------------------------------------------------------ utils
    def _save(self) -> None:
        self.state.updated_at = utc_now()
        atomic_write_json(self.path, self.state.model_dump(mode="json"))

    def _record(self, action: str, **payload: object) -> None:
        entry: dict[str, object] = {"at": utc_now(), "action": action}
        entry.update(payload)
        self.state.history.append(entry)
        if len(self.state.history) > 2000:
            self.state.history = self.state.history[-2000:]

    def committed_cny(self) -> float:
        return self.state.spent_cny + self.state.unknown_cny + self.state.reserved_cny

    def available_for_new_spend_cny(self) -> float:
        return self.state.cap_cny - self.state.wrap_up_reserve_cny - self.committed_cny()

    def remaining_model_attempts(self) -> int:
        return self.state.model_attempts_limit - self.state.model_attempts

    def remaining_search_attempts(self) -> int:
        return self.state.search_attempts_limit - self.state.search_attempts

    def remaining_fetch_attempts(self) -> int:
        return self.state.fetch_attempts_limit - self.state.fetch_attempts

    # --------------------------------------------------------------- reserve
    def _check_cap(self, cost: float, label: str) -> None:
        if cost < 0:
            raise LedgerError("negative cost")
        available = self.available_for_new_spend_cny()
        if cost > available + 1e-9:
            raise BudgetExceeded(
                f"{label}: requires up to CNY {cost:.4f}, only CNY {available:.4f} "
                f"available before the CNY {self.state.wrap_up_reserve_cny:.2f} wrap-up reserve"
            )

    def reserve_model(self, input_text: str, max_output_tokens: int, *, attribution: str = "") -> Reservation:
        """Reserve worst-case cost for one Chat Completions attempt.

        Input tokens are upper-bounded by the UTF-8 byte count, which is
        conservative for BPE tokenizers.  No average character ratio is used.
        """

        if max_output_tokens <= 0:
            raise LedgerError("max_output_tokens must be positive")
        if self.state.model_attempts >= self.state.model_attempts_limit:
            raise BudgetExceeded(
                f"model attempt cap reached ({self.state.model_attempts}/{self.state.model_attempts_limit})"
            )
        input_upper = len(input_text.encode("utf-8"))
        if input_upper > self.state.input_tokens_limit:
            raise BudgetExceeded("single request input exceeds the whole input token cap")
        if self.state.input_tokens + input_upper > self.state.input_tokens_limit:
            raise BudgetExceeded("input token cap would be exceeded by this attempt's upper bound")
        if self.state.output_tokens + max_output_tokens > self.state.output_tokens_limit:
            raise BudgetExceeded("output token cap would be exceeded by this attempt's reservation")
        cost = (
            input_upper / 1_000_000.0 * self.state.input_price_cny_per_mtok
            + max_output_tokens / 1_000_000.0 * self.state.output_price_cny_per_mtok
        )
        self._check_cap(cost, "model request")
        reservation = Reservation(
            reservation_id=f"res_{uuid.uuid4().hex[:12]}",
            kind="model",
            reserved_cny=round(cost, 6),
            created_at=utc_now(),
        )
        self.state.pending[reservation.reservation_id] = {
            "kind": "model",
            "reserved_cny": reservation.reserved_cny,
            "input_upper_tokens": input_upper,
            "max_output_tokens": max_output_tokens,
            "created_at": reservation.created_at,
            "attribution": attribution,
        }
        self.state.reserved_cny += reservation.reserved_cny
        self.state.model_attempts += 1
        self._record(
            "reserve_model",
            reservation_id=reservation.reservation_id,
            reserved_cny=reservation.reserved_cny,
            input_upper_tokens=input_upper,
            max_output_tokens=max_output_tokens,
            attempt=self.state.model_attempts,
            attribution=attribution,
        )
        self._save()
        return reservation

    def settle_model(
        self,
        reservation_id: str,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        returned_model: str = "",
        finish_reason: str = "",
    ) -> float:
        pending = self._pop_pending(reservation_id, "model")
        actual = (
            max(prompt_tokens, 0) / 1_000_000.0 * self.state.input_price_cny_per_mtok
            + max(completion_tokens, 0) / 1_000_000.0 * self.state.output_price_cny_per_mtok
        )
        reserved_value = _number(pending, "reserved_cny")
        self.state.reserved_cny = max(0.0, self.state.reserved_cny - reserved_value)
        self.state.spent_cny += actual
        self.state.input_tokens += max(prompt_tokens, 0)
        self.state.output_tokens += max(completion_tokens, 0)
        self._record(
            "settle_model",
            reservation_id=reservation_id,
            actual_cny=round(actual, 6),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            returned_model=returned_model,
            finish_reason=finish_reason,
            attribution=str(pending.get("attribution", "")),
        )
        self._save()
        return actual

    def release(self, reservation_id: str, reason: str) -> None:
        pending = self._pop_pending(reservation_id, None)
        reserved_value = _number(pending, "reserved_cny")
        self.state.reserved_cny = max(0.0, self.state.reserved_cny - reserved_value)
        self._record(
            "release",
            reservation_id=reservation_id,
            released_cny=reserved_value,
            reason=reason,
            attribution=str(pending.get("attribution", "")),
        )
        self._save()

    def mark_unknown(self, reservation_id: str, reason: str) -> None:
        pending = self._pop_pending(reservation_id, None)
        reserved_value = _number(pending, "reserved_cny")
        self.state.reserved_cny = max(0.0, self.state.reserved_cny - reserved_value)
        self.state.unknown_cny += reserved_value
        self._record(
            "unknown",
            reservation_id=reservation_id,
            unknown_cny=reserved_value,
            reason=reason,
            attribution=str(pending.get("attribution", "")),
        )
        self._save()

    def mark_all_pending_unknown(self, reason: str) -> int:
        pending_ids = list(self.state.pending)
        for reservation_id in pending_ids:
            self.mark_unknown(reservation_id, reason)
        return len(pending_ids)

    def _pop_pending(self, reservation_id: str, expected_kind: str | None) -> dict[str, object]:
        pending = self.state.pending.get(reservation_id)
        if pending is None:
            raise LedgerError(f"unknown reservation {reservation_id}")
        if expected_kind is not None and pending.get("kind") != expected_kind:
            raise LedgerError(f"reservation {reservation_id} is not a {expected_kind} reservation")
        return self.state.pending.pop(reservation_id)

    # ------------------------------------------------------------------ tools
    def reserve_tool(self, kind: str, *, attribution: str = "") -> Reservation:
        if kind not in {"search", "fetch"}:
            raise LedgerError(f"unknown tool kind {kind}")
        limit = (
            self.state.search_attempts_limit
            if kind == "search"
            else self.state.fetch_attempts_limit
        )
        used = self.state.search_attempts if kind == "search" else self.state.fetch_attempts
        if used >= limit:
            raise BudgetExceeded(f"{kind} attempt cap reached ({used}/{limit})")
        cost = self.state.tool_price_cny_per_request
        self._check_cap(cost, f"{kind} request")
        reservation = Reservation(
            reservation_id=f"res_{uuid.uuid4().hex[:12]}",
            kind=kind,
            reserved_cny=cost,
            created_at=utc_now(),
        )
        self.state.pending[reservation.reservation_id] = {
            "kind": kind,
            "reserved_cny": cost,
            "created_at": reservation.created_at,
            "attribution": attribution,
        }
        self.state.reserved_cny += cost
        if kind == "search":
            self.state.search_attempts += 1
        else:
            self.state.fetch_attempts += 1
        self._record(f"reserve_{kind}", reservation_id=reservation.reservation_id, reserved_cny=cost, attribution=attribution)
        self._save()
        return reservation

    def settle_tool(self, reservation_id: str, *, succeeded: bool, note: str = "") -> None:
        pending = self._pop_pending(reservation_id, None)
        reserved_value = _number(pending, "reserved_cny")
        self.state.reserved_cny = max(0.0, self.state.reserved_cny - reserved_value)
        if succeeded:
            self.state.spent_cny += reserved_value
        self._record(
            "settle_tool",
            reservation_id=reservation_id,
            charged_cny=reserved_value if succeeded else 0.0,
            succeeded=succeeded,
            note=note,
            attribution=str(pending.get("attribution", "")),
        )
        self._save()

    # ---------------------------------------------------------------- summary
    def cost_by_attribution(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for entry in self.state.history:
            action = entry.get("action")
            amount = 0.0
            if action == "settle_model":
                amount = _number(entry, "actual_cny")
            elif action == "settle_tool":
                amount = _number(entry, "charged_cny")
            elif action == "unknown":
                amount = _number(entry, "unknown_cny")
            if amount:
                key = str(entry.get("attribution", "")) or "(unattributed)"
                totals[key] = round(totals.get(key, 0.0) + amount, 6)
        return totals

    def snapshot(self) -> dict[str, object]:
        return {
            "run_id": self.state.run_id,
            "cap_cny": self.state.cap_cny,
            "wrap_up_reserve_cny": self.state.wrap_up_reserve_cny,
            "spent_cny": round(self.state.spent_cny, 6),
            "unknown_cny": round(self.state.unknown_cny, 6),
            "reserved_cny": round(self.state.reserved_cny, 6),
            "committed_cny": round(self.committed_cny(), 6),
            "available_for_new_spend_cny": round(self.available_for_new_spend_cny(), 6),
            "model_attempts": self.state.model_attempts,
            "model_attempts_limit": self.state.model_attempts_limit,
            "search_attempts": self.state.search_attempts,
            "search_attempts_limit": self.state.search_attempts_limit,
            "fetch_attempts": self.state.fetch_attempts,
            "fetch_attempts_limit": self.state.fetch_attempts_limit,
            "input_tokens": self.state.input_tokens,
            "output_tokens": self.state.output_tokens,
            "input_tokens_limit": self.state.input_tokens_limit,
            "output_tokens_limit": self.state.output_tokens_limit,
            "input_price_cny_per_mtok": self.state.input_price_cny_per_mtok,
            "output_price_cny_per_mtok": self.state.output_price_cny_per_mtok,
            "tool_price_cny_per_request": self.state.tool_price_cny_per_request,
            "price_source": self.state.price_source,
            "price_checked_at": self.state.price_checked_at,
            "cost_by_attribution": self.cost_by_attribution(),
            "pending": len(self.state.pending),
            "updated_at": self.state.updated_at,
        }


def estimate_tokens_upper(text: str) -> int:
    """Conservative token upper bound used only for reporting."""

    return int(math.ceil(len(text.encode("utf-8")) / 1.0))


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
