"""Public-input construction, JSON parsing, repair, and method-rule plumbing."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from .experiments import SUPPORTED_METRIC_KEYS, validate_request_against_tool
from ..schema import (
    Decision,
    ExperimentResult,
    MetaResponse,
    ModelRequest,
    PublicCase,
    ResearchRule,
)
from ..storage import canonical_json, sha256_text, utc_now

DECISION_JSON_SHAPE = """ACTION:
{
  "decision_type": "action",
  "hypotheses": [
    {"id": "H1", "claim": "...", "mechanism": "...", "supporting_evidence_ids": ["obs_1"], "limitations": "..."},
    {"id": "H2", "claim": "...", "mechanism": "...", "supporting_evidence_ids": ["obs_1"], "limitations": "..."}
  ],
  "request_id": "req_1",
  "tool_id": "split_audit" | "trial_random_labels" | "trial_shuffle_within_subject" | "window_random_labels" | "metadata_only",
  "parameters": {},
  "distinguishes": ["H1", "H2"],
  "prediction": {
    "scoring_status": "numeric" | "not_applicable",
    "metric_key": "one supported key or null",
    "primary_direction": "positive" | "negative" | "near_zero" | null,
    "threshold": 0.05,
    "check_facts": ["..."],
    "conditional_predictions": [{"hypothesis_id": "H1", "direction": "positive", "rationale": "..."}],
    "update_rule_if_opposite": "..."
  },
  "reasoning_summary": "<= 60 words"
}

