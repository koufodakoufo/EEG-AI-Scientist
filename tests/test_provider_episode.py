"""Opt-in delegated episode admission, no model/science/provider starts."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from eegfm.eeg import episode
from eegfm.evaluation.bundle import digest_file
from test_readout_aggregation import case
from test_agent_provider import setup_provider, open_session, call


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


def test_shared_coding_provider_keeps_two_public_fit_reservations(setup_provider):
    """The residual registration reuses this exact episode-wide provider gate."""
    import hashlib
    _, box, _ = setup_provider
    open_session(box)
    call(box, 'task')
    text = '# synthetic fit source, not executed\n'
    call(box, 'write_chunk', {'path': 'candidate/fit.py', 'offset': 0, 'text': text})
    call(box, 'seal_file', {'path': 'candidate/fit.py', 'sha256': hashlib.sha256(text.encode()).hexdigest()})
    submissions = []
    class Bench:
        def submit(self, job_id, path):
            submissions.append(job_id)
            return {'job_id': job_id, 'status': 'waiting'}
    box.workbench_factory = lambda case: Bench()
    for number in (1, 2):
        assert call(box, 'fit_submit', {'job_id': f'fit-{number}', 'candidate_dir': 'candidate'})['status'] == 'ok'
    denied = call(box, 'fit_submit', {'job_id': 'fit-3', 'candidate_dir': 'candidate'})
    assert denied['status'] == 'rejected'
    assert len(submissions) == 2
    with box.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM fits').fetchone()[0] == 2


def test_historical_exact_roles_and_allocation_are_required(tmp_path):
    value=config(tmp_path)
    result=episode.validate_delegated_config(value)
    assert result['previous_successful_test_job']=='old-success-test'
    for update in ({'session_timeout_seconds':900},{'auth_source':'never-read'},{'task_id':'unknown'},{'test_input':value['validation_input']}):
        with pytest.raises(ValueError):episode.validate_delegated_config({**value,**update})


def test_registered_astra_identity_is_admitted_without_relaxing_budget(tmp_path):
    value = {**config(tmp_path), 'model': 'gpt-6-astra', 'reasoning_effort': 'ultra'}
    assert episode.validate_delegated_config(value)['previous_successful_test_job']
    for change in ({'model': 'unregistered'}, {'reasoning_effort': 'invented'},
                   {'session_timeout_seconds': 481}):
        with pytest.raises(ValueError):
            episode.validate_delegated_config({**value, **change})


@pytest.mark.parametrize('context_seconds', [180, 480])
@pytest.mark.parametrize('task', [episode.READOUT_TASK, episode.RESIDUAL_RECOVERY_TASK])
@pytest.mark.parametrize('model,effort', [('gpt-6.1-sol', 'high'), ('gpt-6-astra', 'ultra')])
@pytest.mark.parametrize('session_context_policy', [None, 'trusted_root_pre_task_v1'])
def test_delegated_entry_constructs_real_driver_mailbox_and_service(
        tmp_path, setup_provider, monkeypatch, task, model, effort, context_seconds, session_context_policy):
    """Exercise every startup identity gate; stop at the model dispatch boundary."""
    from eegfm.agent import provider, provider_export
    from eegfm.agent.controller import ResearchDriver
    from eegfm.evaluation import ssh_worker
    from eegfm.evaluation.public_workbench import MODE
    from test_residual_recovery_episode import config as residual_config

    value = residual_config(tmp_path) if task == episode.RESIDUAL_RECOVERY_TASK else config(tmp_path)
    wall_seconds = 4200 if task == episode.RESIDUAL_RECOVERY_TASK and context_seconds == 480 else 2700
    deadline = 1000 + wall_seconds
    from datetime import datetime, timezone
    _, _, enrollment = setup_provider
    case_root, trusted = tmp_path / 'startup-case', tmp_path / 'startup-trusted'
    source = tmp_path / 'startup-public-source'
    (source / 'resources').mkdir(parents=True)
    for key, name in (('train_input', 'train.npz'), ('public_validation_input', 'validation.npz')):
        (source / name).write_bytes(Path(value[key]['path']).read_bytes())
    (source / 'eeg_api.py').write_text('# Synthetic public interface; never executed\n')
    (source / 'resources/CACHE_SCHEMA.json').write_text('{}')
    trusted.mkdir()
    budget = trusted / 'budget.json'
    budget.write_text(json.dumps({'deadline_at': datetime.fromtimestamp(deadline, timezone.utc).isoformat(),
                                 'stop_new_research_at': datetime.fromtimestamp(deadline-420, timezone.utc).isoformat()}))
    value.update(model=model, reasoning_effort=effort, episode_id='startup-episode',
        run_id='startup-run', case_root=str(case_root), trusted_root=str(trusted),
        budget_path=str(budget), episode_timeout_seconds=wall_seconds, session_timeout_seconds=context_seconds, episode_deadline_epoch=deadline,
        condition='no_skill', public_source=str(source),
        public_files=['train.npz', 'validation.npz', 'eeg_api.py', 'resources/CACHE_SCHEMA.json'],
        provider={key: enrollment[key] for key in ('parent_thread', 'agent_prefix', 'gateway', 'inherited_context')})
    if session_context_policy is not None:
        profile = {**value['provider'], 'episode_id': value['episode_id'], 'run_id': value['run_id'],
                   'model': model, 'effort': effort}
        value['provider']['trace_export'] = {
            'schema_version': provider_export.SCHEMA,
            'client_source_sha256': 'a' * 64,
            'sanitizer_source_sha256': provider_export.source_sha256(),
            'audit_profile_sha256': provider._hash(provider_export.audit_profile(profile)),
            'initial_metadata': [], 'session_context_policy': session_context_policy}
    remote = {'config': value['split_manifest'], 'known_hosts': value['split_manifest'],
              'host': 'synthetic', 'port': 22, 'user': 'synthetic', 'python': '/python', 'code': '/code'}
    value.update(cloud_worker=remote, public_fit_worker=remote)
    aggregate = SimpleNamespace(train_truth=episode.binding(value['train_truth']),
        truth={split: episode.binding(binding) for split, binding in value['truth_by_split'].items()},
        inference={split: episode.binding(binding) for split, binding in value['inference_by_split'].items()},
        source_bindings=[])
    if task == episode.RESIDUAL_RECOVERY_TASK:
        aggregate.qualification = episode.binding(value['residual_data_qualification'])
    else:
        aggregate.test_cohort = episode.binding(value['test_cohort'])
    worker_calls = []

    def forbidden_execution(*args, **kwargs):
        raise AssertionError('Startup regression must not execute science or a model')

    def worker(**kwargs):
        worker_calls.append(kwargs)
        identity = {'episode_id': value['episode_id'], 'run_id': value['run_id'],
            'episode_deadline_epoch': deadline,
            'public_manifest_sha256': digest_file(case_root / 'public/PUBLIC_MANIFEST.json'),
            'worker': {'public_artifact_mode': MODE, 'allowed_splits': ['validation']}}
        return SimpleNamespace(identity=identity, timeout=90, deadline_epoch=None,
            _enrollment=lambda: identity, submit=forbidden_execution, poll=forbidden_execution)

    observed = []

    def stop_before_model_dispatch(driver):
        assert isinstance(driver, ResearchDriver)
        assert driver.adapter.model == model
        assert driver.session_provider == provider.PROVIDER
        assert driver.episode_deadline == deadline
        assert isinstance(driver.launch, provider.ProviderLaunch)
        mailbox = driver.launch.mailbox
        assert isinstance(mailbox, provider.ProviderMailbox)
        assert (mailbox.identity['model'], mailbox.identity['effort']) == (model, effort)
        assert mailbox.identity['session_timeout_seconds'] == context_seconds
        assert driver.provider_timeout_seconds == context_seconds
        mailbox.verify()
        service_path = mailbox.root / 'SERVICE.json'
        service = provider.load_service(service_path, digest_file(service_path))
        assert service.identity == mailbox.identity
        assert service.identity.get('trace_export', {}).get('session_context_policy') == session_context_policy
        assert json.loads(service_path.read_bytes())['episode_deadline_epoch'] == deadline
        with mailbox.transaction() as database:
            assert database.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] == 0
        observed.append(driver)
        return 0

    # Scientific transport/aggregation is synthetic; startup objects remain real.
    monkeypatch.setattr(episode, 'os', SimpleNamespace(name='posix'))
    monkeypatch.setattr(episode.time, 'time', lambda: 1000)
    monkeypatch.setattr(episode, 'load_aggregator', lambda *args, **kwargs: aggregate)
    monkeypatch.setattr(episode, 'validate_cloud_bindings', lambda *args: None)
    monkeypatch.setattr(ssh_worker, 'scientific_identity', lambda *args, **kwargs: {})
    monkeypatch.setattr(ssh_worker, 'SshWorkerEvaluator', worker)
    monkeypatch.setattr(provider.ProviderLaunch, '__call__', forbidden_execution)
    monkeypatch.setattr(episode.EpisodeDriver, 'loop', stop_before_model_dispatch)
    result = episode.run_episode(value)
    assert len(worker_calls) == 2 and len(observed) == 1
    assert result['exit_code'] == 0 and result['state']['status'] == 'brief'
    assert json.loads((trusted / 'EPISODE_RESULT.json').read_bytes()) == result


@pytest.mark.parametrize('deadline', [True, 0, -1, 2500.0, float('inf'), '2500'])
def test_absolute_deadline_requires_positive_integer_epoch(tmp_path, deadline):
    value = config(tmp_path)
    with pytest.raises(ValueError, match='deadline'):
        episode.validate_delegated_config({**value, 'episode_deadline_epoch': deadline})


def test_native_timing_must_share_the_explicit_episode_deadline(tmp_path):
    value = config(tmp_path)
    value['provider'] = {'native_timing': {'dispatch_wait_seconds': 180, 'receipt_grace_seconds': 15,
                                          'episode_deadline_epoch': 3500}}
    with pytest.raises(ValueError, match='exact episode deadline'):
        episode.validate_delegated_config(value)
    with pytest.raises(ValueError, match='exact episode deadline'):
        episode.validate_delegated_config({**value, 'episode_deadline_epoch': 3501})
    assert episode.validate_delegated_config({**value, 'episode_deadline_epoch': 3500})['previous_successful_test_job']


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
