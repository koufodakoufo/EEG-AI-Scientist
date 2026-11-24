import numpy as np
import pytest

torch = pytest.importorskip("torch")

from eegfm.eeg.objective_pilot import band_log_energy, masked_objective, plan_for_seed


TRAINING_BANDS = ((1, 4), (4, 8), (8, 13))


def reference_log_energy(waveforms, bands):
    """One-second, 200 Hz windows; bin k is k Hz."""
    window = np.hanning(201)[:-1]
    centered = waveforms - waveforms.mean(axis=-1, keepdims=True)
    coefficients = np.fft.rfft(centered * window, axis=-1)
    powers = np.abs(coefficients) ** 2 / window.sum() ** 2
    return np.stack(
        [np.log(powers[..., low:high].sum(axis=-1) + 1e-8) for low, high in bands],
        axis=-1,
    )


def test_band_energy_matches_periodic_hann_and_half_open_bins():
    time = np.arange(200) / 200
    # Tones at a shared band boundary expose inclusive upper endpoints;
    # the independent DC offsets expose removal of the per-patch mean.
    signal = np.stack([11 + np.cos(2 * np.pi * 4 * time),
                       -3 + 2 * np.sin(2 * np.pi * 13 * time)])
    bands = (*TRAINING_BANDS, (13, 30))
    actual = band_log_energy(torch.from_numpy(signal), bands)
    np.testing.assert_allclose(
        actual.detach().cpu().numpy(), reference_log_energy(signal, bands), rtol=2e-5, atol=3e-5,
    )


@pytest.mark.parametrize("arm", ["recon", "spectral"])
def test_loss_scores_only_masked_waveforms_with_no_gradient_on_visible_tokens(arm):
    rng = np.random.default_rng(32)
    predicted = rng.normal(size=(2, 3, 2, 200)).astype(np.float32)
    truth = rng.normal(size=predicted.shape).astype(np.float32)
    mask = np.array([[[True, False], [False, False], [False, True]],
                     [[False, True], [False, True], [False, False]]])
    pred_tensor = torch.tensor(predicted, requires_grad=True)
    loss = masked_objective(pred_tensor, torch.tensor(truth), torch.from_numpy(mask), arm)
    if arm == "recon":
        difference = predicted[mask] - truth[mask]
    else:
        difference = (reference_log_energy(predicted[mask], TRAINING_BANDS)
                      - reference_log_energy(truth[mask], TRAINING_BANDS))
    assert loss.ndim == 0
    assert loss.item() == pytest.approx(np.mean(difference ** 2), rel=2e-5)
    loss.backward()
    gradient = pred_tensor.grad.detach().numpy()
    assert np.isfinite(gradient).all()
    assert np.count_nonzero(gradient[~mask]) == 0
    assert np.all(np.any(gradient[mask] != 0, axis=-1))


def test_waveform_sign_is_visible_only_to_reconstruction():
    samples = np.random.default_rng(191).normal(size=(1, 2, 1, 200)).astype(np.float32)
    truth = torch.from_numpy(samples)
    mask = torch.ones(truth.shape[:-1], dtype=torch.bool)
    assert masked_objective(-truth, truth, mask, "spectral").item() == pytest.approx(0, abs=1e-7)
    assert masked_objective(-truth, truth, mask, "recon").item() == pytest.approx(
        4 * np.mean(samples ** 2), rel=1e-5,
    )


def test_paired_plans_repeat_rows_and_masks_with_exact_per_window_budget():
    def plan(seed):
        return plan_for_seed(n=17, seed=seed, steps=3, batch=4, channels=3, patches=5)

    reconstruction, spectral, different_seed = plan(42), plan(42), plan(41)
    assert len(reconstruction) == len(spectral) == len(different_seed) == 3
    for (indices, mask), (paired_indices, paired_mask) in zip(reconstruction, spectral):
        assert torch.equal(indices, paired_indices)
        assert torch.equal(mask, paired_mask)
        assert indices.shape == (4,) and indices.unique().numel() == 4
        assert ((0 <= indices) & (indices < 17)).all()
        assert mask.dtype == torch.bool and mask.shape == (4, 3, 5)
        assert (mask.sum(dim=(1, 2)) == 7).all()
    assert any(
        not torch.equal(a[0], b[0]) or not torch.equal(a[1], b[1])
        for a, b in zip(reconstruction, different_seed)
    )


