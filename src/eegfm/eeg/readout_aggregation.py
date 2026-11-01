"""Trusted scorer for the concrete cached EEG readout Actor task.

This module never loads candidate Python, fitted parameters, labels or cohort
declarations. Numerical consistency and declared coverage do not establish the
scientific validity of fitting, selection or competing explanations; those need
the separate source, fit and full-prediction audit.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, TYPE_CHECKING
import zipfile

import numpy as np

from eegfm.eeg.aggregation import _bounded_npz, _write_new
from eegfm.evaluation.bundle import canonical_bytes, digest_file
from eegfm.evaluation.worker import FileBinding, _path, _sha, candidate_digest

if TYPE_CHECKING:
    from eegfm.agent.controller import EvaluationSpec

TASK_ID = 'eegmmidb-readout-bottleneck-v1'
MANIFEST_SCHEMA = 'cached_readout_manifest_v1'
SCORER_SCHEMA = 'trusted_readout_analysis_v1'
MAX_READOUTS = 6
MAX_BYTES = 16 * 1024**2
ROLES = frozenset({'original', 'representation', 'attributes', 'calibration', 'random', 'other'})
SPLITS = ('train', 'validation', 'test')
# These local dependencies implement the reused bounded reader/safe-file/hash
# boundary. The scorer executes on the host; candidate Docker identity does not
# identify its Python or numerical libraries. Host runtime enrollment is separate.
SOURCE_FILES = ('eeg/readout_aggregation.py', 'eeg/aggregation.py', 'eeg/data.py',
                'eeg/statistics.py', 'evaluation/worker.py', 'evaluation/bundle.py')


def _read_npz(path: Path, schema: Mapping) -> dict[str, np.ndarray]:
    path = _path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Readout archive exceeds byte cap')
    with zipfile.ZipFile(path) as archive:
        if sum(item.file_size for item in archive.infolist()) > MAX_BYTES:
            raise ValueError('Readout decompressed archive exceeds byte cap')
    return _bounded_npz(path, schema)


def _unique_json(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate manifest JSON key')
        result[key] = value
    return result


def _manifest(candidate: Path) -> dict[str, Any]:
    path = _path(candidate / 'readouts.json')
    if path.stat().st_size > 16384:
        raise ValueError('Oversized readout manifest')
    document = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_json)
    if (not isinstance(document, dict)
            or not {'schema_version', 'readouts'} <= set(document)
            or not set(document) <= {'schema_version', 'readouts', 'primary_contrast'}
            or document['schema_version'] != MANIFEST_SCHEMA):
        raise ValueError('Unexpected readout manifest schema')
    readouts = document['readouts']
    if not isinstance(readouts, list) or not 1 <= len(readouts) <= MAX_READOUTS:
        raise ValueError('Declare between one and six readouts')
    names: list[str] = []
    for index, record in enumerate(readouts):
        if (not isinstance(record, dict) or set(record) != {'name', 'role', 'description'}
                or not isinstance(record['name'], str)
                or not re.fullmatch(r'[a-z0-9_]{1,32}', record['name'])
                or not isinstance(record['role'], str) or record['role'] not in ROLES
                or not isinstance(record['description'], str)
                or not 1 <= len(record['description'].strip()) <= 1000
                or (index == 0 and (record['name'] != 'original' or record['role'] != 'original'))
                or (index > 0 and record['role'] == 'original')):
            raise ValueError('Invalid semantic readout declaration')
        names.append(record['name'])
    if len(names) != len(set(names)):
        raise ValueError('Readout names must be unique')
    if 'primary_contrast' in document:
        pair = document['primary_contrast']
        if (not isinstance(pair, list) or len(pair) != 2
                or any(not isinstance(name, str) or name not in names for name in pair)
                or pair[0] == pair[1]):
            raise ValueError('Invalid primary contrast')
    return document


def _metric_names() -> frozenset[str]:
    names = {'readout_count', 'representation_readouts', 'numeric_scope_complete', 'baseline_only',
             'bootstrap_resamples', 'pairwise_comparisons'}
    for subset in ('', 'diagnostic_', 'confirmation_'):
        names.update(subset + name for name in ('participants', 'rows', 'undefined_bootstrap_draws'))
        for index in range(MAX_READOUTS):
            names.update(f'{subset}readout_i{index}_{metric}' for metric in (
                'balanced_accuracy', 'auroc', 'logloss', 'balanced_accuracy_ci95_low',
                'balanced_accuracy_ci95_high'))
        for left, right in combinations(range(MAX_READOUTS), 2):
            names.update(f'{subset}contrast_i{left}_i{right}_{metric}' for metric in (
                'balanced_accuracy_difference', 'ci95_low', 'ci95_high', 'family_ci_low', 'family_ci_high'))
        names.update(subset + 'primary_contrast_' + metric for metric in (
            'balanced_accuracy_difference', 'ci95_low', 'ci95_high'))
    return frozenset(names)


def _scores(y: np.ndarray, logits: np.ndarray) -> dict[str, float]:
    predicted = logits >= 0
    balanced = .5 * (float(np.mean(~predicted[y == 0])) + float(np.mean(predicted[y == 1])))
    negative, positive = np.sort(logits[y == 0]), logits[y == 1]
    lower = np.searchsorted(negative, positive, side='left')
    upper = np.searchsorted(negative, positive, side='right')
    auc = float(np.mean((lower + upper) / (2 * len(negative))))
    # logaddexp on the signed margin avoids catastrophic cancellation at large
    # correct logits; averaging scaled losses avoids overflow of a finite sum.
    loss = np.logaddexp(0., np.where(y == 1, -logits, logits))
    logloss = float(np.sum(loss / len(y)))
    if not np.isfinite([balanced, auc, logloss]).all():
        raise ValueError('Nonfinite derived readout metric')
    return {'balanced_accuracy': balanced, 'auroc': auc, 'logloss': logloss}


def _bootstrap(y: np.ndarray, subjects: np.ndarray, logits: np.ndarray, *,
               resamples: int, seed: int) -> np.ndarray:
    """Pool complete sampled participants, preserving unequal window counts."""
    unique = np.unique(subjects)
    counts = np.zeros((len(unique), 2), dtype=np.int64)
    correct = np.zeros((len(unique), 2, logits.shape[1]), dtype=np.int64)
    for index, subject in enumerate(unique):
        for label in (0, 1):
            rows = (subjects == subject) & (y == label)
            counts[index, label] = np.sum(rows)
            correct[index, label] = np.sum((logits[rows] >= 0) == label, axis=0)
    rng = np.random.default_rng(seed)
    result = np.empty((resamples, logits.shape[1]))
    # Bound intermediate advanced-index arrays even for a maximum-row input
    # with one participant per row. Batching preserves the exact RNG sequence.
    batch_size = min(256, max(1, 262144 // len(unique)))
    for start in range(0, resamples, batch_size):
        stop = min(start + batch_size, resamples)
        draws = rng.integers(0, len(unique), size=(stop - start, len(unique)))
        total, hits = counts[draws].sum(axis=1), correct[draws].sum(axis=1)
        with np.errstate(divide='ignore', invalid='ignore'):
            result[start:stop] = np.mean(hits / total[:, :, None], axis=1)
    return result


def _ci(values: np.ndarray, tail: float = .025) -> list[float] | None:
    # Do not silently select only defined draws for class-degenerate bootstraps.
    if not np.isfinite(values).all():
        return None
    return np.quantile(values, [tail, 1 - tail], method='linear').tolist()


class ReadoutAggregator:
    """Worker callable binding public data to private truth/inference and cohorts.

    The actual worker factory supplies ``verify_runtime`` for its enrolled host
    runtime. A controller constructing only the portable identity may omit it.
    The callback is trusted enrollment code, never candidate-supplied code.
    """

    released_metrics = _metric_names()

    def __init__(self, truth_by_split: Mapping[str, FileBinding], train_truth: FileBinding,
                 inference_by_split: Mapping[str, FileBinding], *, test_cohort: FileBinding,
                 public_by_split: Mapping[str, FileBinding],
                 bootstrap_resamples: int = 10000, seed: int = 161803,
                 verify_runtime: Callable[[], None] | None = None,
                 runtime_identity: Mapping[str, Any] | None = None) -> None:
        if set(truth_by_split) != {'validation', 'test'} or set(inference_by_split) != set(SPLITS):
            raise ValueError('Readout scoring requires explicit train/validation/test bindings')
        if set(public_by_split) != {'train', 'validation'}:
            raise ValueError('Readout scoring requires exactly train/validation public bindings')
        if type(bootstrap_resamples) is not int or not 1 <= bootstrap_resamples <= 10000:
            raise ValueError('Invalid bootstrap resample count')
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError('Invalid participant bootstrap seed')
        self.truth = MappingProxyType({name: truth_by_split[name] for name in ('validation', 'test')})
        self.train_truth = train_truth
        self.inference = MappingProxyType({name: inference_by_split[name] for name in SPLITS})
        self.public = MappingProxyType({name: public_by_split[name] for name in ('train', 'validation')})
        self.test_cohort = test_cohort
        self.verify_runtime = verify_runtime
        self.bootstrap_resamples, self.seed = bootstrap_resamples, seed
        package = Path(__file__).resolve().parents[1]
        self.source_bindings = tuple(FileBinding(package / name, digest_file(package / name))
                                     for name in SOURCE_FILES)
        self.input_bindings = (train_truth, *self.truth.values(), *self.inference.values(),
                               *self.public.values(), test_cohort)
        self.bindings = (*self.input_bindings, *self.source_bindings)
        self._scoring_policy = {
            'task_id': TASK_ID, 'schema_version': SCORER_SCHEMA, 'manifest_schema': MANIFEST_SCHEMA,
            'input_schema': 'cached_readout_x325_v1', 'output_schema': 'cached_readout_results_v1',
            'truth_roles': {'train': train_truth.sha256, **{name: item.sha256 for name, item in self.truth.items()}},
            'inference_roles': {name: item.sha256 for name, item in self.inference.items()},
            'public_roles': {name: item.sha256 for name, item in self.public.items()},
            'public_alignment': 'exact_x_sample_ids_subject_ids_to_inference_and_y_to_truth',
            'test_cohort_sha256': test_cohort.sha256,
            'source_sha256': {name: item.sha256 for name, item in zip(SOURCE_FILES, self.source_bindings)},
            'max_readouts': MAX_READOUTS, 'max_archive_bytes': MAX_BYTES, 'max_rows': 4096,
            'original_logit_column': 262, 'original_logit_equality': 'exact_value_no_tolerance',
            'logit_threshold': 0., 'bootstrap_unit': 'participant', 'bootstrap_resamples': bootstrap_resamples,
            'seed': seed, 'paired_draws': True, 'quantile_method': 'linear',
            'multiplicity': 'Bonferroni_over_actual_all_pair_count', 'confidence': .95,
            'useful_balanced_accuracy_margin': .03,
            'undefined_value_policy': 'null_interval_if_any_draw_lacks_a_class; no_scalar_release',
            'test_subsets': ['combined_primary', 'diagnostic_descriptive', 'confirmation_descriptive'],
            'released_metrics': sorted(self.released_metrics)}
        if runtime_identity is not None:
            self._scoring_policy['aggregate_runtime'] = json.loads(canonical_bytes(dict(runtime_identity)))
        self.policy_sha256 = hashlib.sha256(canonical_bytes(self._scoring_policy)).hexdigest()
        self._verify_bindings()

    @property
    def scoring_policy(self) -> dict[str, Any]:
        return json.loads(canonical_bytes(self._scoring_policy))

    def _verify_bindings(self) -> None:
        for binding in (*self.input_bindings, *self.source_bindings):
            binding.verify()

    def _inputs(self) -> tuple[dict[str, dict[str, np.ndarray]], dict[str, np.ndarray], np.ndarray]:
        truths, inferred = {}, {}
        all_truth = {'train': self.train_truth, **self.truth}
        for split in SPLITS:
            truth = _read_npz(all_truth[split].verify(), {
                'sample_ids': ((None,), 'USiu'), 'subject_ids': ((None,), 'USiu'), 'y': ((None,), 'iu')})
            n = len(truth['y'])
            if (n < 4 or any(len(value) != n for value in truth.values())
                    or len(np.unique(truth['sample_ids'])) != n
                    or len(np.unique(truth['subject_ids'])) < 2
                    or set(truth['y'].tolist()) != {0, 1}):
                raise ValueError('Invalid trusted sample/participant/label alignment')
            inference = _read_npz(self.inference[split].verify(), {
                'sample_ids': ((n,), 'USiu'), 'subject_ids': ((n,), 'USiu'), 'x': ((n, 325), 'f')})
            if any(not np.array_equal(truth[key], inference[key]) for key in ('sample_ids', 'subject_ids')):
                raise ValueError('Trusted inference row/participant alignment differs from truth')
            if split in self.public:
                public = _read_npz(self.public[split].verify(), {
                    'sample_ids': ((n,), 'USiu'), 'subject_ids': ((n,), 'USiu'),
                    'y': ((n,), 'iu'), 'x': ((n, 325), 'f')})
                if (any(not np.array_equal(public[key], inference[key])
                        for key in ('x', 'sample_ids', 'subject_ids'))
                        or not np.array_equal(public['y'], truth['y'])):
                    raise ValueError('Public train/validation alignment differs from trusted inputs')
            truths[split], inferred[split] = truth, inference['x']
        for left, right in combinations(SPLITS, 2):
            for key in ('sample_ids', 'subject_ids'):
                if set(truths[left][key].tolist()) & set(truths[right][key].tolist()):
                    raise ValueError('Train/validation/test samples or participants overlap')
        test = truths['test']
        cohort = _read_npz(self.test_cohort.verify(), {
            'sample_ids': ((len(test['y']),), 'USiu'), 'cohort': ((len(test['y']),), 'US')})
        labels = cohort['cohort'].astype(str)
        if (not np.array_equal(cohort['sample_ids'], test['sample_ids'])
                or set(labels.tolist()) != {'diagnostic', 'confirmation'}):
            raise ValueError('Private cohort labels or row alignment mismatch')
        for subject in np.unique(test['subject_ids']):
            if len(np.unique(labels[test['subject_ids'] == subject])) != 1:
                raise ValueError('Private cohort splits a participant')
        for label in ('diagnostic', 'confirmation'):
            if set(test['y'][labels == label].tolist()) != {0, 1}:
                raise ValueError('Each private cohort must contain both task labels')
        return truths, inferred, labels

    def _summary(self, truth: Mapping[str, np.ndarray], logits: np.ndarray, rows: np.ndarray,
                 manifest: dict[str, Any], *, primary: bool) -> tuple[dict[str, float], dict[str, Any]]:
        y, subjects, scores = truth['y'][rows], truth['subject_ids'][rows], logits[rows]
        names = [record['name'] for record in manifest['readouts']]
        boots = _bootstrap(y, subjects, scores, resamples=self.bootstrap_resamples, seed=self.seed)
        metrics = {'participants': float(len(np.unique(subjects))), 'rows': float(len(y)),
                   'undefined_bootstrap_draws': float(np.sum(~np.isfinite(boots).all(axis=1)))}
        report: dict[str, Any] = {'primary': primary, 'rows': len(y),
            'participants': int(metrics['participants']), 'readouts': [], 'contrasts': [],
            'undefined_bootstrap_draws': int(metrics['undefined_bootstrap_draws'])}

        def emit_interval(prefix: str, values: list[float] | None) -> None:
            if values is not None:
                metrics.update({prefix + '_low': values[0], prefix + '_high': values[1]})

        raw_scores = []
        for index, name in enumerate(names):
            values = _scores(y, scores[:, index])
            raw_scores.append(values['balanced_accuracy'])
            metrics.update({f'readout_i{index}_' + key: value for key, value in values.items()})
            ci = _ci(boots[:, index])
            emit_interval(f'readout_i{index}_balanced_accuracy_ci95', ci)
            report['readouts'].append({'name': name, **values, 'balanced_accuracy_ci95': ci})
        pair_count = len(names) * (len(names) - 1) // 2
        for left, right in combinations(range(len(names)), 2):
            delta = boots[:, left] - boots[:, right]
            ci, family = _ci(delta), _ci(delta, .05 / (2 * pair_count))
            difference = raw_scores[left] - raw_scores[right]
            prefix = f'contrast_i{left}_i{right}_'
            metrics[prefix + 'balanced_accuracy_difference'] = difference
            emit_interval(prefix + 'ci95', ci)
            emit_interval(prefix + 'family_ci', family)
            report['contrasts'].append({'left': names[left], 'right': names[right],
                'balanced_accuracy_difference': difference, 'ci95': ci, 'family_ci': family})
        if 'primary_contrast' in manifest:
            left, right = [names.index(name) for name in manifest['primary_contrast']]
            ci = _ci(boots[:, left] - boots[:, right])
            difference = raw_scores[left] - raw_scores[right]
            metrics['primary_contrast_balanced_accuracy_difference'] = difference
            emit_interval('primary_contrast_ci95', ci)
            report['primary_contrast'] = {'left': names[left], 'right': names[right],
                'balanced_accuracy_difference': difference, 'ci95': ci}
        return metrics, report

    def __call__(self, output: Path, spec: EvaluationSpec) -> dict[str, Any]:
        if self.verify_runtime is not None:
            self.verify_runtime()
        if spec.split not in self.truth:
            raise ValueError('Only validation/test scoring is supported')
        output = _path(output, directory=True)
        if {path.name for path in output.iterdir()} != {'results.npz'}:
            raise ValueError('Readout output must contain exactly results.npz')
        self._verify_bindings()
        candidate = _path(spec.candidate_dir, directory=True)
        if candidate_digest(candidate) != _sha(spec.candidate_digest):
            raise ValueError('Candidate differs from frozen identity')
        manifest = _manifest(candidate)
        truth_by_split, inferred, cohorts = self._inputs()
        truth = truth_by_split[spec.split]
        names = [record['name'] for record in manifest['readouts']]
        results_path = output / 'results.npz'
        results_sha256 = digest_file(_path(results_path))
        arrays = _read_npz(results_path, {'sample_ids': ((len(truth['y']),), 'USiu'),
            'readout_names': ((len(names),), 'US'), 'logits': ((len(truth['y']), len(names)), 'f')})
        if (not np.array_equal(arrays['sample_ids'], truth['sample_ids'])
                or arrays['readout_names'].astype(str).tolist() != names):
            raise ValueError('Output sample order or readout names differ from frozen identity')
        canonical = inferred[spec.split][:, 262]
        if not np.array_equal(arrays['logits'][:, 0], canonical):
            raise ValueError('The original readout must equal bound canonical logits exactly')
        logits = arrays['logits'].astype(np.float64)
        logits[:, 0] = canonical  # Every original statistic uses bound inference scores.
        count = len(names)
        representation = sum(record['role'] == 'representation' for record in manifest['readouts'])
        metrics = {'readout_count': float(count), 'representation_readouts': float(representation),
            'numeric_scope_complete': float(count >= 2 and representation >= 1),
            'baseline_only': float(count == 1), 'bootstrap_resamples': float(self.bootstrap_resamples),
            'pairwise_comparisons': float(count * (count - 1) // 2)}
        subsets = {'combined' if spec.split == 'test' else 'validation': np.ones(len(logits), dtype=bool)}
        if spec.split == 'test':
            subsets.update({name: cohorts == name for name in ('diagnostic', 'confirmation')})
        report = {'schema_version': SCORER_SCHEMA, 'task_id': TASK_ID, 'split': spec.split,
            'candidate_digest': spec.candidate_digest, 'policy_sha256': self.policy_sha256,
            'manifest': manifest, 'manifest_sha256': digest_file(candidate / 'readouts.json'),
            'results_sha256': results_sha256, 'subsets': {},
            'scientific_validity': 'pending_source_fit_and_prediction_audit',
            'identity': {name: getattr(spec, name, None) for name in ('job_id', 'episode_id', 'run_id',
                'attempt_id', 'public_manifest_sha256', 'split_manifest_sha256')},
            'uncertainty': {'unit': 'participant', 'resamples': self.bootstrap_resamples,
                'seed': self.seed, 'shared_draws_across_readouts': True,
                'pair_count': count * (count - 1) // 2, 'confidence': .95,
                'quantile_method': 'linear', 'multiplicity': 'Bonferroni over actual all-pair count',
                'useful_balanced_accuracy_margin': .03,
                'limitations': 'Percentile bootstrap and Bonferroni quantiles are approximate; small participant cohorts limit inference.'},
            'limitations': ['Declared roles and numerical completion do not certify scientific discrimination.',
                'Source semantics, train-only fitting, selection and full prediction replay require independent audit.',
                'Diagnostic and confirmation subsets are descriptive; combined test is primary.']}
        for name, rows in subsets.items():
            primary = name in {'combined', 'validation'}
            values, summary = self._summary(truth, logits, rows, manifest, primary=primary)
            prefix = '' if primary else name + '_'
            metrics.update({prefix + key: value for key, value in values.items()})
            report['subsets'][name] = summary
        if (not set(metrics) <= self.released_metrics
                or any(not np.isfinite(value) for value in metrics.values())):
            raise ValueError('Undeclared or nonfinite released readout metric')
        self._verify_bindings()
        if candidate_digest(candidate) != spec.candidate_digest or digest_file(results_path) != results_sha256:
            raise ValueError('Candidate or results changed during scoring')
        if self.verify_runtime is not None:
            self.verify_runtime()
        report['metrics'] = metrics
        report_path = output / 'trusted_readout_analysis.json'
        _write_new(report_path, report)
        return {'metrics': metrics, 'artifacts': [
            {'path': path.name, 'sha256': digest_file(path)} for path in (results_path, report_path)]}
