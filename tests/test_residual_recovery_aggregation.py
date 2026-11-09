from dataclasses import replace
import hashlib
import io
import json
import zipfile

import numpy as np
import pytest

from eegfm.agent.controller import EvaluationSpec
from eegfm.eeg.residual_recovery import baseline_identity, validate_method_manifest, validate_qualification
from eegfm.eeg.residual_recovery_aggregation import ResidualRecoveryAggregator
from eegfm.evaluation.bundle import canonical_bytes, digest_file
from eegfm.evaluation.worker import FileBinding, candidate_digest

VIEWS = ("identity", "leace", "random_2301", "random_2302", "random_2303")
PROVENANCE = (
    "input_manifest", "pooling_source", "join_source", "feature_registry", "backbone_identity",
    "export_identity", "api_source", "preparer_source", "shuffle_permutation", "checks_receipt",
)
CHECKS = ("source_versions_match", "joins_exact", "split_disjoint", "eraser_checks_passed", "pooling_parity_passed")
PUBLIC_SHA = "a" * 64
SPLIT_SHA = "b" * 64


def _method(phase="baseline"):
    recipes = {view: [{"preprocessing": {}, "hyperparameters": {"alpha": 1}},
                      {"preprocessing": {}, "hyperparameters": {"alpha": 2}}] for view in VIEWS}
    families = {"linear": {"description": "linear declaration", "recipes": recipes}}
    parameters = {"linear__selected": np.zeros(5, dtype=np.int64),
                  "linear__coef": np.ones((2, 3)),
                  "linear_shuffled__coef": np.zeros((2, 3))}
    if phase == "final":
        families["flexible"] = {"description": "flexible declaration", "recipes": recipes.copy()}
        parameters["flexible__selected"] = np.zeros(5, dtype=np.int64)
        parameters["flexible_shuffled__coef"] = np.zeros((2, 3))
    return {"schema_version": "residual_recovery_method_v1", "phase": phase,
            "baseline_sources": ["linear.py"], "families": families,
            "parameter_schema": {name: _array_schema(array) for name, array in parameters.items()}}, parameters


def _array_schema(array):
    return {"dtype": array.dtype.name, "shape": list(array.shape), "purpose": "test fixture"}


def _npz(path, **data):
    np.savez_compressed(path, **data)
    return FileBinding(path, digest_file(path))


def _receipt(roles):
    return {"schema_version": "residual_recovery_qualification_v1",
            "status": "cached_residual_inputs_qualified_for_development",
            "task_id": "eegmat-residual-recovery-v1", "not_project_unseen_confirmation": True,
            "bindings": [{"role": role, "sha256": sha} for role, sha in roles.items()],
            "source_provenance": {name + "_sha256": "c" * 64 for name in PROVENANCE},
            "checks": dict.fromkeys(CHECKS, True)}


