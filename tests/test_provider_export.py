"""Trusted-admin privacy projection; synthetic native records, no network."""
import copy
import hashlib
import json
import pytest
from test_provider_trace import trace
from test_agent_provider import setup_provider, open_session, complete_trace, call
from eegfm.agent import provider, provider_export


def fixture(tmp_path):
    path,identity,session,deliveries=trace(tmp_path)
    identity.update(episode_id='episode',run_id='run',agent_prefix='/root/actor')
    binding={'schema_version':provider_export.SCHEMA,'client_source_sha256':'a'*64,
             'sanitizer_source_sha256':provider_export.source_sha256(),
             'audit_profile_sha256':provider._hash(provider_export.audit_profile(identity)), 'initial_metadata':[]}
    identity['trace_export']=binding
    return path,identity,session,deliveries


def test_export_contains_no_platform_account_or_reasoning_text(tmp_path):
    path,identity,session,_=fixture(tmp_path)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    rows[0]['payload']['account_private']='PRIVATE_ACCOUNT_MARKER'
    rows[4]['payload']['world_state']='PRIVATE_WORLD_MARKER'
    rows.insert(4,{'type':'response_item','payload':{'type':'reasoning','encrypted_content':'PRIVATE_REASONING_MARKER'}})
    rows.insert(4,{'type':'event_msg','payload':{'type':'token_count','info':'PRIVATE_TOKEN_MARKER'}})
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    result=provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    data=json.dumps(result)
    for private in ['PRIVATE_','MEMORY_SUMMARY','environment_context>','gAAAAAsynthetic']:
        assert private not in data
    assert result['source']['raw_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    records,audit=provider_export.validate_admin_export(result,identity,session,context_id='context')
    assert audit['valid'] and any(row['payload'].get('type')=='custom_tool_call' for row in records)
    exported=tmp_path/'exported.jsonl'
    exported.write_text(''.join(json.dumps(row)+'\n' for row in records))
    assert not provider.audit_initial_context(exported,identity=identity,agent_path=session['agent_path'],context_id='context')['valid']


@pytest.mark.parametrize('mutation',['profile','source','context','order','extra_initial','late_input','bad_command','bad_template'])
def test_tamper_or_unauthorized_input_rejected_before_export(tmp_path,mutation):
    path,identity,session,_=fixture(tmp_path)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    if mutation in {'late_input','extra_initial','bad_command','bad_template'}:
        if mutation in {'late_input','extra_initial'}:
            rows.insert(-2 if mutation=='late_input' else 2,{'type':'response_item','payload':{'type':'message','role':'developer','content':[{'type':'input_text','text':'PRIVATE_HINT'}],'internal_chat_message_metadata_passthrough':{'content_item_kinds':['model.base_instructions']}}})
        elif mutation=='bad_command':
            next(r['payload']['item'] for r in rows if r['payload'].get('item',{}).get('type')=='CommandExecution')['command']=['cat','credentials']
        else:next(r['payload'] for r in rows if r['payload'].get('type')=='custom_tool_call')['input']='PRIVATE_CREDENTIAL_READ'
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with pytest.raises(ValueError):provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
        return
    result=provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    if mutation=='profile':result['binding']['audit_profile_sha256']='b'*64
    elif mutation=='source':result['binding']['sanitizer_source_sha256']='b'*64
    elif mutation=='context':result['initial_audit']['context_id']='wrong'
    else:result['records'][1],result['records'][2]=result['records'][2],result['records'][1]
    with pytest.raises(ValueError):provider_export.validate_admin_export(result,identity,session,context_id='context')


def test_source_prefix_chain_rejects_local_drift_and_remote_substitution(tmp_path):
    path,identity,session,_=fixture(tmp_path)
    first=provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    second=provider_export.sanitize_admin_trace(path,identity,session,context_id='context',prior_source=first['source'])
    provider_export.validate_admin_export(second,identity,session,context_id='context',prior_source=first['source'])
    wrong=copy.deepcopy(first['source']);wrong['raw_sha256']='b'*64
    with pytest.raises(ValueError):provider_export.validate_admin_export(second,identity,session,context_id='context',prior_source=wrong)
    path.write_bytes(path.read_bytes().replace(b'common',b'changed'))
    with pytest.raises(ValueError):provider_export.sanitize_admin_trace(path,identity,session,context_id='context',prior_source=first['source'])


def test_partial_prefix_has_separate_consumed_bytes_and_complete_async_reuses_it(tmp_path):
    path,identity,session,_=fixture(tmp_path)
    raw=path.read_bytes()
    initial=b''.join(raw.splitlines(keepends=True)[:5])
    path.write_bytes(initial+b'{')
    admitted=provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    source=admitted['source']
    assert source['prefix_bytes']==len(initial)<source['raw_bytes']
    assert source['prefix_sha256']==hashlib.sha256(initial).hexdigest()
    path.write_bytes(raw)
    final=provider_export.sanitize_admin_trace(path,identity,session,context_id='context',prior_source=source,complete=True)
    assert final['records'][:len(admitted['records'])]==admitted['records']
    assert sum(row['payload'].get('type')=='custom_tool_call_output' for row in final['records'])==2


def test_only_enrolled_hashes_for_instruction_bearing_metadata_cross_boundary(tmp_path):
    path,identity,session,_=fixture(tmp_path)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    tool={'type':'additional_tools','role':'developer','content':'PRIVATE_TOOL_INSTRUCTIONS'}
    world={'full':True,'state':'PRIVATE_WORLD_STATE'}
    rows[1:1]=[{'type':'response_item','payload':tool},{'type':'world_state','payload':world}]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError,match='initial metadata'):
        provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    identity['trace_export']['initial_metadata']=[{'kind':'additional_tools','payload_sha256':provider._hash(tool)},
                                                  {'kind':'world_state','payload_sha256':provider._hash(world)}]
    result=provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    assert 'PRIVATE_' not in json.dumps(result)
    assert [row['payload']['kind'] for row in result['records'] if row['type']=='sanitized_metadata']==['additional_tools','world_state']