def test_research_plan_bounds_mixed_loss_and_paired_nested_masks():
    from copy import deepcopy
    from eegfm.eeg.objective_pilot import validate_research_plan

    arm = {"name": "A", "spectral_mix": 0., "bands": [], "lr": 2e-5, "mask_fraction": .5}
    plan = {"steps": 8, "primary": "central_beta",
            "arms": [arm, {**arm, "name": "B", "spectral_mix": .3, "bands": [[2, 5]]}]}
    validate_research_plan(plan)
    for change in ({"bands": [[8, 4]]}, {"bands": []}, {"lr": float("nan")}, {"mask_fraction": True}):
        invalid = deepcopy(plan)
        invalid["arms"][1].update(change)
        with pytest.raises(ValueError):
            validate_research_plan(invalid)
    invalid = deepcopy(plan)
    invalid["arms"][1].update(spectral_mix=0., mask_fraction=.5001)
    with pytest.raises(ValueError, match="effective"):
        validate_research_plan(invalid)
    x, y = torch.randn(2, 2, 3, 200), torch.randn(2, 2, 3, 200)
    mask = torch.ones(2, 2, 3, dtype=torch.bool)
    combined = masked_objective(x, y, mask, "B", spectral_mix=.3, bands=((2, 5),))
    assert torch.allclose(combined, .7 * masked_objective(x, y, mask, "recon") +
                          .3 * masked_objective(x, y, mask, "spectral", bands=((2, 5),)))
    for (i, small), (j, big) in zip(plan_for_seed(12, 42, 3, 4, 19, 5, .4),
                                     plan_for_seed(12, 42, 3, 4, 19, 5, .8)):
        assert torch.equal(i, j) and (small <= big).all()


def test_research_backend_freezes_then_evaluates_only_validation(tmp_path, monkeypatch):
    from eegfm.eeg import objective_pilot as pilot
    from eegfm.common import read_jsonl, write_json, sha256

    arm = {"name": "A", "spectral_mix": 0, "bands": [], "lr": 2e-5, "mask_fraction": .5}
    plan = {"steps": 8, "primary": "condition", "arms": [arm, {**arm, "name": "B", "lr": 1e-4}]}
    write_json(tmp_path / "plan.json", plan)
    monkeypatch.setattr(pilot, "bindings", lambda cfg: {"unit-test-model": "synthetic"})
    def fake_data(path, cfg, partitions):
        assert partitions == ("train", "validation")
        writes = {}
        folder = path / "development_data"
        folder.mkdir()
        rng = np.random.default_rng(81)
        for part in partitions:
            samples = rng.normal(size=(8, 20, 5, 200)).astype("float32")
            output = folder / f"{part}.npz"
            np.savez(output, channels=pilot.data.CHANNELS, x=samples, y=np.tile([0, 1], 4),
                     subject_ids=[f"{part}-{n//2}" for n in range(8)], sample_ids=[f"{part}-{n}" for n in range(8)])
            writes[output.relative_to(path).as_posix()] = sha256(output)
        return writes
    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.offset = torch.nn.Parameter(torch.tensor(.25))
        def forward(self, x, mask=None):
            if mask is not None:
                x = torch.where(mask.unsqueeze(-1), x.mean((1, 2), keepdim=True), x)
            return x + self.offset
    monkeypatch.setattr(pilot, "make_data", fake_data)
    monkeypatch.setattr(pilot, "load_model", lambda cfg: (Encoder(), torch.nn.Identity()))
    result = pilot.execute_research_plan(tmp_path, plan)
    assert result["participants"] == {"train": 4, "validation": 4}
    assert result["seeds"]["42"]["metrics"]["condition"]["by_arm"].keys() == {"init", "A", "B"}
    exp = tmp_path / "experiment"
    actions = [e["action"] for e in read_jsonl(exp / "trajectory.jsonl")]
    assert actions.count("training_complete") == 4
    assert actions.index("all_candidates_frozen") < actions.index("evaluated")
    assert not (exp / "evaluation_data").exists()
    assert pilot.execute_research_plan(tmp_path, plan) == result
    assert [e["action"] for e in read_jsonl(exp / "trajectory.jsonl")] == actions
    write_json(tmp_path / "plan.json", {**plan, "steps": 9})
    with pytest.raises(ValueError, match="changed"):
        pilot.execute_research_plan(tmp_path, {**plan, "steps": 9})


