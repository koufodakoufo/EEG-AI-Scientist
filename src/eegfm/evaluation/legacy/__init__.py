"""Offline, standard-library benchmark contracts; no model or tool execution.

Semantic judgments must be supplied by an independently versioned evaluator.
``fire_inspired_v1`` is a local policy, not a reproduction of FIRE's scores.
"""

from eegfm.evaluation.legacy.schema import AtomicClaim
from eegfm.evaluation.legacy.schema import ClaimMatch
from eegfm.evaluation.legacy.schema import EvaluationReport
from eegfm.evaluation.legacy.schema import EvidenceRecord
from eegfm.evaluation.legacy.schema import ValidationError

__all__ = ["AtomicClaim", "ClaimMatch", "EvidenceRecord", "EvaluationReport", "ValidationError"]