STOP:
{
  "decision_type": "stop",
  "hypotheses": [ ... two or three ... ],
  "reason": "...",
  "final_judgment": "...",
  "evidence_ids": ["obs_1", "req_1"],
  "remaining_uncertainty": "...",
  "reasoning_summary": "<= 60 words"
}"""

TOOL_SPECS: dict[str, dict[str, object]] = {
    "split_audit": {
        "question": "What does each split actually isolate, and how does performance vary by group?",
        "parameters": {},
        "supported_metrics": sorted(SUPPORTED_METRIC_KEYS["split_audit"]),
        "scoring": ["not_applicable", "numeric"],
        "note": "A pure audit is best scored not_applicable with explicit check_facts.",
    },
    "trial_random_labels": {
        "question": "Can a window split exploit a trial-specific signature when labels are reassigned at the trial level?",
        "parameters": {},
        "supported_metrics": sorted(SUPPORTED_METRIC_KEYS["trial_random_labels"]),
        "scoring": ["numeric"],
        "note": "10 pre-registered seeds; window and trial splits; distribution is reported.",
    },
    "trial_shuffle_within_subject": {
        "question": "What happens when the trial-task relation is permuted within each subject while class counts are preserved?",
        "parameters": {},
        "supported_metrics": sorted(SUPPORTED_METRIC_KEYS["trial_shuffle_within_subject"]),
        "scoring": ["numeric"],
        "note": "10 pre-registered seeds; a subject with one class makes the mapping invalid.",
    },
    "window_random_labels": {
        "question": "What is the window-level negative control when labels are independently reassigned per window?",
        "parameters": {},
        "supported_metrics": sorted(SUPPORTED_METRIC_KEYS["window_random_labels"]),
        "scoring": ["numeric"],
        "note": "Window-level metric only; do not aggregate to a trial truth.",
    },
    "metadata_only": {
        "question": "Do subject/session identities alone predict labels under trial isolation?",
        "parameters": {},
        "supported_metrics": sorted(SUPPORTED_METRIC_KEYS["metadata_only"]),
        "scoring": ["numeric"],
        "note": "One-hot metadata only; unseen categories are ignored.",
    },
}


class DecisionParseError(ValueError):
    """A model answer that is not a valid Decision."""


def load_rule_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_json(text: str) -> object:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    if start < 0:
        raise DecisionParseError("no JSON object found")
    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(cleaned[start:])
        return value
    except json.JSONDecodeError as error:
        raise DecisionParseError(f"invalid JSON: {error}") from error


def _normalize_decision_payload(payload: object) -> dict[str, object]:
    """Accept both the compact flat wire shape and the nested action/stop shape."""
    if not isinstance(payload, dict):
        raise DecisionParseError("decision JSON must be an object")
    data: dict[str, object] = dict(payload)
    action_keys = ("request_id", "tool_id", "parameters", "distinguishes", "prediction")
    stop_keys = ("reason", "final_judgment", "evidence_ids", "remaining_uncertainty")
    decision_type = data.get("decision_type")
    action = data.get("action")
    if isinstance(action, dict):
        action_data = dict(action)
        if "stop" in action_data and action_data.get("stop") is None:
            action_data.pop("stop")
        if "reasoning_summary" in action_data:
            inner_summary = action_data.pop("reasoning_summary")
            if not data.get("reasoning_summary") and isinstance(inner_summary, str):
                data["reasoning_summary"] = inner_summary
        data["action"] = action_data
    if decision_type is None:
        if isinstance(data.get("action"), dict):
            decision_type = "action"
        elif isinstance(data.get("stop"), dict):
            decision_type = "stop"
        data["decision_type"] = decision_type
    if decision_type == "action":
        if not isinstance(data.get("action"), dict):
            data["action"] = {key: data[key] for key in action_keys if key in data}
        for key in action_keys:
            data.pop(key, None)
        data["stop"] = None
        action_payload = data.get("action")
        if isinstance(action_payload, dict):
            prediction = action_payload.get("prediction")
            if isinstance(prediction, dict):
                if prediction.get("update_rule_if_opposite") is None:
                    prediction["update_rule_if_opposite"] = ""
                if prediction.get("check_facts") is None:
                    prediction["check_facts"] = []
                if prediction.get("conditional_predictions") is None:
                    prediction["conditional_predictions"] = []
            hypotheses = data.get("hypotheses")
            if isinstance(hypotheses, list):
                for hypothesis in hypotheses:
                    if isinstance(hypothesis, dict):
                        if hypothesis.get("supporting_evidence_ids") is None:
                            hypothesis["supporting_evidence_ids"] = []
                        if hypothesis.get("limitations") is None:
                            hypothesis["limitations"] = ""
    elif decision_type == "stop":
        if not isinstance(data.get("stop"), dict):
            data["stop"] = {key: data[key] for key in stop_keys if key in data}
        for key in stop_keys:
            data.pop(key, None)
        data["action"] = None
        stop_payload = data.get("stop")
        if isinstance(stop_payload, dict):
            if stop_payload.get("remaining_uncertainty") is None:
                stop_payload["remaining_uncertainty"] = ""
            if stop_payload.get("evidence_ids") is None:
                stop_payload["evidence_ids"] = []
    if data.get("reasoning_summary") is None:
        data["reasoning_summary"] = ""
    return data


def parse_decision(text: str) -> Decision:
    try:
        payload = _extract_json(text)
    except DecisionParseError:
        raise
    try:
        normalized = _normalize_decision_payload(payload)
        decision = Decision.model_validate(normalized)
    except DecisionParseError:
        raise
    except Exception as error:  # noqa: BLE001 - boundary validation
        raise DecisionParseError(f"schema validation failed: {error}") from error
    hypothesis_ids = {hypothesis.id for hypothesis in decision.hypotheses}
    if len(hypothesis_ids) != len(decision.hypotheses):
        raise DecisionParseError("hypothesis ids are not unique")
    if decision.action is not None:
        if not set(decision.action.distinguishes).issubset(hypothesis_ids):
            raise DecisionParseError("distinguishes references an unknown hypothesis")
        try:
            validate_request_against_tool(decision.action)
        except Exception as error:  # noqa: BLE001 - convert request errors to decision errors
            raise DecisionParseError(str(error)) from error
        for conditional in decision.action.prediction.conditional_predictions:
            if conditional.hypothesis_id not in hypothesis_ids:
                raise DecisionParseError("conditional prediction references an unknown hypothesis")
    return decision


def build_request(
    public_case: PublicCase,
    rule_text: str,
    *,
    history: list[dict[str, object]],
    development_facts: dict[str, object] | None,
    stage: str,
    force_stop: bool = False,
) -> ModelRequest:
    public_payload = {
        "case": public_case.model_dump(mode="json"),
        "tool_specs": TOOL_SPECS,
        "development_facts": development_facts,
        "history": history,
        "stage": stage,
        "force_stop": force_stop,
        "decision_format": DECISION_JSON_SHAPE,
    }
    user_text = json.dumps(public_payload, ensure_ascii=False, separators=(",", ":"), default=str)
    public_hash = sha256_text(canonical_json(public_payload))
    return ModelRequest(
        request_id=f"req_{uuid.uuid4().hex[:12]}",
        stage=stage,
        messages=[
            {"role": "system", "content": rule_text},
            {"role": "user", "content": user_text},
        ],
        model_settings={
            "temperature": 0.0,
            "max_output_tokens": 1500,
            "think": False,
            "format": "json",
        },
        rule_hash=sha256_text(rule_text),
        public_input_hash=public_hash,
        created_at=utc_now(),
    )


def build_repair_request(
    original_text: str,
    error: str,
    *,
    rule_text: str,
    public_input_hash: str,
) -> ModelRequest:
    repair_system = (
        "You repair malformed JSON. Return ONLY one JSON object matching the requested Decision shape. "
        "Do not add new scientific claims or results; preserve the original intent and fix syntax/schema errors."
    )
    repair_user = json.dumps(
        {
            "original_output": original_text,
            "validation_error": error,
            "decision_format": DECISION_JSON_SHAPE,
            "rule_text": rule_text,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return ModelRequest(
        request_id=f"repair_{uuid.uuid4().hex[:12]}",
        stage="repair",
        messages=[
            {"role": "system", "content": repair_system},
            {"role": "user", "content": repair_user},
        ],
        model_settings={"temperature": 0.0, "max_output_tokens": 1500, "think": False, "format": "json"},
        rule_hash=sha256_text(rule_text),
        public_input_hash=public_input_hash,
        created_at=utc_now(),
    )


def summarize_result(result: ExperimentResult) -> dict[str, object]:
    randomization = result.randomization
    summary_randomization: dict[str, object] = {}
    if randomization:
        summary_randomization = {
            "seeds": randomization.get("seeds"),
            "n_valid_seeds": randomization.get("n_valid_seeds"),
            "per_seed": randomization.get("per_seed"),
            "invalid_reasons": randomization.get("invalid_reasons"),
        }
    return {
        "request_id": result.request_id,
        "tool_id": result.tool_id,
        "valid": result.valid,
        "invalid_reason": result.invalid_reason,
        "metrics": result.metrics,
        "randomization": summary_randomization,
        "audit": {
            level: {
                "overlap": audit.get("overlap"),
                "label_counts": audit.get("label_counts"),
                "n_groups": audit.get("n_groups"),
                "invalid_reason": audit.get("invalid_reason"),
            }
            for level, audit in result.audit.items()
        },
        "details": result.details,
        "elapsed_seconds": result.elapsed_seconds,
    }


def summarize_decision(decision: Decision) -> dict[str, object]:
    return {
        "decision_type": decision.decision_type,
        "hypotheses": [hypothesis.model_dump(mode="json") for hypothesis in decision.hypotheses],
        "action": decision.action.model_dump(mode="json") if decision.action else None,
        "stop": decision.stop.model_dump(mode="json") if decision.stop else None,
        "reasoning_summary": decision.reasoning_summary,
    }


def build_meta_request(
    development_facts: dict[str, object],
    s0_text: str,
    event_ids: list[str],
) -> ModelRequest:
    system = (
        "You are the method-update assistant for a controlled EEG-style study. "
        "Read only the supplied development facts and S0 trajectory metadata. Propose at most 3 general research-method rules. "
        "Each rule must contain trigger, action, boundary, and source event IDs. Rules must be conditional and must not name "
        "any holdout case, family code, hidden mechanism, or a fixed tool choice. If no justified rule exists, return no_update. "
        "Return ONLY JSON: {\"update\":\"rules\"|\"no_update\",\"rules\":[{\"trigger\":\"...\",\"action\":\"...\","
        "\"boundary\":\"...\",\"evidence_event_ids\":[\"...\"]}],\"reasoning_summary\":\"...\"}. "
        "Keep rules under 600 characters total."
    )
    user = json.dumps(
        {"development_facts": development_facts, "s0_text": s0_text, "available_event_ids": event_ids},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return ModelRequest(
        request_id=f"meta_{uuid.uuid4().hex[:12]}",
        stage="meta",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        model_settings={"temperature": 0.0, "max_output_tokens": 1500, "think": False, "format": "json"},
        rule_hash=sha256_text(s0_text),
        public_input_hash=sha256_text(canonical_json(development_facts)),
        created_at=utc_now(),
    )


def parse_meta(text: str, allowed_event_ids: set[str]) -> MetaResponse:
    payload = _extract_json(text)
    try:
        meta = MetaResponse.model_validate(payload)
    except Exception as error:  # noqa: BLE001 - boundary validation
        raise DecisionParseError(f"meta schema validation failed: {error}") from error
    for rule in meta.rules:
        if not set(rule.evidence_event_ids).issubset(allowed_event_ids):
            raise DecisionParseError("rule cites an event that is not in the development facts")
        forbidden = ("case_003", "case_004", "case_005", "case_006", "family", "holdout")
        joined = f"{rule.trigger} {rule.action} {rule.boundary}".lower()
        for token in forbidden:
            if token in joined:
                raise DecisionParseError(f"rule contains forbidden token {token}")
    return meta


def build_s1_text(s0_text: str, meta: MetaResponse) -> str:
    if meta.update == "no_update" or not meta.rules:
        rules_block = "No method update was made. The S0 rules remain unchanged."
    else:
        lines = []
        for index, rule in enumerate(meta.rules, start=1):
            lines.append(
                f"{index}. Trigger: {rule.trigger} | Action: {rule.action} | Boundary: {rule.boundary} | "
                f"Evidence events: {', '.join(rule.evidence_event_ids)}"
            )
        rules_block = "\n".join(lines)
    return (
        s0_text.rstrip()
        + "\n\n## Method rules (S1, frozen)\n\n"
        + rules_block
        + "\n\nThese rules were derived from development trajectories only. They must not be changed after freeze.\n"
    )


def collect_event_ids(development_facts: dict[str, object]) -> list[str]:
    ids: set[str] = set()
    trajectory = development_facts.get("trajectories", [])
    if isinstance(trajectory, list):
        for item in trajectory:
            if isinstance(item, dict):
                for event in item.get("events", []) if isinstance(item.get("events"), list) else []:
                    if isinstance(event, dict) and isinstance(event.get("event_id"), str):
                        ids.add(event["event_id"])
                for key in ("episode_id", "case_id"):
                    value = item.get(key)
                    if isinstance(value, str):
                        ids.add(value)
    return sorted(ids)


def rule_count(meta: MetaResponse) -> int:
    return len(meta.rules)


def sort_rules(rules: list[ResearchRule]) -> list[ResearchRule]:
    return sorted(rules, key=lambda rule: (rule.trigger, rule.action))


def probe_request() -> ModelRequest:
    return ModelRequest(
        request_id="probe_1",
        stage="probe",
        messages=[
            {"role": "user", "content": "Return only one JSON object: {\"ok\": true, \"note\": \"local route works\"}."}
        ],
        model_settings={"temperature": 0.0, "max_output_tokens": 128, "think": False, "format": "json"},
        rule_hash=sha256_text("probe"),
        public_input_hash=sha256_text("probe"),
        created_at=utc_now(),
    )