@pytest.mark.parametrize('changed_content',[False,True])
def test_current_developer_profile_requires_exact_ordered_content_hashes(tmp_path,changed_content):
    path,identity,session,_=fixture(tmp_path)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    memory=rows[1]['payload']['content'][0]['text']
    groups=[
        (['model.base_instructions'],'Synthetic base instructions'),
        (['generic.developer_instructions','memories.instructions','host_skills.instructions','permissions.instructions',
          'collaboration_mode.instructions','tools.deferred_namespaces','plugins.recommendations'],memory+'\nSynthetic recommendations'),
        (['multi_agent.role_instructions'],'Synthetic role instructions'),
        (['multi_agent.mode_instructions'],'Synthetic mode instructions'),
    ]
    messages=[]
    for kinds,text in groups:
        payload={'type':'message','role':'developer','content':[{'type':'input_text','text':text}],
                 'internal_chat_message_metadata_passthrough':{'content_item_kinds':kinds}}
        messages.append({'type':'response_item','payload':payload})
    identity['inherited_context']['initial_messages']=[
        {'role':'developer','kinds':kinds,'content_sha256':provider._hash(row['payload']['content'])}
        for (kinds,_),row in zip(groups,messages)
    ]+identity['inherited_context']['initial_messages'][1:]
    identity['trace_export']['audit_profile_sha256']=provider._hash(provider_export.audit_profile(identity))
    if changed_content:
        messages[1]['payload']['content'][0]['text']+='\nUnexpected recommendation'
    rows[1:2]=messages
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    if changed_content:
        with pytest.raises(ValueError,match='prospective profile'):
            provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    else:
        exported=provider_export.sanitize_admin_trace(path,identity,session,context_id='context',complete=True)
        assert exported['initial_audit']['valid']
        assert 'Synthetic recommendations' not in json.dumps(exported)


@pytest.mark.parametrize('mutation',['late_output','missing_complete','unknown_event','private_timestamp','multiple_bootstrap','late_tool_definition'])
def test_invalid_complete_log_is_rejected_locally(tmp_path,mutation):
    path,identity,session,_=fixture(tmp_path)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    if mutation=='late_output':rows.insert(-1,rows.pop(-3))
    elif mutation=='missing_complete':rows.pop()
    elif mutation=='unknown_event':rows.insert(-2,{'type':'event_msg','payload':{'type':'exec_command_begin'}})
    elif mutation=='private_timestamp':rows[0]['timestamp']='PRIVATE_TIMESTAMP'
    elif mutation=='multiple_bootstrap':rows.insert(4,copy.deepcopy(rows[3]))
    else:rows.insert(-2,{'type':'response_item','payload':{'type':'additional_tools','role':'developer'}})
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError):
        provider_export.sanitize_admin_trace(path,identity,session,context_id='context',complete=True)


def test_explicit_admin_route_admits_then_audits_actual_deliveries(setup_provider,tmp_path,monkeypatch):
    controller,old_box,enrollment=setup_provider
    binding={'schema_version':provider_export.SCHEMA,'client_source_sha256':'a'*64,
             'sanitizer_source_sha256':provider_export.source_sha256(),
             'audit_profile_sha256':provider._hash(provider_export.audit_profile(enrollment)), 'initial_metadata':[]}
    box=provider.ProviderMailbox(root=tmp_path/'sanitized',case_root=controller.case,public_root=old_box.public,
                                 enrollment={**enrollment,'trace_export':binding})
    open_session(box,register=False)
    path=box.root/'synthetic-native-prefix.jsonl'
    state=box.session('session-01')
    projected=provider_export.sanitize_admin_trace(path,box.identity,state,context_id='context')
    args={'session':'session-01','context_id':'context','export':projected}
    with pytest.raises(ValueError):
        box.register_context('session-01',context_id='context',trace_path=path)
    with pytest.raises(ValueError):
        provider.service_request(box,{'session':'session-01','request':{'admin':'admit_sanitized','export':projected}})
    assert provider.service_request(box,{'admin':'admit_sanitized',**args})['status']=='initial_context_admitted'
    assert call(box,'task')['status']=='ok'
    assert call(box,'seal_session',{'requests':[]})['status']=='ok'
    complete_trace(box,path)
    state=box.session('session-01')
    final=provider_export.sanitize_admin_trace(path,box.identity,state,context_id='context',complete=True,
                                              prior_source=state['registered_context']['export_source'])
    tampered=copy.deepcopy(final)
    tampered['records'][0]['timestamp']='2026-11-08T01:00:00Z'
    with pytest.raises(ValueError,match='exact admitted prefix'):
        provider.service_request(box,{'admin':'accept_sanitized',**args,'export':tampered})
    monkeypatch.setattr(provider.time,'time',lambda:state['started_epoch']+3600)
    pointer=provider.service_request(box,{'admin':'accept_sanitized',**args,'export':final})
    assert pointer['receipt_sha256']==box.session('session-01')['receipt_sha256']
    saved=json.loads((box.root/'audits/session-01.json').read_text())
    assert saved['valid'] and saved['trace_export']['source']==final['source']
    assert saved['timing']['completion_epoch']<=saved['timing']['deadline_epoch']
