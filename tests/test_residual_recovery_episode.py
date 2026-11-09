"""Synthetic wiring checks, never remote execution or scientific evidence."""
import copy
import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from eegfm.eeg import episode
from eegfm.evaluation.bundle import canonical_bytes, digest_file
from eegfm.evaluation.worker import SandboxedWorkerEvaluator, FileBinding, RuntimeConfig, SplitInputs, candidate_digest
from eegfm.eeg.residual_recovery_aggregation import ResidualRecoveryAggregator
from eegfm.evaluation import ssh_worker
from test_residual_recovery_aggregation import _fixture, _receipt

TASK = "eegmat-residual-recovery-v1"


@pytest.fixture
def paper_export(tmp_path: Path) -> tuple[dict, bytes]:
    source = tmp_path / "source"
    (source / "resources").mkdir(parents=True)
    names = ["train.npz", "validation.npz", "eeg_api.py", "resources/CACHE_SCHEMA.json"]
    for name in names:
        (source / name).write_bytes(b"synthetic public input")
    public = {"schema_version": "paper_task_v1", "task_id": "synthetic-paper-question", "revision": "r1",
              "question": "What survives the intervention?", "resources": ["Fixed cached inputs"],
              "constraints": ["Keep the existing split"], "budget": {"seconds": 2700},
              "report_contract": ["Report uncertainty"]}
    raw = (json.dumps(public, indent=2) + "\n").encode()
    (source / "resources/PAPER_TASK.json").write_bytes(raw)
    (source / "resources/EXTRA.json").write_bytes(b"{}")
    return {"task_id": TASK, "public_source": str(source), "condition": "no_skill",
            "public_files": [*names, "resources/PAPER_TASK.json"]}, raw


def test_residual_prepare_public_preserves_paper_bytes_and_existing_docs(tmp_path: Path, paper_export: tuple) -> None:
    config, raw = paper_export
    public = episode.prepare_public(config, tmp_path / "case", tmp_path / "private")
    assert (public / "resources/PAPER_TASK.json").read_bytes() == raw
    manifest = episode.verify_public_bundle(public)
    assert {row["path"] for row in manifest["files"]} == set(config["public_files"]) | set(episode.DOCS)
    assert episode.prepare_public(config, tmp_path / "case", tmp_path / "private") == public


@pytest.mark.parametrize("change", ["extra_path", "other_task", "private_field", "private_nested_field", "wrong_schema"])
def test_residual_prepare_public_rejects_unapproved_paper_material(tmp_path: Path, paper_export: tuple, change: str) -> None:
    config, raw = paper_export
    if change == "extra_path":
        config["public_files"].append("resources/EXTRA.json")
    elif change == "other_task":
        config["task_id"] = episode.READOUT_TASK
    else:
        value = json.loads(raw)
        if change == "private_field":
            value["references"] = ["private fragment"]
        elif change == "private_nested_field":
            value["report_contract"] = [{"answer": "private fragment"}]
        else:
            value["schema_version"] = "paper_workflow_freeze_v1"
        (Path(config["public_source"]) / "resources/PAPER_TASK.json").write_bytes(canonical_bytes(value))
    with pytest.raises(ValueError):
        episode.prepare_public(config, tmp_path / "case", tmp_path / "private")
    assert not (tmp_path / "case/public").exists()


@pytest.mark.parametrize("operation", ["enrollment", "validation", "test", "named_test"])
def test_generic_worker_paths_do_not_import_optional_science(operation):
    """Fresh process avoids NumPy already loaded by this test module's fixtures."""
    import subprocess
    import sys
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = r'''
import importlib.abc
import sys
from pathlib import Path
from types import SimpleNamespace
source = Path(sys.argv[1])
sys.path.insert(0, str(source))
class WithoutOptionalScience(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'numpy' or fullname.startswith('numpy.') or fullname.startswith('eegfm.eeg.residual_recovery'):
            raise ModuleNotFoundError('probe: optional science import forbidden: ' + fullname)
sys.meta_path.insert(0, WithoutOptionalScience())
import eegfm.evaluation.worker as module
assert Path(module.__file__).resolve() == source / 'eegfm/evaluation/worker.py'
worker = object.__new__(module.SandboxedWorkerEvaluator)
worker.aggregate = SimpleNamespace()
operation = sys.argv[2]
if operation == 'enrollment':
    binary = Path(sys.executable).resolve()
    worker.aggregate_source_path = Path(module.__file__)
    worker.aggregate_source_sha256 = module.digest_file(worker.aggregate_source_path)
    worker.aggregate_policy_sha256 = 'a' * 64
    worker.docker = None
    worker.runtime = SimpleNamespace(python=binary, bwrap=binary, backend='bwrap', environment_roots=(), manifest=None)
    worker.runtime_hashes = dict.fromkeys(('python', 'bwrap'), module.digest_file(binary))
    worker.inputs = {}
    worker.aggregate_bindings = ()
    worker.released_metrics = frozenset({'synthetic_metric'})
    worker.timeout = 30
    worker.free_floor = 0
    worker.allowed_splits = frozenset({'validation', 'test'})
    worker.public_artifact_mode = None
    result = worker._enrollment()
    assert result['released_metrics'] == ['synthetic_metric']
    assert 'validation_identity_release' not in result
else:
    if operation == 'named_test':
        # Even a possible registered-class match must short-circuit the test split.
        collector = type('ResidualRecoveryAggregator', (), {'__module__': 'eegfm.eeg.residual_recovery_aggregation'})
        worker.aggregate = collector()
    split = 'validation' if operation == 'validation' else 'test'
    assert worker._residual_validation_identity_artifact(Path('.'), {}, SimpleNamespace(split=split)) is None
assert 'numpy' not in sys.modules
assert 'eegfm.eeg.residual_recovery_aggregation' not in sys.modules
print('optional-science-free:' + operation)
'''
    # Isolated mode ignores PYTHONDONTWRITEBYTECODE, so pass -B to protect the source tree.
    result = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(source_root), operation],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "optional-science-free:" + operation


