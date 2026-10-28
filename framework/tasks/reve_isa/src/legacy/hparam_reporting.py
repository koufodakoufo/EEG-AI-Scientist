"""Derived H2 comparisons and observed run accounting; preserve original scores."""
from collections import Counter
import math
from pathlib import Path

from artifact_io import read_json, sha256_file
from data_contract import TARGETS
from evaluation_contract import EVALUATION_HASH
from hparam_contract import load_previous, PREVIOUS_RUN, PREVIOUS_VALIDATION, SUMMARY_SHA256


def reference(path):
    return {'path': str(path), 'sha256': sha256_file(path)}


def compare_previous(report, root):
    previous = load_previous(root)
    if (report.get('execution_valid') is not True or report.get('validation_evaluations') != 72
            or report.get('evaluation_hash') != EVALUATION_HASH
            or set(report['validation_summary']['datasets']) != set(TARGETS)):
        raise ValueError('H2 comparison requires complete identity-matched validation scores')
    datasets = {}
    for target in TARGETS:
        datasets[target] = {}
        for mode in ('lp', 'ft'):
            old = previous['validation_summary']['datasets'][target][mode]['candidate_bacc_mean']
            new = report['validation_summary']['datasets'][target][mode]['candidate_bacc_mean']
            if any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or not 0 <= v <= 1 for v in (old, new)):
                raise ValueError('Invalid validation balanced accuracy')
            datasets[target][mode] = {'H1_validation_bacc_mean': old, 'H2_validation_bacc_mean': new,
                                      'delta': new - old, 'delta_percentage_points': 100 * (new - old)}
    macro = {}
    for mode in ('lp', 'ft'):
        macro[mode] = {
            'H1_validation_bacc_mean': sum(datasets[t][mode]['H1_validation_bacc_mean'] for t in TARGETS) / 6,
            'H2_validation_bacc_mean': sum(datasets[t][mode]['H2_validation_bacc_mean'] for t in TARGETS) / 6,
            'delta': sum(datasets[t][mode]['delta'] for t in TARGETS) / 6,
            'delta_percentage_points': sum(datasets[t][mode]['delta_percentage_points'] for t in TARGETS) / 6,
            'positive_gain_datasets': sum(datasets[t][mode]['delta'] > 0 for t in TARGETS)}
    return {'previous_run_id': PREVIOUS_RUN, 'previous_candidate': 'H1', 'current_candidate': 'H2',
            'previous_validation_original_sha256': PREVIOUS_VALIDATION,
            'selection_evidence': {'path': 'previous_validation_summary.json', 'sha256': SUMMARY_SHA256},
            'test_input_used': False, 'datasets': datasets, 'equal_dataset_macro': macro}


