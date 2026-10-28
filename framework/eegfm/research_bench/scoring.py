"""Auditable, bounded directional claim-graph scoring (fire_inspired_v1).

The caller supplies semantic judgments. Scope, numbers, negation and causality
are never inferred by string matching here. Evidence integrity is a separate
report, never a hidden multiplier on reference agreement.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from .claims import deduplicate_claims
from .schema import AtomicClaim, ClaimMatch, EvaluationReport, MAX_MATCHES, POLICY_VERSION, RELATIONS, SCHEMA_VERSION, ValidationError


def score_directional(
    agent_claims: Iterable[AtomicClaim | Mapping[str, Any]],
    reference_claims: Iterable[AtomicClaim | Mapping[str, Any]],
    matches: Iterable[ClaimMatch | Mapping[str, Any]],
    *, task_id: str | None = None, run_id: str | None = None,
) -> dict[str, Any]:
    """Return JSON-ready counts, scores, graph, provenance and review items.

    Precision counts distinct supported agent claims; recall independently
    counts distinct covered reference claims. Arbitrarily many edges never
    increase either numerator past its denominator. Multiple differing labels
    on the same canonical pair/direction become needs_review and earn no credit.
    Missing directional judgments earn no credit and are explicitly listed.
    Empty gold has null scores and is excluded from means; an empty submission
    against valid gold has zero scores and remains included.

    Unknown IDs and malformed judgments raise ValidationError; they cannot
    silently become nonmatches. All judgments in one report must name the same
    frozen judge version. No default bidirectional or exact-string match exists.
    """
    agents = deduplicate_claims(agent_claims)
    references = deduplicate_claims(reference_claims)
    graph: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[ClaimMatch]] = defaultdict(list)
    judge_versions: set[str] = set()
    for index, value in enumerate(matches):
        if index >= MAX_MATCHES:
            raise ValidationError(f"match count exceeds {MAX_MATCHES}")
        match = ClaimMatch.from_dict(value.to_dict() if isinstance(value, ClaimMatch) else value)
        if match.agent_claim_id not in agents.aliases or match.reference_claim_id not in references.aliases:
            raise ValidationError("match references an unknown claim ID")
        judge_versions.add(match.judge_version)
        if len(judge_versions) > 1:
            raise ValidationError("mixed judge versions require a separate evaluation report")
        agent_id = agents.aliases[match.agent_claim_id]
        reference_id = references.aliases[match.reference_claim_id]
        graph.append({**match.to_dict(), "canonical_agent_claim_id": agent_id, "canonical_reference_claim_id": reference_id})
        grouped[(agent_id, reference_id, match.direction)].append(match)

    supported_agents: set[str] = set()
    covered_references: set[str] = set()
    judged_agents: set[str] = set()
    judged_references: set[str] = set()
    reviews: list[dict[str, Any]] = []
    relation_counts = {direction: {relation: 0 for relation in sorted(RELATIONS)}
                       for direction in ("reference_supports_agent", "agent_covers_reference")}
    resolved_edges: list[dict[str, Any]] = []
    for (agent_id, reference_id, direction), judgments in sorted(grouped.items()):
        relations = {match.relation for match in judgments}
        relation = next(iter(relations)) if len(relations) == 1 else "needs_review"
        edge = {"agent_claim_id": agent_id, "reference_claim_id": reference_id,
                "direction": direction, "relation": relation}
        resolved_edges.append(edge)
        relation_counts[direction][relation] += 1
        if direction == "reference_supports_agent":
            judged_agents.add(agent_id)
            if relation == "supported":
                supported_agents.add(agent_id)
        else:
            judged_references.add(reference_id)
            if relation == "supported":
                covered_references.add(reference_id)
        if relation == "needs_review":
            reviews.append({**edge, "reason": "conflicting_judgments" if len(relations) > 1 else "judge_needs_review"})
    for claim in agents.claims:
        if claim.claim_id not in judged_agents and references.claims:
            reviews.append({"claim_id": claim.claim_id, "direction": "reference_supports_agent", "reason": "missing_directional_judgment"})
    for claim in references.claims:
        if claim.claim_id not in judged_references and agents.claims:
            reviews.append({"claim_id": claim.claim_id, "direction": "agent_covers_reference", "reason": "missing_directional_judgment"})

    n_agent, n_reference = len(agents.claims), len(references.claims)
    if not n_reference:
        status, precision, recall, f1 = "invalid_reference", None, None, None
    elif not n_agent:
        status, precision, recall, f1 = "empty_submission", 0.0, 0.0, 0.0
    else:
        status = "needs_review" if reviews else "scored"
        precision = len(supported_agents) / n_agent
        recall = len(covered_references) / n_reference
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    report = EvaluationReport(
        task_id=task_id, run_id=run_id, version=POLICY_VERSION, status=status,
        eligible_for_mean=bool(n_reference),
        claims={"agent": agents.to_dict(), "reference": references.to_dict()},
        matches=graph,
        counts={"agent_claims": n_agent, "reference_claims": n_reference,
                "agent_claims_raw": len(agents.aliases), "reference_claims_raw": len(references.aliases),
                "supported_agent_claims": len(supported_agents), "covered_reference_claims": len(covered_references),
                "match_records": len(graph), "directional_edges": len(grouped), "relations": relation_counts},
        scores={"precision": precision, "recall": recall, "f1": f1},
        evidence_audit=None, review_items=reviews,
        limitations=["Local fire_inspired_v1 policy; not a claim of official FIRE score compatibility.",
                     "External semantic judgments and source-span accuracy are not validated by arithmetic.",
                     "Unjudged and needs_review edges earn no credit; scores with review items are conservative provisional values.",
                     "not_supported means unsupported by the supplied reference, not scientific falsity.",
                     "Evidence validity is separate and must be audited against a trusted launcher ledger.",
                     "Supported alternative findings require separate evidence and human/scientific review; gold is not revised here."],
        schema_version=SCHEMA_VERSION, judge_versions=sorted(judge_versions), resolved_edges=resolved_edges,
        supported_agent_claim_ids=sorted(supported_agents), covered_reference_claim_ids=sorted(covered_references),
    ).to_dict()
    return report