def config(tmp_path):
    roles = ("public_train", "public_validation", "inference_validation", "inference_test",
             "truth_train", "truth_validation", "truth_test", "split_manifest")
    bindings = {}
    for role in roles:
        path = tmp_path / (role + ".npz")
        path.write_bytes(role.encode())
        bindings[role] = {"path": str(path), "sha256": digest_file(path)}
    proof = tmp_path / "qualification.json"
    proof.write_bytes(canonical_bytes(_receipt({k: v["sha256"] for k, v in bindings.items()})))
    return {"schema_version": "audited_coding_episode_v1", "task_id": TASK, "model": episode.MODEL,
            "reasoning_effort": "high", "session_timeout_seconds": 240, "call_ids": ["coding-1"],
            "residual_data_qualification": {"path": str(proof), "sha256": digest_file(proof)},
            "train_input": bindings["public_train"], "public_validation_input": bindings["public_validation"],
            "validation_input": bindings["inference_validation"], "test_input": bindings["inference_test"],
            "train_truth": bindings["truth_train"], "split_manifest": bindings["split_manifest"],
            "truth_by_split": {s: bindings["truth_" + s] for s in ("validation", "test")},
            "inference_by_split": {s: bindings["inference_" + s] for s in ("validation", "test")}}


def test_residual_task_admission(tmp_path):
    value = config(tmp_path)
    assert episode.task_scope(TASK)["task"] == "eegmat-cached-residual-recovery"
    assert episode.task_scope(TASK)["cached_inputs_only"] is True
    assert episode.episode_time_limits({"task_id": TASK}) == (2700, 240)
    assert episode.validate_delegated_config(value)["task_id"] == TASK
    for update in ({"task_id": "unknown"}, {"max_attempts": 2}, {"recovery_policy": "validation-recovery-v1"},
                   {"session_timeout_seconds": 241}, {"call_ids": [f"call-{i}" for i in range(7)]},
                   {"test_input": value["validation_input"]}):
        with pytest.raises(ValueError):
            episode.validate_delegated_config({**value, **update})
    assert episode.episode_time_limits({"task_id": episode.READOUT_TASK}) == (2700, 600)
    with pytest.raises(ValueError, match="audited|delegated"):
        episode.run_episode({"schema_version": "real_episode_config_v1", "task_id": TASK})


@pytest.mark.parametrize("task,science,fit,allowed", [
    (TASK, 120, 90, True), (TASK, 121, 90, False), (TASK, 120, 91, False), (TASK, 90, 120, False),
    (episode.READOUT_TASK, 180, 120, True), (episode.READOUT_TASK, 181, 120, False),
    (episode.READOUT_TASK, 180, 121, False)])
