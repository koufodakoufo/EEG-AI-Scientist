"""Offline tests for the unified study/review layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eeg_scientist.review_io import (
    ReviewIOError,
    collect_proposals,
    export_packet,
    import_review,
    make_feedback_set,
)
from eeg_scientist.study_runtime import init_study, status, validate_spec
from eeg_scientist.study_spec import StudyArm, StudySpec, load_study_spec, proposal_id, write_study_spec


def _study(root: Path, *, accepted: bool = True) -> tuple[Path, str]:
    (root / "materials").mkdir(parents=True)
    (root / "materials" / "manifest.json").write_text('{"version":"v1"}', encoding="utf-8")
    (root / "prompt.md").write_text("system prompt", encoding="utf-8")
    (root / "rule.md").write_text("rule", encoding="utf-8")
    (root / "task.md").write_text("task", encoding="utf-8")
    spec = StudySpec(
        study_id="review_test",
        title="Review test",
        question="A test question",
        task_path="task.md",
        material_manifest_path="materials/manifest.json",
        material_evidence_dir="materials",
        material_version="v1",
        system_prompt_path="prompt.md",
        deliverables=["one proposal"],
        arms=[StudyArm(name="baseline", backend="deepseek_flash", repeats=1, rule_path="rule.md")],
    )
    study_root = root / "studies" / spec.study_id
    study_root.mkdir(parents=True)
    write_study_spec(study_root / "study.json", spec)
    run_dir = study_root / "runs" / "baseline" / "repeat_01"
    run_dir.mkdir(parents=True)
    body = "# Proposal\n\nA concrete proposal with a citation.\n"
    (run_dir / "final_answer.md").write_text(body, encoding="utf-8")
    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "run_id": f"{spec.study_id}__baseline__01",
                "phase": "completed",
                "accepted": accepted,
                "updated_at": "2026-10-21T19:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "final.json").write_text(json.dumps({"accepted": accepted}), encoding="utf-8")
    return study_root, body


def _feedback(proposal: str, body_sha: str, *, reviewer: str = "reviewer_A") -> str:
    return f"""### B01
proposal_id: {proposal}
body_sha256: {body_sha}
packet_id: PACKET_ID_PLACEHOLDER
reviewer_id: {reviewer}
reviewer_role: EEG researcher
source_type: human
blind: true
developer_reviewer: false
verdict: revise

#### 1. Most important error or evidence gap

The comparison is underspecified.

#### 2. What the proposed experiment can and cannot distinguish

It can separate session drift from trial noise, not identity.

#### 3. If only one change: what should change

Pre-register the session contrast.

#### Unreviewed items

None.
"""


def test_study_init_creates_draft(tmp_path: Path) -> None:
    target = init_study("draft_one", tmp_path)
    assert (target / "study.json").exists()
    assert (target / "task.md").exists()
    spec = load_study_spec(target / "study.json")
    assert spec.study_id == "draft_one"
    assert spec.arms == []


def test_study_validate_reports_missing_files(tmp_path: Path) -> None:
    spec = StudySpec(
        study_id="bad_study",
        title="bad",
        question="",
        material_manifest_path="missing.json",
        material_evidence_dir="missing",
        system_prompt_path="missing.md",
        arms=[StudyArm(name="baseline", backend="deepseek_flash")],
    )
    errors = validate_spec(spec, tmp_path)
    assert any("question" in item for item in errors)
    assert any("missing.json" in item for item in errors)
    assert any("no arms" not in item for item in errors)  # arm exists


def test_review_export_import_and_feedback_set(tmp_path: Path) -> None:
    study_root, body = _study(tmp_path)
    exported = export_packet(tmp_path, "review_test")
    packet_dir = tmp_path / str(exported["path"])
    packet = json.loads((packet_dir / "packet.json").read_text(encoding="utf-8"))
    proposal = str(packet["proposals"][0]["proposal_id"])
    body_sha = str(packet["proposals"][0]["body_sha256"])
    assert proposal == proposal_id((study_root / "runs" / "baseline" / "repeat_01" / "final_answer.md").read_bytes())
    feedback = _feedback(proposal, body_sha).replace("PACKET_ID_PLACEHOLDER", str(packet["packet_id"]))
    feedback_path = tmp_path / "feedback.md"
    feedback_path.write_text(feedback, encoding="utf-8")
    imported = import_review(tmp_path, "review_test", feedback_path)
    assert imported["proposal_id"] == proposal
    record = json.loads((tmp_path / str(imported["record_path"])).read_text(encoding="utf-8"))
    assert record["body_sha256"] == body_sha
    assert record["source_type"] == "human"
    assert record["verdict"] == "revise"
    selected = make_feedback_set(tmp_path, "review_test", [str(imported["review_id"])], "v1")
    payload = json.loads((tmp_path / str(selected["feedback_set"])).read_text(encoding="utf-8"))
    assert payload["review_ids"] == [str(imported["review_id"])]


def test_review_rejects_changed_body(tmp_path: Path) -> None:
    study_root, body = _study(tmp_path)
    exported = export_packet(tmp_path, "review_test")
    packet_dir = tmp_path / str(exported["path"])
    packet = json.loads((packet_dir / "packet.json").read_text(encoding="utf-8"))
    proposal = str(packet["proposals"][0]["proposal_id"])
    body_sha = str(packet["proposals"][0]["body_sha256"])
    (study_root / "runs" / "baseline" / "repeat_01" / "final_answer.md").write_text(body + "changed\n", encoding="utf-8")
    feedback = _feedback(proposal, body_sha).replace("PACKET_ID_PLACEHOLDER", str(packet["packet_id"]))
    feedback_path = tmp_path / "feedback.md"
    feedback_path.write_text(feedback, encoding="utf-8")
    with pytest.raises(ReviewIOError, match="body hash changed"):
        import_review(tmp_path, "review_test", feedback_path)


def test_unaccepted_run_is_not_exported(tmp_path: Path) -> None:
    _study(tmp_path, accepted=False)
    assert collect_proposals(tmp_path, "review_test") == []
