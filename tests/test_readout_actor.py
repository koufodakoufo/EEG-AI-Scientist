"""Readout task wiring regressions; synthetic fixtures are not model evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from eegfm.agent.budget import BudgetExceeded
from eegfm.eeg import episode
from eegfm.evaluation import ssh_worker
from eegfm.evaluation.bundle import create_public_bundle, digest_file
from eegfm.evaluation.worker import FileBinding


READOUT_TASK = "eegmmidb-readout-bottleneck-v1"
READOUT_SCOPE = {"task": "eegmmidb-cached-readout-bottleneck", "public_resources_only": True,
                 "backbone_frozen": True, "head_frozen": True, "selection_split": "validation",
                 "test_after_lock_only": True, "gpu": 0,
                 "cached_inputs_only": True, "train_only_readouts": True}


def test_readout_scope_is_explicit_and_cannot_accept_the_old_question() -> None:
    episode.validate_scope(READOUT_SCOPE, READOUT_TASK)
    with pytest.raises(ValueError, match="scope"):
        episode.validate_scope(episode.task_scope("eegmmidb-attribute-dependence-v1"), READOUT_TASK)
    with pytest.raises(ValueError, match="task"):
        episode.task_scope("eegmmidb-readout-bottleneck-v99")
    assert episode.task_scope() == episode.SCOPE
    assert episode.review_policy_hash() == episode.POLICY_HASH


def test_readout_public_export_keeps_hidden_builder_material_out(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "resources").mkdir(parents=True)
    names = ["train.npz", "validation.npz", "eeg_api.py", "resources/CACHE_SCHEMA.json"]
    for name in names:
        (source / name).write_text("synthetic permitted fixture")
    (source / "builder-findings.json").write_text("private findings")
    (source / "resources" / "private-plan.md").write_text("private recipe")
    config = {"task_id": READOUT_TASK, "public_source": str(source),
              "public_files": names, "condition": "no_skill"}
    public = episode.prepare_public(config, tmp_path / "case", tmp_path / "private")
    manifest = episode.verify_public_bundle(public)
    assert manifest["task_id"] == READOUT_TASK
    assert {row["path"] for row in manifest["files"]} == set(names) | set(episode.DOCS)
    assert not (public / "builder-findings.json").exists()
    for bad_names in (names[:-1], names + ["resources/builder-results.md"],
                      names + ["resources/notes.md"]):
        with pytest.raises(ValueError):
            episode.prepare_public({**config, "public_files": bad_names},
                                   tmp_path / "other-case", tmp_path / "other-private")


class MetricsEvaluator:
    sandboxed = True

    def __init__(self, metrics: dict[str, float], final: dict[str, float] | None = None) -> None:
        self.metrics, self.final = metrics, metrics if final is None else final

    def submit(self, spec):
        return {"job_id": spec.job_id, "candidate_digest": spec.candidate_digest,
                "split": spec.split, "status": "succeeded",
                "metrics": self.final if spec.split == "test" else self.metrics,
                "artifacts": [], "sandbox_receipt": "SYNTHETIC_NO_EXECUTION"}


def _complete(tmp_path: Path, task_id: str, metrics: dict[str, float],
              final: dict[str, float] | None = None) -> episode.EpisodeController:
    case = tmp_path / "case"
    output = case / "output"
    (output / "candidate").mkdir(parents=True)
    (output / "candidate/main.py").write_text("# synthetic controller boundary\n")
    (output / "brief.md").write_text("A bounded question with train-only fitting and declared controls.")
    controller = episode.EpisodeController(trusted_root=tmp_path / "trusted", case_root=case,
        episode_id="readout-test", run_id="readout-test", public_manifest_sha256="a" * 64,
        split_manifest_sha256="b" * 64, evaluator=MetricsEvaluator(metrics, final), task_id=task_id)
    def request(operation, payload):
        return controller.handle({"request_id": operation, "episode_id": "readout-test",
                                  "operation": operation, "payload": payload})
    request("brief", {"path": "brief.md"})
    controller.review(approved=True, reviewer_id="synthetic", policy_sha256="c" * 64)
    request("contract", {"protocol": {**episode.task_scope(task_id), "research_mode": "analysis"}})
    request("baseline", {"candidate_dir": "candidate", "split": "validation", "title": "baseline"})
    attempt = request("attempt", {"candidate_dir": "candidate", "split": "validation", "title": "readouts"})
    request("lock", {"attempt_id": attempt["attempt_id"], "candidate_digest": attempt["candidate_digest"]})
    request("test", {"candidate_digest": attempt["candidate_digest"], "split": "test"})
    controller.record_session({"status": "completed", "exit_code": 0,
        "stdout": '{"type":"turn.completed"}', "stderr": "", "process_cleanup": {"surviving_owned_pids": []}})
    (output / "REPORT.md").write_text("Synthetic lifecycle fixture only, no scientific finding.")
    request("report", {"path": "REPORT.md"})
    controller.validate_done()
    return controller


def test_readout_completion_accepts_new_evidence_without_q1(tmp_path: Path) -> None:
    controller = _complete(tmp_path, READOUT_TASK, {"readout_count": 2, "representation_readouts": 1})
    assert controller.projection()["state"]["status"] == "done"


@pytest.mark.parametrize("metrics,final", [
    ({"q1_groups": 24}, None),
    ({"readout_count": 1, "representation_readouts": 0}, None),
    ({"readout_count": 2, "representation_readouts": 0}, None),
    ({"readout_count": 2, "representation_readouts": 1}, {"q1_groups": 24}),
])
def test_readout_completion_requires_representation_in_locked_and_final_evidence(tmp_path, metrics, final) -> None:
    with pytest.raises(ValueError, match="readout"):
        _complete(tmp_path, READOUT_TASK, metrics, final)


def test_old_completion_still_requires_q1(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Q1 evidence"):
        _complete(tmp_path, episode.DEFAULT_TASK, {"readout_count": 2, "representation_readouts": 1})


def test_configured_deadline_reaches_worker_and_prevents_late_submission(monkeypatch) -> None:
    calls = []
    worker = SimpleNamespace(timeout=600, operation_timeout_seconds=780, deadline_epoch=None,
                             submit=lambda spec: calls.append(spec) or {"ok": True})
    wrapped = episode.DeadlineEvaluator(worker, 1000.0, timeout_seconds=2700)
    assert worker.deadline_epoch == 3700
    monkeypatch.setattr(episode.time, "time", lambda: 2800.0)
    assert wrapped.submit("early") == {"ok": True}
    monkeypatch.setattr(episode.time, "time", lambda: 2900.0)
    with pytest.raises(BudgetExceeded):
        wrapped.submit("late")
    assert calls == ["early"]


@pytest.mark.parametrize("config", [
    {"episode_timeout_seconds": 0}, {"episode_timeout_seconds": float("inf")},
    {"episode_timeout_seconds": True}, {"episode_timeout_seconds": 5401},
    {"task_id": READOUT_TASK, "episode_timeout_seconds": 2701},
    {"task_id": READOUT_TASK, "session_timeout_seconds": 601},
])
def test_invalid_episode_limits_rejected_before_launch(config, tmp_path) -> None:
    with pytest.raises(ValueError, match="timeout"):
        episode.NativeEpisodeLaunch(config, None, tmp_path, tmp_path, 1000.0)


def test_native_readout_deadline_prevents_any_reservation(tmp_path, monkeypatch) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "sessions.jsonl").write_text('{"session":1}\n')
    config = {"task_id": READOUT_TASK, "call_ids": ["R01"]}
    launcher = episode.NativeEpisodeLaunch(config, SimpleNamespace(run=run), tmp_path, tmp_path, 1000.0)
    monkeypatch.setattr(episode.time, "time", lambda: 3671.0)
    with pytest.raises(BudgetExceeded, match="deadline"):
        launcher({})


def _bound(path: Path, value: str) -> dict[str, str]:
    path.write_text(value)
    return {"path": str(path), "sha256": digest_file(path)}


@pytest.fixture
def readout_config(tmp_path: Path) -> dict:
    config = {"task_id": READOUT_TASK, "episode_id": "episode", "run_id": "run",
              "bootstrap_resamples": 7, "seed": 161803,
              "train_truth": _bound(tmp_path / "train-truth.npz", "train truth"),
              "test_cohort": _bound(tmp_path / "cohort.npz", "cohort"),
              "truth_by_split": {}, "inference_by_split": {}}
    for split in ("train", "validation", "test"):
        config["inference_by_split"][split] = _bound(tmp_path / f"{split}-input.npz", split + " inputs")
        if split != "train":
            config["truth_by_split"][split] = _bound(tmp_path / f"{split}-truth.npz", split + " truth")
    stage, public = tmp_path / "public-stage", tmp_path / "public"
    stage.mkdir()
    for name in ("train.npz", "validation.npz"):
        (stage / name).write_text("public " + name)
    create_public_bundle(stage, public, ["train.npz", "validation.npz"],
                         task_id=READOUT_TASK, tier="synthetic_mechanism")
    config["public_root"] = str(public)
    config["aggregate_runtime"] = ssh_worker.readout_runtime_identity()
    return config


def test_readout_runtime_record_verifies_current_host_and_rejects_drift() -> None:
    actual = ssh_worker.readout_runtime_identity()
    ssh_worker.verify_readout_runtime(actual)
    assert set(actual["packages"]) == {"numpy", "scipy", "sklearn"}
    assert actual["python"]["executable_sha256"]
    assert actual["modules"]["numpy.random._generator"]
    drifted = copy.deepcopy(actual)
    drifted["python"]["version"] += "-changed"
    with pytest.raises(ValueError, match="runtime"):
        ssh_worker.verify_readout_runtime(drifted)


def test_readout_factory_rejects_missing_runtime_enrollment(readout_config) -> None:
    del readout_config["aggregate_runtime"]
    with pytest.raises(ValueError, match="runtime"):
        episode.load_aggregator(readout_config)


def test_host_runtime_guard_is_stable_after_scoring_numerics() -> None:
    import numpy as np
    before = ssh_worker.readout_runtime_identity()
    samples = np.random.default_rng(161803).normal(size=(20, 3))
    np.quantile(np.logaddexp(0, samples), [.025, .975], axis=0)
    np.linalg.svd(samples)
    ssh_worker.verify_readout_runtime(before)


def test_factory_binds_actual_public_files_and_rejects_manifest_drift(readout_config, tmp_path) -> None:
    readout_config["public_by_split"] = {name: readout_config["inference_by_split"][name]
                                         for name in ("train", "validation")}
    aggregate = episode.load_aggregator(readout_config)
    for name in ("train", "validation"):
        actual = Path(readout_config["public_root"]) / f"{name}.npz"
        assert aggregate.public[name].path == actual
        assert aggregate.public[name].sha256 == digest_file(actual)
    (Path(readout_config["public_root"]) / "train.npz").write_text("changed public input")
    with pytest.raises(ValueError):
        episode.load_aggregator(readout_config)


def test_factory_rejects_wrong_enrolled_public_manifest(readout_config) -> None:
    readout_config["public_manifest_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="public"):
        episode.load_aggregator(readout_config)


def test_controller_can_bind_foreign_runtime_but_executing_factory_rejects_it(readout_config) -> None:
    original = episode.load_aggregator(readout_config)
    readout_config["aggregate_runtime"]["python"]["version"] = "a different frozen cloud Python"
    aggregate = episode.load_aggregator(readout_config)
    assert aggregate.policy_sha256 != original.policy_sha256
    identity = ssh_worker.scientific_identity(readout_config, aggregate=aggregate,
        public_manifest_sha256="d" * 64, split_manifest_sha256="e" * 64)
    assert identity["aggregate_runtime"]["python"]["version"] == "a different frozen cloud Python"
    with pytest.raises(ValueError, match="runtime"):
        episode.load_aggregator(readout_config, verify_runtime=True)


def test_executing_factory_rechecks_runtime_before_scoring(readout_config, monkeypatch, tmp_path) -> None:
    aggregate = episode.load_aggregator(readout_config, verify_runtime=True)
    drifted = copy.deepcopy(readout_config["aggregate_runtime"])
    drifted["packages"]["numpy"] += "-changed"
    monkeypatch.setattr(ssh_worker, "readout_runtime_identity", lambda: drifted)
    with pytest.raises(ValueError, match="runtime"):
        aggregate(tmp_path / "unused", SimpleNamespace(split="validation"))


def test_local_and_cloud_readout_identity_bind_semantics_and_all_roles(readout_config) -> None:
    aggregate = episode.load_aggregator(readout_config)
    assert type(aggregate).__name__ == "ReadoutAggregator"
    identity = ssh_worker.scientific_identity(readout_config, aggregate=aggregate,
        public_manifest_sha256="d" * 64, split_manifest_sha256="e" * 64)
    assert identity["task_id"] == READOUT_TASK
    assert identity["inference_roles"] == {name: value["sha256"] for name, value in readout_config["inference_by_split"].items()}
    assert identity["public_roles"] == {name: digest_file(Path(readout_config["public_root"]) / f"{name}.npz")
                                        for name in ("train", "validation")}
    assert identity["test_cohort_sha256"] == readout_config["test_cohort"]["sha256"]
    assert identity["aggregate_policy_sha256"] == aggregate.policy_sha256
    assert "layers" not in identity["scoring_policy"]
    assert "feature_columns" not in identity["scoring_policy"]
    assert episode.aggregator_source_sha256(READOUT_TASK) == digest_file(
        Path(episode.__file__).with_name("readout_aggregation.py"))
    assert episode.aggregator_source_sha256() == digest_file(Path(episode.__file__).with_name("aggregation.py"))


def test_cloud_binding_rejects_inference_cohort_policy_and_source_swaps(readout_config) -> None:
    aggregate = episode.load_aggregator(readout_config)
    identity = ssh_worker.scientific_identity(readout_config, aggregate=aggregate,
        public_manifest_sha256="d" * 64, split_manifest_sha256="e" * 64)
    files = {name: episode.binding(value) for name, value in readout_config["inference_by_split"].items()}
    source = episode.aggregator_source_sha256(READOUT_TASK)
    remote = {**identity, "worker": {"aggregate_source_sha256": source,
        "aggregate_policy_sha256": aggregate.policy_sha256,
        "inputs": {name: {"train": {"sha256": files["train"].sha256},
                          "evaluation": {"sha256": files[name].sha256}}
                   for name in ("validation", "test")}}}
    episode.validate_cloud_bindings(remote, files["train"], files["validation"], files["test"], identity, source)
    for field in ("inference_roles", "public_roles", "aggregate_runtime", "test_cohort_sha256", "aggregate_policy_sha256", "task_id"):
        changed = copy.deepcopy(remote)
        changed[field] = "wrong"
        with pytest.raises(ValueError, match="cloud"):
            episode.validate_cloud_bindings(changed, files["train"], files["validation"], files["test"], identity, source)
    for field in ("aggregate_source_sha256", "aggregate_policy_sha256"):
        changed = copy.deepcopy(remote)
        changed["worker"][field] = "f" * 64
        with pytest.raises(ValueError, match="cloud"):
            episode.validate_cloud_bindings(changed, files["train"], files["validation"], files["test"], identity, source)


def test_old_aggregator_defaults_and_identity_are_preserved(readout_config) -> None:
    legacy = {key: value for key, value in readout_config.items()
              if key not in {"task_id", "bootstrap_resamples", "seed", "inference_by_split", "test_cohort"}}
    aggregate = episode.load_aggregator(legacy)
    assert type(aggregate).__name__ == "ScientificAggregator"
    assert aggregate.bootstrap_resamples == 2000
    identity = ssh_worker.scientific_identity(legacy, aggregate=aggregate,
        public_manifest_sha256="d" * 64, split_manifest_sha256="e" * 64)
    assert set(identity) == {"episode_id", "run_id", "public_manifest_sha256", "split_manifest_sha256", "truth_roles", "scoring_policy"}
    assert identity["scoring_policy"]["schema"] == "scientific_aggregate_v1"
    assert identity["scoring_policy"]["seed"] == 20261029


def test_cloud_schema_does_not_allow_silent_scorer_switch(tmp_path, readout_config) -> None:
    path = tmp_path / "worker.json"
    for config in ({**readout_config, "schema_version": "ssh_scientific_worker_v1"},
                   {**readout_config, "schema_version": "ssh_readout_worker_v1", "task_id": episode.DEFAULT_TASK}):
        path.write_text(json.dumps(config))
        with pytest.raises(ValueError, match="task|configuration"):
            ssh_worker.load_worker(FileBinding(path, digest_file(path)))


def test_cloud_loader_dispatch_matches_local_scorer_and_rejects_input_role_swap(
        tmp_path, readout_config, monkeypatch) -> None:
    # Substitute only worker construction: Docker/process execution is tested on
    # Linux. Configuration parsing, file verification and both scorers are real.
    monkeypatch.setattr(ssh_worker, "SandboxedWorkerEvaluator", lambda **kwargs: SimpleNamespace(**kwargs))
    public = Path(readout_config["public_root"])
    public_train = {"path": str(public / "train.npz"), "sha256": digest_file(public / "train.npz")}
    config = {**readout_config, "schema_version": "ssh_readout_worker_v1",
              "public_manifest_sha256": digest_file(public / "PUBLIC_MANIFEST.json"),
              "split_manifest": _bound(tmp_path / "split.json", "split manifest"),
              "runtime": {"python": str(tmp_path / "python"), "docker": str(tmp_path / "docker"),
                          "image": "sha256:" + "a" * 64, "host": "unix:///run/docker.sock"},
              "inputs_by_split": {name: {"train": public_train,
                                          "evaluation": readout_config["inference_by_split"][name]}
                                  for name in ("validation", "test")}}
    config.update({key: str(tmp_path / key) for key in ("staging_root", "private_root")})
    path = tmp_path / "worker.json"
    path.write_text(json.dumps(config))
    _, cloud = ssh_worker.load_worker(FileBinding(path, digest_file(path)))
    local = episode.load_aggregator(readout_config)
    assert type(cloud.aggregate).__name__ == "ReadoutAggregator"
    assert cloud.aggregate_policy_sha256 == local.policy_sha256
    assert ssh_worker.scientific_identity(config, aggregate=cloud.aggregate,
        public_manifest_sha256="c" * 64, split_manifest_sha256=config["split_manifest"]["sha256"]) == \
        ssh_worker.scientific_identity(config, aggregate=local,
        public_manifest_sha256="c" * 64, split_manifest_sha256=config["split_manifest"]["sha256"])
    config["inputs_by_split"]["test"]["evaluation"] = config["inference_by_split"]["validation"]
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="inference"):
        ssh_worker.load_worker(FileBinding(path, digest_file(path)))
    config["inputs_by_split"]["test"]["evaluation"] = config["inference_by_split"]["test"]
    config["inputs_by_split"]["test"]["train"] = config["inference_by_split"]["train"]
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="training|public"):
        ssh_worker.load_worker(FileBinding(path, digest_file(path)))