@pytest.fixture
def waiting_scientist(tmp_path, monkeypatch):
    """Two real controller invocations. Only provider I/O and EEG computation are stubbed."""
    import json
    from eegfm.common import read_json, write_json
    from eegfm.eeg import scientist

    monkeypatch.setattr(scientist, "EPISODES", tmp_path)
    run = scientist.episode_path("ordinary-study")
    arm = {"name": "A", "spectral_mix": 0, "bands": [], "lr": 2e-5, "mask_fraction": .5}
    plan = {"action": "experiment", "question": "Does masking affect transfer?",
            "rationale": "Test two mask ratios", "alternative": "A ceiling effect",
            "prediction": "Larger masks improve condition BA", "controls": "Pair seeds",
            "decision_rule": "Require improvement at both seeds; otherwise inconclusive",
            "primary": "condition", "steps": 8, "arms": [arm, {**arm, "name": "B", "mask_fraction": .8}]}
    result = {"condition": {"seed42": .125, "seed43": -.125}, "fixture": True}

    def design(folder, prompt):
        assert folder.name == "design-1"
        assert scientist.QUESTION in prompt and '"frozen_plan"' not in prompt
        folder.mkdir()
        receipt = {"status": "completed", "thread_id": "design-thread", "text": json.dumps(plan)}
        write_json(folder / "receipt.json", receipt)
        return receipt

    def experiment(path, selected):
        assert path == run
        assert selected == read_json(run / "plan.json") == {**plan, "researcher_session": "design-thread"}
        return result

    def unexpected(*_):
        pytest.fail("A completed stage was repeated or an unrequested stage was started")

    assert scientist.advance(run, through="design", launch=design, execute=unexpected) == "experiment"
    assert not (run / "results.json").exists()
    assert scientist.advance(run, through="experiment", launch=unexpected, execute=experiment) == "interpret"
    assert read_json(run / "results.json") == result
    assert not (run / "decision.json").exists()
    return run, plan, result, unexpected


def _interpret_fixture(folder, prompt, identity="interpret-thread"):
    import json
    from eegfm.common import write_json
    from eegfm.eeg import scientist

    assert folder.name == "interpret-1"
    folder.mkdir()
    decision = {field: "Fixture interpretation using paired outcomes" for field in scientist.DECISION_FIELDS}
    decision.update(verdict="redirect", next_decision="Collect another recording condition")
    receipt = {"status": "completed", "thread_id": identity, "text": json.dumps(decision)}
    write_json(folder / "receipt.json", receipt)
    return receipt


def test_scientist_fresh_session_gets_persisted_plan_and_results(waiting_scientist):
    import json
    from eegfm.common import read_json, read_jsonl
    from eegfm.eeg import scientist

    run, plan, result, unexpected = waiting_scientist

    def interpret(folder, prompt):
        received = json.loads(prompt.splitlines()[-1])
        assert received["frozen_plan"] == plan
        assert received["executor_results"] == result
        assert received["admitted_brief"] == read_json(run / "brief.json")
        return _interpret_fixture(folder, prompt)

    assert scientist.advance(run, launch=interpret, execute=unexpected) == "closed"
    assert scientist.advance(run, launch=unexpected, execute=unexpected) == "closed"
    assert read_json(run / "decision.json")["researcher_session"] == "interpret-thread"
    events = read_jsonl(run / "trajectory.jsonl")
    assert [r["role"] for r in events if r["action"] == "session_requested"] == ["design", "interpret"]
    assert sum(r["action"] == "experiment_returned" for r in events) == 1