def _fixture(tmp, phase="baseline", split="validation", *, input_edit=None, result_edit=None):
    public, truth, inference, roles = {}, {}, {}, {}
    splits = {}
    for name, subjects in (("train", 12), ("validation", 6), ("test", 6)):
        rows = subjects * 24
        ids = np.array([f"{name}-s{i}" for i in range(rows)])
        people = np.repeat([f"{name}-p{i}" for i in range(subjects)], 24)
        y = np.tile(np.resize([-1., 1.], rows)[:, None], (1, 6))
        x = np.zeros((rows, 5, 200))
        t = {"sample_ids": ids, "subject_ids": people, "y": y}
        features = {"sample_ids": ids.copy(), "subject_ids": people.copy(), "x": x}
        p = {**{key: value.copy() for key, value in features.items()}, "y": y.copy()}
        if input_edit:
            input_edit(name, t, features, p)
        truth[name] = _npz(tmp / f"truth-{name}.npz", **t)
        if name != "train":
            inference[name] = _npz(tmp / f"inference-{name}.npz", **features)
        if name != "test":
            public[name] = _npz(tmp / f"public-{name}.npz", **p)
        splits[name] = y, ids

    roles.update({f"truth_{name}": item.sha256 for name, item in truth.items()})
    roles.update({f"inference_{name}": item.sha256 for name, item in inference.items()})
    roles.update({f"public_{name}": item.sha256 for name, item in public.items()})
    roles["split_manifest"] = SPLIT_SHA
    qualification_path = tmp / "qualification.json"
    qualification_path.write_bytes(canonical_bytes(_receipt(roles)))
    candidate = tmp / "candidate"
    candidate.mkdir()
    # It is legitimate for the statistical scorer to read this as source text,
    # but an accidental import would raise before any report is written.
    (candidate / "linear.py").write_text("raise RuntimeError('must never execute')\n")
    method, params = _method(phase)
    (candidate / "method.json").write_bytes(canonical_bytes(method))
    _npz(candidate / "parameters.npz", **params)

    output = tmp / "output"
    output.mkdir()
    y, ids = splits[split]
    models = 2 if phase == "baseline" else 4
    predictions = np.broadcast_to(y[:, None, None, :], (len(y), 5, models, 6)).copy()
    predictions[:, :, 0, :] += .5
    predictions[:, :, 1::2, :] += 2
    results = {"predictions": predictions, "sample_ids": ids}
    if result_edit:
        result_edit(results)
    _npz(output / "results.npz", **results)
    spec = EvaluationSpec("job", "episode", "run", "attempt", split, candidate, candidate_digest(candidate),
                          SPLIT_SHA, PUBLIC_SHA)
    runtime_checks = []
    aggregator = ResidualRecoveryAggregator(
        {name: truth[name] for name in ("validation", "test")}, truth["train"], inference,
        public_by_split=public, qualification=FileBinding(qualification_path, digest_file(qualification_path)),
        runtime_identity={"runtime": "synthetic"}, verify_runtime=lambda: runtime_checks.append(True),
    )
    return aggregator, output, spec, runtime_checks


@pytest.mark.parametrize("phase, split", [("baseline", "validation"), ("final", "validation"), ("final", "test")])
def test_exact_regression_artifacts(tmp_path, phase, split):
    agg, output, spec, runtime_checks = _fixture(tmp_path, phase, split)
    expected = {"results.npz", "trusted_residual_recovery_analysis.json"}
    if split == "validation":
        expected.add("baseline_identity.json")
    result = agg(output, spec)
    assert runtime_checks == [True, True]
    assert {item["path"] for item in result["artifacts"]} == expected
    assert {file.name for file in output.iterdir()} == expected
    assert all(item["sha256"] == digest_file(output / item["path"]) for item in result["artifacts"])
    with np.load(output / "results.npz", allow_pickle=False) as data:
        assert set(data.files) == {"predictions", "sample_ids"}
    metrics = result["metrics"]
    assert metrics["model_count"] == (2 if phase == "baseline" else 4)
    assert metrics["baseline_only"] == (phase == "baseline")
    assert metrics["numeric_scope_complete"] == (phase == "final")
    assert metrics["bootstrap_valid"] == 10000
    assert metrics["leace__linear__r2"] == .75
    assert set(metrics) <= agg.released_metrics
    assert ("primary_delta" in metrics) == (phase == "final")
    assert ("leace__flexible__r2" in metrics) == (phase == "final")
    assert metrics["registered_useful_effect"] == (phase == "final")
    policy = agg.scoring_policy
    assert policy["schema_version"] == "residual_recovery_metric_policy_v1"
    assert agg.policy_sha256 == hashlib.sha256(canonical_bytes(policy)).hexdigest()
    assert policy["qualification"]["receipt"]["source_provenance"]["checks_receipt_sha256"] == "c" * 64
    assert "test-p0" not in (output / "trusted_residual_recovery_analysis.json").read_text()


