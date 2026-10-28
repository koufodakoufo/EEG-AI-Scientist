from __future__ import annotations

import json
from pathlib import Path

import pytest

from eeg_scientist.cases import build_public_case, generate_case
from eeg_scientist.experiments import compute_baselines
from eeg_scientist.provider import provider_from_config
from eeg_scientist.schema import CaseSpec, StudyState
from eeg_scientist.scientist import (
    DecisionParseError,
    build_meta_request,
    build_request,
    build_s1_text,
    parse_decision,
    parse_meta,
)
from eeg_scientist.splits import build_all_splits
from eeg_scientist.storage import redact, sha256_text
from eeg_scientist.study import check_freeze, freeze_hash


def _public_case() -> object:
    spec = CaseSpec(
        case_id="case_x",
        family="T",
        data_seed=1101,
        split_seed=2101,
        label_seed=3101,
        model_seed=4101,
    )
    dataset = generate_case(spec)
    return build_public_case(dataset, compute_baselines(dataset, build_all_splits(dataset, spec.split_seed)))


def _flat_action(tool: str = "trial_random_labels") -> dict[str, object]:
    return {
        "decision_type": "action",
        "hypotheses": [
            {"id": "H1", "claim": "a", "mechanism": "b", "supporting_evidence_ids": ["obs_1"], "limitations": "c"},
            {"id": "H2", "claim": "d", "mechanism": "e", "supporting_evidence_ids": ["obs_1"], "limitations": "f"},
        ],
        "request_id": "req_1",
        "tool_id": tool,
        "parameters": {},
        "distinguishes": ["H1", "H2"],
        "prediction": {
            "scoring_status": "numeric",
            "metric_key": "trial_random_gap_mean",
            "primary_direction": "positive",
            "threshold": 0.05,
            "check_facts": [],
            "conditional_predictions": [],
            "update_rule_if_opposite": None,
        },
        "reasoning_summary": "test",
    }


def test_flat_and_nested_decisions_parse() -> None:
    flat = parse_decision(json.dumps(_flat_action()))
    assert flat.action is not None and flat.action.tool_id == "trial_random_labels"
    nested = _flat_action()
    action = {key: nested.pop(key) for key in ("request_id", "tool_id", "parameters", "distinguishes", "prediction")}
    nested["action"] = action
    nested["stop"] = None
    parsed = parse_decision(json.dumps(nested))
    assert parsed.action is not None


def test_unknown_tool_rejected() -> None:
    with pytest.raises(DecisionParseError):
        parse_decision(json.dumps(_flat_action("no_such_tool")))


def test_public_prompt_excludes_private_fields() -> None:
    case = _public_case()
    request = build_request(case, "S0 rules", history=[], development_facts=None, stage="initial")
    user = request.messages[1]["content"]
    for forbidden in ("family", "data_seed", "split_seed", "label_seed", "trial_scale", "noise_std"):
        assert forbidden not in user
    assert "synthetic_features" in user


def test_s0_s1_share_same_public_facts_and_tools() -> None:
    case = _public_case()
    facts = {"development_cases": [{"case_id": "case_001"}], "trajectories": []}
    s0 = build_request(case, "S0", history=[], development_facts=facts, stage="initial")
    s1 = build_request(case, "S1", history=[], development_facts=facts, stage="initial")
    assert s0.public_input_hash == s1.public_input_hash
    assert s0.messages[1] == s1.messages[1]
    assert s0.rule_hash != s1.rule_hash
    assert s0.model_settings == s1.model_settings


def test_no_cross_case_memory_in_prompt() -> None:
    case = _public_case()
    request = build_request(case, "S0", history=[], development_facts=None, stage="initial")
    assert "case_999" not in request.messages[1]["content"]


def test_meta_rejects_holdout_or_family_tokens() -> None:
    text = json.dumps(
        {
            "update": "rules",
            "rules": [
                {
                    "trigger": "when case_003 is seen",
                    "action": "use split_audit",
                    "boundary": "holdout",
                    "evidence_event_ids": ["dev-case_001-action-1"],
                }
            ],
            "reasoning_summary": "x",
        }
    )
    with pytest.raises(DecisionParseError):
        parse_meta(text, {"dev-case_001-action-1"})


def test_meta_no_update_and_s1_text() -> None:
    meta = parse_meta(
        json.dumps({"update": "no_update", "rules": [], "reasoning_summary": "nothing justified"}),
        {"dev-case_001-action-1"},
    )
    text = build_s1_text("S0 rules", meta)
    assert "No method update" in text
    assert "S0 rules" in text


def test_meta_request_uses_only_supplied_facts() -> None:
    facts = {"development_cases": [{"case_id": "case_001"}], "trajectories": []}
    request = build_meta_request(facts, "S0", ["dev-case_001-action-1"])
    user = request.messages[1]["content"]
    assert "case_001" in user
    assert "case_003" not in user


def test_freeze_edit_is_rejected() -> None:
    state = StudyState(study_id="s", phase="frozen", deadline="x", freeze_manifest_hash="")
    manifest = {"a": 1}
    state.freeze_manifest_hash = freeze_hash(manifest)
    assert check_freeze(state, manifest) == freeze_hash(manifest)
    with pytest.raises(RuntimeError):
        check_freeze(state, {"a": 2})


def test_secret_redaction() -> None:
    assert redact("hello SECRET world", ["SECRET"]) == "hello [REDACTED] world"


def test_provider_config_returns_local_provider() -> None:
    provider = provider_from_config({"kind": "ollama_native", "model": "qwen3.5:9b"})
    assert provider.provider_name == "ollama_local"
    assert provider.model_name == "qwen3.5:9b"