def test_delegated_worker_budgets_preserve_task_specific_caps(tmp_path, monkeypatch, task, science, fit, allowed):
    """Exercise the route's cap gate; stub enrollment/launch, never execute jobs."""
    from test_provider_episode import config as historical_config
    from eegfm.evaluation.public_workbench import MODE
    value = config(tmp_path) if task == TASK else historical_config(tmp_path)
    value.update(episode_id="episode", run_id="run", case_root=str(tmp_path / "case"),
                 trusted_root=str(tmp_path / "private"), budget_path=str(tmp_path / "budget"))
    public = tmp_path / "public"
    public.mkdir()
    (public / "PUBLIC_MANIFEST.json").write_text("{}")
    for key, name in (("train_input", "train.npz"), ("public_validation_input", "validation.npz")):
        (public / name).write_bytes(Path(value[key]["path"]).read_bytes())
    aggregate = SimpleNamespace(train_truth=episode.binding(value["train_truth"]),
        truth={s: episode.binding(v) for s, v in value["truth_by_split"].items()},
        inference={s: episode.binding(v) for s, v in value["inference_by_split"].items()}, source_bindings=[])
    if task == TASK: aggregate.qualification = episode.binding(value["residual_data_qualification"])
    else: aggregate.test_cohort = episode.binding(value["test_cohort"])
    cloud = {"config": value["split_manifest"], "known_hosts": value["split_manifest"],
             "host": "synthetic", "port": 22, "user": "synthetic", "python": "/python", "code": "/code"}
    value.update(cloud_worker=cloud, public_fit_worker=cloud)
    class PassedBudgetGate(Exception): pass
    def stop_enrollment(): raise PassedBudgetGate
    scientific = SimpleNamespace(timeout=science, identity={}, _enrollment=stop_enrollment)
    fitter = SimpleNamespace(timeout=fit, identity={"episode_id": "episode", "run_id": "run",
        "public_manifest_sha256": digest_file(public / "PUBLIC_MANIFEST.json"),
        "worker": {"public_artifact_mode": MODE, "allowed_splits": ["validation"]}})
    workers = iter([scientific, fitter])
    monkeypatch.setattr(episode, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(episode, "prepare_public", lambda *args: public)
    monkeypatch.setattr(episode, "load_aggregator", lambda *args, **kwargs: aggregate)
    monkeypatch.setattr(episode, "validate_cloud_bindings", lambda *args: None)
    monkeypatch.setattr(ssh_worker, "scientific_identity", lambda *args, **kwargs: {})
    monkeypatch.setattr(ssh_worker, "SshWorkerEvaluator", lambda **kwargs: next(workers))
    if allowed:
        with pytest.raises(PassedBudgetGate): episode.run_delegated_episode(value)
    else:
        with pytest.raises(ValueError, match="timeout exceeds task allocation"): episode.run_delegated_episode(value)


@pytest.mark.parametrize("edit", ["missing", "duplicate", "extra", "mismatch", "false_check"])
def test_exact_qualification_roles(tmp_path, edit):
    value = config(tmp_path)
    path = Path(value["residual_data_qualification"]["path"])
    receipt = json.loads(path.read_text())
    if edit == "missing": receipt["bindings"].pop()
    if edit == "duplicate": receipt["bindings"].append(receipt["bindings"][0])
    if edit == "extra": receipt["bindings"].append({"role": "cohort", "sha256": "a" * 64})
    if edit == "mismatch": receipt["bindings"][0]["sha256"] = "a" * 64
    if edit == "false_check": receipt["checks"]["joins_exact"] = False
    path.write_bytes(canonical_bytes(receipt))
    value["residual_data_qualification"]["sha256"] = digest_file(path)
    with pytest.raises(ValueError): episode.validate_residual_qualification(value)


def test_trusted_identity_artifact_release(tmp_path):
    aggregate, output, spec, _ = _fixture(tmp_path)
    result = aggregate(output, spec)
    worker = object.__new__(SandboxedWorkerEvaluator)
    worker.aggregate = aggregate
    artifact = worker._residual_validation_identity_artifact(output, result, spec)
    assert artifact == {"path": "baseline_identity.json", "sha256": digest_file(output / "baseline_identity.json")}
    released = {"status": "succeeded", "split": "validation", "artifacts": [artifact]}
    assert episode.residual_baseline_identity_sha(released) == artifact["sha256"]
    for artifacts in ([], [artifact, artifact], [{**artifact, "path": "nested/baseline_identity.json"}]):
        with pytest.raises(ValueError): episode.residual_baseline_identity_sha({**released, "artifacts": artifacts})
    worker.aggregate = SimpleNamespace()
    assert worker._residual_validation_identity_artifact(output, result, spec) is None


@pytest.mark.parametrize("phase", ["baseline", "final"])
def test_visible_evidence_matches_trusted_statistics(tmp_path, phase):
    aggregate, output, spec, _ = _fixture(tmp_path, phase)
    metrics = aggregate(output, spec)["metrics"]
    scored = json.loads((output / "trusted_residual_recovery_analysis.json").read_text())["statistics"]
    assert metrics["leace__linear__column0_r2"] == scored["views"]["leace"]["linear"]["per_column_r2"][0]
    assert metrics["train_mean__column0_r2"] == scored["views"]["identity"]["train_mean"]["per_column_r2"][0]
    assert metrics["target_column0_included"] == 1
    assert metrics["leace__linear_minus_shuffled__ci95_low"] == scored["contrasts"]["leace"]["linear_minus_shuffled"]["ci95"][0]
    assert metrics["loo_p0__valid"] == 1
    assert metrics["loo_p0__leace_linear_r2"] == scored["leave_one_participant_out"][0]["views"]["leace"]["linear"]
    assert ("loo_p0__primary_delta" in metrics) == (phase == "final")
    assert not any("train_mean__column" in k and k.startswith("identity") for k in metrics)


def controller_state(tmp_path):
    case = tmp_path / "case"
    (case / "output/candidate").mkdir(parents=True)
    (case / "output/candidate/main.py").write_text("pass\n")
    controller = episode.EpisodeController(trusted_root=tmp_path / "trusted", case_root=case,
        episode_id="episode", run_id="run", public_manifest_sha256="a" * 64,
        split_manifest_sha256="b" * 64, evaluator=SimpleNamespace(sandboxed=True), task_id=TASK)
    with controller._transaction() as db:
        state = controller._load(db)
    state.update(status="working", contract={"sha256": "c" * 64}, review={"approved": True})
    for operation, count in (("baseline", 2), ("attempt", 4)):
        response, job = controller._dispatch(state, operation, {"candidate_dir": "candidate", "split": "validation", "title": operation})
        metrics = {"model_count": count, "view_count": 5, "target_count": 6,
                   "numeric_scope_complete": float(count == 4), "baseline_only": float(count == 2),
                   "registered_useful_effect": 0.0}
        job.update(status="succeeded", result={"job_id": job["job_id"], "candidate_digest": job["candidate_digest"],
            "split": "validation", "status": "succeeded", "metrics": metrics,
            "artifacts": [{"path": "baseline_identity.json", "sha256": "d" * 64}]})
        state["attempts"][-1].update(status="evaluated", metrics=metrics)
        state["status"] = "working"
    return controller, state, {k: state["attempts"][-1]["id" if k == "attempt_id" else k] for k in ("attempt_id", "candidate_digest")}


@pytest.mark.parametrize("bad", [None, "mismatch", "missing", "duplicate", "different_job", "wrong_count", "candidate", "baseline_lock"])
def test_lock_requires_actual_job_fingerprint_parity(tmp_path, bad):
    controller, state, payload = controller_state(tmp_path)
    job = state["jobs"][state["attempts"][-1]["jobs"][0]]
    result = job["result"]
    if bad == "mismatch": result["artifacts"][0]["sha256"] = "e" * 64
    if bad == "missing": result["artifacts"] = []
    if bad == "duplicate": result["artifacts"] *= 2
    if bad == "different_job": result["job_id"] = "different-job"
    if bad == "wrong_count": result["metrics"]["model_count"] = 2
    if bad == "candidate": result["candidate_digest"] = "e" * 64
    if bad == "baseline_lock": payload["attempt_id"] = state["attempts"][0]["id"]
    before = copy.deepcopy(state)
    if bad:
        with pytest.raises(ValueError): controller._dispatch(state, "lock", payload)
        assert state == before
        assert not (controller.run / "locks.jsonl").exists()
    else:
        assert state["identity"]["max_attempts"] == 1
        with pytest.raises(ValueError): controller._dispatch(state, "test", {"candidate_digest": payload["candidate_digest"], "split": "test"})
        with pytest.raises(ValueError): controller._dispatch(state, "attempt", {"candidate_dir": "candidate", "split": "validation", "title": "extra"})
        assert controller._dispatch(state, "lock", payload)[0]["status"] == "locked"
        _, final = controller._dispatch(state, "test", {"candidate_digest": payload["candidate_digest"], "split": "test"})
        final.update(status="succeeded", result={"metrics": result["metrics"], "status": "succeeded"})
        state.update(status="working", sessions=[{"ok": True}])
        with pytest.raises(ValueError): controller._dispatch(state, "test", {"candidate_digest": payload["candidate_digest"], "split": "test"})
        controller._completion_ready(state)
        final["result"]["metrics"] = {**result["metrics"], "model_count": 2}
        with pytest.raises(ValueError, match="four-model"): controller._completion_ready(state)


RUNTIME = {"schema_version": "readout_host_runtime_v1",
           "python": {"implementation": "CPython", "version": "fixture", "executable_sha256": "a" * 64},
           "packages": {"numpy": "fixture", "scipy": "fixture", "sklearn": "fixture"},
           "modules": {"numpy": "b" * 64}, "libraries": [], "verifier_source_sha256": "c" * 64}


def worker_fixture(tmp_path, monkeypatch, phase="baseline", split="validation", forged=False):
    """Real evaluator and scorer; only container execution/process identity mocked."""
    from eegfm.evaluation.bundle import create_public_bundle
    from eegfm.agent import processes
    aggregate, output, spec, _ = _fixture(tmp_path, phase, split)
    source = tmp_path / "public-source"
    (source / "resources").mkdir(parents=True)
    for name, item in aggregate.public.items():
        (source / (name + ".npz")).write_bytes(item.path.read_bytes())
    (source / "eeg_api.py").write_text("# synthetic cached API\n")
    (source / "resources/CACHE_SCHEMA.json").write_text("{}")
    bundle = tmp_path / "public"
    create_public_bundle(source, bundle, ["train.npz", "validation.npz", "eeg_api.py", "resources/CACHE_SCHEMA.json"],
                         task_id=TASK, tier="synthetic_mechanism")
    split_path = tmp_path / "split.json"
    split_path.write_text("{}")
    proof = json.loads(aggregate.qualification.path.read_text())
    next(item for item in proof["bindings"] if item["role"] == "split_manifest")["sha256"] = digest_file(split_path)
    aggregate.qualification.path.write_bytes(canonical_bytes(proof))
    aggregate = ResidualRecoveryAggregator(aggregate.truth, aggregate.train_truth, aggregate.inference,
        public_by_split={s: FileBinding(bundle / (s + ".npz"), item.sha256) for s, item in aggregate.public.items()},
        qualification=FileBinding(aggregate.qualification.path, digest_file(aggregate.qualification.path)), runtime_identity=RUNTIME)
    (spec.candidate_dir / "main.py").write_text("# process execution is mocked\n")
    spec = replace(spec, candidate_digest=candidate_digest(spec.candidate_dir),
                   split_manifest_sha256=digest_file(split_path), public_manifest_sha256=digest_file(bundle / "PUBLIC_MANIFEST.json"))
    prediction_bytes = (output / "results.npz").read_bytes()
    def execute(job, *args):
        (job / "out/results.npz").write_bytes(prediction_bytes)
        if forged:
            (job / "out/baseline_identity.json").write_text('{}')
        return {"status": "completed", "exit_code": 0, "process_cleanup": {"surviving_owned_pids": []},
                "container_cleanup": "verified_removed"}
    backend = SimpleNamespace(inspect_image=lambda: {"image": "fixture"}, execute=execute)
    docker = tmp_path / "docker"
    docker.write_text("synthetic executable")
    monkeypatch.setattr(processes, "process_info", lambda pid: {"start": "synthetic"})
    with patch("eegfm.evaluation.worker.sys.platform", "linux"), patch("eegfm.evaluation.docker_worker.DockerBackend", return_value=backend):
        worker = SandboxedWorkerEvaluator(private_root=tmp_path / "worker", public_root=bundle,
            public_manifest_sha256=spec.public_manifest_sha256, split_manifest_path=split_path,
            split_manifest_sha256=spec.split_manifest_sha256,
            inputs_by_split={s: SplitInputs(aggregate.public["train"], item) for s, item in aggregate.inference.items()},
            runtime=RuntimeConfig(None, Path("/usr/bin/python"), backend="docker", docker=docker,
                                  docker_image="sha256:" + "a" * 64),
            aggregate=aggregate, released_metrics=aggregate.released_metrics, aggregate_bindings=aggregate.bindings,
            aggregate_policy_sha256=aggregate.policy_sha256, timeout_seconds=90)
    return worker, spec


@pytest.mark.parametrize("phase,split,forged", [("baseline", "validation", False), ("final", "validation", False),
                                               ("final", "test", False), ("baseline", "validation", True)])
def test_actual_worker_result_survives_ssh_and_controller(tmp_path, monkeypatch, phase, split, forged):
    worker, spec = worker_fixture(tmp_path, monkeypatch, phase, split, forged)
    result = worker.submit(spec)
    if forged:
        assert result["status"] == "failed"
        assert result["artifacts"] == []
        return
    assert result["status"] == "succeeded", (worker.job_directory(spec.job_id) / "receipt.json").read_text()
    assert {item["path"] for item in result["artifacts"]} == ({"released_metrics.json", "baseline_identity.json"}
                                                           if split == "validation" else {"released_metrics.json"})
    assert "public_artifacts" not in result
    assert worker._enrollment()["validation_identity_release"] == "residual_baseline_identity_hash_v1"
    assert worker.aggregate.scoring_policy["validation_identity_release"] == "residual_baseline_identity_hash_v1"
    # Use actual SSH result acceptance and durable terminal immutability, with no SSH process.
    remote = object.__new__(ssh_worker.SshWorkerEvaluator)
    remote.database = tmp_path / "ssh.sqlite3"
    with sqlite3.connect(remote.database) as db:
        db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY,result TEXT)")
        db.execute("INSERT INTO jobs VALUES (?,NULL)", (spec.job_id,))
    record = {name: getattr(spec, name) for name in ssh_worker.SPEC_FIELDS}
    assert remote._accept(record, result) == result
    with pytest.raises(ValueError): remote._accept(record, {**result, "job_id": "another-job"})
    case = tmp_path / "actor"
    (case / "output").mkdir(parents=True)
    controller = episode.EpisodeController(trusted_root=tmp_path / "control", case_root=case, episode_id="episode",
        run_id="run", evaluator=worker, task_id=TASK, public_manifest_sha256=worker.public_hash,
        split_manifest_sha256=worker.split_hash)
    import shutil
    shutil.copytree(spec.candidate_dir, controller.run / "candidates" / spec.candidate_digest)
    with controller._transaction() as db:
        state = controller._load(db)
        state["attempts"] = [{"id": spec.attempt_id, "kind": "baseline" if phase == "baseline" else "iteration",
                              "candidate_digest": spec.candidate_digest, "status": "submitted", "jobs": [spec.job_id]}]
        state["jobs"][spec.job_id] = {"job_id": spec.job_id, "attempt_id": spec.attempt_id,
            "candidate_digest": spec.candidate_digest, "split": split, "status": "dispatching"}
        controller._save(db, state)
    controller._accept_result(spec.job_id, result)
    with controller._transaction() as db:
        accepted = controller._load(db)["jobs"][spec.job_id]["result"]
    assert accepted == result
    if split == "validation":
        assert episode.residual_baseline_identity_sha(accepted) == digest_file(worker.job_directory(spec.job_id) / "out/baseline_identity.json")
        projection = controller.projection()
        assert projection["attempts"][0]["metrics"]["leace__linear__column0_r2"] == .75


