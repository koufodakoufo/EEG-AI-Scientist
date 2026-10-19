from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from eeg_scientist.cases import write_case_specs
from eeg_scientist.experiments import ExperimentError
from eeg_scientist.provider import ScriptedProvider, UnavailableProvider
from eeg_scientist.runner import resume_episode, run_episode
from eeg_scientist.schema import (
    CaseSpec,
    EpisodeConfig,
    ExperimentRequest,
    Prediction,
    ProviderResponse,
    SealedRequest,
)
from eeg_scientist.storage import (
    CorruptEventLog,
    append_event,
    has_result,
    load_result,
    read_events,
    seal_prediction,
    verify_sealed,
)


def _response(payload: object, status: str = "ok") -> ProviderResponse:
    return ProviderResponse(
        status=status,
        visible_text=json.dumps(payload) if not isinstance(payload, str) else payload,
        model_id="scripted",
        usage={"total_tokens": 10},
        latency_ms=1.0,
    )


def _action(request_id: str = "req_1", tool: str = "trial_random_labels") -> dict[str, object]:
    metric_keys = {
        "trial_random_labels": "trial_random_gap_mean",
        "trial_shuffle_within_subject": "trial_shuffle_gap_mean",
        "window_random_labels": "window_random_ba_mean",
        "metadata_only": "metadata_only_balanced_accuracy",
    }
    return {
        "decision_type": "action",
        "hypotheses": [
            {
                "id": "H1",
                "claim": "trial-specific information",
                "mechanism": "windows share a trial signature",
                "supporting_evidence_ids": ["obs_1"],
                "limitations": "not causal",
            },
            {
                "id": "H2",
                "claim": "noise",
                "mechanism": "finite-sample fluctuation",
                "supporting_evidence_ids": ["obs_1"],
                "limitations": "not exhaustive",
            },
        ],
        "request_id": request_id,
        "tool_id": tool,
        "parameters": {},
        "distinguishes": ["H1", "H2"],
        "prediction": {
            "scoring_status": "numeric",
            "metric_key": metric_keys.get(tool, "trial_random_gap_mean"),
            "primary_direction": "positive",
            "threshold": 0.05,
            "check_facts": [],
            "conditional_predictions": [],
            "update_rule_if_opposite": "revise",
        },
        "reasoning_summary": "test action",
    }


def _stop() -> dict[str, object]:
    return {
        "decision_type": "stop",
        "hypotheses": [
            {
                "id": "H1",
                "claim": "trial-specific information",
                "mechanism": "windows share a trial signature",
                "supporting_evidence_ids": ["obs_1"],
                "limitations": "not causal",
            },
            {
                "id": "H2",
                "claim": "noise",
                "mechanism": "finite-sample fluctuation",
                "supporting_evidence_ids": ["obs_1"],
                "limitations": "not exhaustive",
            },
        ],
        "reason": "enough evidence",
        "final_judgment": "H1 is supported in this controlled case",
        "evidence_ids": ["obs_1", "req_1"],
        "remaining_uncertainty": "small synthetic sample",
        "reasoning_summary": "stop",
    }


def _episode_config(tmp_path: Path, provider: object, responses: list[ProviderResponse], max_actions: int = 3) -> tuple[EpisodeConfig, ScriptedProvider]:
    specs_path = tmp_path / "case_specs.json"
    write_case_specs(
        specs_path,
        [
            CaseSpec(
                case_id="case_001",
                family="T",
                data_seed=1101,
                split_seed=2101,
                label_seed=3101,
                model_seed=4101,
            )
        ],
    )
    scripted = ScriptedProvider(responses)
    config = EpisodeConfig(
        episode_id="test_episode",
        case_id="case_001",
        case_specs_path=str(specs_path),
        rule_path="prompts/S0.md",
        provider={"kind": "scripted"},
        backend="scripted",
        model="scripted",
        max_actions=max_actions,
        max_calls=4,
        max_attempts=12,
        deadline="2099-01-01T00:00:00+08:00",
        run_dir=str(tmp_path / "run"),
        shared_facts_path=None,
    )
    return config, scripted


