"""Opt-in delegated episode admission, no model/science/provider starts."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from eegfm.eeg import episode
from eegfm.evaluation.bundle import digest_file
from test_readout_aggregation import case


def config(tmp_path):
    roles=['public_train','public_validation','inference_train','inference_validation','inference_test','truth_train','truth_validation','truth_test','cohort','split_manifest']
    bindings={}
    for role in roles:
        p=tmp_path/f'{role}.npz';p.write_bytes(role.encode());bindings[role]={'path':str(p),'sha256':digest_file(p)}
    proof=tmp_path/'historical.json';proof.write_text(json.dumps({'status':'exact_historical_readout_inputs_qualified_for_development_replay','not_project_unseen_confirmation':True,'previous_successful_test_job':'old-success-test','bindings':[{'role':name,'sha256':value['sha256']} for name,value in bindings.items()]}))
    return {'schema_version':'audited_coding_episode_v1','task_id':episode.READOUT_TASK,'model':'gpt-6.1-sol','reasoning_effort':'high','session_timeout_seconds':180,'episode_timeout_seconds':2700,'call_ids':['coding-1','coding-2'],
      'historical_data_qualification':{'path':str(proof),'sha256':digest_file(proof)},'train_input':bindings['public_train'],'public_validation_input':bindings['public_validation'],
      'validation_input':bindings['inference_validation'],'test_input':bindings['inference_test'],'inference_by_split':{s:bindings['inference_'+s] for s in ('train','validation','test')},
      'train_truth':bindings['truth_train'],'truth_by_split':{s:bindings['truth_'+s] for s in ('validation','test')},'test_cohort':bindings['cohort'],'split_manifest':bindings['split_manifest']}


def test_new_provider_schema_explicitly_routes_without_native_auth_path(tmp_path):
    value=config(tmp_path)
    with patch.object(episode,'run_delegated_episode',return_value={'typed_provider':True}):
        assert episode.run_episode(value)=={'typed_provider':True}


def test_historical_exact_roles_and_allocation_are_required(tmp_path):
    value=config(tmp_path)
    result=episode.validate_delegated_config(value)
    assert result['previous_successful_test_job']=='old-success-test'
    for update in ({'session_timeout_seconds':900},{'auth_source':'never-read'},{'task_id':'unknown'},{'test_input':value['validation_input']}):
        with pytest.raises(ValueError):episode.validate_delegated_config({**value,**update})


@pytest.mark.parametrize('deadline', [True, 0, -1, 2500.0, float('inf'), '2500'])
def test_absolute_deadline_requires_positive_integer_epoch(tmp_path, deadline):
    value = config(tmp_path)
    with pytest.raises(ValueError, match='deadline'):
        episode.validate_delegated_config({**value, 'episode_deadline_epoch': deadline})


def test_delegated_allocation_keeps_actual_start_and_original_deadline(tmp_path):
    value = config(tmp_path)
    value['episode_deadline_epoch'] = 3500
    budget = tmp_path / 'budget.json'
    budget.write_text(json.dumps({'deadline_at': '1970-01-01T00:58:20+00:00',
                                 'stop_new_research_at': '1970-01-01T00:58:00+00:00'}))
    value['budget_path'] = str(budget)
    assert episode.delegated_deadline(value, 1000.25) == 3500
    # A later process reuses the actual enrollment start, not its restart time.
    with patch.object(episode.time, 'time', return_value=3000):
        assert episode.delegated_deadline(value, 1000.25) == 3500
    assert episode.delegated_deadline(config(tmp_path), 1000.25) == 3700.25
    for start in (3500, 3501, 799):
        with pytest.raises(ValueError, match='deadline'):
            episode.delegated_deadline(value, start)
    budget.write_text(json.dumps({'deadline_at': '1970-01-01T01:00:00+00:00',
                                 'stop_new_research_at': '1970-01-01T00:58:00+00:00'}))
    with pytest.raises(ValueError, match='budget'):
        episode.delegated_deadline(value, 1000.25)


def test_fixed_deadline_propagates_to_worker_and_refuses_late_science(monkeypatch):
    from types import SimpleNamespace
    calls = []
    worker = SimpleNamespace(timeout=180, operation_timeout_seconds=360,
                             deadline_epoch=None, submit=lambda value: calls.append(value))
    evaluator = episode.DeadlineEvaluator(worker, 1000.25, timeout_seconds=2700, deadline_epoch=3500)
    assert evaluator.started_at == 1000.25
    assert evaluator.deadline_epoch == worker.deadline_epoch == 3500
    monkeypatch.setattr(episode.time, 'time', lambda: 3100)
    evaluator.submit('within-allocation')
    monkeypatch.setattr(episode.time, 'time', lambda: 3111)
    with pytest.raises(episode.BudgetExceeded):
        evaluator.submit('too-late')
    assert calls == ['within-allocation']
    with pytest.raises(ValueError, match='deadline'):
        episode.DeadlineEvaluator(worker, 1000.25, timeout_seconds=2700, deadline_epoch=3800)


@pytest.mark.parametrize('private_alias', [None, 'truth_train', 'truth_validation', 'truth_test',
                                            'inference_train', 'inference_validation', 'inference_test', 'cohort'])
def test_delegated_entry_keeps_public_resources_and_denies_private_role_aliases(case, monkeypatch, private_alias):
    from eegfm.eeg.readout_aggregation import ReadoutAggregator
    from eegfm.evaluation import ssh_worker

    root = case.root
    actor, trusted, source = root / 'actor-case', root / 'trusted', root / 'public-source'
    source.mkdir()
    (source / 'resources').mkdir()
    (source / 'eeg_api.py').write_text('# Synthetic public resource\n', encoding='utf-8')
    (source / 'resources/CACHE_SCHEMA.json').write_text('{}', encoding='utf-8')
    for split, path in case.public.items():
        (source / (split + '.npz')).write_bytes(path.read_bytes())
    split_manifest = root / 'splits.json'
    split_manifest.write_text('{}', encoding='utf-8')
    paths = {**{'public_' + split: source / (split + '.npz') for split in case.public},
             **{'truth_' + split: path for split, path in case.truth.items()},
             **{'inference_' + split: path for split, path in case.inference.items()},
             'cohort': case.cohort, 'split_manifest': split_manifest}
    value = {'schema_version':'audited_coding_episode_v1','task_id':episode.READOUT_TASK,'model':'gpt-6.1-sol',
             'reasoning_effort':'high','session_timeout_seconds':240,'episode_timeout_seconds':2700,
             'call_ids':['actor-01'],'case_root':str(actor),'trusted_root':str(trusted),'condition':'no_skill',
             'public_source':str(source),'public_files':['train.npz','validation.npz','eeg_api.py','resources/CACHE_SCHEMA.json'],
             'budget_path':str(trusted / 'budget.json'), 'aggregate_runtime':{
                 'schema_version':'readout_host_runtime_v1','python':{'implementation':'CPython','version':'fixture',
                 'executable_sha256':'a'*64},'packages':{'numpy':'fixture','scipy':'fixture','sklearn':'fixture'},
                 'modules':{'numpy':'b'*64},'libraries':[],'verifier_source_sha256':'c'*64}}
    if private_alias:
        # Exercise the resume-side guard with a byte-identical, declared public
        # file masquerading as a private role. A path-based exemption is unsafe.
        public = episode.prepare_public(value, actor, trusted)
        (trusted / 'ENROLLMENT.json').write_text('{}', encoding='utf-8')
        paths[private_alias] = public / 'train.npz'
    bindings = {role:{'path':str(path),'sha256':digest_file(path)} for role,path in paths.items()}
    proof = root / 'historical.json'
    proof.write_text(json.dumps({'status':'exact_historical_readout_inputs_qualified_for_development_replay',
          'not_project_unseen_confirmation':True,'previous_successful_test_job':'synthetic-prior-test',
          'bindings':[{'role':role,'sha256':item['sha256']} for role,item in bindings.items()]}),encoding='utf-8')
    value.update(historical_data_qualification={'path':str(proof),'sha256':digest_file(proof)},
                 train_input=bindings['public_train'],public_validation_input=bindings['public_validation'],
                 validation_input=bindings['inference_validation'],test_input=bindings['inference_test'],
                 inference_by_split={split:bindings['inference_'+split] for split in case.inference},
                 train_truth=bindings['truth_train'],truth_by_split={split:bindings['truth_'+split] for split in ('validation','test')},
                 test_cohort=bindings['cohort'],split_manifest=bindings['split_manifest'],
                 cloud_worker={'host':'fixture','port':22,'user':'fixture','known_hosts':bindings['split_manifest'],
                               'python':'/usr/bin/python','code':'/fixture','config':bindings['split_manifest']})
    observed = []
    real_load = episode.load_aggregator

    def observe_aggregate(*args, **kwargs):
        aggregate = real_load(*args, **kwargs)
        assert isinstance(aggregate, ReadoutAggregator)
        observed.append(aggregate)
        return aggregate

    class ReachedWorkerBoundary(Exception):
        pass

    def stop_before_ssh(**kwargs):
        raise ReachedWorkerBoundary

    monkeypatch.setattr(episode, 'os', SimpleNamespace(name='posix'))
    monkeypatch.setattr(episode, 'load_aggregator', observe_aggregate)
    monkeypatch.setattr(ssh_worker, 'SshWorkerEvaluator', stop_before_ssh)
    if private_alias:
        with pytest.raises(ValueError, match='Private bindings cannot be mounted inside Actor case'):
            episode.run_delegated_episode(value)
    else:
        with pytest.raises(ReachedWorkerBoundary):
            episode.run_delegated_episode(value)
    assert len(observed) == 1
    assert {binding.path for binding in observed[0].public.values()} == {
        actor / 'public/train.npz', actor / 'public/validation.npz'}
