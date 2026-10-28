"""Typed study, proposal, and review records for the unified entry point."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from .backends import BackendRegistry, require_verified
from .schema import StrictModel

STUDY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,80}$")
PROPOSAL_ID_RE = re.compile(r"^p_[0-9a-f]{16}$")


class StudyBudget(StrictModel):
    cap_cny: float = 20.0
    wrap_up_reserve_cny: float = 2.0
    model_attempts_cap: int = 120
    search_attempts_cap: int = 60
    fetch_attempts_cap: int = 90
    input_tokens_cap: int = 2_000_000
    output_tokens_cap: int = 500_000


class StudyLimits(StrictModel):
    max_model_calls: int = 12
    max_tool_calls: int = 14
    max_turns: int = 3
    max_model_calls_per_turn: int = 8
    max_tool_calls_per_turn: int = 8
    max_output_tokens: int = 12000
    max_output_tokens_retry: int = 24000
    context_char_target: int = 120000


class StudyArm(StrictModel):
    name: str
    backend: str
    repeats: int = 2
    rule_path: str | None = None

    @field_validator("name")
    @classmethod
    def safe_name(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,40}", value):
            raise ValueError("arm name must be lowercase letters/digits/_-")
        return value


class StudySpec(StrictModel):
    schema_version: str = "1"
    study_id: str
    title: str
    question: str
    task_path: str = "task.md"
    material_manifest_path: str
    material_evidence_dir: str
    material_version: str = ""
    system_prompt_path: str
    deliverables: list[str] = Field(default_factory=list)
    deadline: str = ""
    tool_backend: str = "deepseek_search_fetch"
    arms: list[StudyArm] = Field(default_factory=list)
    budget: StudyBudget = Field(default_factory=StudyBudget)
    limits: StudyLimits = Field(default_factory=StudyLimits)
    archived: bool = False

    @field_validator("study_id")
    @classmethod
    def safe_id(cls, value: str) -> str:
        if not STUDY_ID_RE.fullmatch(value):
            raise ValueError("study_id must be 3-80 chars: lowercase letters/digits/_-")
        return value


class ProposalRecord(StrictModel):
    proposal_id: str
    run_id: str
    arm: str
    repeat: int
    accepted: bool
    body_path: str
    body_sha256: str
    produced_at: str = ""
    cost_cny: float | None = None
    binding_source: str = "path"

    @field_validator("proposal_id")
    @classmethod
    def valid_proposal_id(cls, value: str) -> str:
        if not PROPOSAL_ID_RE.fullmatch(value):
            raise ValueError("proposal_id must be p_<16 hex>")
        return value


ReviewSource = Literal["human", "chatgpt_manual", "model_api"]
ReviewVerdict = Literal["accept", "revise", "reject", "uncertain", "unreviewed"]


class ReviewRecord(StrictModel):
    schema_version: str = "1"
    review_id: str
    study_id: str
    packet_id: str
    display_id: str = ""
    proposal_id: str
    run_id: str
    body_sha256: str
    reviewer_id: str
    reviewer_role: str
    source_type: ReviewSource
    blind: bool
    developer_reviewer: bool = False
    submitted_at: str
    verdict: ReviewVerdict = "uncertain"
    answers: dict[str, str] = Field(default_factory=dict)
    unreviewed: list[str] = Field(default_factory=list)
    raw_path: str
    raw_sha256: str
    form_version: str = ""
    binding_source: str = ""
    converter: str = "review_import.py"
    notes: str = ""

    @field_validator("proposal_id")
    @classmethod
    def valid_proposal_id(cls, value: str) -> str:
        if not PROPOSAL_ID_RE.fullmatch(value):
            raise ValueError("proposal_id must be p_<16 hex>")
        return value


def proposal_id(body: bytes) -> str:
    return "p_" + hashlib.sha256(body).hexdigest()[:16]


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_study_spec(path: Path | str) -> StudySpec:
    return StudySpec.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_study_spec(path: Path, spec: StudySpec) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve(root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def validate_spec(spec: StudySpec, root: Path, registry: BackendRegistry | None = None) -> list[str]:
    errors: list[str] = []
    task_path = resolve(root, spec.task_path)
    for label, value in (
        ("task", spec.task_path),
        ("material manifest", spec.material_manifest_path),
        ("material evidence dir", spec.material_evidence_dir),
        ("system prompt", spec.system_prompt_path),
    ):
        if not resolve(root, value).exists():
            errors.append(f"{label} missing: {value}")
    if task_path.exists():
        try:
            if not task_path.read_text(encoding="utf-8").strip():
                errors.append(f"task file is empty: {spec.task_path}")
        except OSError as error:
            errors.append(f"task file unreadable: {spec.task_path} ({type(error).__name__})")
    elif not spec.question.strip():
        errors.append("no task text: task.md is missing and question is empty")
    manifest_path = resolve(root, spec.material_manifest_path)
    if manifest_path.exists():
        try:
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"material manifest unreadable: {spec.material_manifest_path} ({type(error).__name__})")
        else:
            materials = raw_manifest.get("materials") if isinstance(raw_manifest, dict) else None
            if not isinstance(materials, list) or not materials:
                errors.append("material manifest has no materials; add at least one registered item before running")
    if not spec.arms:
        errors.append("no arms configured")
    if len({arm.name for arm in spec.arms}) != len(spec.arms):
        errors.append("duplicate arm names")
    for arm in spec.arms:
        if arm.repeats < 1 or arm.repeats > 3:
            errors.append(f"arm {arm.name}: repeats must be 1..3")
        if arm.rule_path:
            rule_path = resolve(root, arm.rule_path)
            if not rule_path.exists():
                errors.append(f"arm {arm.name}: rule missing: {arm.rule_path}")
            else:
                try:
                    if not rule_path.read_text(encoding="utf-8").strip():
                        errors.append(f"arm {arm.name}: rule file is empty: {arm.rule_path}")
                except OSError as error:
                    errors.append(f"arm {arm.name}: rule unreadable: {arm.rule_path} ({type(error).__name__})")
    if registry is not None:
        for arm in spec.arms:
            try:
                backend = registry.chat(arm.backend)
                require_verified(backend)
                if not backend.model_name:
                    errors.append(f"arm {arm.name}: backend {arm.backend} has no model_name")
                if backend.price is None:
                    errors.append(f"arm {arm.name}: backend {arm.backend} has no configured price")
            except Exception as error:  # noqa: BLE001 - validation boundary
                errors.append(f"arm {arm.name}: {type(error).__name__}: {error}")
    return errors