def task_ids(value):
    """Only copy identifiers from receipts, never arbitrary receipt payloads."""
    names = {'task_id', 'job_id', 'cloud_task_id', 'tione_task_id', 'TaskId', 'TrainingJobId'}
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in names and isinstance(item, str):
                found.add(item)
            elif isinstance(item, (dict, list)):
                found.update(task_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(task_ids(item))
    return sorted(found)


def runtime_summary(artifacts, report):
    artifacts = Path(artifacts)
    receipts = []
    for path in sorted((artifacts / 'tione/receipts').glob('*.json')):
        value = read_json(path)
        receipts.append({'evidence': reference(path), 'request_id': value.get('request_id', path.stem),
                         'observed_status': value.get('status'), 'task_ids': task_ids(value),
                         'requested_gpus': value.get('gpus'),
                         'timing': {k: value[k] for k in ('created_at', 'submitted_at', 'started_at', 'finished_at',
                                                         'completed_at', 'updated_at', 'wall_seconds') if k in value}})
    details = []
    for pattern in ('tione/outputs/*/worker_result.json', 'tione/outputs/*/preflight.json',
                    'tione/outputs/*/throughput_plan.json', 'tione/outputs/*/telemetry*.json',
                    'conditions/R*/*/*/posttrain/training.json', 'conditions/R*/*/*/posttrain/epochs.json'):
        details.extend(reference(path) for path in sorted(artifacts.glob(pattern)))
    workers = []
    for path in sorted(artifacts.glob('tione/outputs/*/worker_result.json')):
        value = read_json(path)
        workers.append({'evidence': reference(path), 'phase': value.get('phase'),
                        'target': value.get('target'), 'actual_visible_gpu_count': value.get('actual_gpu_count')})
    diagnostics = {}
    for target, value in report.get('training_and_throughput_diagnostics', {}).items():
        training = value.get('posttrain', {})
        telemetry = training.get('telemetry', {})
        smoke = value.get('cuda_smoke', {})
        diagnostics[target] = {'epochs_completed': training.get('epochs_completed'),
                               'updates_completed': training.get('updates_completed'),
                               'posttrain_wall_seconds': telemetry.get('wall_seconds'),
                               'posttrain_telemetry': telemetry,
                               'smoke_telemetry': smoke.get('telemetry'),
                               'active_posttrain_source_replicas': smoke.get('source_gpu_replicas'),
                               'throughput_plan': value.get('throughput_plan')}
    statuses = dict(Counter(row['observed_status'] or 'UNAVAILABLE' for row in receipts))
    failures = [row for row in receipts if row['observed_status'] in
                {'FAILED', 'STOPPED', 'REJECTED', 'SUBMISSION_UNRESOLVED'}]
    return {'receipt_count': len(receipts), 'receipt_status_counts': statuses,
            'receipts': receipts, 'observed_failed_or_unresolved_receipts': failures,
            'workers': workers, 'target_training': diagnostics, 'detail_evidence': details,
            'requested_allocation': {'gpus_per_worker': 6, 'parallel_workers_max': 6, 'active_gpu_max': 36},
            'recovery_accounting_boundary': 'Observed current-run receipts and saved worker telemetry only; '
                'overwritten or external attempt histories are not inferred. Missing receipt fields remain null. '
                'Training wall times may overlap and are not deployment elapsed time.'}


def enrich_report(report, *, root, artifacts):
    comparison = compare_previous(report, root)
    report['cross_run_mapping'] = {'controller_round': 1, 'controller_round_limit': 1,
                                   'internal_condition': 'R1', 'candidate_label': 'H2',
                                   'previous_run_id': PREVIOUS_RUN, 'previous_candidate_label': 'H1'}
    report['previous_ISA_validation_comparison'] = comparison
    report['runtime_summary'] = runtime_summary(artifacts, report)
    report['performance_assessment'] = {
        'progress_vs_previous_ISA': {'criterion': 'equal_dataset_FT_validation_delta_vs_H1 > 0',
            'met': comparison['equal_dataset_macro']['ft']['delta'] > 0,
            'metrics': comparison['equal_dataset_macro']['ft']}}
    if 'final' in report:
        final = report['final']
        delta, positives = final['ft_macro_paired_delta'], final['ft_positive_gain_datasets']
        report['performance_assessment']['overall_gain_vs_original_REVE'] = {
            'criterion': 'locked_candidate_equal_dataset_FT_test_delta_vs_R0 > 0',
            'met': delta > 0, 'mean_delta': delta, 'positive_gain_datasets': positives}
        report['performance_assessment']['original_research_goal'] = {
            'criterion': 'all_six_dataset_FT_test_deltas_vs_R0 > 0', 'met': positives == 6,
            'positive_gain_datasets': positives}
        report['final']['limitations'].append(
            'Historical test results had already been viewed before this exploratory H2 follow-up; '
            'validation-only parameter selection does not create an unseen independent confirmatory test.')
    report['scope'] = ('Exploratory H2 follow-up using historical subject splits and previously viewed historical test sets. '
                       'New parameters use validation/training evidence only; no independent confirmatory test claim.')
    return report
