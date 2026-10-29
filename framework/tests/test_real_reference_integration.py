"""Engineering-only synthetic end-to-end review; never load EEG or checkpoints.

All models, EEG-shaped inputs and feature targets in this file are artificial.
The declared 24/6/6 participant partitions are exercised at four rows/subject.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch
from threadpoolctl import threadpool_limits

from eegfm.research_bench import real_reference as reference
from eegfm.research_bench.real_data import CBraModCPU, FEATURE_COLUMNS, compute_feature_panel
from eegfm.research_bench.real_public import sanitize_head
from eegfm.research_bench.real_science import (
    fit_probe, head_logits, permute_subject_blocks, perturb, predict_probe, subspace,
)


class _SyntheticLayer(torch.nn.Module):
    def __init__(self, number: int) -> None:
        super().__init__()
        self.scale = 0.005 * number

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.scale * torch.tanh(torch.roll(x, 1, dims=-1))


def _generic_model() -> torch.nn.Module:
    model = torch.nn.Module()
    model.patch_embedding = torch.nn.Identity()
    model.encoder = torch.nn.Module()
    model.encoder.layers = torch.nn.ModuleList([_SyntheticLayer(i) for i in range(1, 13)])
    model.encoder.norm = torch.nn.LayerNorm(200)
    model.proj_out = torch.nn.Identity()
    return model.cpu().eval().requires_grad_(False)


def _synthetic_features(x: np.ndarray) -> np.ndarray:
    z = x.mean((1, 2))
    values = np.stack([z[:, i % 12] + 0.04 * z[:, (i + 31) % 200] for i in range(62)], 1)
    values[:, 0] = 3.0
    values[:, -1] = 0.0
    return values.astype(np.float32)


def _write_synthetic_split(folder: Path, split: str, first: int, count: int) -> None:
    rng = np.random.default_rng(901 + first)
    n = count * 4
    y = np.tile([0, 0, 1, 1], count)
    latent = rng.normal(0, 0.4, size=(n, 200))
    latent[:, 0] += y * 1.3 - 0.65
    x = (latent[:, None, None, :] + rng.normal(0, 0.1, (n, 20, 5, 200))).astype(np.float32)
    subjects = np.repeat([f'Subject{i:02d}' for i in range(first, first + count)], 4)
    recordings = np.asarray([f'{s}_{label + 1}' for s, label in zip(subjects, y)])
    windows = np.tile([0, 1], n // 2)
    np.savez(folder / f'{split}.npz', x=x, y=y, subject_ids=subjects,
             sample_ids=np.asarray([f'{r}-{w}' for r, w in zip(recordings, windows)]),
             recording_ids=recordings, window_indices=windows, split=np.asarray(split),
             input_unit=np.asarray('uV/100'), sample_rate=np.asarray(200))


@pytest.fixture(scope='module')
def synthetic_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp('synthetic-reference-engineering-only')
    prepared, output, resources = root / 'prepared', root / 'output', root / 'fake-resources'
    prepared.mkdir()
    resources.mkdir()
    _write_synthetic_split(prepared, 'train', 0, 24)
    _write_synthetic_split(prepared, 'validation', 24, 6)
    protocol = root / 'SYNTHETIC_PROTOCOL.json'
    protocol.write_text(json.dumps({'engineering_fixture': True}), encoding='utf-8')
    model = CBraModCPU(_generic_model())
    loads: list[str] = []

    def fake_load(path: Path, *, threads: int = 4) -> CBraModCPU:
        assert path == resources and threads == 4
        loads.append('generic model; no checkpoint')
        return model

    def fake_prepare(cache: Path, target: Path, **kwargs: Any) -> dict[str, Path]:
        assert cache == resources and target == prepared
        assert kwargs['splits'] == ('test',) and kwargs['allow_test'] is True
        assert (output / 'TEST_RESERVATION.json').exists()
        _write_synthetic_split(prepared, 'test', 30, 6)
        return {'test': prepared / 'test.npz'}

    with pytest.MonkeyPatch.context() as patch, threadpool_limits(limits=4):
        torch.set_num_threads(4)
        patch.setattr(reference, 'load_cbramod', fake_load)
        patch.setattr(reference, 'compute_feature_panel', _synthetic_features)
        patch.setattr(reference, 'prepare_eegmat', fake_prepare)
        patch.setattr(reference, 'cache_provenance', lambda path: {'engineering_only': True, 'producer': 'generic-model-v1'})
        patch.setattr(reference, 'MODEL_RESOURCES', ())
        preparation = reference.prepare_reference(resources, prepared, output, protocol)
        assert preparation['test_accessed'] is False
        assert not (prepared / 'test.npz').exists()
        evaluation = reference.evaluate_reference(resources, prepared, output)
        with pytest.raises(FileExistsError):
            reference.evaluate_reference(resources, prepared, output)
    return {'root': root, 'prepared': prepared, 'output': output, 'resources': resources,
            'model': model, 'loads': loads, 'evaluation': evaluation}


def test_synthetic_full_prepare_test_round_trip(synthetic_run: dict[str, Any]) -> None:
    output = synthetic_run['output']
    result = json.loads((output / 'REFERENCE_TEST_RESULT.json').read_text(encoding='utf-8'))
    assert result['test_subjects'] == 6 and result['test_windows'] == 24
    assert len(result['q1']) == 24 and len(result['q2_q3']) == 2
    assert result['bootstrap']['resamples'] == 2000
    assert result['status'] == 'real_reference_partial'
    assert result['estimable_feature_layer_groups'] == 22
    assert result['nonzero_rank_interventions'] == 2
    assert len(synthetic_run['loads']) == 4
    assert all(p['active_train_columns'] == 0 for p in result['q1'] if p['feature'].startswith('R002'))
    assert all(p['r2'] is None for p in result['q1'] if p['feature'].startswith('R002'))
    assert all(p['active_train_columns'] == 5 for p in result['q1'] if p['feature'].startswith('T001'))
    for item in result['q2_q3']:
        assert len(item['variants']) == 4
        assert [v['random_seed'] for v in item['variants']] == [None, 1301, 1302, 1303]
        assert all(v['rank'] == item['rank'] for v in item['variants'])
    assert 'NaN' not in (output / 'REFERENCE_TEST_RESULT.json').read_text(encoding='utf-8')


def test_synthetic_intervention_continuation_and_control_strength(synthetic_run: dict[str, Any]) -> None:
    output = synthetic_run['output']
    fits = json.loads((output / 'REFERENCE_FITS.json').read_text(encoding='utf-8'))
    head = reference.array_fit(json.loads((output / 'FROZEN_HEAD.json').read_text(encoding='utf-8')))
    model = synthetic_run['model']
    with np.load(output / 'test-representations.npz', allow_pickle=False) as cache, np.load(
            output / 'REFERENCE_TEST_ARRAYS.npz', allow_pickle=False) as saved:
        for index, item in enumerate(fits['interventions']):
            layer = item['layer']
            original = cache[f'layer_{layer}']
            continuation = model.continue_from(original[:3], layer=layer).mean((1, 2))
            np.testing.assert_allclose(continuation, cache['embedding'][:3], rtol=1e-6, atol=1e-7)
            for variant, seed in enumerate((None, 1301, 1302, 1303)):
                changed, metadata = perturb(original, np.asarray(item['basis']), np.asarray(item['center']), random_seed=seed)
                replay = model.continue_from(changed[:3].astype(np.float32), layer=layer).mean((1, 2))
                np.testing.assert_allclose(head_logits(head, replay), saved[f'intervention_{index}_{variant}_logits'][:3], atol=1e-6)
                np.testing.assert_allclose(saved[f'intervention_{index}_{variant}_shift_l2'], metadata['pooled_shift_l2'], rtol=1e-5, atol=1e-6)
                np.testing.assert_allclose(saved[f'intervention_{index}_{variant}_shift_l2'], saved[f'intervention_{index}_0_shift_l2'], rtol=1e-5, atol=1e-6)


def test_json_probe_and_head_roundtrip_preserve_predictions(synthetic_run: dict[str, Any]) -> None:
    output = synthetic_run['output']
    fits = json.loads((output / 'REFERENCE_FITS.json').read_text(encoding='utf-8'))
    with np.load(output / 'train-representations.npz', allow_pickle=False) as train:
        for item in fits['probes']:
            z = train[f"layer_{item['layer']}"].mean((1, 2))
            original = fit_probe(z, train['features'][:, item['columns']], alpha=item['fit']['alpha'])
            restored = reference.array_fit(item['fit'])
            np.testing.assert_allclose(predict_probe(original, z), predict_probe(restored, z), rtol=1e-10, atol=1e-10)
            np.testing.assert_allclose(restored['x_mean'], z.astype(float).mean(0))


def _public_api() -> Any:
    path = Path(__file__).parents[1] / 'benchmarks/brainpec_real/eeg_api.py'
    spec = importlib.util.spec_from_file_location('synthetic_review_public_eeg_api', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_private_feature_and_model_interfaces_agree_on_synthetic_data() -> None:
    api = _public_api()
    rng = np.random.default_rng(2029)
    x = rng.normal(0, 0.4, (3, 20, 5, 200)).astype(np.float32)
    x[0, 0] = 0
    np.testing.assert_array_equal(compute_feature_panel(x), api.compute_feature_panel(x))
    assert tuple(api.FEATURE_COLUMNS) == FEATURE_COLUMNS
    model = _generic_model()
    private, public = CBraModCPU(model), api._CPUBackbone(model)
    for layer in (6, 12):
        pa = private.activations(x, layers=(layer,))[layer]
        qa = public.activations(x, layers=(layer,))[layer]
        np.testing.assert_array_equal(pa, qa)
        np.testing.assert_array_equal(private.continue_from(pa, layer=layer), public.continue_from(qa, layer=layer))
    head = {'x_mean': rng.normal(size=200), 'x_scale': rng.uniform(0.5, 2, 200),
            'coefficient': rng.normal(size=200), 'intercept': 0.4}
    embedding = private.encode(x)
    np.testing.assert_allclose(head_logits(head, embedding), api.head_logits(sanitize_head(head), embedding), atol=0)


def test_participant_derangement_also_breaks_condition_only_target_alignment() -> None:
    subjects = np.repeat([f's{i}' for i in range(24)], 24)
    condition = np.tile(np.repeat([0., 1.], 12), 24)
    indices = permute_subject_blocks(subjects, seed=20261029)
    assert np.all(subjects[indices] != subjects)
    # The diagnostic must break position/condition alignment within each block.
    assert not np.array_equal(condition[indices], condition)
    assert 0.3 < np.mean(condition[indices] != condition) < 0.7
    for start in range(0, len(subjects), 24):
        assert len(set(subjects[indices[start:start + 24]])) == 1
        np.testing.assert_array_equal(np.sort(condition[indices[start:start + 24]]), np.sort(condition[start:start + 24]))


def test_cache_producer_change_rejected_before_model_load(synthetic_run: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reference, 'cache_provenance', lambda path: {'engineering_only': True, 'producer': 'generic-model-v2'})
    with pytest.raises(ValueError, match='producer/model/runtime changed'):
        reference.cache_split(synthetic_run['resources'], synthetic_run['prepared'], synthetic_run['output'], 'train')


def test_cache_tamper_rejected_by_reference_lock(synthetic_run: dict[str, Any], tmp_path: Path) -> None:
    lock = json.loads((synthetic_run['output'] / 'REFERENCE_LOCK.json').read_text(encoding='utf-8'))
    bound = {Path(item['path']).name for item in lock['files']}
    assert {'train-representations.npz', 'validation-representations.npz',
            'train-representations.json', 'validation-representations.json'} <= bound
    damaged = tmp_path / 'train-representations.npz'
    damaged.write_bytes(b'engineering-test corrupted cache')
    item = next(item for item in lock['files'] if Path(item['path']).name == 'train-representations.npz')
    item['path'] = str(damaged)
    (tmp_path / 'REFERENCE_LOCK.json').write_text(json.dumps(lock), encoding='utf-8')
    with pytest.raises(ValueError, match='Frozen reference bytes changed'):
        reference.reserve_reference_test(tmp_path)
    assert not (tmp_path / 'TEST_RESERVATION.json').exists()


def test_ridge_direction_erasure_zeroes_frozen_readout_and_retains_nullspace() -> None:
    rng = np.random.default_rng(530)
    z = rng.normal(size=(80, 20, 5, 12))
    pooled = z.mean((1, 2))
    target = pooled[:, :3] @ rng.normal(size=(3, 4))
    fit = fit_probe(pooled, target, alpha=1)
    basis = subspace(fit['directions'])
    altered, _ = perturb(z, basis, fit['x_mean'])
    prediction = predict_probe(fit, altered.mean((1, 2)))
    np.testing.assert_allclose(prediction, np.broadcast_to(fit['y_mean'], prediction.shape), atol=1e-12)
    complement = np.eye(12) - basis @ basis.T
    np.testing.assert_allclose(altered @ complement, z @ complement, atol=1e-12)

