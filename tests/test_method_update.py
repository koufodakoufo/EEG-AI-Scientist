"""Scripted boundary tests only: these never call a model or generate study methods."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from eegfm.agent.budget import BudgetExceeded
from eegfm.evaluation.bundle import create_public_bundle, digest_file
from eegfm.improvement import update


@pytest.fixture
def config(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'DEVELOPMENT.json').write_text(json.dumps({'sources':[{'source_id':'dev-trajectory','evidence':'SCRIPTED TEST FIXTURE ONLY'}]}))
    public=tmp_path/'frozen-public'
    create_public_bundle(source,public,['DEVELOPMENT.json'],task_id='update-test',tier='synthetic_mechanism')
    now=datetime.now(timezone.utc)
    budget=tmp_path/'budget.json'
    budget.write_text(json.dumps({'calls':[],'extra_model_calls_max':1,'max_parallel_model_workers':1,
        'stop_new_research_at':(now+timedelta(hours=1)).isoformat(),'deadline_at':(now+timedelta(hours=2)).isoformat(),
        'per_call_timeout_seconds':900,'preflight_timeout_seconds':60}))
    gate=tmp_path/'gate.json';gate.write_text('{"test_only":true}')
    manifest=tmp_path/'runtime.json';manifest.write_text('{"test_only":true}')
    return {'case':str(tmp_path/'case'),'private':str(tmp_path/'private'),
        'public_source':str(public),'public_manifest_sha256':digest_file(public/'PUBLIC_MANIFEST.json'),
        'budget_path':str(budget),'call_id':'method-update-test','timeout_seconds':900,
        'isolation_report':{'path':str(gate),'sha256':digest_file(gate)},
        'runtime_manifest':{'path':str(manifest),'sha256':digest_file(manifest)},
        'native_binary':'/tools/codex','bwrap':'/tools/bwrap','auth_source':'/protected/auth.json',
        'scientific_roots':['/env/science'],'proxy_url':'http://127.0.0.1:1234'}


def proposal(case):
    output=case/'output';output.mkdir(exist_ok=True)
    (output/'METHOD.md').write_text('SCRIPTED_TEST_METHOD_ONLY\n')
    (output/'KNOWLEDGE.md').write_text('SCRIPTED_TEST_FACT_ONLY\n')
    data={'schema_version':'method_update_v1','methods':[{'id':'fixture-rule','source_ids':['dev-trajectory'],
        'rule':'scripted test rule','trigger':'scripted condition','counterexample':'scripted exception'}],
        'knowledge':[{'id':'fixture-fact','source_ids':['dev-trajectory'],'fact':'scripted source fact'}]}
    (output/'UPDATE.json').write_text(json.dumps(data))
    return data


def mocked_run(config, *, mutate=None, model='gpt-6.1-sol', gate_error=None):
    def launch(metadata,prompt,**kwargs):
        assert kwargs['role']=='distiller' and kwargs['timeout_seconds']==900
        assert kwargs['prompt_via_stdin'] is True
        assert prompt==update.METHOD_UPDATE_PROMPT
        output=kwargs['output_dir'];output.mkdir(parents=True)
        (output/'stdout.jsonl').write_text(json.dumps({'type':'turn.completed','usage':{'input_tokens':200,'output_tokens':40}}))
        proposal(Path(config['case']))
        if mutate:mutate(config)
        return {'status':'completed','exit_code':0,'process_cleanup':{'surviving_owned_pids':[]}}
    def prepare(**kwargs):
        assert kwargs['auth_mode']=='readonly_bind'
        assert kwargs['model']=='gpt-6.1-sol'
        assert kwargs['read_only_roots']==(Path('/env/science'),)
        return {'control_home':str(kwargs['control_home'])}
    with patch.object(update,'prepare_control',side_effect=prepare) as prepared, \
         patch.object(update,'launch_actor',side_effect=launch) as launched, \
         patch.object(update,'validate_isolation_gate',side_effect=gate_error), \
         patch.object(update,'collect_visible_trace',return_value={'turn_metadata':[{'model':model,'effort':'medium','approval_policy':'never'}],'trace_sha256':'f'*64}):
        result=update.run_method_update(config)
        return result,prepared.call_count,launched.call_count


def test_success_is_only_a_reviewable_proposal_and_records_usage(config):
    result,prepared,launched=mocked_run(config)
    assert result['status']=='completed' and result['eligible_for_review'] is True
    assert result['review_status']=='pending_builder_review' and result['scientific_validity']=='not_assessed'
    assert result['usage']=={'input_tokens':200,'output_tokens':40}
    assert set(result['outputs'])=={'METHOD.md','KNOWLEDGE.md','UPDATE.json'}
    assert result['source_ids']==['dev-trajectory'] and prepared==launched==1
    calls=json.loads(Path(config['budget_path']).read_text())['calls']
    assert len(calls)==1 and calls[0]['role']=='distiller' and calls[0]['status']=='completed'
    with pytest.raises(FileExistsError):update.run_method_update(config)


@pytest.mark.parametrize('kind',['unknown_source','too_many_methods','missing_file','empty_file','too_large','public_mutated','wrong_model'])
def test_bad_outputs_or_provenance_are_failed_not_frozen(config,kind):
    def mutate(c):
        output=Path(c['case'])/'output';path=output/'UPDATE.json';data=json.loads(path.read_text())
        if kind=='unknown_source':data['methods'][0]['source_ids']=['invented-source']
        elif kind=='too_many_methods':data['methods']=[{**data['methods'][0],'id':f'fixture-{i}'} for i in range(4)]
        elif kind=='missing_file':(output/'METHOD.md').unlink()
        elif kind=='empty_file':(output/'METHOD.md').write_text('')
        elif kind=='too_large':(output/'METHOD.md').write_bytes(b'x'*(update.MAX_DOCUMENT_BYTES+1))
        elif kind=='public_mutated':(Path(c['case'])/'public/DEVELOPMENT.json').write_text('{}')
        path.write_text(json.dumps(data))
    result,_,launched=mocked_run(config,mutate=mutate,model='wrong-model' if kind=='wrong_model' else 'gpt-6.1-sol')
    assert result['status']=='failed' and result['eligible_for_review'] is False and launched==1
    assert result['usage']=={'input_tokens':200,'output_tokens':40}
    assert result['error']['type']
    assert result['outputs']['UPDATE.json']['sha256']==digest_file(Path(config['case'])/'output/UPDATE.json')


def test_failed_gate_reserves_but_never_calls_model(config):
    result,_,launched=mocked_run(config,gate_error=RuntimeError('SCRIPTED gate failure'))
    assert result['status']=='failed' and launched==0 and result['usage'] is None
    call=json.loads(Path(config['budget_path']).read_text())['calls'][0]
    assert call['status']=='blocked'


def test_input_hash_mismatch_never_reserves(config):
    config['public_manifest_sha256']='0'*64
    result,prepared,launched=mocked_run(config)
    assert result['status']=='failed' and prepared==launched==0
    assert json.loads(Path(config['budget_path']).read_text())['calls']==[]


def test_timeout_cannot_exceed_single_call_limit(config):
    config['timeout_seconds']=901
    with pytest.raises(ValueError,match='900'):update.run_method_update(config)
    assert json.loads(Path(config['budget_path']).read_text())['calls']==[]


def test_exhausted_parent_budget_never_calls_model(config):
    path=Path(config['budget_path']);budget=json.loads(path.read_text());budget['extra_model_calls_max']=0
    path.write_text(json.dumps(budget))
    result,prepared,launched=mocked_run(config)
    assert result['status']=='failed' and result['error']['type']=='BudgetExceeded'
    assert prepared==launched==0 and json.loads(path.read_text())['calls']==[]


def test_empty_source_code_file_is_valid_but_empty_proposal_is_not(config):
    source=Path(config['public_source'])
    (source/'empty.py').write_bytes(b'')
    manifest=json.loads((source/'PUBLIC_MANIFEST.json').read_text())
    manifest['files'].append({'path':'empty.py','bytes':0,'sha256':digest_file(source/'empty.py')})
    from eegfm.evaluation.bundle import canonical_bytes
    manifest['files'].sort(key=lambda entry:entry['path'])
    (source/'PUBLIC_MANIFEST.json').write_bytes(canonical_bytes(manifest))
    config['public_manifest_sha256']=digest_file(source/'PUBLIC_MANIFEST.json')
    result,_,_=mocked_run(config)
    assert result['status']=='completed'


@pytest.mark.skipif(os.name!='posix',reason='Linux symlink/hardlink output boundary')
@pytest.mark.parametrize('kind',['symlink','hardlink'])
def test_output_links_are_rejected_without_reading_target(config,kind):
    def mutate(c):
        path=Path(c['case'])/'output/METHOD.md';path.unlink()
        source=Path(c['private'])/'outside.txt';source.write_text('DO_NOT_READ')
        if kind=='symlink':path.symlink_to(source)
        else:os.link(source,path)
    result,_,_=mocked_run(config,mutate=mutate)
    assert result['status']=='failed' and result['eligible_for_review'] is False