@pytest.mark.parametrize("bad", ["extra", "dtype", "models", "order", "nan", "ids", "duplicate"])
def test_rejects_invalid_prediction_archive(tmp_path, bad):
    def edit(data):
        if bad == "extra":
            data["y"] = data["predictions"][:, 0, 0]
        elif bad == "dtype":
            data["predictions"] = data["predictions"].astype(np.float32)
        elif bad == "models":
            data["predictions"] = np.repeat(data["predictions"], 2, axis=2)
        elif bad == "order":
            data["sample_ids"] = data["sample_ids"][::-1]
        elif bad == "nan":
            data["predictions"][0, 0, 0, 0] = np.nan
        elif bad == "ids":
            data["sample_ids"] = data["sample_ids"].astype("S")

    agg, output, spec, _ = _fixture(tmp_path, result_edit=edit)
    if bad == "duplicate":
        with zipfile.ZipFile(output / "results.npz", "a") as archive:
            original = archive.read("sample_ids.npy")
            with pytest.warns(UserWarning, match="Duplicate"):
                archive.writestr("sample_ids.npy", original)
    with pytest.raises(ValueError):
        agg(output, spec)
    assert {path.name for path in output.iterdir()} == {"results.npz"}


@pytest.mark.parametrize("bad", ["validation_x", "train_y", "inference_order", "participants", "overlap", "sample_overlap",
                                 "duplicate_samples", "extra_inference", "dtype"])
def test_qualification_does_not_override_invalid_trusted_joins(tmp_path, bad):
    def edit(split, truth, inference, public):
        if bad == "train_y" and split == "train":
            public["y"][0, 0] += 1
        if bad == "validation_x" and split == "validation":
            public["x"][0, 0, 0] = 1
        if split != "test":
            return
        if bad == "inference_order":
            inference["sample_ids"] = inference["sample_ids"][::-1]
        elif bad == "participants":
            inference["subject_ids"][0] = "test-p1"
        elif bad == "overlap":
            inference["subject_ids"] = truth["subject_ids"] = truth["subject_ids"].astype("U16")
            truth["subject_ids"][:24] = "train-p0"
        elif bad == "sample_overlap":
            inference["sample_ids"][0] = truth["sample_ids"][0] = "train-s0"
        elif bad == "duplicate_samples":
            inference["sample_ids"][0] = truth["sample_ids"][0] = truth["sample_ids"][1]
        elif bad == "extra_inference":
            inference["y"] = truth["y"]
        elif bad == "dtype":
            inference["x"] = inference["x"].astype(np.float32)

    agg, output, spec, _ = _fixture(tmp_path, input_edit=edit)
    with pytest.raises(ValueError):
        agg(output, spec)


def test_rejects_actor_fingerprint_before_scoring(tmp_path):
    agg, output, spec, runtime_checks = _fixture(tmp_path)
    (output / "baseline_identity.json").write_text("{}")
    with pytest.raises(ValueError, match="exactly results.npz"):
        agg(output, spec)
    assert runtime_checks == []


def test_rejects_wrong_split_hash_and_baseline_test(tmp_path):
    agg, output, spec, _ = _fixture(tmp_path, split="test")
    with pytest.raises(ValueError, match="qualification.*binding"):
        agg(output, replace(spec, split_manifest_sha256="0" * 64))
    with pytest.raises(ValueError, match="final"):
        agg(output, spec)


@pytest.mark.parametrize("edit", ["duplicate", "extra_role", "false_check", "provenance", "wrong_hash", "coercion"])
def test_qualification_exact_attestation(edit):
    roles = {name: "1" * 64 for name in ("public_train", "public_validation", "inference_validation",
             "inference_test", "truth_train", "truth_validation", "truth_test", "split_manifest")}
    receipt = _receipt(roles)
    assert validate_qualification(receipt, roles) == receipt
    if edit == "duplicate":
        receipt["bindings"][-1] = receipt["bindings"][0]
    elif edit == "extra_role":
        receipt["bindings"].append({"role": "inference_train", "sha256": "1" * 64})
    elif edit == "false_check":
        receipt["checks"]["joins_exact"] = False
    elif edit == "provenance":
        del receipt["source_provenance"]["pooling_source_sha256"]
    elif edit == "wrong_hash":
        receipt["bindings"][0]["sha256"] = "2" * 64
    elif edit == "coercion":
        receipt["not_project_unseen_confirmation"] = 1
    with pytest.raises(ValueError):
        validate_qualification(receipt, roles)