@pytest.mark.parametrize("bad", ["missing", "duplicate", "alternate", "sha", "noncanonical", "schema"])
def test_release_rejects_invalid_scorer_manifest_or_file(tmp_path, bad):
    aggregate, output, spec, _ = _fixture(tmp_path)
    aggregated = aggregate(output, spec)
    item = next(item for item in aggregated["artifacts"] if item["path"] == "baseline_identity.json")
    path = output / item["path"]
    if bad == "missing": aggregated["artifacts"].remove(item)
    if bad == "duplicate": aggregated["artifacts"].append(item)
    if bad == "alternate": item["path"] = "sub/baseline_identity.json"
    if bad == "sha": item["sha256"] = "0" * 64
    if bad == "noncanonical": path.write_bytes(path.read_bytes() + b"\n"); item["sha256"] = digest_file(path)
    if bad == "schema":
        doc = json.loads(path.read_text()); doc["schema_version"] = "wrong"
        path.write_bytes(canonical_bytes(doc)); item["sha256"] = digest_file(path)
    worker = object.__new__(SandboxedWorkerEvaluator); worker.aggregate = aggregate
    with pytest.raises(ValueError): worker._residual_validation_identity_artifact(output, aggregated, spec)


def enrolled_config(worker, tmp_path):
    def bound(item): return {"path": str(item.path), "sha256": item.sha256}
    agg = worker.aggregate
    return {"schema_version": "ssh_residual_recovery_worker_v1", "task_id": TASK,
            "episode_id": "episode", "run_id": "run", "public_root": str(worker.public),
            "private_root": str(tmp_path / "loaded-worker"), "staging_root": str(tmp_path / "staging"),
            "public_manifest_sha256": worker.public_hash, "split_manifest": {"path": str(worker.split_path), "sha256": worker.split_hash},
            "truth_by_split": {s: bound(item) for s, item in agg.truth.items()}, "train_truth": bound(agg.train_truth),
            "inference_by_split": {s: bound(item) for s, item in agg.inference.items()},
            "residual_data_qualification": bound(agg.qualification), "aggregate_runtime": RUNTIME,
            "inputs_by_split": {s: {"train": bound(pair.train), "evaluation": bound(pair.evaluation)} for s, pair in worker.inputs.items()},
            "runtime": {"python": "/usr/bin/python", "docker": str(worker.runtime.docker),
                        "image": worker.runtime.docker_image, "host": worker.runtime.docker_host}}


