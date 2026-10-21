"""Explicit data structures for the overnight EEG-style study.

Internal arrays use dataclasses with numpy types.  JSON crossing an I/O or
model boundary uses Pydantic models with ``extra="forbid"``.  No core model
uses ``Any``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SplitLevel = Literal["window", "trial", "subject"]
Family = Literal["T", "G", "D", "N"]
Direction = Literal["positive", "negative", "near_zero"]
BackendKind = Literal["real_llm", "scripted", "mock"]
ProviderStatus = Literal["ok", "timeout", "http_error", "unavailable", "unknown_completion"]
ScoringStatus = Literal["numeric", "not_applicable"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


@dataclass(frozen=True)
class FeatureDataset:
    """One synthetic EEG-style table.  Labels are constant within a trial."""

    x: NDArray[np.float64]
    y: NDArray[np.int64]
    sample_ids: list[str]
    subject_ids: list[str]
    session_uids: list[str]
    trial_uids: list[str]
    feature_names: list[str]
    case_id: str
    data_source_type: Literal["synthetic_features"] = "synthetic_features"

    def __post_init__(self) -> None:
        n = len(self.sample_ids)
        if self.x.ndim != 2:
            raise ValueError("x must be 2-D")
        if self.x.shape[0] != n or len(self.y) != n:
            raise ValueError("array lengths do not match sample_ids")
        if self.x.shape[1] != len(self.feature_names):
            raise ValueError("feature count does not match feature_names")
        if not (
            len(self.subject_ids) == len(self.session_uids) == len(self.trial_uids) == n
        ):
            raise ValueError("all metadata columns must match sample count")
        if len(set(self.sample_ids)) != n:
            raise ValueError("duplicate sample_id")
        if not np.isfinite(self.x).all():
            raise ValueError("x contains non-finite values")
        if not np.isin(self.y, np.array([-1, 1])).all():
            raise ValueError("labels must be -1 or +1")
        first_label: dict[str, int] = {}
        for uid, label in zip(self.trial_uids, self.y.tolist(), strict=True):
            previous = first_label.setdefault(uid, int(label))
            if previous != int(label):
                raise ValueError(f"label is not constant within trial {uid}")


@dataclass(frozen=True)
class SplitIndices:
    train_indices: NDArray[np.int64]
    test_indices: NDArray[np.int64]
    split_level: SplitLevel
    split_seed: int

    def __post_init__(self) -> None:
        if self.train_indices.ndim != 1 or self.test_indices.ndim != 1:
            raise ValueError("split indices must be 1-D")
        if len(np.intersect1d(self.train_indices, self.test_indices)) != 0:
            raise ValueError("train/test sample overlap")
        if len(self.train_indices) == 0 or len(self.test_indices) == 0:
            raise ValueError("empty split")


@dataclass(frozen=True)
class BaselineBundle:
    metrics: dict[str, float]
    audits: dict[str, dict[str, object]]
    data_hash: str
    config_hash: str


@dataclass(frozen=True)
class ExperimentContext:
    splits: dict[str, SplitIndices]
    random_label_seeds: list[int]
    tool_version: str
    timeout_seconds: int
    data_hash: str
    classifier_config: dict[str, object] = field(
        default_factory=lambda: {"scaler": "StandardScaler", "classifier": "KNeighborsClassifier", "n_neighbors": 1}
    )
    seed: int = 0


class CaseSpec(StrictModel):
    case_id: str = Field(min_length=1)
    family: Family
    data_seed: int
    split_seed: int
    label_seed: int
    model_seed: int
    generator_version: str = "1.0"
    params: dict[str, float] = Field(default_factory=dict)
    n_subjects: int = 16
    n_sessions: int = 2
    n_trials: int = 16
    n_windows: int = 8
    n_features: int = 32


class PublicCase(StrictModel):
    case_id: str
    data_source_type: Literal["synthetic_features"]
    structure_summary: dict[str, int]
    baseline: dict[str, float]
    audit_summary: dict[str, object]
    allowed_tools: list[str]
    data_hash: str


class Hypothesis(StrictModel):
    id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    mechanism: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    limitations: str = ""


class ConditionalPrediction(StrictModel):
    hypothesis_id: str
    direction: Direction
    rationale: str = ""


class Prediction(StrictModel):
    scoring_status: ScoringStatus
    metric_key: str | None = None
    primary_direction: Direction | None = None
    threshold: float = 0.05
    check_facts: list[str] = Field(default_factory=list)
    conditional_predictions: list[ConditionalPrediction] = Field(default_factory=list)
    update_rule_if_opposite: str = ""

    @field_validator("threshold")
    @classmethod
    def _threshold_positive(cls, value: float) -> float:
        if not np.isfinite(value) or value <= 0:
            raise ValueError("threshold must be finite and positive")
        return value

    @model_validator(mode="after")
    def _status_fields(self) -> "Prediction":
        if self.scoring_status == "numeric":
            if not self.metric_key or self.primary_direction is None:
                raise ValueError("numeric prediction needs metric_key and primary_direction")
        else:
            if not self.check_facts:
                raise ValueError("not_applicable prediction needs check_facts")
            if self.metric_key is not None or self.primary_direction is not None:
                raise ValueError("not_applicable prediction must not set metric fields")
        return self


class ExperimentRequest(StrictModel):
    request_id: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    distinguishes: list[str] = Field(min_length=2)
    prediction: Prediction


class StopDecision(StrictModel):
    reason: str = Field(min_length=1)
    final_judgment: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    remaining_uncertainty: str = ""


class Decision(StrictModel):
    decision_type: Literal["action", "stop"]
    hypotheses: list[Hypothesis] = Field(min_length=2, max_length=3)
    action: ExperimentRequest | None = None
    stop: StopDecision | None = None
    reasoning_summary: str = ""

    @model_validator(mode="after")
    def _exactly_one(self) -> "Decision":
        if self.decision_type == "action" and (self.action is None or self.stop is not None):
            raise ValueError("action decision must have action and no stop")
        if self.decision_type == "stop" and (self.stop is None or self.action is not None):
            raise ValueError("stop decision must have stop and no action")
        return self


class ExperimentResult(StrictModel):
    request_id: str
    tool_id: str
    valid: bool
    invalid_reason: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    randomization: dict[str, object] = Field(default_factory=dict)
    audit: dict[str, dict[str, object]] = Field(default_factory=dict)
    data_hash: str
    config_hash: str
    elapsed_seconds: float
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("metrics")
    @classmethod
    def _finite_metrics(cls, value: dict[str, float]) -> dict[str, float]:
        for key, number in value.items():
            if not np.isfinite(float(number)):
                raise ValueError(f"metric {key} is not finite")
        return value


class ModelRequest(StrictModel):
    request_id: str
    stage: str
    messages: list[dict[str, str]]
    model_settings: dict[str, object]
    rule_hash: str
    public_input_hash: str
    created_at: str


class ProviderResponse(StrictModel):
    status: ProviderStatus
    visible_text: str = ""
    model_id: str = ""
    usage: dict[str, int | float] = Field(default_factory=dict)
    latency_ms: float = 0.0
    raw_response: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class SealedRequest(StrictModel):
    request: ExperimentRequest
    canonical_json: str
    sha256: str
    sealed_at: str
    event_sequence: int
    run_dir: str


class RunEvent(StrictModel):
    sequence: int
    event_type: str
    timestamp: str
    payload: dict[str, object]
    prev_hash: str
    event_hash: str


class EpisodeState(StrictModel):
    episode_id: str
    case_id: str
    rule_version: str
    phase: str
    actions_used: int = 0
    calls_used: int = 0
    attempts_used: int = 0
    tokens_used: int = 0
    last_event_sequence: int = 0
    stop_reason: str = ""
    backend: BackendKind = "real_llm"
    provider: str = ""
    model: str = ""
    started_at: str = ""
    updated_at: str = ""


class StudyState(StrictModel):
    study_id: str
    phase: str
    deadline: str
    freeze_manifest_hash: str = ""
    pairs: dict[str, dict[str, object]] = Field(default_factory=dict)
    current: str = ""
    attempts_used: int = 0
    tokens_used: int = 0
    stopped_reason: str = ""
    created_at: str = ""
    updated_at: str = ""


class ResearchRule(StrictModel):
    trigger: str = Field(min_length=1)
    action: str = Field(min_length=1)
    boundary: str = Field(min_length=1)
    evidence_event_ids: list[str] = Field(min_length=1)
    author: str = "developer_assisted_dsh"


class MetaResponse(StrictModel):
    update: Literal["rules", "no_update"]
    rules: list[ResearchRule] = Field(default_factory=list)
    reasoning_summary: str = ""

    @model_validator(mode="after")
    def _rules_shape(self) -> "MetaResponse":
        if self.update == "no_update" and self.rules:
            raise ValueError("no_update must not include rules")
        if len(self.rules) > 3:
            raise ValueError("at most 3 rules")
        total = sum(len(r.trigger) + len(r.action) + len(r.boundary) for r in self.rules)
        if total > 600:
            raise ValueError("rules exceed 600 characters")
        return self


class EpisodeConfig(StrictModel):
    episode_id: str
    case_id: str
    case_specs_path: str
    rule_path: str
    provider: dict[str, object]
    backend: BackendKind = "real_llm"
    model: str = ""
    max_actions: int = 3
    max_calls: int = 4
    max_attempts: int = 12
    deadline: str
    run_dir: str
    shared_facts_path: str | None = None


class StudyConfig(StrictModel):
    study_id: str
    deadline: str
    report_reserve_minutes: int = 60
    case_specs_path: str
    dev_case_ids: list[str]
    holdout_case_ids: list[str]
    provider: dict[str, object]
    max_attempts: int = 96
    max_tokens: int = 1_000_000
    max_actions_per_episode: int = 3
    max_calls_per_episode: int = 4
    max_retries: int = 2
    request_timeout_seconds: int = 120
    max_experiment_seconds: int = 300
    max_threads: int = 4
    arm_order_seed: int = 20261019
    freeze_manifest_path: str = "FREEZE_MANIFEST.json"
    run_root: str = "runs"
    reports_dir: str = "reports"


class EpisodeSummary(StrictModel):
    episode_id: str
    case_id: str
    status: str
    backend: BackendKind
    model: str
    actions_used: int
    calls_used: int
    attempts_used: int
    tokens_used: int
    predictions_total: int = 0
    predictions_hit: int = 0
    stop_reason: str = ""
    run_dir: str


class StudySummary(StrictModel):
    study_id: str
    phase: str
    pairs_completed: int
    pairs_total: int
    stopped_reason: str
    study_dir: str


class ReportPaths(StrictModel):
    morning_report: str
    results_table: str
    failure_cases: str
    walkthrough: str
    review_bundle: str