@pytest.mark.parametrize("bad", ["duplicate_json", "nonfinite_json", "oversize_json", "extra_parameter",
                                 "duplicate_parameter", "rank", "expanded", "compressed", "elements",
                                 "recipe_count", "selected", "selected_dtype", "source_escape", "binary_source"])
def test_bounded_method_parameters_and_source(tmp_path, bad):
    agg, output, spec, _ = _fixture(tmp_path)
    candidate = spec.candidate_dir
    method, params = _method()
    if bad == "oversize_json":
        method["families"]["linear"]["description"] = "z" * 65536
    elif bad == "extra_parameter":
        params["linear__undeclared"] = np.zeros(1)
    elif bad == "rank":
        params["linear__coef"] = np.zeros((1, 1, 1, 1, 1))
    elif bad == "expanded":
        params["linear__coef"] = np.zeros(600000)
        params["linear_shuffled__coef"] = np.zeros(600000)
    elif bad == "compressed":
        params["linear__coef"] = np.random.default_rng(1).normal(size=150000)
    elif bad == "elements":
        params["linear__coef"] = np.zeros(1000001, dtype=np.uint8)
    elif bad == "recipe_count":
        recipes = method["families"]["linear"]["recipes"]["identity"]
        recipes.extend(recipes + recipes[:1])
    elif bad == "selected":
        params["linear__selected"][0] = 2
    elif bad == "selected_dtype":
        params["linear__selected"] = np.zeros(5, dtype=np.int32)
    elif bad == "source_escape":
        method["baseline_sources"] = ["../linear.py"]
    elif bad == "binary_source":
        method["baseline_sources"] = ["parameters.npz"]
    for name in set(params) & set(method["parameter_schema"]):
        method["parameter_schema"][name] = _array_schema(params[name])
    encoded = canonical_bytes(method)
    if bad == "duplicate_json":
        encoded = b'{"phase":"baseline",' + encoded[1:]
    elif bad == "nonfinite_json":
        encoded = encoded.replace(b'"alpha":1', b'"alpha":1e999')
    (candidate / "method.json").write_bytes(encoded)
    _npz(candidate / "parameters.npz", **params)
    if bad == "duplicate_parameter":
        with zipfile.ZipFile(candidate / "parameters.npz", "a") as archive:
            data = archive.read("linear__coef.npy")
            with pytest.warns(UserWarning, match="Duplicate"):
                archive.writestr("linear__coef.npy", data)
    with pytest.raises(ValueError):
        agg(output, replace(spec, candidate_digest=candidate_digest(candidate)))


@pytest.mark.parametrize("change", ["source", "recipe", "selection", "dtype", "shape", "value", "prediction",
                                    "shuffle_prediction", "public_rows", "inference_rows", "flexible"])
def test_fingerprint_changes_only_for_bound_baseline_inputs(tmp_path, change):
    (tmp_path / "linear.py").write_text("x = 1\n")
    method, params = _method()
    pred = np.zeros((144, 5, 2, 6))
    hashes = {"public_manifest_sha256": PUBLIC_SHA, "inference_sha256": "d" * 64}
    reference = baseline_identity(tmp_path, validate_method_manifest(method), params, pred, **hashes)
    if change == "source":
        (tmp_path / "linear.py").write_text("x = 2\n")
    elif change == "recipe":
        method["families"]["linear"]["recipes"]["identity"][0]["hyperparameters"]["alpha"] = 9
    elif change == "selection":
        params["linear__selected"][0] = 1
    elif change == "dtype":
        params["linear__coef"] = params["linear__coef"].astype(np.float32)
    elif change == "shape":
        params["linear__coef"] = params["linear__coef"].reshape(3, 2)
    elif change == "value":
        params["linear__coef"][0, 0] += 1
    elif change == "prediction":
        pred[0, 0, 0, 0] = 1
    elif change == "shuffle_prediction":
        pred[0, 0, 1, 0] = 1
    elif change == "public_rows":
        hashes["public_manifest_sha256"] = "e" * 64
    elif change == "inference_rows":
        hashes["inference_sha256"] = "e" * 64
    elif change == "flexible":
        method, params = _method("final")
        params["flexible_shuffled__coef"] += 1
        pred = np.concatenate([pred, np.ones_like(pred)], axis=2)
    for name in params:
        method["parameter_schema"][name] = _array_schema(params[name])
    modified = baseline_identity(tmp_path, method, params, pred, **hashes)
    assert (canonical_bytes(modified) == canonical_bytes(reference)) == (change == "flexible")


