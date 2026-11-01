"""Synthetic checks of the independent Actor's bounded readout evidence."""
from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import warnings
import zipfile

import numpy as np
import pytest

from eegfm.evaluation.bundle import digest_file
from eegfm.evaluation.worker import FileBinding, candidate_digest


def test_concrete_actor_readout_scorer_is_available():
    assert importlib.util.find_spec('eegfm.eeg.readout_aggregation') is not None, (
        'The bounded Actor readout scorer has not been implemented')


@pytest.fixture
def case(tmp_path: Path) -> SimpleNamespace:
    assert importlib.util.find_spec('eegfm.eeg.readout_aggregation') is not None, (
        'The bounded Actor readout scorer has not been implemented')
    module = importlib.import_module('eegfm.eeg.readout_aggregation')
    truth, inference, public, arrays = {}, {}, {}, {}
    for split in ('train', 'validation', 'test'):
        sizes = [2, 4, 6] if split != 'test' else [2, 4, 2, 4]
        subjects = np.concatenate([np.repeat(f'{split}_p{i}', n) for i, n in enumerate(sizes)])
        y = np.tile([0, 1], len(subjects) // 2)
        ids = np.asarray([f'{split}_s{i}' for i in range(len(y))])
        # Deliberate original ties and values immediately around the threshold.
        original = np.tile([-1e-13, 1e-13, 0., 0., -1., 1.], 2)
        x = np.zeros((len(y), 325))
        x[:, 262] = original
        truth[split] = tmp_path / f'{split}_truth.npz'
        inference[split] = tmp_path / f'{split}_inference.npz'
        np.savez(truth[split], sample_ids=ids, subject_ids=subjects, y=y)
        np.savez(inference[split], sample_ids=ids, subject_ids=subjects, x=x)
        arrays[split] = dict(sample_ids=ids, subject_ids=subjects, y=y, x=x)
        if split != 'test':
            public[split] = tmp_path / f'{split}_public.npz'
            np.savez(public[split], **arrays[split])
    cohort = tmp_path / 'cohort.npz'
    np.savez(cohort, sample_ids=arrays['test']['sample_ids'],
             cohort=np.asarray(['diagnostic'] * 6 + ['confirmation'] * 6))
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    # The scorer must never import or execute either file.
    (candidate / 'main.py').write_text('raise RuntimeError("candidate code must not execute")\n')
    (candidate / 'fit.py').write_text('raise RuntimeError("fit code must not execute")\n')
    manifest = {'schema_version': 'cached_readout_manifest_v1', 'readouts': [
        {'name': 'original', 'role': 'original', 'description': 'Unchanged original head'},
        {'name': 'nearest_centroid', 'role': 'representation', 'description': 'Train centroids'},
        {'name': 'attribute_tree', 'role': 'attributes', 'description': 'A bounded decision tree'}],
        'primary_contrast': ['nearest_centroid', 'original']}
    (candidate / 'readouts.json').write_text(json.dumps(manifest))
    output = tmp_path / 'out'
    output.mkdir()
    return SimpleNamespace(module=module, root=tmp_path, truth=truth, inference=inference, public=public,
        arrays=arrays, cohort=cohort, candidate=candidate, output=output, manifest=manifest)


def binding(path: Path) -> FileBinding:
    return FileBinding(path, digest_file(path))


def aggregate(case: SimpleNamespace, **kwargs):
    public = kwargs.pop('public_by_split', {key: binding(path) for key, path in case.public.items()})
    return case.module.ReadoutAggregator(
        {key: binding(case.truth[key]) for key in ('validation', 'test')},
        binding(case.truth['train']),
        {key: binding(path) for key, path in case.inference.items()},
        test_cohort=binding(case.cohort), public_by_split=public, **kwargs)


def specification(case: SimpleNamespace, split: str = 'validation') -> SimpleNamespace:
    return SimpleNamespace(split=split, candidate_dir=case.candidate,
        candidate_digest=candidate_digest(case.candidate), job_id='job', episode_id='episode',
        run_id='run', attempt_id='attempt', public_manifest_sha256='a' * 64,
        split_manifest_sha256='b' * 64)


def output(case: SimpleNamespace, split: str = 'validation', **changes) -> dict[str, np.ndarray]:
    arrays = case.arrays[split]
    truth_score = 2 * arrays['y'].astype(float) - 1
    second = truth_score.copy()
    second[[0, 3, 8]] *= -1
    third = truth_score.copy()
    third[[1, 4, 9, 10]] *= -1
    values = {'sample_ids': arrays['sample_ids'],
        'readout_names': np.asarray([item['name'] for item in case.manifest['readouts']]),
        'logits': np.column_stack([arrays['x'][:, 262], second, third])}
    values.update(changes)
    np.savez(case.output / 'results.npz', **values)
    return values


def report(case: SimpleNamespace) -> dict:
    return json.loads((case.output / 'trusted_readout_analysis.json').read_text())


def test_alternative_lawful_models_use_trusted_canonical_metrics_without_execution(case):
    output(case)
    scorer = aggregate(case, bootstrap_resamples=64)
    result = scorer(case.output, specification(case))
    metrics = result['metrics']
    assert metrics['readout_count'] == 3
    assert metrics['representation_readouts'] == 1
    assert metrics['numeric_scope_complete'] == 1
    assert metrics['readout_i0_balanced_accuracy'] == pytest.approx(5 / 6)
    assert metrics['readout_i0_auroc'] == pytest.approx(17 / 18)
    assert metrics['readout_i0_logloss'] == pytest.approx(
        (4 * np.log(2) + 2 * np.logaddexp(0, -1.)) / 6, abs=1e-13)
    assert set(metrics) <= scorer.released_metrics
    assert report(case)['manifest'] == case.manifest
    assert report(case)['scientific_validity'] == 'pending_source_fit_and_prediction_audit'
    assert {item['path'] for item in result['artifacts']} == {
        'results.npz', 'trusted_readout_analysis.json'}


def test_original_only_is_a_valid_incomplete_baseline(case):
    case.manifest['readouts'] = case.manifest['readouts'][:1]
    case.manifest.pop('primary_contrast')
    (case.candidate / 'readouts.json').write_text(json.dumps(case.manifest))
    output(case, logits=case.arrays['validation']['x'][:, 262, None])
    metrics = aggregate(case, bootstrap_resamples=8)(case.output, specification(case))['metrics']
    assert metrics['baseline_only'] == 1
    assert metrics['numeric_scope_complete'] == 0
    assert metrics['pairwise_comparisons'] == 0


@pytest.mark.parametrize('mutation', ['reordered_ids', 'missing_ids', 'extra_labels',
    'extra_targets', 'wrong_names', 'reordered_names', 'nonfinite', 'object', 'duplicate_ids'])
def test_untrusted_output_cannot_replace_ids_labels_targets_or_manifest(case, mutation):
    values = output(case)
    if mutation == 'reordered_ids': values['sample_ids'] = values['sample_ids'][::-1]
    if mutation == 'missing_ids': values.pop('sample_ids')
    if mutation == 'extra_labels': values['y'] = case.arrays['validation']['y']
    if mutation == 'extra_targets': values['features'] = np.zeros((12, 62))
    if mutation == 'wrong_names': values['readout_names'][1] = 'other'
    if mutation == 'reordered_names': values['readout_names'] = values['readout_names'][::-1]
    if mutation == 'nonfinite': values['logits'][1, 1] = np.inf
    if mutation == 'object': values['logits'] = values['logits'].astype(object)
    if mutation == 'duplicate_ids': values['sample_ids'][1] = values['sample_ids'][0]
    np.savez(case.output / 'results.npz', **values)
    with pytest.raises(ValueError):
        aggregate(case, bootstrap_resamples=8)(case.output, specification(case))


@pytest.mark.parametrize('row,replacement', [(0, 1e-13), (2, 1e-13), (3, -1e-13)])
def test_original_near_zero_sign_and_tied_rank_changes_are_rejected_exactly(case, row, replacement):
    values = output(case)
    values['logits'][row, 0] = replacement
    np.savez(case.output / 'results.npz', **values)
    with pytest.raises(ValueError, match='original'):
        aggregate(case, bootstrap_resamples=8)(case.output, specification(case))


@pytest.mark.parametrize('mutation', ['duplicate', 'oversized', 'structured', 'extra_file'])
def test_archive_and_output_directory_are_bounded_before_loading(case, mutation):
    values = output(case)
    if mutation == 'duplicate':
        with zipfile.ZipFile(case.output / 'results.npz', 'a') as archive:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                archive.writestr('sample_ids.npy', b'duplicate')
    if mutation == 'oversized':
        with zipfile.ZipFile(case.output / 'results.npz', 'w') as archive:
            for name, value in values.items():
                content = io.BytesIO()
                if name == 'logits':
                    np.lib.format.write_array_header_1_0(content, {
                        'descr': '<f8', 'fortran_order': False, 'shape': (10**12, 3)})
                else:
                    np.save(content, value)
                archive.writestr(name + '.npy', content.getvalue())
    if mutation == 'structured':
        values['logits'] = np.zeros((12, 3), dtype=[('unsafe', '<f8')])
        np.savez(case.output / 'results.npz', **values)
    if mutation == 'extra_file': (case.output / 'untrusted.json').write_text('{}')
    with pytest.raises(ValueError):
        aggregate(case, bootstrap_resamples=8)(case.output, specification(case))


@pytest.mark.parametrize('mutation', ['duplicate', 'too_many', 'wrong_original', 'unknown_role',
                                    'unknown_primary', 'same_primary', 'bad_name', 'extra_field'])
def test_manifest_is_semantic_bounded_and_frozen(case, mutation):
    manifest = case.manifest
    if mutation == 'duplicate': manifest['readouts'][2]['name'] = 'original'
    if mutation == 'too_many':
        manifest['readouts'] += [dict(name=f'other_{i}', role='other', description='Control') for i in range(4)]
    if mutation == 'wrong_original': manifest['readouts'][0]['role'] = 'representation'
    if mutation == 'unknown_role': manifest['readouts'][1]['role'] = 'builder'
    if mutation == 'unknown_primary': manifest['primary_contrast'] = ['unknown', 'original']
    if mutation == 'same_primary': manifest['primary_contrast'] = ['original', 'original']
    if mutation == 'bad_name': manifest['readouts'][1]['name'] = '../unsafe'
    if mutation == 'extra_field': manifest['builder_answer'] = 1
    (case.candidate / 'readouts.json').write_text(json.dumps(manifest))
    output(case)
    with pytest.raises(ValueError):
        aggregate(case, bootstrap_resamples=8)(case.output, specification(case))


def test_changed_frozen_manifest_and_private_input_are_rejected(case):
    output(case)
    scorer = aggregate(case, bootstrap_resamples=8)
    spec = specification(case)
    path = case.candidate / 'readouts.json'
    frozen = path.read_bytes()
    path.write_text(frozen.decode() + '\n')
    with pytest.raises(ValueError, match='Candidate|candidate'):
        scorer(case.output, spec)
    path.write_bytes(frozen)
    case.inference['test'].write_bytes(b'changed even though scoring validation')
    with pytest.raises(ValueError, match='Bound input changed'):
        scorer(case.output, spec)


@pytest.mark.parametrize('mutation', ['train_overlap', 'validation_overlap', 'inference_labels',
                                    'inference_ids', 'cohort_order', 'cohort_split_participant'])
def test_private_split_cohort_and_label_free_inference_alignment(case, mutation):
    if mutation in ('train_overlap', 'validation_overlap'):
        split = 'train' if mutation == 'train_overlap' else 'validation'
        arrays = case.arrays[split]
        subjects = arrays['subject_ids'].copy()
        subjects[:2] = case.arrays['test']['subject_ids'][0]
        np.savez(case.truth[split], sample_ids=arrays['sample_ids'], subject_ids=subjects, y=arrays['y'])
        np.savez(case.inference[split], sample_ids=arrays['sample_ids'], subject_ids=subjects, x=arrays['x'])
        np.savez(case.public[split], sample_ids=arrays['sample_ids'], subject_ids=subjects,
                 x=arrays['x'], y=arrays['y'])
    if mutation in ('inference_labels', 'inference_ids'):
        arrays = {k: v for k, v in case.arrays['test'].items() if k != 'y'}
        if mutation == 'inference_labels': arrays['y'] = case.arrays['test']['y']
        else: arrays['sample_ids'] = arrays['sample_ids'][::-1]
        np.savez(case.inference['test'], **arrays)
    if mutation.startswith('cohort_'):
        ids = case.arrays['test']['sample_ids']
        cohorts = np.asarray(['diagnostic'] * 6 + ['confirmation'] * 6)
        if mutation == 'cohort_order': ids = ids[::-1]
        else: cohorts[0] = 'confirmation'
        np.savez(case.cohort, sample_ids=ids, cohort=cohorts)
    output(case)
    with pytest.raises(ValueError):
        aggregate(case, bootstrap_resamples=8)(case.output, specification(case))


def test_bootstrap_matches_independent_resampling_of_whole_unequal_participants(case):
    values = output(case)
    scorer = aggregate(case)
    metrics = scorer(case.output, specification(case))['metrics']
    truth = case.arrays['validation']
    blocks = [np.flatnonzero(truth['subject_ids'] == subject) for subject in np.unique(truth['subject_ids'])]
    draws = np.random.default_rng(161803).integers(0, len(blocks), size=(10000, len(blocks)))
    boots = []
    for draw in draws:
        rows = np.concatenate([blocks[index] for index in draw])
        y, logits = truth['y'][rows], values['logits'][rows]
        boots.append([np.mean(logits[y == 0] < 0, axis=0), np.mean(logits[y == 1] >= 0, axis=0)])
    boots = np.mean(boots, axis=1)
    for index in range(3):
        actual = [metrics[f'readout_i{index}_balanced_accuracy_ci95_{end}'] for end in ('low', 'high')]
        np.testing.assert_allclose(actual, np.quantile(boots[:, index], [.025, .975]))
    assert metrics['bootstrap_resamples'] == 10000
    for left, right in ((0, 1), (0, 2), (1, 2)):
        delta = boots[:, left] - boots[:, right]
        prefix = f'contrast_i{left}_i{right}_'
        for name, quantiles in [('ci95', [.025, .975]), ('family_ci', [.05 / 6, 1 - .05 / 6])]:
            np.testing.assert_allclose([metrics[prefix + name + '_' + end] for end in ('low', 'high')],
                                       np.quantile(delta, quantiles))
    np.testing.assert_allclose([metrics[f'primary_contrast_ci95_{end}'] for end in ('low', 'high')],
                              np.quantile(boots[:, 1] - boots[:, 0], [.025, .975]))
    assert report(case)['uncertainty']['pair_count'] == 3


def test_sealed_test_releases_combined_and_descriptive_cohorts_together(case):
    output(case, 'test')
    metrics = aggregate(case, bootstrap_resamples=32)(case.output, specification(case, 'test'))['metrics']
    assert metrics['participants'] == 4
    assert metrics['diagnostic_participants'] == 2
    assert metrics['confirmation_participants'] == 2
    assert set(report(case)['subsets']) == {'combined', 'diagnostic', 'confirmation'}
    assert report(case)['subsets']['combined']['primary'] is True
    assert report(case)['subsets']['diagnostic']['primary'] is False


def test_policy_binds_split_roles_cohort_and_dependencies_and_checks_source_drift(case, tmp_path):
    scorer = aggregate(case, bootstrap_resamples=32)
    changed_seed = aggregate(case, bootstrap_resamples=32, seed=161804)
    assert scorer.policy_sha256 != changed_seed.policy_sha256
    assert scorer.scoring_policy['inference_roles']['test'] == digest_file(case.inference['test'])
    assert scorer.scoring_policy['truth_roles']['train'] == digest_file(case.truth['train'])
    assert scorer.scoring_policy['test_cohort_sha256'] == digest_file(case.cohort)
    assert 'eeg/readout_aggregation.py' in scorer.scoring_policy['source_sha256']
    assert 'eeg/aggregation.py' in scorer.scoring_policy['source_sha256']
    # Change a bound copy instead of mutating a shared source file during parallel development.
    source = tmp_path / 'source_copy.py'
    source.write_text('original\n')
    scorer.source_bindings = (*scorer.source_bindings, binding(source))
    source.write_text('changed\n')
    output(case)
    with pytest.raises(ValueError, match='Bound input changed'):
        scorer(case.output, specification(case))


def test_role_swap_changes_policy_even_when_flattened_bound_hashes_are_identical(case):
    original = aggregate(case, bootstrap_resamples=8)
    swapped = case.module.ReadoutAggregator(
        {'validation': binding(case.truth['test']), 'test': binding(case.truth['validation'])},
        binding(case.truth['train']),
        {key: binding(path) for key, path in case.inference.items()},
        public_by_split={key: binding(path) for key, path in case.public.items()},
        test_cohort=binding(case.cohort), bootstrap_resamples=8)
    assert {item.sha256 for item in original.bindings} == {item.sha256 for item in swapped.bindings}
    assert original.policy_sha256 != swapped.policy_sha256


@pytest.mark.parametrize('kind', ['disk_bytes', 'decompressed_bytes', 'hardlink'])
def test_readout_byte_caps_and_single_link_files_are_enforced(case, kind):
    output(case)
    path = case.output / 'results.npz'
    if kind == 'disk_bytes':
        with path.open('wb') as stream:
            stream.seek(16 * 1024**2)
            stream.write(b'x')
    elif kind == 'decompressed_bytes':
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('logits.npy', bytes(16 * 1024**2 + 1))
    else:
        os.link(path, case.root / 'linked_result.npz')
    with pytest.raises(ValueError, match='byte cap|single-link'):
        aggregate(case, bootstrap_resamples=8)(case.output, specification(case))


def test_duplicate_json_keys_cannot_override_the_frozen_manifest(case):
    path = case.candidate / 'readouts.json'
    text = json.dumps(case.manifest)
    path.write_text('{"schema_version":"other",' + text[1:])
    output(case)
    with pytest.raises(ValueError, match='Duplicate'):
        aggregate(case, bootstrap_resamples=8)(case.output, specification(case))


def test_undefined_participant_draws_are_counted_without_selective_interval_filtering(case):
    arrays = case.arrays['validation']
    # Unequal, class-pure participants cause some complete-participant draws to
    # contain only one class. Keep estimates, suppress all affected intervals.
    subjects = np.asarray(['validation_p0'] * 6 + ['validation_p1'] * 6)
    y = np.asarray([0] * 6 + [1] * 6)
    arrays.update(subject_ids=subjects, y=y)
    np.savez(case.truth['validation'], sample_ids=arrays['sample_ids'], subject_ids=subjects, y=y)
    np.savez(case.inference['validation'], sample_ids=arrays['sample_ids'], subject_ids=subjects, x=arrays['x'])
    np.savez(case.public['validation'], **arrays)
    output(case)
    metrics = aggregate(case, bootstrap_resamples=32)(case.output, specification(case))['metrics']
    assert 0 < metrics['undefined_bootstrap_draws'] < 32
    assert 'readout_i0_balanced_accuracy' in metrics
    assert 'readout_i0_balanced_accuracy_ci95_low' not in metrics
    assert 'contrast_i0_i1_ci95_low' not in metrics
    assert report(case)['subsets']['validation']['readouts'][0]['balanced_accuracy_ci95'] is None


def test_extreme_finite_correct_scores_have_stable_near_zero_logloss(case):
    values = output(case)
    values['logits'][:, 1] = np.where(case.arrays['validation']['y'] == 1, 1e308, -1e308)
    np.savez(case.output / 'results.npz', **values)
    metrics = aggregate(case, bootstrap_resamples=8)(case.output, specification(case))['metrics']
    assert metrics['readout_i1_logloss'] == 0
    assert metrics['readout_i1_balanced_accuracy'] == 1


def test_actual_actor_public_bindings_are_required(case):
    with pytest.raises((TypeError, ValueError)):
        case.module.ReadoutAggregator(
            {key: binding(case.truth[key]) for key in ('validation', 'test')},
            binding(case.truth['train']),
            {key: binding(path) for key, path in case.inference.items()},
            test_cohort=binding(case.cohort), bootstrap_resamples=8)


@pytest.mark.parametrize('split', ['train', 'validation'])
@pytest.mark.parametrize('mutation', ['x', 'subject_ids', 'y', 'sample_ids', 'row_order'])
def test_public_actor_data_must_exactly_match_private_truth_and_inference(case, split, mutation):
    public = {key: value.copy() for key, value in case.arrays[split].items()}
    if mutation == 'row_order':
        public = {key: value[::-1] for key, value in public.items()}
    elif mutation == 'x':
        public['x'][0, 17] = 1e-12
    elif mutation == 'y':
        public['y'][0] = 1 - public['y'][0]
    else:
        public[mutation][0] = public[mutation][-1]
    np.savez(case.public[split], **public)
    output(case, 'test')
    with pytest.raises(ValueError, match='Public.*alignment'):
        aggregate(case, bootstrap_resamples=8)(case.output, specification(case, 'test'))


@pytest.mark.parametrize('split', ['train', 'validation'])
def test_public_actor_file_hash_is_frozen_and_checked_when_scoring_test(case, split):
    scorer = aggregate(case, bootstrap_resamples=8)
    case.public[split].write_bytes(b'Actor mounted file was changed after enrollment')
    output(case, 'test')
    with pytest.raises(ValueError, match='Bound input changed'):
        scorer(case.output, specification(case, 'test'))


def test_public_role_hashes_are_bound_and_role_swaps_change_identity(case):
    scorer = aggregate(case, bootstrap_resamples=8)
    wanted = {key: digest_file(path) for key, path in case.public.items()}
    assert scorer.scoring_policy['public_roles'] == wanted
    assert all(binding(path) in scorer.bindings for path in case.public.values())
    swapped = aggregate(case, bootstrap_resamples=8, public_by_split={
        'train': binding(case.public['validation']), 'validation': binding(case.public['train'])})
    assert {item.sha256 for item in scorer.bindings} == {item.sha256 for item in swapped.bindings}
    assert scorer.policy_sha256 != swapped.policy_sha256


@pytest.mark.parametrize('roles', [(), ('train',), ('validation',), ('train', 'validation', 'test')])
def test_public_bindings_require_both_and_only_actual_actor_public_splits(case, roles):
    public = {key: binding(case.public.get(key, case.inference['test'])) for key in roles}
    with pytest.raises(ValueError, match='public'):
        aggregate(case, bootstrap_resamples=8, public_by_split=public)


def test_host_runtime_changed_before_scoring_prevents_metric_release(case):
    runtime = case.root / 'runtime_identity'
    runtime.write_text('enrolled host runtime')
    frozen = binding(runtime)
    scorer = aggregate(case, bootstrap_resamples=8, verify_runtime=frozen.verify)
    runtime.write_text('changed host runtime')
    output(case)
    with pytest.raises(ValueError, match='Bound input changed'):
        scorer(case.output, specification(case))
    assert not (case.output / 'trusted_readout_analysis.json').exists()


def test_host_runtime_changed_during_scoring_prevents_metric_release(case):
    runtime = case.root / 'runtime_identity'
    runtime.write_text('enrolled host runtime')
    frozen = binding(runtime)

    def verify_then_simulate_drift() -> None:
        frozen.verify()
        # First check succeeds, then the host dependency changes. A second
        # verification must reject publication of already calculated metrics.
        runtime.write_text('changed after initial verification')

    scorer = aggregate(case, bootstrap_resamples=8, verify_runtime=verify_then_simulate_drift)
    output(case)
    with pytest.raises(ValueError, match='Bound input changed'):
        scorer(case.output, specification(case))
    assert not (case.output / 'trusted_readout_analysis.json').exists()


def test_verified_runtime_and_metadata_only_scorers_have_same_policy_and_scores(case):
    runtime = case.root / 'runtime_identity'
    runtime.write_text('enrolled host runtime')
    verified = aggregate(case, bootstrap_resamples=8, verify_runtime=binding(runtime).verify)
    metadata = aggregate(case, bootstrap_resamples=8)
    assert verified.policy_sha256 == metadata.policy_sha256
    output(case)
    metrics = verified(case.output, specification(case))['metrics']
    assert metrics['readout_i0_balanced_accuracy'] == pytest.approx(5 / 6)
