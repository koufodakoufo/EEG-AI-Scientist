"""V3 trusted row/split/metric binding and declarative replay validation.

CSV artifacts are inert data. No eval, pickle, model execution or subprocesses.
Trusted manifests/receipts must come from the controller, never from the Actor.
The controller must freeze files and isolate the process to prevent write races.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import random
import re
from typing import Any, Mapping, Sequence

from .evidence import _hash_artifact, _is_link, _portable_path, _safe_artifact

VERSION = 'evidence_binding_v3'
MAX_CSV_BYTES = 64 * 1024**2
MAX_CSV_ROWS = 200_000
FORMULA_VERSION = 'registered_metrics_v3.0'


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('Invalid SHA256')
    return value


def _finite(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError('Boolean is not a numeric measurement')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite measurement')
    return result


def _validate_manifest(manifest: Mapping[str, Any], run_id: str) -> None:
    if set(manifest) != {'schema_version','run_id','samples'} or manifest['schema_version'] != 'split_manifest_v3' or manifest['run_id'] != run_id:
        raise ValueError('Trusted split manifest identity mismatch')
    samples = manifest['samples']
    if not isinstance(samples, dict) or not samples:
        raise ValueError('Trusted split manifest needs samples')
    subjects: dict[str,str] = {}
    for sample, item in samples.items():
        if not isinstance(sample,str) or not sample or not isinstance(item,dict) or set(item) != {'subject_id','split'}:
            raise ValueError('Malformed trusted sample entry')
        if not isinstance(item['subject_id'],str) or not item['subject_id'] or item['split'] not in {'train','validation','test','synthetic'}:
            raise ValueError('Invalid subject or split')
        previous = subjects.setdefault(item['subject_id'],item['split'])
        if previous != item['split']:
            raise ValueError('Participant crosses trusted splits')


def _quantile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    offset = (len(ordered)-1)*q
    left = int(math.floor(offset)); right = int(math.ceil(offset))
    return ordered[left] + (ordered[right]-ordered[left])*(offset-left)


def calculate_metric(rows: Sequence[Mapping[str,str]], calculation: Mapping[str,Any]) -> float | list[float]:
    """Allowlisted scalar formulas, explicitly versioned; never arbitrary expressions."""
    if set(calculation) != {'name','columns','parameters'} or not rows:
        raise ValueError('Metric calculation fields or rows invalid')
    name, columns, parameters = calculation['name'], calculation['columns'], calculation['parameters']
    required = {'mean':{'value'}, 'paired_mean_difference':{'before','after'},
                'accuracy':{'prediction','target'}, 'balanced_accuracy':{'prediction','target'},
                'mse':{'prediction','target'}, 'r2':{'prediction','target'},
                'cluster_bootstrap_mean_ci':{'value','group'}}
    if name not in required or not isinstance(columns,dict) or set(columns) != required[name] or not isinstance(parameters,dict):
        raise ValueError('Unregistered formula or incorrect columns')
    if any(not isinstance(column,str) or not column for column in columns.values()):
        raise ValueError('Column names must be nonempty strings')
    if name != 'cluster_bootstrap_mean_ci' and parameters:
        raise ValueError('This formula has no free parameters')
    values = {key:[_finite(row[column]) for row in rows] for key,column in columns.items() if key != 'group'}
    n = len(rows)
    if name == 'mean':
        return math.fsum(values['value'])/n
    if name == 'paired_mean_difference':
        return math.fsum(after-before for before,after in zip(values['before'],values['after']))/n
    if name in {'accuracy','balanced_accuracy'}:
        correct = [float(p == t) for p,t in zip(values['prediction'],values['target'])]
        if name == 'accuracy':
            return math.fsum(correct)/n
        classes = sorted(set(values['target']))
        if len(classes) < 2:
            raise ValueError('Balanced accuracy needs at least two observed target classes')
        return math.fsum(math.fsum(c for c,t in zip(correct,values['target']) if t == label)/values['target'].count(label) for label in classes)/len(classes)
    if name in {'mse','r2'}:
        error = math.fsum((p-t)**2 for p,t in zip(values['prediction'],values['target']))
        if name == 'mse':
            return error/n
        mean = math.fsum(values['target'])/n
        denominator = math.fsum((target-mean)**2 for target in values['target'])
        if denominator <= 0:
            raise ValueError('R2 undefined for constant target')
        return 1-error/denominator
    if set(parameters) != {'seed','iterations','level'} or type(parameters['seed']) is not int or type(parameters['iterations']) is not int:
        raise ValueError('Cluster bootstrap needs explicit seed, iterations, level')
    if columns['group'] != 'subject_id':
        raise ValueError('This registered cluster bootstrap uses trusted subject_id, never individual sample IDs')
    iterations, level = parameters['iterations'], _finite(parameters['level'])
    if not 2 <= iterations <= 10000 or not 0 < level < 1:
        raise ValueError('Invalid bootstrap iteration/level limits')
    grouped: dict[str,list[float]] = {}
    for row,value in zip(rows,values['value']):
        grouped.setdefault(row[columns['group']],[]).append(value)
    if len(grouped) < 2:
        raise ValueError('Cluster bootstrap requires at least two groups')
    keys = sorted(grouped)
    rng = random.Random(parameters['seed'])
    draws = []
    for _ in range(iterations):
        selected = [grouped[key] for key in rng.choices(keys,k=len(keys))]
        draws.append(math.fsum(v for group in selected for v in group)/sum(map(len,selected)))
    tail = (1-level)/2
    return [_quantile(draws,tail),_quantile(draws,1-tail)]


def audit_metric_binding(binding: Mapping[str,Any], artifact_root: Path | str,
                         trusted_split_manifest: Mapping[str,Any], *, expected_run_id: str,
                         trusted_receipt: Mapping[str,Any] | None = None,
                         allowed_splits: Sequence[str] = ('train','validation','synthetic'),
                         expected_sample_ids: Sequence[str] | None = None,
                         atol: float = 1e-8, rtol: float = 1e-6) -> dict[str,Any]:
    """Fail closed; split permission is checked before any artifact content is read.

    Tolerances and optional exact cohort IDs are trusted evaluator parameters.
    Returned data contain computed metrics and row counts, not EEG/row contents.
    """
    result: dict[str,Any] = {'version':VERSION,'binding_id':binding.get('binding_id') if isinstance(binding,Mapping) else None,
                            'valid':False,'errors':[],'computed_value':None,'formula_version':FORMULA_VERSION}
    try:
        required = {'binding_id','run_id','split','artifact_path','artifact_sha256','split_manifest_sha256',
                    'row_selection','row_conditions','calculation','reported_value'}
        if not isinstance(binding,Mapping) or set(binding) != required or binding['run_id'] != expected_run_id:
            raise ValueError('Binding schema or run mismatch')
        if binding['split'] not in allowed_splits:
            raise ValueError('Split is not authorized')
        if not isinstance(binding['binding_id'],str) or not binding['binding_id']:
            raise ValueError('Invalid binding ID')
        if not math.isfinite(atol) or not math.isfinite(rtol) or atol < 0 or rtol < 0:
            raise ValueError('Invalid trusted numerical tolerance')
        _validate_manifest(trusted_split_manifest,expected_run_id)
        if _digest(binding['split_manifest_sha256']) != canonical_sha256(trusted_split_manifest):
            raise ValueError('Trusted split manifest hash mismatch')
        digest = _digest(binding['artifact_sha256'])
        if not isinstance(trusted_receipt,Mapping) or trusted_receipt.get('run_id') != expected_run_id or trusted_receipt.get('status') != 'completed' or type(trusted_receipt.get('exit_code')) is not int or trusted_receipt.get('exit_code') != 0:
            raise ValueError('Missing successful trusted execution receipt')
        if not isinstance(trusted_receipt.get('artifacts'),Mapping) or trusted_receipt['artifacts'].get(binding['artifact_path']) != digest:
            raise ValueError('Artifact is not bound to trusted execution receipt')
        selection = binding['row_selection']
        if not isinstance(selection,dict) or set(selection) != {'indices','sample_ids'}:
            raise ValueError('Explicit row indices and aligned sample IDs required')
        indices, sample_ids = selection['indices'], selection['sample_ids']
        if not isinstance(indices,list) or not isinstance(sample_ids,list) or not indices or len(indices)!=len(sample_ids):
            raise ValueError('Invalid row selector lengths')
        if any(type(index) is not int or index < 0 for index in indices) or len(set(indices))!=len(indices):
            raise ValueError('Duplicate or invalid selected row indices')
        if any(not isinstance(item,str) or not item for item in sample_ids) or len(set(sample_ids))!=len(sample_ids):
            raise ValueError('Duplicate or invalid selected sample IDs')
        if expected_sample_ids is not None and list(expected_sample_ids) != sample_ids:
            raise ValueError('Selected cohort differs from frozen expected cohort')
        for sample in sample_ids:
            if sample not in trusted_split_manifest['samples'] or trusted_split_manifest['samples'][sample]['split'] != binding['split']:
                raise ValueError('Selected sample is outside the declared trusted split')
        conditions = binding['row_conditions']
        if not isinstance(conditions,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in conditions.items()):
            raise ValueError('Row conditions must map column names to exact strings')
        original_root = Path(artifact_root).absolute()
        if any(_is_link(path.lstat()) for path in (original_root,*original_root.parents)):
            raise ValueError('Artifact root links are forbidden')
        root = original_root.resolve(strict=True)
        path = _safe_artifact(root,binding['artifact_path'])
        if path.suffix != '.csv':
            raise ValueError('V3 metric verifier currently supports CSV only')
        if _hash_artifact(path,MAX_CSV_BYTES) != digest:
            raise ValueError('Artifact hash mismatch')
        rows: list[dict[str,str]] = []
        with path.open(encoding='utf-8',newline='') as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not {'sample_id','subject_id','split'} <= set(reader.fieldnames):
                raise ValueError('CSV needs unique headers and sample_id/subject_id/split')
            for row in reader:
                if len(rows) >= MAX_CSV_ROWS or None in row or any(value is None for value in row.values()):
                    raise ValueError('CSV row count/width mismatch')
                rows.append(row)
        if _hash_artifact(path,MAX_CSV_BYTES) != digest:
            raise ValueError('Artifact changed during metric computation')
        if max(indices) >= len(rows):
            raise ValueError('Selected row outside artifact')
        selected = []
        for index,sample in zip(indices,sample_ids):
            row = rows[index]
            trusted = trusted_split_manifest['samples'][sample]
            if row['sample_id'] != sample or row['subject_id'] != trusted['subject_id'] or row['split'] != binding['split']:
                raise ValueError('Row/sample/subject/split mismatch')
            if any(row.get(column) != value for column,value in conditions.items()):
                raise ValueError('Selected row violates declared conditions')
            selected.append(row)
        computed = calculate_metric(selected,binding['calculation'])
        observed = binding['reported_value']
        expected_values = computed if isinstance(computed,list) else [computed]
        actual_values = observed if isinstance(observed,list) else [observed]
        if len(expected_values)!=len(actual_values) or any(not math.isclose(_finite(actual),expected,abs_tol=atol,rel_tol=rtol) for actual,expected in zip(actual_values,expected_values)):
            raise ValueError('Reported numeric value differs from registered recomputation')
        result.update(valid=True,computed_value=computed,row_count=len(selected),
                      split=binding['split'],artifact_sha256=digest,
                      split_manifest_sha256=binding['split_manifest_sha256'],
                      selection_sha256=canonical_sha256(selection),calculation_sha256=canonical_sha256(binding['calculation']))
    except (ValueError,TypeError,KeyError,OSError,OverflowError,csv.Error) as exc:
        result['errors'].append(str(exc))
    return result


def _path(value: Any, *, cwd: bool = False) -> str:
    if cwd and value == '.':
        return '.'
    if not isinstance(value,str):
        raise ValueError('Replay path must be text')
    _portable_path(value)
    return value


def validate_replay_contract(contract: Mapping[str,Any]) -> dict[str,Any]:
    """Validate a declared DAG only. Does not execute or approve any argv.

    No hidden 8-command cap, Python flags or required preregistration filenames.
    Runtime/sandbox restrictions must be separately frozen and shown pre-run.
    """
    if set(contract) != {'schema_version','run_id','limits','seeded_inputs','commands'} or contract['schema_version'] != 'replay_contract_v3':
        raise ValueError('Replay contract schema mismatch')
    limits = contract['limits']
    if not isinstance(limits,dict) or set(limits) != {'max_commands','timeout_seconds','storage_bytes','threads'} or any(type(v) is not int or v <= 0 for v in limits.values()):
        raise ValueError('Explicit positive replay limits required')
    if limits['max_commands'] > 256 or limits['threads'] > 4:
        raise ValueError('Published validator caps: at most 256 commands and 4 threads')
    seeded = contract['seeded_inputs']
    if not isinstance(seeded,dict):
        raise ValueError('Seeded inputs must map paths to hashes')
    for name,digest in seeded.items():
        _path(name); _digest(digest)
    commands = contract['commands']
    if not isinstance(commands,list) or not 1 <= len(commands) <= limits['max_commands']:
        raise ValueError('Command count exceeds declared limits')
    by_id: dict[str,Mapping[str,Any]] = {}
    owners: dict[str,str] = {}
    for command in commands:
        if not isinstance(command,dict) or set(command) != {'command_id','argv','cwd','env','seeds','depends_on','inputs','writable_paths','outputs'}:
            raise ValueError('Replay command fields mismatch')
        identifier = command['command_id']
        if not isinstance(identifier,str) or not identifier or identifier in by_id:
            raise ValueError('Duplicate or invalid command ID')
        by_id[identifier] = command
        if not isinstance(command['argv'],list) or not command['argv'] or any(not isinstance(v,str) or not v or '\x00' in v for v in command['argv']):
            raise ValueError('Explicit nonempty argv required')
        _path(command['cwd'],cwd=True)
        if not isinstance(command['env'],dict) or any(not isinstance(k,str) or not isinstance(v,str) or '\x00' in k+v for k,v in command['env'].items()):
            raise ValueError('Explicit string environment required; no inherited environment')
        if not isinstance(command['seeds'],dict) or any(type(v) is not int for v in command['seeds'].values()):
            raise ValueError('Explicit integer seeds mapping required')
        for field in ('depends_on','inputs','writable_paths'):
            if not isinstance(command[field],list) or any(not isinstance(v,str) for v in command[field]) or len(set(command[field])) != len(command[field]):
                raise ValueError(f'Invalid unique list: {field}')
        for value in command['inputs'] + command['writable_paths']:
            _path(value)
        outputs = command['outputs']
        if not isinstance(outputs,dict) or not outputs:
            raise ValueError('Declared generated outputs required')
        for name,spec in outputs.items():
            _path(name)
            if name in seeded or name in owners:
                raise ValueError('Output cannot replace a seeded input or another command output')
            if not any(name == writable or name.startswith(writable+'/') for writable in command['writable_paths']):
                raise ValueError('Output outside declared writable paths')
            owners[name] = identifier
            if not isinstance(spec,dict) or spec.get('role') not in {'scientific','diagnostic'}:
                raise ValueError('Every output needs an explicit scientific/diagnostic role')
            comparison = spec.get('comparison')
            if spec['role']=='diagnostic':
                if spec != {'role':'diagnostic','comparison':'record_only'}:
                    raise ValueError('Diagnostics are retained but not used for scientific equality')
            elif comparison == 'sha256':
                if set(spec) != {'role','comparison'}:
                    raise ValueError('Exact scientific comparison fields mismatch')
            elif comparison == 'json_numeric':
                if set(spec) != {'role','comparison','atol','rtol'} or _finite(spec['atol']) < 0 or _finite(spec['rtol']) < 0:
                    raise ValueError('Numeric scientific comparison needs frozen tolerances')
            else:
                raise ValueError('Scientific outputs cannot use record_only comparison')
    order: list[str] = []
    remaining = set(by_id)
    while remaining:
        ready = sorted(identifier for identifier in remaining if set(by_id[identifier]['depends_on']) <= set(order))
        if not ready:
            raise ValueError('Replay dependency cycle or missing command dependency')
        order.extend(ready); remaining.difference_update(ready)
    ancestors: dict[str,set[str]] = {}
    for identifier in order:
        ancestors[identifier] = set(by_id[identifier]['depends_on'])
        for parent in by_id[identifier]['depends_on']:
            ancestors[identifier].update(ancestors[parent])
        for name in by_id[identifier]['inputs']:
            if name not in seeded and (name not in owners or owners[name] not in ancestors[identifier]):
                raise ValueError('Input is not seeded or generated by a declared ancestor')
    canonical_sha256(contract)
    return {'schema_version':'replay_contract_validation_v3','contract_sha256':canonical_sha256(contract),
            'execution_order':order,'seeded_inputs':sorted(seeded),'generated_outputs':owners,
            'status':'structurally_valid_not_executed',
            'pending':['runtime allowlist/environment resolution','clean-directory replay execution',
                       'scientific output comparison','sandbox enforcement']}
