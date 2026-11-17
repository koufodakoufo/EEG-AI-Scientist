"""Trusted-admin privacy projection; synthetic native records, no network."""
import copy
import hashlib
import json
from datetime import datetime, timezone
import pytest
from test_provider_trace import WAIT, trace
from test_agent_provider import setup_provider, open_session, complete_trace, call
from eegfm.agent import provider, provider_export, provider_trace


def fixture(tmp_path, *, wait_status=False):
    path,identity,session,deliveries=trace(tmp_path,wait_status=wait_status)
    identity.update(episode_id='episode',run_id='run',agent_prefix='/root/actor')
    binding={'schema_version':provider_export.SCHEMA,'client_source_sha256':'a'*64,
             'sanitizer_source_sha256':provider_export.source_sha256(),
             'audit_profile_sha256':provider._hash(provider_export.audit_profile(identity)), 'initial_metadata':[]}
    identity['trace_export']=binding
    return path,identity,session,deliveries


PACKAGED_SHELL = (r'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1112-611-0_26.1112.611.0_x64__3k8sg7r9htsxt'
                  r'\dependencies\native\powershell\pwsh.exe')


@pytest.mark.parametrize('shell', [provider_trace.SHELL_PREFIX[0], PACKAGED_SHELL])
def test_qualified_shell_paths_preserve_full_trace_and_export_audit(tmp_path, shell):
    path, identity, session, deliveries = fixture(tmp_path)
    rows = provider._trace_records(path)
    native = next(r['payload']['item'] for r in rows
                  if r['payload'].get('item', {}).get('type') == 'CommandExecution')
    native['command'][0] = shell
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    assert provider_trace.audit_native_context(path, identity, session, deliveries)['valid']
    exported = provider_export.sanitize_admin_trace(path, identity, session, context_id='context', complete=True)
    records, initial = provider_export.validate_admin_export(exported, identity, session, context_id='context')
    assert provider_trace._audit_native_records(records, identity, session, deliveries, initial, sanitized=True)['valid']


@pytest.mark.parametrize('duration', [480, 1200])
def test_explicit_longer_reservation_survives_both_trace_audits(tmp_path, duration):
    path, identity, session, deliveries = fixture(tmp_path)
    session['timeout_seconds'] = duration
    assert provider_trace.audit_native_context(path, identity, session, deliveries)['valid']
    provider_export.sanitize_admin_trace(path, identity, session, context_id='context', complete=True)
    session['timeout_seconds'] = 1201
    assert not provider_trace.audit_native_context(path, identity, session, deliveries)['valid']


@pytest.mark.parametrize('prefix', [
    [r'C:\unreviewed\pwsh.exe', '-Command'],
    [PACKAGED_SHELL.replace('26-1112-611-0', '26-9999-999-0'), '-Command'],
    [PACKAGED_SHELL, '-CommandWithArgs'],
    [PACKAGED_SHELL, '-NoProfile', '-Command'],
    [PACKAGED_SHELL],
])
def test_shell_path_or_invocation_changes_fail_both_audits(tmp_path, prefix):
    path, identity, session, deliveries = fixture(tmp_path)
    rows = provider._trace_records(path)
    native = next(r['payload']['item'] for r in rows
                  if r['payload'].get('item', {}).get('type') == 'CommandExecution')
    native['command'] = prefix + [native['command'][-1]]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    assert not provider_trace.audit_native_context(path, identity, session, deliveries)['valid']
    with pytest.raises(ValueError, match='Unauthorized native shell'):
        provider_export.sanitize_admin_trace(path, identity, session, context_id='context', complete=True)