def test_residual_ssh_registration_exact_scorer_runtime_roles_policy_and_timeout(tmp_path, monkeypatch):
    worker, spec = worker_fixture(tmp_path, monkeypatch)
    config = enrolled_config(worker, tmp_path)
    path = tmp_path / "ssh-config.json"
    def load(value):
        path.write_bytes(canonical_bytes(value))
        with patch.object(ssh_worker, "verify_readout_runtime") as verify, patch.object(ssh_worker, "SandboxedWorkerEvaluator") as factory, patch("eegfm.evaluation.docker_worker.DockerBackend"):
            ssh_worker.load_worker(FileBinding(path, digest_file(path)))
            assert verify.call_count == 1
            return factory.call_args.kwargs
    kwargs = load(config)
    assert type(kwargs["aggregate"]) is ResidualRecoveryAggregator
    assert kwargs["timeout_seconds"] == 120
    identity = ssh_worker.scientific_identity(config, aggregate=kwargs["aggregate"],
        public_manifest_sha256=worker.public_hash, split_manifest_sha256=worker.split_hash)
    assert set(identity["scoring_policy"]["role_sha256"]) == {"public_train", "public_validation", "truth_train",
        "truth_validation", "truth_test", "inference_validation", "inference_test", "split_manifest"}
    assert "test_cohort_sha256" not in identity
    assert identity["aggregate_runtime"]["schema_version"] == "readout_host_runtime_v1"
    assert identity["scoring_policy"]["released_metrics"] == sorted(worker.released_metrics)
    remote = {**identity, "worker": worker._enrollment()}
    episode.validate_cloud_bindings(remote, worker.aggregate.public["train"], worker.aggregate.inference["validation"],
        worker.aggregate.inference["test"], identity, episode.aggregator_source_sha256(TASK))
    for update in ({"schema_version": "ssh_readout_worker_v1"}, {"task_id": "unknown"},
                   {"timeout_seconds": 121}, {"bootstrap_resamples": 2},
                   {"inference_by_split": {**config["inference_by_split"], "train": config["inference_by_split"]["validation"]}}):
        with pytest.raises(ValueError): load({**config, **update})
    wrong = copy.deepcopy(config)
    wrong["inputs_by_split"]["test"]["evaluation"] = wrong["inputs_by_split"]["validation"]["evaluation"]
    with pytest.raises(ValueError): load(wrong)
    with pytest.raises(ValueError): ssh_worker.scientific_identity(config, aggregate=SimpleNamespace(),
        public_manifest_sha256=worker.public_hash, split_manifest_sha256=worker.split_hash)
    del remote["worker"]["validation_identity_release"]
    with pytest.raises(ValueError): episode.validate_cloud_bindings(remote, worker.aggregate.public["train"],
        worker.aggregate.inference["validation"], worker.aggregate.inference["test"], identity, episode.aggregator_source_sha256(TASK))


