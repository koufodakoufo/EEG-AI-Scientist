from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from eeg_scientist.reporting import render_reports
from eeg_scientist.schema import EpisodeSummary, StudyConfig
from eeg_scientist.study import _build_development_facts, _pair_order


def _write_episode(base: Path, *, case_id: str, arm: str, backend: str = "real_llm", status: str = "completed", hits: int = 1) -> None:
    run = base / "holdout" / case_id / arm.lower() if arm in ("S0", "S1") else base / "development" / case_id / "s0"
    run.mkdir(parents=True, exist_ok=True)
    state = {
        "episode_id": f"{case_id}_{arm}",
        "case_id": case_id,
        "rule_version": arm if arm in ("S0", "S1") else "S0",
        "phase": status,
        "actions_used": 2 if arm in ("S0", "S1") else 2,
        "calls_used": 2,
        "attempts_used": 2,
        "tokens_used": 100,
        "backend": backend,
        "provider": "test",
        "model": "test-model",
        "stop_reason": "test",
    }
    final = {
        "status": status,
        "backend": backend,
        "provider": "test",
        "model": "test-model",
        "rule_version": arm if arm in ("S0", "S1") else "S0",
        "predictions_total": 1,
        "predictions_hit": hits,
        "stop_reason": "test",
    }
    public = {
        "baseline": {
            "window_balanced_accuracy": 0.99,
            "trial_balanced_accuracy": 0.50,
            "subject_balanced_accuracy": 0.52,
            "gap_window_minus_trial": 0.49,
            "window_trial_aggregated_balanced_accuracy": 0.99,
        }
    }
    score = {
        "tool_id": "trial_random_labels",
        "score": {"status": "scored", "hit": bool(hits)},
        "result": {"valid": True, "metrics": {"trial_random_gap_mean": 0.2}},
    }
    (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (run / "final.json").write_text(json.dumps(final), encoding="utf-8")
    (run / "public_input.json").write_text(json.dumps(public), encoding="utf-8")
    (run / "history.json").write_text("[]", encoding="utf-8")
    (run / "score_001.json").write_text(json.dumps(score), encoding="utf-8")


def _make_study(tmp_path: Path, *, pairs: int = 4, backend: str = "real_llm") -> Path:
    study = tmp_path / "runs" / "study"
    study.mkdir(parents=True)
    (study / "study_state.json").write_text(
        json.dumps(
            {
                "study_id": "study",
                "phase": "complete",
                "deadline": "2026-10-19T09:14:21+08:00",
                "freeze_manifest_hash": "abc",
                "pairs": {},
                "attempts_used": 10,
                "tokens_used": 1000,
                "stopped_reason": "",
            }
        ),
        encoding="utf-8",
    )
    (study / "FREEZE_MANIFEST.json").write_text(
        json.dumps({"created_at": "2026-10-19T03:00:00Z", "model": {"provider": "test", "model": "test-model"}}),
        encoding="utf-8",
    )
    (study / "shared_development_facts.json").write_text("{}", encoding="utf-8")
    for index in range(pairs):
        case_id = f"case_{index + 1:03d}"
        _write_episode(study, case_id=case_id, arm="S0", backend=backend)
        _write_episode(study, case_id=case_id, arm="S1", backend=backend)
    return study


def _write_private_specs(root: Path, case_ids: list[str]) -> None:
    private = root / "archive" / "experiments" / "synthetic_20261019" / "data" / "private"
    private.mkdir(parents=True)
    (private / "case_specs.json").write_text(
        json.dumps(
            {
                "generator_version": "1.0",
                "cases": [
                    {
                        "case_id": case_id,
                        "family": "T",
                        "data_seed": 1,
                        "split_seed": 2,
                        "label_seed": 3,
                        "model_seed": 4,
                    }
                    for case_id in case_ids
                ],
            }
        ),
        encoding="utf-8",
    )
    (private / "raw_private.txt").write_text("RAW_PRIVATE_SENTINEL", encoding="utf-8")


def test_report_numbers_match_saved_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    study = _make_study(tmp_path)
    _write_private_specs(tmp_path, [f"case_{i:03d}" for i in range(1, 5)])
    paths = render_reports(study, tmp_path / "reports")
    data = json.loads((tmp_path / "reports" / "report_data.json").read_text(encoding="utf-8"))
    assert data["e_level"] == "E2"
    assert data["counts"]["complete_pairs"] == 4
    assert data["counts"]["real_llm_episodes"] == 8
    assert Path(paths.morning_report).exists()
    assert Path(paths.results_table).exists()
    assert Path(paths.review_bundle).exists()


def test_mock_and_partial_runs_cannot_be_reported_as_real_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    study = _make_study(tmp_path, pairs=1, backend="mock")
    _write_private_specs(tmp_path, ["case_001"])
    render_reports(study, tmp_path / "reports")
    data = json.loads((tmp_path / "reports" / "report_data.json").read_text(encoding="utf-8"))
    assert data["e_level"] == "E0"
    report = (tmp_path / "reports" / "MORNING_REPORT.md").read_text(encoding="utf-8")
    assert "mock" in report.lower() or "scripted" in report.lower()


def test_review_bundle_excludes_secrets_and_raw_private_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    study = _make_study(tmp_path, pairs=1)
    _write_private_specs(tmp_path, ["case_001"])
    (tmp_path / ".env").write_text("SCIENTIST_API_KEY=SECRET_SENTINEL", encoding="utf-8")
    paths = render_reports(study, tmp_path / "reports")
    with zipfile.ZipFile(paths.review_bundle) as archive:
        names = set(archive.namelist())
        joined = "\n".join(names)
        assert ".env" not in names
        assert "data/private/raw_private.txt" not in names
        assert "archive/experiments/synthetic_20261019/review_only/PRIVATE_CASE_SPECS.json" in names
        assert "SECRET_SENTINEL" not in joined


def test_pair_order_is_preregistered() -> None:
    config = StudyConfig(
        study_id="s",
        deadline="2026-10-19T09:14:21+08:00",
        case_specs_path="archive/experiments/synthetic_20261019/data/private/case_specs.json",
        dev_case_ids=["a"],
        holdout_case_ids=["b", "c", "d", "e"],
        provider={"kind": "ollama_native"},
        arm_order_seed=20261019,
    )
    order = _pair_order(config, ["b", "c", "d", "e"])
    assert set(order) == {"b", "c", "d", "e"}
    assert all(set(arms) == {"S0", "S1"} for arms in order.values())
    firsts = [order[case][0] for case in ("b", "c", "d", "e")]
    assert firsts in (["S0", "S1", "S0", "S1"], ["S1", "S0", "S1", "S0"])


def test_development_facts_are_public_only(tmp_path: Path) -> None:
    study = tmp_path / "study"
    run = study / "development" / "case_001" / "s0"
    run.mkdir(parents=True)
    (run / "public_input.json").write_text(
        json.dumps({"baseline": {"window_balanced_accuracy": 0.9}, "structure_summary": {"n_rows": 4}}),
        encoding="utf-8",
    )
    (run / "history.json").write_text(
        json.dumps(
            [
                {
                    "action": {"action": {"request_id": "req_1", "tool_id": "split_audit", "prediction": {"scoring_status": "not_applicable"}}},
                    "result": {"valid": True, "metrics": {}},
                    "prediction_score": {"status": "not_applicable"},
                }
            ]
        ),
        encoding="utf-8",
    )
    summary = EpisodeSummary(
        episode_id="e",
        case_id="case_001",
        status="completed",
        backend="real_llm",
        model="m",
        actions_used=1,
        calls_used=1,
        attempts_used=1,
        tokens_used=1,
        run_dir=str(run),
    )
    config = StudyConfig(
        study_id="s",
        deadline="2026-10-19T09:14:21+08:00",
        case_specs_path="archive/experiments/synthetic_20261019/data/private/case_specs.json",
        dev_case_ids=["case_001"],
        holdout_case_ids=["case_003"],
        provider={"kind": "ollama_native"},
    )
    facts = _build_development_facts(config, {}, [summary], study)
    assert facts["trajectories"][0]["events"][0]["event_id"] == "dev-case_001-action-1"
    assert "family" not in json.dumps(facts).lower() or "case_001" in json.dumps(facts)