def test_wait_status_prefix_survives_native_projection_and_delivery_audit(tmp_path):
    path,identity,session,deliveries=fixture(tmp_path,wait_status=True)
    exported=provider_export.sanitize_admin_trace(path,identity,session,context_id='context',complete=True)
    rows,initial=provider_export.validate_admin_export(exported,identity,session,context_id='context')
    first=next(row for row in rows if row['payload'].get('type')=='custom_tool_call')
    native=next(row for row in provider._trace_records(path) if row['payload'].get('type')=='custom_tool_call')
    assert first['payload']['input']==native['payload']['input']
    assert first['payload']['input'].startswith(WAIT)
    audited=provider_trace._audit_native_records(rows,identity,session,deliveries,initial,sanitized=True)
    assert audited['valid'] and audited['gateway_calls']==1 and audited['native_poll_calls']==1
    assert audited['timing']['execution_wall_seconds']>=15


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
    definitions={'type':'additional_tools','role':'developer','tools':[{'description':'PRIVATE_TOOL_INSTRUCTIONS'}]}
    tool={**definitions,'id':'at_00000000-0000-0000-0000-000000000001'}
    world={'full':True,'state':'PRIVATE_WORLD_STATE'}
    rows[1:1]=[{'type':'response_item','payload':tool},{'type':'world_state','payload':world}]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError,match='initial metadata'):
        provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    identity['trace_export']['initial_metadata']=[{'kind':'additional_tools','payload_sha256':provider._hash(definitions)},
                                                  {'kind':'world_state','payload_sha256':provider._hash(world)}]
    result=provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    assert 'PRIVATE_' not in json.dumps(result)
    assert [row['payload']['kind'] for row in result['records'] if row['type']=='sanitized_metadata']==['additional_tools','world_state']
    tool['id']='at_00000000-0000-0000-0000-000000000002'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    another=provider_export.sanitize_admin_trace(path,identity,session,context_id='context')
    assert another['records'][1]['payload']['payload_sha256']==result['records'][1]['payload']['payload_sha256']
    assert another['records'][1]['payload']['record_sha256']!=result['records'][1]['payload']['record_sha256']
    assert another['source']['raw_sha256']!=result['source']['raw_sha256']


@pytest.mark.parametrize('mutation',['invalid_id','non_string_id','missing_id','extra_key','role','tools','world_state'])
def test_only_valid_tool_nonce_is_excluded_from_initial_metadata_hash(tmp_path,mutation):
    path,identity,session,_=fixture(tmp_path)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    definitions={'type':'additional_tools','role':'developer','tools':[{'name':'synthetic'}]}
    tool={**definitions,'id':'at_00000000-0000-0000-0000-000000000001'}
    world={'full':True,'state':'original'}
    identity['trace_export']['initial_metadata']=[{'kind':'additional_tools','payload_sha256':provider._hash(definitions)},
                                                  {'kind':'world_state','payload_sha256':provider._hash(world)}]
    if mutation=='invalid_id':tool['id']='PRIVATE_NOT_A_NATIVE_ID'
    elif mutation=='non_string_id':tool['id']=1
    elif mutation=='missing_id':del tool['id']
    elif mutation=='extra_key':tool['extra']='PRIVATE_EXTRA'
    elif mutation=='role':tool['role']='system'
    elif mutation=='tools':tool['tools']=[{'name':'changed'}]
    else:world['state']='changed'
    rows[1:1]=[{'type':'response_item','payload':tool},{'type':'world_state','payload':world}]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError,match='initial metadata|additional_tools'):
        provider_export.sanitize_admin_trace(path,identity,session,context_id='context')


def test_old_full_payload_export_binding_requires_a_separate_enrollment(tmp_path):
    path,identity,session,_=fixture(tmp_path)
    identity['trace_export']['schema_version']='trusted_admin_trace_v1'
    with pytest.raises(ValueError,match='sanitizer/profile binding'):
        provider_export.sanitize_admin_trace(path,identity,session,context_id='context')


def variant_fixture(tmp_path):
    path,identity,session,_=fixture(tmp_path)
    original=[json.loads(line) for line in path.read_text().splitlines()]
    shared=identity['inherited_context']['initial_messages']
    variants=[]
    for name in ('old','new'):
        messages=[]
        profile=[]
        for kind in ('model.base_instructions','multi_agent.role_instructions'):
            content=[{'type':'input_text','text':f'{name} synthetic {kind}'}]
            profile.append({'role':'developer','kinds':[kind],'content_sha256':provider._hash(content)})
            messages.append({'type':'response_item','payload':{'type':'message','role':'developer','content':content,
                             'internal_chat_message_metadata_passthrough':{'content_item_kinds':[kind]}}})
        description=f'{name} synthetic functions.exec'
        if name=='new':description+=' declares literature_search_query'
        tool={'type':'additional_tools','role':'developer','tools':[{'description':description}],
              'id':'at_00000000-0000-0000-0000-000000000001'}
        world={'full':True,'state':name}
        metadata=[{'type':'response_item','payload':tool},{'type':'world_state','payload':world}]
        bundle={'initial_messages':profile+shared,'memory_summary_sha256':identity['inherited_context']['memory_summary_sha256'],
                'initial_metadata':[{'kind':kind,'payload_sha256':provider_export.initial_metadata_sha256(kind,value)}
                                    for kind,value in [('additional_tools',tool),('world_state',world)]]}
        variants.append((messages,metadata,bundle))
    identity['inherited_context']['initial_messages']=variants[0][2]['initial_messages']
    identity['trace_export'].update(audit_profile_sha256=provider._hash(provider_export.audit_profile(identity)),
                                    initial_metadata=variants[0][2]['initial_metadata'],context_variants=[x[2] for x in variants])
    return path,identity,session,original,variants


