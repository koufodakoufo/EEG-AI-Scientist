"""Offline tests for preflight control checks, generic study init, and project-root paths."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from eeg_scientist.paths import project_root
from eeg_scientist.run_manifest import sha256_file, sha256_text
from eeg_scientist.study_runtime import StudyRuntimeError, init_study, preflight, run_study
from eeg_scientist.study_spec import StudyArm, StudySpec, load_study_spec, validate_spec, write_study_spec


def _study(
    root: Path,
    *,
    arms: list[StudyArm],
    study_id: str = "control_test",
    manifest_materials: list[dict[str, object]] | None = None,
) -> Path:
    study_root = root / "studies" / study_id
    (study_root / "materials" / "evidence").mkdir(parents=True)
    backends_target = root / "configs" / "models" / "backends_20261021.json"
    backends_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(project_root() / "configs" / "models" / "backends_20261021.json", backends_target)
    (study_root / "task.md").write_text("# Task\n\nTASK_MARKER_CONTROL\n", encoding="utf-8")
    (study_root / "system.md").write_text("SYSTEM_BASE_CONTROL\n", encoding="utf-8")
    materials = manifest_materials if manifest_materials is not None else [{"evidence_id": "ev_" + "a" * 12, "title": "A"}]
    (study_root / "materials" / "manifest.json").write_text(
        json.dumps({"version": "control_v1", "materials": materials}, indent=2),
        encoding="utf-8",
    )
    spec = StudySpec(
        study_id=study_id,
        title="Control test",
        question="metadata label",
        task_path=f"studies/{study_id}/task.md",
        material_manifest_path=f"studies/{study_id}/materials/manifest.json",
        material_evidence_dir=f"studies/{study_id}/materials/evidence",
        material_version="control_v1",
        system_prompt_path=f"studies/{study_id}/system.md",
        arms=arms,
    )
    study_root.mkdir(parents=True, exist_ok=True)
    write_study_spec(study_root / "study.json", spec)
    return study_root


def test_preflight_reports_task_material_rule_hashes_and_prompt_diff(tmp_path: Path) -> None:
    rule = tmp_path / "meta_rule.md"
    rule.write_text("RULE_CONTROL_MARKER: prefer discriminating tests.\n", encoding="utf-8")
    study_root = _study(
        tmp_path,
        arms=[
            StudyArm(name="baseline", backend="deepseek_flash", repeats=1),
            StudyArm(name="meta_rule", backend="deepseek_flash", repeats=1, rule_path=str(rule)),
        ],
    )
    payload = preflight(tmp_path, "control_test")
    assert payload["ok"] is True
    assert payload["task"]["sha256"] == sha256_text((study_root / "task.md").read_text(encoding="utf-8"))
    assert payload["material"]["sha256"] == sha256_file(study_root / "materials" / "manifest.json")
    arms = payload["arms"]
    assert isinstance(arms, list) and len(arms) == 2
    baseline, meta = arms
    assert isinstance(baseline, dict) and isinstance(meta, dict)
    assert baseline["model"]["model_name"] == "deepseek-flash"
    assert baseline["rule_sha256"] == sha256_text("")
    assert meta["rule_sha256"] == sha256_text(rule.read_text(encoding="utf-8"))
    assert "RULE_CONTROL_MARKER" in str(meta["system_text"])
    assert "RULE_CONTROL_MARKER" not in str(baseline["system_text"])
    diff = meta["prompt_diff_vs_first"]
    assert isinstance(diff, list)
    assert any("Applied research rules" in line for line in diff if isinstance(line, str))
    contrast = payload["rule_contrast"]
    assert isinstance(contrast, dict)
    assert contrast["requested"] is True
    assert set(contrast["distinct_rule_hashes"]) == {baseline["rule_sha256"], meta["rule_sha256"]}
    assert contrast["valid"] is True


def test_preflight_rejects_distinct_rule_files_with_identical_text(tmp_path: Path) -> None:
    first = tmp_path / "rule_a.md"
    second = tmp_path / "rule_b.md"
    first.write_text("SAME_RULE_TEXT\n", encoding="utf-8")
    second.write_text("SAME_RULE_TEXT\n", encoding="utf-8")
    _study(
        tmp_path,
        arms=[
            StudyArm(name="rule_a", backend="deepseek_flash", repeats=1, rule_path=str(first)),
            StudyArm(name="rule_b", backend="deepseek_flash", repeats=1, rule_path=str(second)),
        ],
    )
    payload = preflight(tmp_path, "control_test")
    assert payload["ok"] is False
    contrast = payload["rule_contrast"]
    assert isinstance(contrast, dict)
    assert contrast["requested"] is True
    assert contrast["valid"] is False
    with pytest.raises(StudyRuntimeError, match="preflight rejected"):
        run_study(tmp_path, "control_test")
    assert not (tmp_path / "studies" / "control_test" / "runs").exists()


def test_same_rule_file_on_two_arms_is_not_a_rule_contrast(tmp_path: Path) -> None:
    rule = tmp_path / "shared_rule.md"
    rule.write_text("SHARED_RULE_TEXT\n", encoding="utf-8")
    _study(
        tmp_path,
        arms=[
            StudyArm(name="model_a", backend="deepseek_flash", repeats=1, rule_path=str(rule)),
            StudyArm(name="model_b", backend="deepseek_flash", repeats=1, rule_path=str(rule)),
        ],
    )
    payload = preflight(tmp_path, "control_test")
    assert payload["ok"] is True
    contrast = payload["rule_contrast"]
    assert isinstance(contrast, dict)
    assert contrast["requested"] is False


def test_generic_study_init_has_no_old_emotion_dependency(tmp_path: Path) -> None:
    target = init_study("fresh_study", tmp_path)
    spec = load_study_spec(target / "study.json")
    assert spec.arms == []
    assert spec.question == ""
    for value in (spec.task_path, spec.material_manifest_path, spec.system_prompt_path):
        assert "emotion" not in value
        assert "archive" not in value
        assert (tmp_path / value).exists()
    assert "2026" not in (target / "study.json").read_text(encoding="utf-8")
    manifest = json.loads((target / "materials" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["materials"] == []
    errors = validate_spec(spec, tmp_path)
    assert any("material manifest has no materials" in error for error in errors)


def test_explicit_old_material_template_is_opt_in(tmp_path: Path) -> None:
    target = init_study("old_material_study", tmp_path, template="emotion_20261021")
    spec = load_study_spec(target / "study.json")
    assert spec.material_manifest_path == "configs/materials/emotion_state_trait_v1.json"
    assert "emotion_20261021" in spec.material_evidence_dir
    assert "emotion" in spec.system_prompt_path
    assert "explicitly selected" in (target / "README.md").read_text(encoding="utf-8")
    assert not (target / "materials").exists()


def test_project_root_resolves_from_subdirectory(tmp_path: Path) -> None:
    root = project_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "eeg_scientist").is_dir()
    assert project_root(root / "group-meeting") == root
    fake = tmp_path / "fake_project"
    (fake / "src" / "eeg_scientist").mkdir(parents=True)
    (fake / "pyproject.toml").write_text("[project]\nname='fake'\n", encoding="utf-8")
    nested = fake / "a" / "b"
    nested.mkdir(parents=True)
    assert project_root(nested) == fake
