"""Pure fixed-catalog diagnostic: no code execution, filesystem or transport.

Source hashes are externally verified bindings, not proof that source bytes were
inspected here. Structural conclusions are validated; scientific support is audited
separately. Persist complete receipts externally and replay them when resuming.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Iterable


def canonical_json(value: Any) -> str:
    """Strict JSON snapshot, also used as the immutable state representation."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be finite JSON") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _keys(value: Any, names: str) -> None:
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("object has missing or unknown fields")


def _text(value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected nonempty text")


def _strings(value: Any, *, nonempty: bool = False) -> None:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError("expected text list")
    for item in value:
        _text(item)
    if len(set(value)) != len(value):
        raise ValueError("duplicate text identifiers")


def _parameters(action: str, parameters: Any) -> None:
    names = "method fit_design penalty" + (" controls" if action == "consequence" else "")
    _keys(parameters, names)
    if parameters["method"] not in ("identity", "probe_direction", "leace"):
        raise ValueError("unknown method")
    if parameters["fit_design"] not in ("same_sample", "split_subjects"):
        raise ValueError("unknown fit design")
    if type(parameters["penalty"]) is not int or parameters["penalty"] not in (1, 10, 100):
        raise ValueError("penalty must be integer 1, 10 or 100")
    if action == "consequence" and type(parameters["controls"]) is not bool:
        raise ValueError("controls must be boolean")


def validate_action(action: Any, *, evidence_ids: Iterable[str] = ()) -> dict:
    """Validate a decision envelope and return a detached JSON copy."""
    _keys(action, "action parameters reason discriminates evidence_refs conclusion")
    name = action["action"]
    if name not in ("recovery", "consequence", "finish"):
        raise ValueError("unknown action; no test or execution action exists")
    _text(action["reason"])
    _strings(action["discriminates"])
    _strings(action["evidence_refs"])
    known = set(evidence_ids)
    if not set(action["evidence_refs"]) <= known:
        raise ValueError("unknown evidence reference")
    if name == "finish":
        _keys(action["parameters"], "")
        conclusion = action["conclusion"]
        _keys(conclusion, "statement support_ids unresolved not_tested")
        _text(conclusion["statement"])
        _strings(conclusion["support_ids"])
        _strings(conclusion["unresolved"], nonempty=True)
        _strings(conclusion["not_tested"], nonempty=True)
        if not set(conclusion["support_ids"]) <= known:
            raise ValueError("unknown conclusion support")
    else:
        _parameters(name, action["parameters"])
        if action["conclusion"] is not None:
            raise ValueError("operator conclusion must be null")
    return json.loads(canonical_json(action))


@dataclass(frozen=True)
class Episode:
    """Use start/resume/dispatch; all nested state is immutable JSON text."""
    catalog_json: str
    identity_json: str
    receipts: tuple[str, ...] = ()
    requests_used: int = 0
    finished: bool = False


def start(catalog: dict, *, source_bindings: dict[str, str], identity: dict) -> Episode:
    """Freeze a catalog against supplied, externally verified input hashes."""
    _keys(catalog, "task_id layer code_hash input_hashes entries")
    _text(catalog["task_id"])
    if type(catalog["layer"]) is not int or catalog["layer"] not in (6, 12):
        raise ValueError("unsupported layer")
    hashes = catalog["input_hashes"]
    if not isinstance(hashes, dict) or not hashes or hashes != source_bindings:
        raise ValueError("source bindings mismatch or missing")
    for name, value in [("code", catalog["code_hash"]), *hashes.items()]:
        _text(name)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("invalid SHA256 binding")
    if not isinstance(identity, dict) or not identity:
        raise ValueError("nonempty enrollment identity required")
    if not isinstance(catalog["entries"], list) or not catalog["entries"]:
        raise ValueError("empty catalog")
    seen = set()
    for entry in catalog["entries"]:
        _keys(entry, "action parameters result")
        if entry["action"] not in ("recovery", "consequence"):
            raise ValueError("unregistered operator")
        if entry["action"] == "consequence" and catalog["layer"] != 12:
            raise ValueError("consequence requires final layer")
        _parameters(entry["action"], entry["parameters"])
        if not isinstance(entry["result"], dict):
            raise ValueError("catalog result must be object")
        key = canonical_json([entry["action"], entry["parameters"]])
        if key in seen:
            raise ValueError("duplicate catalog entry")
        seen.add(key)
    frozen = canonical_json(catalog)
    binding = {"enrollment": identity, "catalog_hash": digest(catalog)}
    return Episode(frozen, canonical_json(binding))


def dispatch(episode: Episode, action: Any) -> tuple[Episode, dict]:
    """One mechanical turn. Malformed requests count; never repair parameters."""
    if episode.finished:
        raise ValueError("episode already finished")
    # Public transport supplies JSON. Invalid JSON values cannot be journaled.
    request = json.loads(canonical_json(action))
    prior = [json.loads(item) for item in episode.receipts]
    known = [item["output_id"] for item in prior
             if item["error"] is None and item["request"]["action"] != "finish"]
    finish_attempt = isinstance(request, dict) and request.get("action") == "finish"
    final_turn = episode.requests_used == 4
    finished = finish_attempt or final_turn
    used = episode.requests_used + (0 if finish_attempt or final_turn else 1)
    result, error = None, None
    try:
        if final_turn and not finish_attempt:
            raise ValueError("operator budget exhausted; final turn requires finish")
        valid = validate_action(request, evidence_ids=known)
        if finish_attempt:
            result = {"conclusion": valid["conclusion"]}
        else:
            catalog = json.loads(episode.catalog_json)
            matches = [entry for entry in catalog["entries"]
                       if entry["action"] == valid["action"] and entry["parameters"] == valid["parameters"]]
            if not matches:
                raise ValueError("requested operator parameters are not registered")
            result = {"data": matches[0]["result"], "provenance": {
                "catalog_hash": digest(catalog), "code_hash": catalog["code_hash"],
                "input_hashes": catalog["input_hashes"], "action": valid["action"], "parameters": valid["parameters"]}}
    except ValueError as exc:
        error = str(exc)
    receipt = {"output_id": f"output-{len(prior) + 1:03d}", "request": request,
               "result": result, "error": error, "remaining_requests": 4 - used,
               "finished": finished, "identity_hash": digest(json.loads(episode.identity_json)),
               "previous_hash": prior[-1]["receipt_hash"] if prior else None}
    receipt["receipt_hash"] = digest(receipt)
    current = Episode(episode.catalog_json, episode.identity_json,
                      episode.receipts + (canonical_json(receipt),), used, finished)
    return current, receipt


def resume(catalog: dict, *, source_bindings: dict[str, str], identity: dict,
           receipts: list[dict]) -> Episode:
    """Replay receipts, rejecting altered enrollment, catalog, results or chain."""
    if not isinstance(receipts, list):
        raise ValueError("receipts must be ordered list")
    state = start(catalog, source_bindings=source_bindings, identity=identity)
    for retained in receipts:
        if not isinstance(retained, dict) or "request" not in retained:
            raise ValueError("invalid retained receipt")
        state, actual = dispatch(state, retained["request"])
        if canonical_json(actual) != canonical_json(retained):
            raise ValueError("receipt or resume identity mismatch")
    return state