def write_variant(path, original, messages, metadata):
    rows=original[:1]+messages+metadata+original[1:]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


@pytest.mark.parametrize('index',[0,1])
def test_joint_variant_accepts_only_one_complete_bundle(tmp_path,index):
    path,identity,session,original,variants=variant_fixture(tmp_path)
    messages,metadata,bundle=variants[index]
    write_variant(path,original,messages,metadata)
    assert provider.audit_initial_context(path,identity=identity,agent_path=session['agent_path'],context_id='context')['valid']
    result=provider_export.sanitize_admin_trace(path,identity,session,context_id='context',complete=True)
    _,audit=provider_export.validate_admin_export(result,identity,session,context_id='context')
    assert [row['content_sha256'] for row in audit['initial_messages'] if row['role']!='agent_message']==[
        row['content_sha256'] for row in bundle['initial_messages']]


@pytest.mark.parametrize('case',['old_messages_new_metadata','new_messages_old_metadata','mixed_messages',
                                 'third_variant','changed_tool','literature_call'])
def test_joint_variant_rejects_hybrids_and_unapproved_context_or_tool(tmp_path,case):
    path,identity,session,original,variants=variant_fixture(tmp_path)
    messages,metadata,_=copy.deepcopy(variants[0])
    if case=='old_messages_new_metadata':metadata=variants[1][1]
    elif case=='new_messages_old_metadata':messages=variants[1][0]
    elif case=='mixed_messages':messages[0]=variants[1][0][0]
    elif case=='third_variant':messages[0]['payload']['content'][0]['text']='Unknown variant'
    elif case=='changed_tool':metadata[0]['payload']['tools'][0]['description']='Changed tool instruction'
    else:
        messages,metadata,_=variants[1]
        call_row=next(row for row in original if row['payload'].get('type')=='custom_tool_call')
        call_row['payload']['input']='const result = await tools.web__run({literature_search_query:[{q:"synthetic"}]}); text(result);'
    write_variant(path,original,messages,metadata)
    if case!='literature_call':
        assert not provider.audit_initial_context(path,identity=identity,agent_path=session['agent_path'],context_id='context')['valid']
    with pytest.raises(ValueError):
        provider_export.sanitize_admin_trace(path,identity,session,context_id='context')


@pytest.mark.parametrize('index',[0,1])
def test_remote_rejects_individually_enrolled_messages_and_metadata_from_different_variants(tmp_path,index):
    path,identity,session,original,variants=variant_fixture(tmp_path)
    exports=[]
    for messages,metadata,_ in variants:
        write_variant(path,original,messages,metadata)
        exports.append(provider_export.sanitize_admin_trace(path,identity,session,context_id='context'))
    message_export,metadata_export=exports[index],exports[1-index]
    for row,other in zip(message_export['records'],metadata_export['records']):
        if row['type']=='sanitized_metadata':row['payload']=other['payload']
    with pytest.raises(ValueError,match='prospective profile'):
        provider_export.validate_admin_export(message_export,identity,session,context_id='context')


def test_remote_requires_the_entire_enrolled_variant_family(tmp_path):
    path,identity,session,original,variants=variant_fixture(tmp_path)
    write_variant(path,original,*variants[0][:2])
    exported=copy.deepcopy(provider_export.sanitize_admin_trace(path,identity,session,context_id='context'))
    del exported['binding']['context_variants']
    with pytest.raises(ValueError,match='Unenrolled export'):
        provider_export.validate_admin_export(exported,identity,session,context_id='context')