def test_partial_last_log_line_recoverable(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    append_event(run_dir, "first", {"x": 1})
    with (run_dir / "events.jsonl").open("ab") as handle:
        handle.write(b'{"partial":')
    events = read_events(run_dir)
    assert len(events) == 1
    assert (run_dir / "events.corrupt.lastline").exists()
    append_event(run_dir, "second", {"x": 2})
    assert len(read_events(run_dir)) == 2


def test_corrupt_middle_log_fails_loudly(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    append_event(run_dir, "first", {"x": 1})
    log = run_dir / "events.jsonl"
    log.write_bytes(log.read_bytes() + b"{not-json}\n")
    with pytest.raises(CorruptEventLog):
        read_events(run_dir)


def test_seal_and_verify(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    request = ExperimentRequest(
        request_id="req_1",
        tool_id="split_audit",
        parameters={},
        distinguishes=["H1", "H2"],
        prediction=Prediction(scoring_status="not_applicable", check_facts=["inspect overlap"]),
    )
    sealed = seal_prediction(run_dir, request)
    assert verify_sealed(sealed)
    assert not has_result(run_dir, "req_1")
    append_event(run_dir, "experiment_started", {"request_id": "req_1"})
    append_event(run_dir, "experiment_result", {"request_id": "req_1", "valid": True})
    assert has_result(run_dir, "req_1")


def test_execution_requires_sealed_prediction(tmp_path: Path) -> None:
    from eeg_scientist.experiments import run_sealed_experiment

    run_dir = tmp_path / "run"
    request = ExperimentRequest(
        request_id="req_1",
        tool_id="split_audit",
        parameters={},
        distinguishes=["H1", "H2"],
        prediction=Prediction(scoring_status="not_applicable", check_facts=["inspect overlap"]),
    )
    fake = SealedRequest(
        request=request,
        canonical_json="{}",
        sha256="deadbeef",
        sealed_at="2026-10-19T00:00:00Z",
        event_sequence=1,
        run_dir=str(run_dir),
    )
    with pytest.raises(ExperimentError):
        run_sealed_experiment(None, fake, None)  # type: ignore[arg-type]


def test_prediction_event_precedes_result(tmp_path: Path) -> None:
    config, _ = _episode_config(tmp_path, None, [_response(_action()), _response(_stop())])
    summary = run_episode(config, ScriptedProvider([_response(_action()), _response(_stop())]))
    assert summary.status == "completed"
    events = read_events(Path(config.run_dir))
    sealed = next(index for index, event in enumerate(events) if event.event_type == "prediction_sealed")
    result = next(index for index, event in enumerate(events) if event.event_type == "experiment_result")
    assert sealed < result
    assert any(event.event_type == "decision_final" for event in events)
    assert load_result(Path(config.run_dir), "req_1") is not None


def test_action_budget_enforced(tmp_path: Path) -> None:
    tools = ["trial_random_labels", "trial_shuffle_within_subject", "window_random_labels", "metadata_only"]
    responses = [_response(_action(f"req_{index}", tool)) for index, tool in enumerate(tools, start=1)] + [_response(_stop())]
    config, _ = _episode_config(tmp_path, None, responses)
    summary = run_episode(config, ScriptedProvider(responses))
    assert summary.actions_used == 3
    assert summary.status == "completed"
    assert len(list(Path(config.run_dir).glob("result_*.json"))) == 3


def test_unavailable_api_is_not_mock_success(tmp_path: Path) -> None:
    config, _ = _episode_config(tmp_path, None, [])
    summary = run_episode(config, UnavailableProvider())
    assert summary.status == "blocked"
    assert summary.predictions_total == 0
    assert not (Path(config.run_dir) / "final.json").exists()


def test_unknown_api_completion_recorded(tmp_path: Path) -> None:
    config, _ = _episode_config(tmp_path, None, [])
    provider = ScriptedProvider([ProviderResponse(status="unknown_completion", model_id="scripted", error="timeout")])
    summary = run_episode(config, provider)
    assert summary.status == "blocked"
    state = json.loads((Path(config.run_dir) / "state.json").read_text(encoding="utf-8"))
    assert state["stop_reason"] == "provider_unknown_completion"


def test_format_repair_cannot_see_experiment_result(tmp_path: Path) -> None:
    responses = [_response("not-json", status="ok"), _response(_action()), _response(_stop())]
    config, _ = _episode_config(tmp_path, None, responses)
    provider = ScriptedProvider(responses)
    summary = run_episode(config, provider)
    assert summary.status == "completed"
    repair_request = provider.requests[1]
    assert "not-json" in repair_request.messages[1]["content"]
    assert "SENTINEL_RESULT" not in repair_request.messages[1]["content"]


def test_resume_after_result_does_not_rerun_experiment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import eeg_scientist.runner as runner

    calls = {"count": 0}
    original = runner.run_sealed_experiment

    def counting(*args: object, **kwargs: object) -> object:
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(runner, "run_sealed_experiment", counting)
    first_responses = [_response(_action()), _response("", status="unavailable")]
    config, _ = _episode_config(tmp_path, None, first_responses)
    first = run_episode(config, ScriptedProvider(first_responses))
    assert first.status == "blocked"
    assert calls["count"] == 1
    second = resume_episode(config, ScriptedProvider([_response(_stop())]))
    assert second.status == "completed"
    assert calls["count"] == 1