def test_scientist_rejects_reused_native_thread(waiting_scientist):
    from eegfm.eeg import scientist

    run, _, _, unexpected = waiting_scientist
    with pytest.raises(RuntimeError, match="different"):
        scientist.advance(run, launch=lambda f, p: _interpret_fixture(f, p, "design-thread"), execute=unexpected)
    assert not (run / "decision.json").exists()


def test_scientist_rejects_mismatched_native_receipt_on_resume(waiting_scientist):
    import hashlib
    from eegfm.common import write_json
    from eegfm.eeg import scientist

    run, _, _, unexpected = waiting_scientist

    def interrupted(folder, prompt):
        receipt = _interpret_fixture(folder, prompt)
        wrong_hash = hashlib.sha256((prompt + "different request").encode()).hexdigest()
        receipt["calls"] = [{"phase": "research", "prompt_sha256": wrong_hash}]
        write_json(folder / "receipt.json", receipt)
        raise InterruptedError("controller stopped after the provider wrote the receipt")

    with pytest.raises(InterruptedError):
        scientist.advance(run, launch=interrupted, execute=unexpected)
    with pytest.raises(ValueError, match="native receipt does not match the recorded request"):
        scientist.advance(run, launch=unexpected, execute=unexpected)
    assert not (run / "decision.json").exists()


@pytest.mark.parametrize("fault", ["changed_result", "missing_receipt"])
def test_scientist_rejects_unverified_results_before_requesting_interpretation(waiting_scientist, fault):
    import json
    from eegfm.common import read_jsonl, write_json
    from eegfm.eeg import scientist

    run, _, _, unexpected = waiting_scientist
    if fault == "changed_result":
        write_json(run / "results.json", {"changed": True})
    else:
        # A worker can finish writing its result just before the controller dies.
        log = run / "trajectory.jsonl"
        events = [r for r in read_jsonl(log) if r["action"] != "experiment_returned"]
        log.write_text("".join(json.dumps(r) + "\n" for r in events), encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError)):
        scientist.advance(run, launch=unexpected, execute=unexpected)
    assert not (run / "decision.json").exists()


def test_scientist_checks_parent_integrity_before_import(waiting_scientist):
    from eegfm.common import write_json
    from eegfm.eeg import scientist

    parent, _, _, unexpected = waiting_scientist
    assert scientist.advance(parent, launch=_interpret_fixture, execute=unexpected) == "closed"
    write_json(parent / "results.json", {"changed": True})
    child = scientist.episode_path("next-study")
    with pytest.raises((ValueError, RuntimeError)):
        scientist.advance(child, parent=parent.name, launch=unexpected, execute=unexpected)
    assert not (child / "brief.json").exists()


def test_scientist_declined_research_has_no_executor_or_interpretation(tmp_path):
    import json
    from eegfm.common import read_json, write_json
    from eegfm.eeg import scientist

    def decline(folder, prompt):
        assert folder.name == "design-1"
        folder.mkdir()
        receipt = {"status": "completed", "thread_id": "decline-thread",
                   "text": json.dumps({"action": "decline", "rationale": "No useful contrast"})}
        write_json(folder / "receipt.json", receipt)
        return receipt

    def unexpected(*_):
        pytest.fail("Declined design consumed another experiment or session")

    assert scientist.advance(tmp_path, launch=decline, execute=unexpected) == "closed"
    assert scientist.advance(tmp_path, launch=unexpected, execute=unexpected) == "closed"
    assert read_json(tmp_path / "decision.json")["verdict"] == "declined_without_training"
    assert not (tmp_path / "results.json").exists()
