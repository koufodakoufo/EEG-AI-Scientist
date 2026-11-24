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