@pytest.mark.parametrize('case',['duplicate','missing_primary','third','environment','memory_row','memory_hash','shape'])
def test_variant_enrollment_requires_two_exact_bundles_with_common_context(tmp_path,case):
    _,identity,_,_,_=variant_fixture(tmp_path)
    variants=copy.deepcopy(identity['trace_export']['context_variants'])
    if case=='duplicate':variants[1]=variants[0]
    elif case=='missing_primary':variants[0]['initial_messages'][0]['content_sha256']='f'*64
    elif case=='third':variants.append(variants[0])
    elif case=='environment':variants[1]['initial_messages'][-1]['content_sha256']='f'*64
    elif case=='memory_row':variants[1]['initial_messages'][-2]['content_sha256']='f'*64
    elif case=='memory_hash':variants[1]['memory_summary_sha256']='f'*64
    else:variants[1]['initial_messages'][0]['kinds']=['host_skills.instructions']
    identity['trace_export']['context_variants']=variants
    with pytest.raises(ValueError):provider_export.validate_binding(identity)


def bundled_variant_fixture(tmp_path, *, different_metadata=False):
    """Native platform layout: generic instructions and memory share one message."""
    path,identity,session,_=fixture(tmp_path)
    original=provider._trace_records(path)
    memory=original[1]['payload']['content'][0]['text']
    kinds=['generic.developer_instructions','memories.instructions','host_skills.instructions',
           'permissions.instructions','collaboration_mode.instructions','tools.deferred_namespaces',
           'plugins.recommendations']
    variants=[]
    for index,version in enumerate(('1.0.103','1.0.89')):
        rows=copy.deepcopy(original)
        text=memory+'\nSynthetic generic developer instructions\nvisualize/'+version+'/skills/visualize/SKILL.md'
        if index==0:text+='\n- mcp__codex_apps__search_service: Tool for accessing the internet.'
        rows[1]['payload']['content']=[{'type':'input_text','text':text}]
        rows[1]['payload']['internal_chat_message_metadata_passthrough']['content_item_kinds']=kinds
        tool={'type':'additional_tools','role':'developer','tools':[{'name':'synthetic','version':index if different_metadata else 0}],
              'id':'at_00000000-0000-0000-0000-000000000001'}
        rows.insert(1,{'type':'response_item','payload':tool})
        messages=copy.deepcopy(identity['inherited_context']['initial_messages'])
        messages[0].update(kinds=kinds,content_sha256=provider._hash(rows[2]['payload']['content']))
        bundle={'initial_messages':messages,'memory_summary_sha256':identity['inherited_context']['memory_summary_sha256'],
                'initial_metadata':[{'kind':'additional_tools','payload_sha256':provider_export.initial_metadata_sha256('additional_tools',tool)}]}
        variants.append((rows,bundle))
    identity['inherited_context']['initial_messages']=variants[0][1]['initial_messages']
    identity['trace_export'].update(audit_profile_sha256=provider._hash(provider_export.audit_profile(identity)),
        initial_metadata=variants[0][1]['initial_metadata'],context_variants=[bundle for _,bundle in variants])
    return path,identity,session,variants


@pytest.mark.parametrize('index',[0,1])
def test_predeclared_bundled_generic_memory_variants_pass_raw_and_export_audits(tmp_path,index):
    path,identity,session,variants=bundled_variant_fixture(tmp_path)
    rows,bundle=variants[index]
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    provider_export.validate_binding(identity)
    assert provider.audit_initial_context(path,identity=identity,agent_path=session['agent_path'],context_id='context')['valid']
    result=provider_export.sanitize_admin_trace(path,identity,session,context_id='context',complete=True)
    _,audit=provider_export.validate_admin_export(result,identity,session,context_id='context')
    assert audit['valid'] and audit['memory_summary_sha256']==bundle['memory_summary_sha256']
    assert result['binding']['context_variants']==[value for _,value in variants]
    assert 'Synthetic generic developer instructions' not in json.dumps(result)


@pytest.mark.parametrize('case',['pure_memory','memory_with_skills','system_bundle','memory_summary','environment'])
def test_bundled_variant_enrollment_keeps_memory_and_environment_guards(tmp_path,case):
    _,identity,_,_=bundled_variant_fixture(tmp_path)
    variants=identity['trace_export']['context_variants']
    if case in {'pure_memory','memory_with_skills','system_bundle'}:
        for bundle in variants:
            message=bundle['initial_messages'][0]
            if case=='system_bundle':message['role']='system'
            else:message['kinds']=['memories.instructions']+(['host_skills.instructions'] if case=='memory_with_skills' else [])
    elif case=='memory_summary':variants[1]['memory_summary_sha256']='f'*64
    else:variants[1]['initial_messages'][-1]['content_sha256']='f'*64
    identity['trace_export']['audit_profile_sha256']=provider._hash(provider_export.audit_profile(identity))
    with pytest.raises(ValueError,match='common ordered structure, memory and environment'):
        provider_export.validate_binding(identity)