def test_release_policy_changes_enrollment_and_does_not_affect_other_collectors(tmp_path, monkeypatch):
    from eegfm.evaluation.public_workbench import PublicFitAggregator
    worker, spec = worker_fixture(tmp_path, monkeypatch)
    original = worker._enrollment()
    agg = worker.aggregate
    monkeypatch.setattr(ResidualRecoveryAggregator, "released_metrics", agg.released_metrics | {"synthetic_new_metric"})
    changed = ResidualRecoveryAggregator(agg.truth, agg.train_truth, agg.inference, public_by_split=agg.public,
                                        qualification=agg.qualification, runtime_identity=RUNTIME)
    assert changed.policy_sha256 != agg.policy_sha256
    worker.aggregate_policy_sha256 = changed.policy_sha256
    assert worker._enrollment() != original
    worker.aggregate = PublicFitAggregator(worker.public, worker.public_hash)
    assert "validation_identity_release" not in worker._enrollment()
    assert worker._residual_validation_identity_artifact(tmp_path, {}, spec) is None


@pytest.mark.parametrize("subclass", [False, True])
def test_lazy_collector_name_prefilter_never_authorizes_impostor_or_subclass(tmp_path, monkeypatch, subclass):
    worker, spec = worker_fixture(tmp_path, monkeypatch)
    bases = (ResidualRecoveryAggregator,) if subclass else ()
    collector = type("ResidualRecoveryAggregator", bases,
                     {"__module__": "eegfm.eeg.residual_recovery_aggregation"})
    worker.aggregate = object.__new__(collector)
    assert "validation_identity_release" not in worker._enrollment()
    assert worker._residual_validation_identity_artifact(tmp_path, {}, spec) is None


def test_worker_generated_baseline_and_final_results_can_lock_and_complete(tmp_path, monkeypatch):
    import numpy as np
    import shutil
    from test_residual_recovery_aggregation import _method
    worker, spec = worker_fixture(tmp_path, monkeypatch)
    case = tmp_path / "full-case"
    (case / "output").mkdir(parents=True)
    shutil.copytree(spec.candidate_dir, case / "output/baseline")
    shutil.copytree(spec.candidate_dir, case / "output/final")
    method, arrays = _method("final")
    (case / "output/final/method.json").write_bytes(canonical_bytes(method))
    np.savez_compressed(case / "output/final/parameters.npz", **arrays)
    controller = episode.EpisodeController(trusted_root=tmp_path / "full-control", case_root=case,
        episode_id="episode", run_id="run", evaluator=worker, task_id=TASK,
        public_manifest_sha256=worker.public_hash, split_manifest_sha256=worker.split_hash)
    with controller._transaction() as db:
        state = controller._load(db)
        state.update(status="working", contract={"sha256": "c" * 64}, review={"approved": True})
        controller._save(db, state)
    def request(operation, payload):
        return controller.handle({"request_id": operation, "episode_id": "episode", "operation": operation, "payload": payload})
    baseline = request("baseline", {"candidate_dir": "baseline", "split": "validation", "title": "baseline"})
    assert worker.poll(baseline["job_id"])["status"] == "succeeded"
    controller.poll_jobs()
    with np.load(tmp_path / "output/results.npz", allow_pickle=False) as archive:
        final_predictions = np.concatenate([archive["predictions"], archive["predictions"]], axis=2)
    def execute(job, fingerprint, split, *args):
        with np.load(worker.aggregate.inference[split].path, allow_pickle=False) as archive:
            np.savez_compressed(job / "out/results.npz", predictions=final_predictions, sample_ids=archive["sample_ids"])
        return {"status": "completed", "exit_code": 0, "process_cleanup": {"surviving_owned_pids": []},
                "container_cleanup": "verified_removed"}
    worker.docker.execute = execute
    iteration = request("attempt", {"candidate_dir": "final", "split": "validation", "title": "final"})
    controller.poll_jobs()
    baseline_result = worker.poll(baseline["job_id"])
    final_result = worker.poll(iteration["job_id"])
    assert final_result["status"] == "succeeded"
    assert episode.residual_baseline_identity_sha(baseline_result) == episode.residual_baseline_identity_sha(final_result)
    assert request("lock", {"attempt_id": iteration["attempt_id"], "candidate_digest": iteration["candidate_digest"]})["status"] == "locked"
    final = request("test", {"candidate_digest": iteration["candidate_digest"], "split": "test"})
    controller.poll_jobs()
    assert worker.poll(final["job_id"])["status"] == "succeeded"
    with controller._transaction() as db:
        state = controller._load(db)
    state["sessions"] = [{"ok": True}]  # Only lifecycle prerequisite; no real model execution claim.
    controller._completion_ready(state)


