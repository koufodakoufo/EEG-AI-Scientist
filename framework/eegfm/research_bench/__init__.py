"""Offline, standard-library benchmark contracts; no model or tool execution.

Semantic judgments must be supplied by an independently versioned evaluator.
``fire_inspired_v1`` is a local policy, not a reproduction of FIRE's scores.
"""

from .schema import AtomicClaim, ClaimMatch, EvaluationReport, EvidenceRecord, ValidationError

__all__ = ["AtomicClaim", "ClaimMatch", "EvidenceRecord", "EvaluationReport", "ValidationError"]
