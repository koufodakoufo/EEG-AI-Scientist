"""End-to-end offline review roundtrip: export a fillable form, fill it, import it."""

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
from eeg_scientist.study_spec import StudyArm, StudySpec, write_study_spec


def _study(tmp_path: Path, bodies: dict[str, str], *, study_id: str = "review_test") -> Path:
    study_root = tmp_path / "studies" / study_id
    (study_root / "materials").mkdir(parents=True)
    (study_root / "materials" / "manifest.json").write_text('{"version":"v1","materials":[{"evidence_id":"ev_x"}]}', encoding="utf-8")
    (study_root / "prompt.md").write_text("system prompt", encoding="utf-8")
    (study_root / "task.md").write_text("task body", encoding="utf-8")
    spec = StudySpec(
        study_id=study_id,
        title="Review test",
        question="",
        task_path=f"studies/{study_id}/task.md",
        material_manifest_path=f"studies/{study_id}/materials/manifest.json",
        material_evidence_dir=f"studies/{study_id}/materials",
        material_version="v1",
        system_prompt_path=f"studies/{study_id}/prompt.md",
        arms=[StudyArm(name=name, backend="deepseek_flash", repeats=1) for name in bodies],
    )
    write_study_spec(study_root / "study.json", spec)
    for arm, body in bodies.items():
        run_dir = study_root / "runs" / arm / "repeat_01"
        run_dir.mkdir(parents=True)
        (run_dir / "final_answer.md").write_text(body, encoding="utf-8")
        (run_dir / "state.json").write_text(
            json.dumps(
                {
                    "run_id": f"{study_id}__{arm}__01",
                    "study_id": study_id,
                    "arm": arm,
                    "repeat": 1,
                    "phase": "completed",
                    "accepted": True,
                    "acceptance": "accepted",
                    "updated_at": "2026-10-22T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
    return study_root


def _fill(path: Path, *, reviewer: str = "expert_A", marker: str = "answer") -> str:
    text = path.read_text(encoding="utf-8")
    text = text.replace("reviewer_id: \n", f"reviewer_id: {reviewer}\n")
    text = text.replace("reviewer_role: \n", "reviewer_role: EEG researcher\n")
    text = text.replace(
        "#### 1. Most important error or evidence gap\n",
        f"#### 1. Most important error or evidence gap\n\n{marker} one.\n",
    )
    text = text.replace(
        "#### 2. What the proposed experiment can and cannot distinguish\n",
        f"#### 2. What the proposed experiment can and cannot distinguish\n\n{marker} two.\n",
    )
    text = text.replace(
        "#### 3. If only one change: what should change\n",
        f"#### 3. If only one change: what should change\n\n{marker} three.\n",
    )
    return text


def _write_feedback(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_exported_form_can_be_filled_without_reformatting(tmp_path: Path) -> None:
    body = "# Proposal\n\nConcrete proposal with a claim.\n"
    _study(tmp_path, {"baseline": body})
    exported = export_packet(tmp_path, "review_test")
    packet_dir = tmp_path / str(exported["path"])
    packet = json.loads((packet_dir / "packet.json").read_text(encoding="utf-8"))
    form_path = tmp_path / str(exported["forms"][0])
    form = form_path.read_text(encoding="utf-8")
    assert body.rstrip() in form
    assert "<!-- BEGIN REVIEW -->" in form
    assert "body_sha256: " + str(packet["proposals"][0]["body_sha256"]) in form
    overview = (packet_dir / "review_packet.md").read_text(encoding="utf-8")
    assert "baseline" not in overview
    assert str(packet["proposals"][0]["run_id"]) not in overview

    feedback = _write_feedback(tmp_path, "filled", _fill(form_path))
    imported = import_review(tmp_path, "review_test", feedback)
    assert imported["status"] == "imported"
    assert imported["display_id"] == "B01"
    assert imported["run_id"] == str(packet["proposals"][0]["run_id"])
    record = json.loads((tmp_path / str(imported["record_path"])).read_text(encoding="utf-8"))
    assert record["packet_id"] == packet["packet_id"]
    assert record["proposal_id"] == packet["proposals"][0]["proposal_id"]
    assert record["body_sha256"] == packet["proposals"][0]["body_sha256"]
    assert len(record["body_sha256"]) == 64
    assert record["reviewer_id"] == "expert_A"
    assert record["display_id"] == "B01"
    assert record["form_version"] == "review_form_v2"
    assert len(record["answers"]) == 3
    assert record["raw_sha256"]
    assert record["binding_source"] == "state"


def test_identical_body_in_two_runs_binds_to_its_own_run(tmp_path: Path) -> None:
    body = "# Identical\n\nThe same bytes in two runs.\n"
    _study(tmp_path, {"baseline": body, "meta_rule": body})
    proposals = collect_proposals(tmp_path, "review_test")
    assert len(proposals) == 2
    assert proposals[0].body_sha256 == proposals[1].body_sha256
    assert proposals[0].proposal_id == proposals[1].proposal_id
    exported = export_packet(tmp_path, "review_test")
    packet_dir = tmp_path / str(exported["path"])
    packet = json.loads((packet_dir / "packet.json").read_text(encoding="utf-8"))
    key = json.loads(
        (tmp_path / "studies" / "review_test" / "reviews" / "keys" / f"{packet['packet_id']}.json").read_text(encoding="utf-8")
    )["key"]
    expected = {entry["display_id"]: key[entry["display_id"]]["run_id"] for entry in packet["proposals"]}
    imported_runs: dict[str, str] = {}
    for index, form_rel in enumerate(exported["forms"]):
        form_path = tmp_path / str(form_rel)
        feedback = _write_feedback(tmp_path, f"identical_{index}", _fill(form_path, reviewer=f"expert_{index}"))
        imported = import_review(tmp_path, "review_test", feedback)
        imported_runs[imported["display_id"]] = imported["run_id"]
    assert imported_runs == expected
    assert len(set(imported_runs.values())) == 2


def test_swapped_display_is_rejected(tmp_path: Path) -> None:
    _study(tmp_path, {"baseline": "# A\n\nFirst body.\n", "meta_rule": "# B\n\nSecond body.\n"})
    exported = export_packet(tmp_path, "review_test")
    form_path = tmp_path / str(exported["forms"][0])
    text = _fill(form_path).replace("display_id: B01", "display_id: B02", 1)
    feedback = _write_feedback(tmp_path, "swapped", text)
    with pytest.raises(ReviewIOError, match="belongs to proposal|does not match"):
        import_review(tmp_path, "review_test", feedback)


def test_packet_from_another_study_is_rejected(tmp_path: Path) -> None:
    _study(tmp_path, {"baseline": "# A\n\nFirst body.\n"}, study_id="review_test")
    _study(tmp_path, {"baseline": "# B\n\nOther study body.\n"}, study_id="other_study")
    own = export_packet(tmp_path, "review_test")
    other = export_packet(tmp_path, "other_study")
    form_path = tmp_path / str(own["forms"][0])
    text = _fill(form_path).replace(
        f"packet_id: {own['packet_id']}",
        f"packet_id: {other['packet_id']}",
        1,
    )
    feedback = _write_feedback(tmp_path, "foreign_packet", text)
    with pytest.raises(ReviewIOError, match="was not exported for this study"):
        import_review(tmp_path, "review_test", feedback)


def test_duplicate_import_is_idempotent(tmp_path: Path) -> None:
    _study(tmp_path, {"baseline": "# A\n\nBody.\n"})
    exported = export_packet(tmp_path, "review_test")
    feedback = _write_feedback(tmp_path, "dup", _fill(tmp_path / str(exported["forms"][0])))
    first = import_review(tmp_path, "review_test", feedback)
    second = import_review(tmp_path, "review_test", feedback)
    assert first["status"] == "imported"
    assert second["status"] == "unchanged"
    records = list((tmp_path / "studies" / "review_test" / "reviews" / "records").glob("*.json"))
    raws = list((tmp_path / "studies" / "review_test" / "reviews" / "raw").glob("*.md"))
    assert len(records) == 1
    assert len(raws) == 1


def test_feedback_set_version_is_immutable(tmp_path: Path) -> None:
    _study(tmp_path, {"baseline": "# A\n\nFirst body.\n", "meta_rule": "# B\n\nSecond body.\n"})
    exported = export_packet(tmp_path, "review_test")
    ids: list[str] = []
    for index, form_rel in enumerate(exported["forms"]):
        feedback = _write_feedback(
            tmp_path, f"immutable_{index}", _fill(tmp_path / str(form_rel), reviewer=f"expert_{index}", marker=f"set{index}")
        )
        ids.append(str(import_review(tmp_path, "review_test", feedback)["review_id"]))
    created = make_feedback_set(tmp_path, "review_test", [ids[0]], "v1")
    assert created["status"] == "created"
    again = make_feedback_set(tmp_path, "review_test", [ids[0]], "v1")
    assert again["status"] == "unchanged"
    with pytest.raises(ReviewIOError, match="already exists with different content"):
        make_feedback_set(tmp_path, "review_test", [ids[1]], "v1")
    v2 = make_feedback_set(tmp_path, "review_test", [ids[1]], "v2")
    assert v2["status"] == "created"
    payload = json.loads((tmp_path / str(v2["feedback_set"])).read_text(encoding="utf-8"))
    assert payload["review_ids"] == [ids[1]]
    assert payload["records"][0]["review_id"] == ids[1]


def test_unknown_cost_is_null_in_packet_and_key(tmp_path: Path) -> None:
    _study(tmp_path, {"baseline": "# A\n\nBody.\n"})
    exported = export_packet(tmp_path, "review_test")
    packet_dir = tmp_path / str(exported["path"])
    packet = json.loads((packet_dir / "packet.json").read_text(encoding="utf-8"))
    key = json.loads(
        (tmp_path / "studies" / "review_test" / "reviews" / "keys" / f"{packet['packet_id']}.json").read_text(encoding="utf-8")
    )["key"]
    assert packet["proposals"][0]["cost_cny"] is None
    assert packet["proposals"][0]["cost_status"] == "unknown"
    assert key["B01"]["cost_cny"] is None
    assert "unknown" in (packet_dir / "review_packet.md").read_text(encoding="utf-8")


def test_legacy_state_without_arm_falls_back_to_verified_path(tmp_path: Path) -> None:
    study_root = _study(tmp_path, {"baseline": "# A\n\nBody.\n"})
    state_path = study_root / "runs" / "baseline" / "repeat_01" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.pop("arm")
    state.pop("repeat")
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proposals = collect_proposals(tmp_path, "review_test")
    assert proposals[0].arm == "baseline"
    assert proposals[0].repeat == 1
    assert proposals[0].binding_source == "path"


def test_state_run_id_mismatch_is_rejected(tmp_path: Path) -> None:
    study_root = _study(tmp_path, {"baseline": "# A\n\nBody.\n"})
    exported = export_packet(tmp_path, "review_test")
    feedback = _write_feedback(tmp_path, "state_guard", _fill(tmp_path / str(exported["forms"][0])))
    state_path = study_root / "runs" / "baseline" / "repeat_01" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["run_id"] = "different_run_id"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(ReviewIOError, match="does not match the run's state.json"):
        import_review(tmp_path, "review_test", feedback)
