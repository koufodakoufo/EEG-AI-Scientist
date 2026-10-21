"""Controlled Meta update for literature trajectories.

The Meta model gets an independent context containing only:

* the old `literature_v1` final answer / structured result summary;
* explicitly labelled reviewer feedback from `EVIDENCE_AUDIT.md` and
  `REASONING_REVIEW.md`.

It never receives the new emotion question, the new material package, any new
answer, or any score.  The output is at most one transferable research rule or
`no_update`.  This reuses the old `ResearchRule` / `MetaResponse` structure and
its length/source-ID checks, but not the old synthetic study.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..deepseek_api import ModelChatClient
from ..schema import MetaResponse, ResearchRule
from ..storage import atomic_write_json, atomic_write_text, ensure_dir, utc_now

META_SYSTEM = """You are the method-update assistant for a controlled research study. You are given one completed development trajectory and explicitly labelled reviewer feedback. Your job is to propose at most ONE transferable research-method rule that could improve future literature-based research proposals.

You do NOT know and must not ask for the new evaluation question, its materials, answers, scores, model identity, or rule group. Do not mention a specific new topic, dataset, or answer. The rule must be generic, conditional, and applicable to a different question.

Return ONLY one JSON object:
{"update":"rules"|"no_update",
 "rules":[{"trigger":"...","action":"...","boundary":"...","evidence_event_ids":["..."]}],
 "reasoning_summary":"..."}