@pytest.mark.parametrize('case',['unregistered_text','memory_summary','environment','cross_bundle_metadata'])
def test_bundled_variants_reject_raw_drift_and_cross_bundle_mix(tmp_path,case):
    path,identity,session,variants=bundled_variant_fixture(tmp_path,different_metadata=True)
    provider_export.validate_binding(identity)
    rows=copy.deepcopy(variants[1][0])
    if case=='cross_bundle_metadata':rows[1]=copy.deepcopy(variants[0][0][1])
    elif case=='environment':rows[3]['payload']['content'][0]['text']+='\nChanged environment'
    elif case=='memory_summary':
        rows[2]['payload']['content'][0]['text']=rows[2]['payload']['content'][0]['text'].replace('common','changed')
        # Even an exact enrolled message hash cannot change the separately bound summary.
        variants[1][1]['initial_messages'][0]['content_sha256']=provider._hash(rows[2]['payload']['content'])
    else:rows[2]['payload']['content'][0]['text']+='\nUnregistered instruction'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    audit=provider.audit_initial_context(path,identity=identity,agent_path=session['agent_path'],context_id='context')
    assert not audit['valid']
    if case=='memory_summary':assert 'inherited memory summary mismatch or missing' in audit['issues']
    with pytest.raises(ValueError,match='prospective profile'):
        provider_export.sanitize_admin_trace(path,identity,session,context_id='context')


def test_bundled_variants_reject_remote_cross_bundle_hash_mix(tmp_path):
    path,identity,session,variants=bundled_variant_fixture(tmp_path,different_metadata=True)
    exports=[]
    for rows,_ in variants:
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        exports.append(provider_export.sanitize_admin_trace(path,identity,session,context_id='context'))
    mixed=copy.deepcopy(exports[0])
    metadata=next(row for row in mixed['records'] if row['type']=='sanitized_metadata')
    metadata['payload']=next(row for row in exports[1]['records'] if row['type']=='sanitized_metadata')['payload']
    with pytest.raises(ValueError,match='prospective profile'):
        provider_export.validate_admin_export(mixed,identity,session,context_id='context')


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
    task=call(box,'task')['result']
    page=call(box,'read_projection',{'offset':0})['result']
    assert page['sha256']==task['projection']['sha256']
    assert json.loads(page['text'])==box.session('session-01')['projection']
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


@pytest.mark.parametrize('scenario', ['success','late_admit','global_bound','expired_actor','late_native','late_receipt',
                                      'wrong_turn','pre_admit_write','promotion_too_late','commit_crosses_deadline'])