def test_fingerprint_ignores_zip_order_and_enclosing_candidate_job(tmp_path):
    agg, output, spec, _ = _fixture(tmp_path)
    agg(output, spec)
    original = (output / "baseline_identity.json").read_bytes()
    assert original == canonical_bytes(json.loads(original))
    archive_path = spec.candidate_dir / "parameters.npz"
    with np.load(archive_path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in reversed(archive.files)}
    old_sha = digest_file(archive_path)
    np.savez(archive_path, **arrays)
    assert digest_file(archive_path) != old_sha
    (spec.candidate_dir / "wrapper.py").write_text("x = 7\n")
    other_output = tmp_path / "other"
    other_output.mkdir()
    (other_output / "results.npz").write_bytes((output / "results.npz").read_bytes())
    agg(other_output, replace(spec, job_id="other-job", candidate_digest=candidate_digest(spec.candidate_dir)))
    assert (other_output / "baseline_identity.json").read_bytes() == original


def test_undefined_intervals_stay_private_null_and_absent_from_release(tmp_path):
    def input_edit(split, truth, inference, public):
        if split == "validation":
            truth["y"][:, 0] = public["y"][:, 0] = np.repeat([-1.] * 3 + [1.] * 3, 24)

    agg, output, spec, _ = _fixture(tmp_path, "final", input_edit=input_edit)
    metrics = agg(output, spec)["metrics"]
    assert metrics["bootstrap_invalid"] > 0
    assert metrics["intervals_valid"] == 0
    assert metrics["registered_useful_effect"] == 0
    assert "primary_delta" in metrics and "primary_ci95_low" not in metrics and "primary_ci95_high" not in metrics
    report = json.loads((output / "trusted_residual_recovery_analysis.json").read_text())
    assert report["statistics"]["primary"]["ci95"] is None
    assert report["statistics"]["gates"]["registered_useful_effect"] == "inconclusive"


def test_baseline_source_cannot_be_linked_to_a_different_tree(tmp_path):
    from os import link

    candidate = tmp_path / "candidate"
    candidate.mkdir()
    external = tmp_path / "external.py"
    external.write_text("x = 1\n")
    link(external, candidate / "linear.py")
    method, params = _method()
    with pytest.raises(ValueError, match="single-link"):
        baseline_identity(candidate, method, params, np.zeros((144, 5, 2, 6)),
                          public_manifest_sha256=PUBLIC_SHA, inference_sha256="d" * 64)


def test_qualification_provenance_is_bound_to_the_policy(tmp_path):
    original, output, spec, _ = _fixture(tmp_path)
    path = original.qualification.path
    receipt = json.loads(path.read_text())
    receipt["source_provenance"]["pooling_source_sha256"] = "d" * 64
    path.write_bytes(canonical_bytes(receipt))
    with pytest.raises(ValueError, match="Bound input changed"):
        original(output, spec)
    changed = ResidualRecoveryAggregator(
        original.truth, original.train_truth, original.inference, public_by_split=original.public,
        qualification=FileBinding(path, digest_file(path)), runtime_identity={"runtime": "synthetic"},
    )
    assert changed.policy_sha256 != original.policy_sha256
    assert changed.scoring_policy["qualification"]["canonical_sha256"] != (
        original.scoring_policy["qualification"]["canonical_sha256"])