@pytest.mark.parametrize("alias", [None, "truth_train", "truth_validation", "truth_test", "inference_validation", "inference_test", "qualification", "split"])
def test_delegated_private_role_exclusion_without_public_cohort_fiction(tmp_path, monkeypatch, alias):
    worker, _ = worker_fixture(tmp_path, monkeypatch)
    value = enrolled_config(worker, tmp_path)
    value.update(schema_version="audited_coding_episode_v1", model=episode.MODEL, reasoning_effort="high", call_ids=["coding-1"],
                 public_source=str(tmp_path / "public-source"), public_files=["train.npz", "validation.npz", "eeg_api.py", "resources/CACHE_SCHEMA.json"],
                 condition="no_skill", case_root=str(tmp_path / "actor-case"), trusted_root=str(tmp_path / "trusted"),
                 budget_path=str(tmp_path / "budget.json"), cloud_worker={})
    value.update(train_input=value["inputs_by_split"]["validation"]["train"],
                 public_validation_input={"path": str(worker.aggregate.public["validation"].path), "sha256": worker.aggregate.public["validation"].sha256},
                 validation_input=value["inference_by_split"]["validation"], test_input=value["inference_by_split"]["test"])
    # Actual admission/scorer above; replace just path locations for the boundary check.
    public = episode.prepare_public(value, Path(value["case_root"]), Path(value["trusted_root"]))
    value["public_manifest_sha256"] = digest_file(public / "PUBLIC_MANIFEST.json")
    (Path(value["trusted_root"]) / "ENROLLMENT.json").write_text("{}")
    real_load = episode.load_aggregator
    def relocate(*args, **kwargs):
        aggregate = real_load(*args, **kwargs)
        assert set(aggregate.public) == {"train", "validation"}
        assert not hasattr(aggregate, "test_cohort")
        if alias:
            target = FileBinding(public / "train.npz", digest_file(public / "train.npz"))
            if alias == "truth_train": aggregate.train_truth = target
            elif alias.startswith("truth_"): aggregate.truth = {**aggregate.truth, alias[6:]: target}
            elif alias.startswith("inference_"): aggregate.inference = {**aggregate.inference, alias[10:]: target}
            elif alias == "qualification": aggregate.qualification = target
        return aggregate
    if alias == "split":
        # Admission can attest matching bytes; actor/private path overlap must still fail.
        original_binding = episode.binding
        def alias_split(record):
            result = original_binding(record)
            return FileBinding(public / "train.npz", result.sha256) if record == value["split_manifest"] else result
        monkeypatch.setattr(episode, "binding", alias_split)
    monkeypatch.setattr(episode, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(episode, "load_aggregator", relocate)
    class WorkerBoundary(Exception): pass
    monkeypatch.setattr(ssh_worker, "SshWorkerEvaluator", lambda **kw: (_ for _ in ()).throw(WorkerBoundary()))
    # Cloud configuration must be structurally valid to reach the constructor.
    value["cloud_worker"] = {"config": value["split_manifest"], "host": "fixture", "port": 22, "user": "fixture",
                             "known_hosts": value["train_input"], "python": "/python", "code": "/code"}
    if alias:
        with pytest.raises(ValueError, match="Private bindings"): episode.run_delegated_episode(value)
    else:
        with pytest.raises(WorkerBoundary): episode.run_delegated_episode(value)


def test_undefined_scalar_evidence_is_omitted_not_zero(tmp_path):
    import numpy as np
    def edit(name, truth, features, public):
        truth["y"][:, 0] = public["y"][:, 0] = 0
        if name != "train":
            truth["y"][:, 1:] = public["y"][:, 1:] = np.repeat([0., 0., 0., 0., 0., 1.], 24)[:, None]
    aggregate, output, spec, _ = _fixture(tmp_path, "final", input_edit=edit)
    metrics = aggregate(output, spec)["metrics"]
    assert metrics["target_column0_included"] == 0
    assert metrics["intervals_valid"] == 0
    assert metrics["loo_p5__valid"] == 0
    assert not any("ci95" in name or "column0_r2" in name for name in metrics)
    assert not any(name.startswith("loo_p5__") and name != "loo_p5__valid" for name in metrics)


@pytest.mark.parametrize("component", [None, "source", "recipe", "selection", "dtype", "shape", "value",
                                        "prediction", "shuffle_prediction", "public", "inference"])
def test_two_text_staged_fits_and_each_baseline_identity_component_guard_lock(tmp_path, component):
    """Tiny deterministic local fixture fits; no scientific/model worker launched."""
    import numpy as np
    import subprocess
    import sys
    from eegfm.evaluation import public_workbench as public
    from eegfm.eeg.residual_recovery import baseline_identity
    from test_residual_recovery_aggregation import _method, _array_schema
    from test_public_workbench import FakeWorker
    case = tmp_path / "fits"
    (case / "output").mkdir(parents=True)
    public_root = tmp_path / "fit-public"
    public_root.mkdir()
    np.savez(public_root / "train.npz", y=np.arange(48, dtype=np.float64).reshape(8, 6))
    linear_source = "import numpy as np\ndef fitted(y):\n    return np.mean(y, axis=0)\n"
    fit_source = '''import argparse, json
from pathlib import Path
import numpy as np
from linear import fitted
p=argparse.ArgumentParser();p.add_argument('--public');p.add_argument('--output');args=p.parse_args()
root=Path(__file__).parent
assert not list(root.rglob('parameters.npz'))
with np.load(Path(args.public)/'train.npz',allow_pickle=False) as z: mean=fitted(z['y'])
arrays={'linear__selected':np.zeros(5,dtype=np.int64),'linear__coef':mean,'linear_shuffled__coef':mean.copy()}
if json.loads((root/'method.json').read_text())['phase']=='final':
    arrays.update(flexible__selected=np.zeros(5,dtype=np.int64),flexible_shuffled__coef=mean.copy())
np.savez(Path(args.output)/'parameters.npz',**arrays)
'''
    class LocalSyntheticFit(FakeWorker):
        def submit(self, spec):
            self.submissions += 1
            self.spec = spec
            output = tmp_path / spec.job_id
            output.mkdir()
            assert not list(spec.candidate_dir.rglob("parameters.npz"))
            subprocess.run([sys.executable, "-B", str(spec.candidate_dir / "authored/fit.py"),
                "--public", str(public_root), "--output", str(output)], check=True, capture_output=True, timeout=10)
            return {"job_id": spec.job_id, "candidate_digest": spec.candidate_digest, "split": "validation",
                    "status": "succeeded", "public_artifacts": [public.encode_parameters(output / "parameters.npz")]}
    worker = LocalSyntheticFit("a" * 64)
    bench = public.PublicWorkbench(evaluator=worker, private_root=tmp_path / "fits-private", case_root=case,
        episode_id="episode", run_id="run", public_manifest_sha256="a" * 64, split_manifest_sha256="b" * 64)
    hashes = []
    for phase in ("baseline", "final"):
        candidate = case / "output" / phase
        (candidate / "old").mkdir(parents=True)
        (candidate / "linear.py").write_text(linear_source)
        (candidate / "fit.py").write_text(fit_source)
        (candidate / "main.py").write_text("# synthetic prediction fixture\n")
        # Existing artifacts at both depths must never become fit inputs.
        for dest in (candidate, candidate / "old"): np.savez(dest / "parameters.npz", stale=np.ones(1))
        method, params = _method(phase)
        mean = np.arange(48, dtype=np.float64).reshape(8, 6).mean(axis=0)
        for name in params:
            if not name.endswith("selected"): params[name] = mean.copy()
        method["parameter_schema"] = {name: _array_schema(array) for name, array in params.items()}
        (candidate / "method.json").write_bytes(canonical_bytes(method))
        np.savez(candidate / "parameters.npz", **params)
        assert bench.submit("fit-" + phase, phase)["status"] == "succeeded"
        with np.load(candidate / "parameters.npz", allow_pickle=False) as archive:
            fitted = {name: archive[name] for name in archive.files}
        assert all(np.array_equal(fitted[name], array) for name, array in params.items())
        models = 2 if phase == "baseline" else 4
        pred = np.broadcast_to(fitted["linear__coef"], (144, 5, models, 6)).copy()
        public_sha, inference_sha = "a" * 64, "b" * 64
        if phase == "final":
            if component == "source": (candidate / "linear.py").write_text(linear_source + "# changed\n")
            if component == "recipe": method["families"]["linear"]["recipes"]["identity"][0]["hyperparameters"]["alpha"] = 3
            if component == "selection": fitted["linear__selected"][0] = 1
            if component == "dtype": fitted["linear__coef"] = fitted["linear__coef"].astype(np.float32)
            if component == "shape": fitted["linear__coef"] = fitted["linear__coef"].reshape(2, 3)
            if component == "value": fitted["linear__coef"][0] += 1
            if component == "prediction": pred[0, 0, 0, 0] += 1
            if component == "shuffle_prediction": pred[0, 0, 1, 0] += 1
            if component == "public": public_sha = "e" * 64
            if component == "inference": inference_sha = "e" * 64
            method["parameter_schema"] = {name: _array_schema(array) for name, array in fitted.items()}
        document = baseline_identity(candidate, method, fitted, pred, public_manifest_sha256=public_sha, inference_sha256=inference_sha)
        import hashlib
        hashes.append(hashlib.sha256(canonical_bytes(document)).hexdigest())
    controller, state, payload = controller_state(tmp_path / "lock")
    for attempt, sha in zip(state["attempts"], hashes):
        state["jobs"][attempt["jobs"][0]]["result"]["artifacts"][0]["sha256"] = sha
    before = copy.deepcopy(state)
    if component:
        with pytest.raises(ValueError, match="parity"): controller._dispatch(state, "lock", payload)
        assert state == before
    else:
        assert controller._dispatch(state, "lock", payload)[0]["status"] == "locked"
    assert worker.submissions == 2
