"""Parse externally extracted claims, preserving raw output and provenance.

No text-to-claim heuristics or model calls are provided. The same frozen external
extraction protocol must be used for both sides. A format repair, if needed, is
performed externally at most once and both strings remain in the return value.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from .schema import AtomicClaim, MAX_CLAIMS, MAX_OUTPUT_CHARS, SCHEMA_VERSION, ValidationError


def validate_claims(claims: Iterable[AtomicClaim | Mapping[str, Any]]) -> list[AtomicClaim]:
    """Validate IDs and bounds, including dataclasses potentially mutated upstream."""
    result: list[AtomicClaim] = []
    seen: set[str] = set()
    for value in claims:
        claim = AtomicClaim.from_dict(value.to_dict() if isinstance(value, AtomicClaim) else value)
        if claim.claim_id in seen:
            raise ValidationError(f"duplicate claim_id: {claim.claim_id}")
        seen.add(claim.claim_id)
        result.append(claim)
        if len(result) > MAX_CLAIMS:
            raise ValidationError(f"claim count exceeds {MAX_CLAIMS}")
    return result


def extract_structured_claims(payload: Any) -> list[AtomicClaim]:
    """Read a claim list or strict {'schema_version': ..., 'claims': [...]} object.

    This extracts already structured claims; it does not infer claims from prose.
    Source spans are structurally checked, but require original-source review.
    """
    if isinstance(payload, dict):
        if set(payload) != {"schema_version", "claims"} or payload["schema_version"] != SCHEMA_VERSION:
            raise ValidationError("claim envelope requires matching schema_version and claims only")
        payload = payload["claims"]
    if not isinstance(payload, list):
        raise ValidationError("claims must be a JSON list")
    return validate_claims(payload)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValidationError(f"nonfinite JSON constant: {value}")


def parse_claim_output(raw_output: str, *, repair_output: str | None = None) -> dict[str, Any]:
    """Parse strict JSON once, optionally one externally obtained repair.

    Returns raw_output, repair_output, repair_attempts, status, errors and claims.
    Never executes fenced text, retries a model, or changes the original string.
    A repair after a valid original is rejected. Invalid/oversize outputs remain
    available verbatim in this diagnostic result; callers control retention.
    """
    if not isinstance(raw_output, str) or (repair_output is not None and not isinstance(repair_output, str)):
        raise ValidationError("raw_output and repair_output must be strings")
    result: dict[str, Any] = {"raw_output": raw_output, "repair_output": repair_output,
                            "repair_attempts": 0, "status": "invalid_output", "errors": [], "claims": []}
    candidates = [raw_output] + ([repair_output] if repair_output is not None else [])
    for index, candidate in enumerate(candidates):
        result["repair_attempts"] = index
        try:
            if len(candidate) > MAX_OUTPUT_CHARS:
                raise ValidationError(f"output exceeds {MAX_OUTPUT_CHARS} characters")
            parsed = json.loads(candidate, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            claims = extract_structured_claims(parsed)
        except (ValueError, TypeError, RecursionError) as error:
            result["errors"].append({"attempt": index, "message": str(error)})
            continue
        if index == 0 and repair_output is not None:
            raise ValidationError("repair_output supplied although original output is valid")
        result.update(status="parsed" if index == 0 else "repaired", claims=[claim.to_dict() for claim in claims])
        break
    return result


@dataclass(frozen=True)
class DeduplicationResult:
    """Canonical claims plus all original identifiers and source locations."""

    claims: tuple[AtomicClaim, ...]
    aliases: dict[str, str]
    source_spans: dict[str, list[dict[str, Any]]]

    def to_dict(self) -> dict[str, Any]:
        return {"claims": [claim.to_dict() for claim in self.claims],
                "aliases": dict(self.aliases), "source_spans": self.source_spans}


def deduplicate_claims(claims: Iterable[AtomicClaim | Mapping[str, Any]]) -> DeduplicationResult:
    """Merge exact text only within identical scope and polarity.

    No case folding, whitespace normalization, numerical tolerance, or semantic
    merging is attempted. Different scope/polarity remain distinct. Evidence IDs
    are unioned, and every original ID/span remains visible in the audit trail.
    """
    canonical: dict[tuple[str, str, str], AtomicClaim] = {}
    aliases: dict[str, str] = {}
    spans: dict[str, list[dict[str, Any]]] = {}
    for claim in validate_claims(claims):
        key = (claim.text, json.dumps(claim.scope, sort_keys=True, ensure_ascii=False), claim.polarity)
        if key not in canonical:
            canonical[key] = claim
            spans[claim.claim_id] = []
        original = canonical[key]
        canonical[key] = replace(original, evidence_ids=tuple(dict.fromkeys(original.evidence_ids + claim.evidence_ids)))
        aliases[claim.claim_id] = original.claim_id
        spans[original.claim_id].append({"claim_id": claim.claim_id, **claim.source_span})
    return DeduplicationResult(tuple(canonical.values()), aliases, spans)
