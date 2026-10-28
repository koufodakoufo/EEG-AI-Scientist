"""Versioned, validated JSON contracts independent of legacy framework imports.

Source spans use ``{'source': str, 'start': int, 'end': int}`` with half-open
Unicode character offsets. Scope is a JSON object describing model/data/conditions.
Validation establishes structure, never truth, atomicity, or semantic support.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, fields
from typing import Any, ClassVar, Mapping, TypeVar

SCHEMA_VERSION = "research_bench_v1"
POLICY_VERSION = "fire_inspired_v1"
MAX_CLAIM_CHARS = 16000
MAX_CLAIMS = 500
MAX_MATCHES = 20000
MAX_OUTPUT_CHARS = 1000000
DIRECTIONS = frozenset({"reference_supports_agent", "agent_covers_reference"})
RELATIONS = frozenset({"supported", "contradicted", "not_supported", "needs_review"})
T = TypeVar("T", bound="JsonRecord")


class ValidationError(ValueError):
    """An input violates the frozen structural contract."""


def require_text(value: Any, field: str, *, limit: int = 1000) -> str:
    """Validate nonempty inert text without rewriting it."""
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f"{field} must be nonempty text of at most {limit} characters")
    if "\x00" in value:
        raise ValidationError(f"{field} contains a NUL character")
    return value


def validate_json(value: Any, field: str, depth: int = 0) -> None:
    """Require finite JSON data; no arbitrary Python objects or executable hooks."""
    if depth > 20:
        raise ValidationError(f"{field} exceeds JSON nesting limit")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            validate_json(item, field, depth + 1)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            validate_json(item, field, depth + 1)
        return
    raise ValidationError(f"{field} must contain only finite JSON data")


def validate_span(span: Any) -> None:
    if not isinstance(span, dict) or set(span) != {"source", "start", "end"}:
        raise ValidationError("source_span requires exactly source, start, end")
    require_text(span["source"], "source_span.source")
    start, end = span["start"], span["end"]
    if type(start) is not int or type(end) is not int or not 0 <= start < end:
        raise ValidationError("source_span requires integer offsets 0 <= start < end")


class JsonRecord:
    """Strict dictionary conversion; unknown/missing fields are errors."""

    schema_version: ClassVar[str] = SCHEMA_VERSION

    @classmethod
    def from_dict(cls: type[T], value: Mapping[str, Any]) -> T:
        if not isinstance(value, dict):
            raise ValidationError(f"{cls.__name__} must be a JSON object")
        names = {field.name for field in fields(cls)}  # type: ignore[arg-type]
        if set(value) != names:
            raise ValidationError(f"{cls.__name__} fields mismatch: missing={sorted(names - set(value))}, unknown={sorted(set(value) - names)}")
        try:
            return cls(**value)  # type: ignore[call-arg]
        except (TypeError, RecursionError) as error:
            raise ValidationError(f"invalid {cls.__name__}: {error}") from error

    def to_dict(self) -> dict[str, Any]:
        # JSON round-trip produces lists rather than tuples and copies nested data.
        return json.loads(json.dumps(asdict(self), allow_nan=False))  # type: ignore[arg-type,no-any-return]


@dataclass(frozen=True)
class AtomicClaim(JsonRecord):
    claim_id: str
    text: str
    scope: dict[str, Any]
    polarity: str
    source_span: dict[str, Any]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.claim_id, "claim_id", limit=200)
        require_text(self.text, "text", limit=MAX_CLAIM_CHARS)
        if not isinstance(self.scope, dict):
            raise ValidationError("scope must be a JSON object")
        validate_json(self.scope, "scope")
        if self.polarity not in {"positive", "negative", "uncertain", "neutral"}:
            raise ValidationError("polarity must be positive, negative, uncertain, or neutral")
        validate_span(self.source_span)
        if not isinstance(self.evidence_ids, (tuple, list)):
            raise ValidationError("evidence_ids must be a list of identifiers")
        for evidence_id in self.evidence_ids:
            require_text(evidence_id, "evidence_id", limit=200)
        object.__setattr__(self, "evidence_ids", tuple(dict.fromkeys(self.evidence_ids)))
        # Do not retain caller-owned mutable dictionaries.
        object.__setattr__(self, "scope", json.loads(json.dumps(self.scope, allow_nan=False)))
        object.__setattr__(self, "source_span", dict(self.source_span))


@dataclass(frozen=True)
class ClaimMatch(JsonRecord):
    agent_claim_id: str
    reference_claim_id: str
    direction: str
    relation: str
    reason: str
    judge_version: str

    def __post_init__(self) -> None:
        for field in ("agent_claim_id", "reference_claim_id", "judge_version"):
            require_text(getattr(self, field), field, limit=200)
        if self.direction not in DIRECTIONS:
            raise ValidationError("unknown match direction")
        if self.relation not in RELATIONS:
            raise ValidationError("unknown match relation")
        require_text(self.reason, "reason", limit=4000)


@dataclass(frozen=True)
class EvidenceRecord(JsonRecord):
    evidence_id: str
    run_id: str
    artifact_path: str
    sha256: str
    command_id: str
    status: str
    data_split: str

    def __post_init__(self) -> None:
        for field in ("evidence_id", "run_id", "command_id", "data_split", "status"):
            require_text(getattr(self, field), field, limit=200)
        require_text(self.artifact_path, "artifact_path", limit=2000)
        if not isinstance(self.sha256, str) or re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValidationError("sha256 must be a lowercase 64-digit hexadecimal digest")


@dataclass(frozen=True)
class EvaluationReport(JsonRecord):
    task_id: str | None
    run_id: str | None
    version: str
    status: str
    eligible_for_mean: bool
    claims: dict[str, Any]
    matches: list[dict[str, Any]]
    counts: dict[str, Any]
    scores: dict[str, Any]
    evidence_audit: dict[str, Any] | None
    review_items: list[dict[str, Any]]
    limitations: list[str]
    schema_version: str = SCHEMA_VERSION
    judge_versions: list[str] = field(default_factory=list)
    resolved_edges: list[dict[str, Any]] = field(default_factory=list)
    supported_agent_claim_ids: list[str] = field(default_factory=list)
    covered_reference_claim_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field in ("task_id", "run_id"):
            if getattr(self, field) is not None:
                require_text(getattr(self, field), field, limit=200)
        if self.version != POLICY_VERSION:
            raise ValidationError("unsupported scoring policy version")
        if self.schema_version != SCHEMA_VERSION:
            raise ValidationError("unsupported report schema_version")
        if self.status not in {"scored", "needs_review", "empty_submission", "invalid_reference"}:
            raise ValidationError("unknown evaluation status")
        if type(self.eligible_for_mean) is not bool:
            raise ValidationError("eligible_for_mean must be boolean")
        for field in ("claims", "counts", "scores"):
            if not isinstance(getattr(self, field), dict):
                raise ValidationError(f"{field} must be a JSON object")
        for field in ("matches", "review_items", "limitations", "judge_versions", "resolved_edges",
                      "supported_agent_claim_ids", "covered_reference_claim_ids"):
            if not isinstance(getattr(self, field), list):
                raise ValidationError(f"{field} must be a list")
        if set(self.scores) != {"precision", "recall", "f1"}:
            raise ValidationError("scores require precision, recall and f1")
        if self.status == "invalid_reference":
            if self.eligible_for_mean or any(value is not None for value in self.scores.values()):
                raise ValidationError("invalid_reference requires null scores and exclusion from means")
        elif not self.eligible_for_mean:
            raise ValidationError("valid references must remain included in means")
        else:
            for value in self.scores.values():
                if type(value) not in (float, int) or not 0 <= value <= 1:
                    raise ValidationError("scores must be bounded finite numbers in [0, 1]")
            if self.status == "empty_submission" and any(self.scores.values()):
                raise ValidationError("empty_submission requires zero scores")
        validate_json(asdict(self), "EvaluationReport")