def test_opt_in_native_timing_separates_dispatch_actor_and_receipt(setup_provider,tmp_path,monkeypatch,scenario):
    controller,old_box,enrollment=setup_provider
    published=1_900_000_000
    native_start=published+100
    clock=[published]
    monkeypatch.setattr(provider.time,'time',lambda:clock[0])
    enrollment={**enrollment,'native_timing':{'dispatch_wait_seconds':180,'receipt_grace_seconds':15,
                                               'episode_deadline_epoch':published+(365 if scenario=='global_bound' else 2700)}}
    binding={'schema_version':provider_export.SCHEMA,'client_source_sha256':'a'*64,
             'sanitizer_source_sha256':provider_export.source_sha256(),
             'audit_profile_sha256':provider._hash(provider_export.audit_profile(enrollment)), 'initial_metadata':[]}
    box=provider.ProviderMailbox(root=tmp_path/'timed'/'provider',case_root=controller.case,public_root=old_box.public,
                                 enrollment={**enrollment,'trace_export':binding})
    public=open_session(box,register=False)
    assert public['dispatch_deadline_epoch']==published+(110 if scenario=='global_bound' else 180)
    path=box.root/'synthetic-native-prefix.jsonl'
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    rows.insert(1,{'type':'event_msg','payload':{'type':'task_started','turn_id':'wrong' if scenario=='wrong_turn' else 'turn-1'}})
    if scenario=='pre_admit_write':
        request={'request_id':'early-write','operation':'write_chunk','payload':{'path':'draft.py','offset':0,'text':'x=1'}}
        rows.append({'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':'early-write',
                                                      'input':provider.call_template(box.identity,'session-01',json.dumps(request))}})
    for i,row in enumerate(rows):
        row['timestamp']=datetime.fromtimestamp(native_start+i-1,timezone.utc).isoformat()
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    clock[0]=published+(180 if scenario=='late_admit' else 120)
    if scenario=='pre_admit_write':
        with pytest.raises(ValueError,match='may precede native admission'):
            provider_export.sanitize_admin_trace(path,box.identity,box.session('session-01'),context_id='context')
        assert box.session('session-01')['registered_context'] is None
        return
    prefix=provider_export.sanitize_admin_trace(path,box.identity,box.session('session-01'),context_id='context')
    admit={'admin':'admit_sanitized','session':'session-01','context_id':'context','export':prefix}
    if scenario in {'late_admit','global_bound','wrong_turn'}:
        with pytest.raises(ValueError):provider.service_request(box,admit)
        assert box.session('session-01')['registered_context'] is None
        return
    admission=provider.service_request(box,admit)
    state=box.session('session-01')
    assert state['started_epoch']==published
    timing=state['registered_context']['native_timing']
    assert timing=={'started_epoch':native_start,'actor_deadline_epoch':native_start+240,'receipt_deadline_epoch':native_start+255}
    assert admission['native_timing']==timing
    if scenario=='expired_actor':
        clock[0]=native_start+241
        assert call(box,'task')['status']=='rejected'
        return
    clock[0]=native_start+230  # Already beyond the old publication-based window.
    assert call(box,'task')['status']=='ok'
    if scenario=='commit_crosses_deadline':
        written=call(box,'write_chunk',{'path':'draft.py','offset':0,'text':'x=1\n'})
        assert call(box,'seal_file',{'path':'draft.py','sha256':written['result']['sha256']})['status']=='ok'
    assert call(box,'seal_session',{'requests':[]})['status']=='ok'
    complete_trace(box,path)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    for index,row in enumerate(rows[len(prefix['records']):],start=220):
        row['timestamp']=datetime.fromtimestamp(native_start+index,timezone.utc).isoformat()
    rows[-1]['timestamp']=datetime.fromtimestamp(native_start+(241 if scenario=='late_native' else 239),timezone.utc).isoformat()
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    if scenario=='late_native':
        with pytest.raises(ValueError,match='execution audit'):
            provider_export.sanitize_admin_trace(path,box.identity,box.session('session-01'),context_id='context',
                                                 complete=True,prior_source=prefix['source'])
        return
    full=provider_export.sanitize_admin_trace(path,box.identity,box.session('session-01'),context_id='context',
                                             complete=True,prior_source=prefix['source'])
    clock[0]=native_start+(255 if scenario=='late_receipt' else 250)
    accept={**admit,'admin':'accept_sanitized','export':full}
    if scenario=='promotion_too_late':
        manifest=provider.tree_manifest
        def delayed_manifest(path):
            clock[0]=native_start+255
            return manifest(path)
        monkeypatch.setattr(provider,'tree_manifest',delayed_manifest)
    if scenario=='commit_crosses_deadline':
        copy=provider.shutil.copyfile
        def delayed_copy(source,destination):
            result=copy(source,destination)
            clock[0]=native_start+256
            return result
        monkeypatch.setattr(provider.shutil,'copyfile',delayed_copy)
    if scenario in {'late_receipt','promotion_too_late'}:
        with pytest.raises(ValueError,match='receipt deadline'):
            provider.service_request(box,accept)
        assert box.session('session-01')['receipt_sha256'] is None
    else:
        pointer=provider.service_request(box,accept)
        assert pointer['receipt_sha256']
        accepted=provider.service_request(box,{'admin':'status','session':'session-01'})
        crossed=scenario=='commit_crosses_deadline'
        assert accepted['status']=='accepted' and accepted['receipt_sha256']==pointer['receipt_sha256']
        assert accepted['receipt_timing']=={'accepted_started_epoch':native_start+250,
            'commit_recorded_epoch':native_start+(256 if crossed else 250),'recorded_after_receipt_deadline':crossed}
        if crossed:
            assert (controller.case/'output/draft.py').read_text()=='x=1\n'
            with pytest.raises(ValueError,match='audit only'):
                provider.read_trusted_receipt(pointer,controller_run=box.root.parent,reservation_id='session-01',
                                              episode_id='episode',run_id='run')
