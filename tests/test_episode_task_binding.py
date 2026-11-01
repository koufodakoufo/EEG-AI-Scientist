"""Task identity regressions; these fixtures are not scientific/model evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eegfm.eeg import episode
from eegfm.evaluation.worker import FileBinding


TARGET = "eegmmidb-attribute-dependence-v1"
TARGET_SCOPE = {"task": "eegmmidb-eyes-open-closed-baseline",
                "public_resources_only": True, "backbone_frozen": True,
                "head_frozen": True, "selection_split": "validation",
                "test_after_lock_only": True, "gpu": 0}


@pytest.fixture
def export_config(tmp_path: Path) -> dict:
    source = tmp_path / "source"
    source.mkdir()
    names = ["train.npz", "validation.npz", "eeg_api.py"]
    for name in names:
        (source / name).write_text("synthetic export fixture")
    return {"public_source": str(source), "public_files": names, "condition": "no_skill"}


def test_target_export_supplies_target_contract_and_documents(tmp_path: Path, export_config: dict) -> None:
    public = episode.prepare_public({**export_config, "task_id": TARGET},
                                    tmp_path / "case", tmp_path / "private")
    manifest = episode.verify_public_bundle(public)
    assert manifest["task_id"] == TARGET
    assert "EEGMMIDB" in (public / "TASK.md").read_text()
    assert '"task":"eegmmidb-eyes-open-closed-baseline"' in (
        public / "INTERFACE.md").read_text().replace(" ", "")


def test_unregistered_task_is_rejected_before_export(tmp_path: Path, export_config: dict) -> None:
    with pytest.raises(ValueError, match="task"):
        episode.prepare_public({**export_config, "task_id": "unregistered-task"},
                               tmp_path / "case", tmp_path / "private")
    assert not (tmp_path / "case" / "public").exists()


def test_existing_bundle_cannot_be_silently_relabelled(tmp_path: Path, export_config: dict) -> None:
    episode.prepare_public(export_config, tmp_path / "case", tmp_path / "private")
    with pytest.raises(ValueError, match="task|identity"):
        episode.prepare_public({**export_config, "task_id": "eegmat-attribute-dependence-v1"},
                               tmp_path / "case", tmp_path / "private")


class NoExecutionEvaluator:
    sandboxed = True


def test_target_review_and_contract_enforce_same_target_scope(tmp_path: Path) -> None:
    case = tmp_path / "case"
    (case / "output").mkdir(parents=True)
    controller = episode.EpisodeController(
        trusted_root=tmp_path / "trusted", case_root=case,
        episode_id="target", run_id="target", public_manifest_sha256="a" * 64,
        split_manifest_sha256="b" * 64, evaluator=NoExecutionEvaluator(), task_id=TARGET)
    brief = case / "output" / "brief.md"
    brief.write_text("```json\n" + json.dumps(TARGET_SCOPE) + "\n```\n" +
                     "Analyze recoverability and prediction dependence on the allowed training and validation data.")
    controller.handle({"request_id": "brief", "episode_id": "target", "operation": "brief",
                       "payload": {"path": "brief.md"}})
    review = episode.review_brief(controller, controller.projection())
    assert review["approved"] is True
    assert review["policy_sha256"] != episode.POLICY_HASH
    controller.review(**review)
    with pytest.raises(ValueError, match="scope"):
        controller.handle({"request_id": "wrong", "episode_id": "target", "operation": "contract",
                           "payload": {"protocol": {**episode.SCOPE, "research_mode": "analysis"}}})
    controller.handle({"request_id": "correct", "episode_id": "target", "operation": "contract",
                       "payload": {"protocol": {**TARGET_SCOPE, "research_mode": "analysis"}}})
    prompt = episode.session_prompt(controller.projection(), 2, Path("/env/bin/python"), [], task_id=TARGET)
    assert TARGET in prompt
    assert "EEGMAT episode" not in prompt


def test_cloud_worker_must_use_same_inputs_and_private_truth(tmp_path: Path) -> None:
    train = FileBinding(tmp_path / "train", "a" * 64)
    validation = FileBinding(tmp_path / "validation", "b" * 64)
    test = FileBinding(tmp_path / "test", "c" * 64)
    expected = {"episode_id": "source", "run_id": "source-r01",
                "public_manifest_sha256": "1" * 64, "split_manifest_sha256": "2" * 64,
                "truth_roles": {"train_truth": "3" * 64,
                                "truth_by_split": {"validation": "4" * 64, "test": "5" * 64}},
                "scoring_policy": {"bootstrap_resamples": 2000}}
    remote = {**json.loads(json.dumps(expected)), "worker": {"inputs": {"validation": {"train": {"sha256": train.sha256},
                                       "evaluation": {"sha256": validation.sha256}},
                         "test": {"train": {"sha256": train.sha256},
                                  "evaluation": {"sha256": test.sha256}}},
              "aggregate_source_sha256": "e" * 64}}
    episode.validate_cloud_bindings(remote, train, validation, test, expected, "e" * 64)
    remote["worker"]["inputs"]["test"]["evaluation"]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="cloud"):
        episode.validate_cloud_bindings(remote, train, validation, test, expected, "e" * 64)
    remote["worker"]["inputs"]["test"]["evaluation"]["sha256"] = test.sha256
    for key, wrong in (("episode_id", "other"), ("public_manifest_sha256", "9" * 64),
                       ("scoring_policy", {"bootstrap_resamples": 1}),
                       ("truth_roles", {"train_truth": "3" * 64,
                                        "truth_by_split": {"validation": "5" * 64, "test": "4" * 64}})):
        changed = {**remote, key: wrong}
        with pytest.raises(ValueError, match="cloud"):
            episode.validate_cloud_bindings(changed, train, validation, test, expected, "e" * 64)


def test_private_inputs_cannot_hide_inside_allowed_scientific_runtime(tmp_path: Path) -> None:
    case, runtime = tmp_path / "case", tmp_path / "runtime"
    runtime.mkdir()
    private = tmp_path / "private" / "truth.npz"
    episode.validate_private_boundaries(case, [private], (runtime,))
    with pytest.raises(ValueError, match="runtime"):
        episode.validate_private_boundaries(case, [runtime / "truth.npz"], (runtime,))
    with pytest.raises(ValueError, match="case"):
        episode.validate_private_boundaries(case, [case / "truth.npz"], (runtime,))