Constraints:
- at most one rule; total trigger+action+boundary <= 600 characters;
- each rule needs at least one source ID from the supplied allowed list;
- do not name a specific case, dataset, paper, topic, or hidden answer;
- if the trajectory does not justify a transferable rule, return no_update rather than inventing one.
"""


class MetaDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    accepted: bool
    decision: str
    reason: str
    rule_text: str = ""
    rule: dict[str, object] | None = None
    source_ids: list[str] = []
    created_at: str = ""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_meta_messages(
    *,
    old_run_dir: Path,
    review_files: list[Path],
    allowed_source_ids: list[str],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    final_path = old_run_dir / "final.json"
    answer_path = old_run_dir / "final_answer.md"
    if not final_path.exists() or not answer_path.exists():
        raise RuntimeError("old literature_v1 final.json/final_answer.md is missing")
    final = json.loads(final_path.read_text(encoding="utf-8"))
    answer = _read(answer_path)
    reviews: list[dict[str, str]] = []
    for path in review_files:
        if not path.exists():
            continue
        reviews.append({"source_id": f"review:{path.stem}", "path": str(path), "text": _read(path)})

    source_labels = [
        {"source_id": "literature_v1:final_answer", "kind": "development trajectory answer"},
        {"source_id": "literature_v1:final_json", "kind": "development structured result"},
    ] + [{"source_id": item["source_id"], "kind": "explicit reviewer feedback"} for item in reviews]
    allowed = list(dict.fromkeys(allowed_source_ids + [item["source_id"] for item in source_labels]))

    payload = {
        "allowed_source_ids": allowed,
        "development_trajectory": {
            "run_id": final.get("run_id", ""),
            "stop_reason": final.get("stop_reason", ""),
            "accepted": final.get("accepted", False),
            "acceptance": final.get("acceptance", ""),
            "evidence_ids": final.get("evidence_ids", []),
            "final_answer": answer,
            "final_json_summary": {
                "unresolved": final.get("unresolved", []),
                "limitations": final.get("limitations", ""),
            },
        },
        "reviewer_feedback": reviews,
        "instruction": "Propose at most one transferable rule, or no_update. Do not ask for or infer the new evaluation question.",
    }
    user_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    messages: list[dict[str, object]] = [
        {"role": "system", "content": META_SYSTEM},
        {"role": "user", "content": user_text},
    ]
    return messages, {
        "allowed_source_ids": allowed,
        "old_run_id": final.get("run_id", ""),
        "review_sources": [str(path) for path in review_files if path.exists()],
        "payload_sha256": __import__("hashlib").sha256(user_text.encode("utf-8")).hexdigest(),
    }


def _rule_text(rule: ResearchRule) -> str:
    return (
        f"Trigger: {rule.trigger}\n"
        f"Action: {rule.action}\n"
        f"Boundary: {rule.boundary}\n"
        f"Evidence: {', '.join(rule.evidence_event_ids)}\n"
    )


def validate_meta_response(
    meta: MetaResponse,
    *,
    allowed_source_ids: set[str],
    max_rules: int = 1,
    max_chars: int = 600,
    forbidden_tokens: tuple[str, ...] = (),
) -> MetaDecision:
    if meta.update == "no_update":
        return MetaDecision(
            accepted=False,
            decision="no_update",
            reason="Meta returned no_update; no rule is applied.",
            source_ids=[],
            created_at=utc_now(),
        )
    if len(meta.rules) != 1 or max_rules != 1:
        return MetaDecision(
            accepted=False,
            decision="rejected",
            reason=f"expected exactly one rule, got {len(meta.rules)}",
            created_at=utc_now(),
        )
    rule = meta.rules[0]
    text = _rule_text(rule)
    if len(text) > max_chars:
        return MetaDecision(
            accepted=False,
            decision="rejected",
            reason=f"rule text exceeds {max_chars} characters ({len(text)})",
            created_at=utc_now(),
        )
    unknown = sorted(set(rule.evidence_event_ids) - allowed_source_ids)
    if unknown:
        return MetaDecision(
            accepted=False,
            decision="rejected",
            reason="rule cites source IDs outside the allowed development list: " + ", ".join(unknown),
            created_at=utc_now(),
        )
    lowered = text.lower()
    for token in forbidden_tokens:
        if token.lower() in lowered:
            return MetaDecision(
                accepted=False,
                decision="rejected",
                reason=f"rule contains forbidden new-study token {token!r}",
                created_at=utc_now(),
            )
    return MetaDecision(
        accepted=True,
        decision="rules",
        reason="one transferable rule accepted by structural checks",
        rule_text=text,
        rule=rule.model_dump(mode="json"),
        source_ids=list(rule.evidence_event_ids),
        created_at=utc_now(),
    )


def run_meta(
    client: ModelChatClient,
    *,
    old_run_dir: Path,
    review_files: list[Path],
    out_dir: Path,
    allowed_source_ids: list[str],
    max_output_tokens: int = 4000,
) -> dict[str, object]:
    target = ensure_dir(out_dir)
    messages, provenance = build_meta_messages(
        old_run_dir=old_run_dir,
        review_files=review_files,
        allowed_source_ids=allowed_source_ids,
    )
    atomic_write_json(target / "meta_input.json", {"messages": messages, "provenance": provenance})
    result = client.chat(messages, tools=None, max_tokens=max_output_tokens, json_mode=True, stage="meta_literature_v1")
    atomic_write_json(
        target / "meta_response.json",
        {
            "at": utc_now(),
            "model": result.returned_model,
            "request_id": result.request_id,
            "usage": result.usage.model_dump(mode="json"),
            "content": result.content,
            "reasoning_content": result.reasoning_content,
            "raw": result.raw,
        },
    )
    try:
        raw = json.loads(result.content)
        meta = MetaResponse.model_validate(raw)
    except Exception as error:  # noqa: BLE001 - Meta validation boundary
        decision = MetaDecision(
            accepted=False,
            decision="rejected",
            reason=f"Meta response is not a valid rule JSON: {type(error).__name__}: {error}",
            created_at=utc_now(),
        )
    else:
        decision = validate_meta_response(
            meta,
            allowed_source_ids=set(provenance["allowed_source_ids"]),
            max_rules=1,
            max_chars=600,
            forbidden_tokens=("emotion_state_trait", "flash_emotion_20261021", "state-vs-trait question"),
        )
    atomic_write_json(target / "meta_decision.json", decision.model_dump(mode="json"))
    if decision.accepted and decision.rule_text:
        atomic_write_text(target / "meta_rule.md", decision.rule_text)
    atomic_write_text(
        target / "META_REVIEW.md",
        "# Controlled Meta decision\n\n"
        f"- decision: `{decision.decision}`\n"
        f"- accepted: `{decision.accepted}`\n"
        f"- reason: {decision.reason}\n\n"
        "The Meta model did not receive the new question, new materials, new answers, or scores.\n",
    )
    return decision.model_dump(mode="json")
