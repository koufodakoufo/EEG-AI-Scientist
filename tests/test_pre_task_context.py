"""Atomic trusted-root context enrollment; synthetic traces, no network/model."""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import pytest
from test_agent_provider import setup_provider, open_session, call
from eegfm.agent import provider, provider_export as export, provider_trace as trace


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def append_delivery(rows, identity, delivery, index):
    request,response=delivery['request'],delivery['response']
    stdout=provider.canonical_bytes(response).decode()+'\n'
    rows.extend([
        {'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':f'call-{index}',
            'input':provider.call_template(identity,'session-01',json.dumps(request))}},
        {'type':'event_msg','payload':{'type':'item_completed','item':{'type':'CommandExecution',
            'command':trace.SHELL_PREFIX+[provider.command(identity,'session-01')+trace.percent_encode(request)],
            'aggregated_output':stdout,'status':'completed','exit_code':0}}},
        {'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':f'call-{index}',
            'output':[{'type':'input_text','text':'Script completed\nWall time 0.1 seconds\nOutput:\n'},
                      {'type':'input_text','text':json.dumps({'output':stdout,'exit_code':0,'wall_time_seconds':0.1})}]}}])
    for index,row in enumerate(rows):
        row.setdefault('timestamp',datetime.fromtimestamp(1001+index,timezone.utc).isoformat())


def context_case(setup_provider,tmp_path,monkeypatch,*,timeout=240):
    _,old,enrollment=setup_provider
    clock=[1000.];monkeypatch.setattr(provider.time,'time',lambda:clock[0])
    enrollment=copy.deepcopy(enrollment)
    enrollment['session_timeout_seconds']=timeout
    enrollment['inherited_context']['initial_messages'][0]['kinds']=['generic.developer_instructions','memories.instructions']
    enrollment['native_timing']={'dispatch_wait_seconds':600,'receipt_grace_seconds':15,'episode_deadline_epoch':5200}
    enrollment['trace_export']={'schema_version':export.SCHEMA,'client_source_sha256':'a'*64,
        'sanitizer_source_sha256':export.source_sha256(),'audit_profile_sha256':provider._hash(export.audit_profile(enrollment)),
        'initial_metadata':[{'kind':'world_state','payload_sha256':provider._hash({'version':'base'})}],
        'session_context_policy':'trusted_root_pre_task_v1'}
    box=provider.ProviderMailbox(root=tmp_path/'attested-run/provider',case_root=old.case,public_root=old.public,enrollment=enrollment)
    open_session(box,timeout=timeout,register=False)
    path=box.root/'synthetic-native-prefix.jsonl';rows=provider._trace_records(path)
    rows[1]['payload']['internal_chat_message_metadata_passthrough']['content_item_kinds']=['generic.developer_instructions','memories.instructions']
    rows[1]['payload']['content'][0]['text']+='\nA newly reviewed generic platform catalog.'
    rows.insert(1,{'type':'event_msg','payload':{'type':'task_started','turn_id':'turn-1'}})
    rows.insert(3,{'type':'world_state','payload':{'version':'reviewed'}})
    for index,row in enumerate(rows):row['timestamp']=datetime.fromtimestamp(1001+index,timezone.utc).isoformat()
    request={'request_id':'task','operation':'task','payload':{}}
    response=box.handle('session-01',request);assert response['status']=='awaiting_context_admission'
    append_delivery(rows,box.identity,{'request':request,'response':response},0);write_rows(path,rows)
    messages=copy.deepcopy(enrollment['inherited_context']['initial_messages'])
    messages[0]['content_sha256']=provider._hash(rows[2]['payload']['content'])
    raw=path.read_bytes();state=box.session('session-01')
    attestation={'schema_version':'trusted_root_pre_task_context_v1','base_profile_sha256':export.base_profile_sha256(box.identity),
        'episode_id':'episode','run_id':'run','session_id':'session-01','context_id':'context','agent_path':state['agent_path'],
        'context_bundle':{'initial_messages':messages,'initial_metadata':[{'kind':'world_state','payload_sha256':provider._hash({'version':'reviewed'})}],
                          'memory_summary_sha256':enrollment['inherited_context']['memory_summary_sha256']},
        'reviewed_source':{'path_sha256':provider._hash(str(path.resolve())),'prefix_bytes':len(raw),'prefix_sha256':hashlib.sha256(raw).hexdigest()},
        'bootstrap_sha256':hashlib.sha256(state['published']['bootstrap'].encode()).hexdigest(),'spawn_evidence_sha256':'b'*64,'review_sha256':'c'*64}
    clock[0]=1030.
    return box,path,attestation,clock


def admit_body(box,path,attestation):
    projected=export.sanitize_admin_trace(path,box.identity,box.session('session-01'),context_id='context',context_enrollment=attestation)
    return {'admin':'admit_sanitized','session':'session-01','context_id':'context','export':projected,'context_enrollment':attestation}


@pytest.mark.parametrize('timeout',[240,480])
def test_opt_in_attestation_atomically_releases_only_completed_waiting_task(setup_provider,tmp_path,monkeypatch,timeout):
    box,path,attestation,_=context_case(setup_provider,tmp_path,monkeypatch,timeout=timeout)
    base=copy.deepcopy(box.identity);before=box.session('session-01')
    body=admit_body(box,path,attestation)
    result=provider.service_request(box,body);state=box.session('session-01')
    assert result['status']=='initial_context_admitted' and state['task_read'] is True
    assert result['context_enrollment_sha256']==provider._hash(attestation)
    assert state['registered_context']['context_enrollment']==attestation
    assert state['registered_context']['context_enrollment_sha256']==provider._hash(attestation)
    assert box.identity==base and state['started_epoch']==before['started_epoch'] and state['timeout_seconds']==timeout
    with box.transaction() as db:
        response=json.loads(db.execute('SELECT response FROM requests WHERE id=?',('task',)).fetchone()[0])
    assert response['status']=='ok'
    assert provider.service_request(box,body)==result
    assert box.session('session-01')==state


@pytest.mark.parametrize('field',['base_profile_sha256','episode_id','run_id','session_id','context_id','agent_path',
                                  'bootstrap_sha256','spawn_evidence_sha256','review_sha256'])
def test_bad_attestation_never_registers_or_releases_task(setup_provider,tmp_path,monkeypatch,field):
    box,path,attestation,_=context_case(setup_provider,tmp_path,monkeypatch)
    bad=copy.deepcopy(attestation);bad[field]='wrong'
    with pytest.raises(ValueError):admit_body(box,path,bad)
    state=box.session('session-01');assert state['registered_context'] is None and not state['task_read']


@pytest.mark.parametrize('case',['memory','environment','pure_memory','shape','source_path','source_hash','prefix_size'])
def test_fixed_context_and_reviewed_raw_prefix_cannot_be_replaced(setup_provider,tmp_path,monkeypatch,case):
    box,path,a,_=context_case(setup_provider,tmp_path,monkeypatch);a=copy.deepcopy(a)
    if case=='memory':a['context_bundle']['memory_summary_sha256']='f'*64
    elif case=='environment':a['context_bundle']['initial_messages'][-1]['content_sha256']='f'*64
    elif case=='pure_memory':a['context_bundle']['initial_messages'][0]['kinds']=['memories.instructions']
    elif case=='shape':a['context_bundle']['initial_messages'].append(a['context_bundle']['initial_messages'][0])
    elif case=='source_path':a['reviewed_source']['path_sha256']='f'*64
    elif case=='source_hash':a['reviewed_source']['prefix_sha256']='f'*64
    else:a['reviewed_source']['prefix_bytes']=True
    with pytest.raises(ValueError):admit_body(box,path,a)
    assert not box.session('session-01')['task_read']


@pytest.mark.parametrize('case',['missing_policy','policy_with_variants','public_request','missing_enrollment','accept_supplied_enrollment'])
def test_attestation_is_explicit_admin_only_and_strict_default_is_unchanged(setup_provider,tmp_path,monkeypatch,case):
    box,path,a,_=context_case(setup_provider,tmp_path,monkeypatch)
    if case in {'missing_policy','policy_with_variants'}:
        identity=copy.deepcopy(box.identity)
        if case=='missing_policy':del identity['trace_export']['session_context_policy']
        else:identity['trace_export']['context_variants']=[a['context_bundle'],a['context_bundle']]
        with pytest.raises(ValueError):export.derive_session_context_identity(identity,box.session('session-01'),context_id='context',context_enrollment=a)
    else:
        body=admit_body(box,path,a)
        if case=='public_request':body={'session':'session-01','request':body}
        elif case=='missing_enrollment':body.pop('context_enrollment')
        else:body['admin']='accept_sanitized'
        with pytest.raises(ValueError):provider.service_request(box,body)
    assert not box.session('session-01')['task_read']


@pytest.mark.parametrize('late',['pending_status','unauthorized_call','late_input'])
def test_live_tail_is_checked_but_allowed_inflight_status_does_not_change_reviewed_prefix(setup_provider,tmp_path,monkeypatch,late):
    box,path,a,_=context_case(setup_provider,tmp_path,monkeypatch);rows=provider._trace_records(path)
    if late=='late_input':rows.append(copy.deepcopy(rows[2]))
    else:
        request={'request_id':'later','operation':'request_status' if late=='pending_status' else 'write_chunk','payload':{'request_id':'task'} if late=='pending_status' else {'path':'x.py','offset':0,'text':'x=1'}}
        rows.append({'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':'later','input':provider.call_template(box.identity,'session-01',json.dumps(request))}})
    write_rows(path,rows)
    if late=='pending_status':
        body=admit_body(box,path,a);assert body['export']['source']['prefix_bytes']==a['reviewed_source']['prefix_bytes']
        assert len(body['export']['records'])==len(rows)-1
        assert provider.service_request(box,body)['status']=='initial_context_admitted'
    else:
        with pytest.raises(ValueError):admit_body(box,path,a)
        assert not box.session('session-01')['task_read']


def test_changed_concurrent_admission_cannot_replace_the_stored_attestation(setup_provider,tmp_path,monkeypatch):
    box,path,a,_=context_case(setup_provider,tmp_path,monkeypatch);first=admit_body(box,path,a)
    second=copy.deepcopy(first);second['context_enrollment']['review_sha256']='d'*64
    def submit(body):
        try:return provider.service_request(box,body)['status']
        except (ValueError,FileExistsError):return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(submit,[first,second]))
    assert sorted(results)==['initial_context_admitted','rejected']
    state=box.session('session-01');assert state['task_read'] and state['registered_context']['context_enrollment'] in [a,second['context_enrollment']]


def test_transaction_failure_cannot_release_pending_task(setup_provider,tmp_path,monkeypatch):
    box,path,a,_=context_case(setup_provider,tmp_path,monkeypatch);body=admit_body(box,path,a)
    def fail(*args):raise RuntimeError('synthetic commit failure')
    monkeypatch.setattr(box,'_save_session',fail)
    with pytest.raises(RuntimeError,match='commit failure'):provider.service_request(box,body)
    state=box.session('session-01');assert state['registered_context'] is None and state['task_read'] is False
    with box.transaction() as db:assert db.execute('SELECT response FROM requests WHERE id=?',('task',)).fetchone()[0] is None


@pytest.mark.parametrize('role,kind',[('system','model.base_instructions'),('developer','model.base_instructions'),
    ('developer','permissions.instructions'),('developer','multi_agent.role_instructions'),('developer','collaboration_mode.instructions')])
def test_attestation_cannot_change_separate_noncatalogue_instructions(setup_provider,tmp_path,monkeypatch,role,kind):
    box,_,a,_=context_case(setup_provider,tmp_path,monkeypatch);identity=copy.deepcopy(box.identity)
    row={'role':role,'kinds':[kind],'content_sha256':'d'*64}
    identity['inherited_context']['initial_messages'].insert(0,row)
    identity['trace_export']['audit_profile_sha256']=provider._hash(export.audit_profile(identity))
    a['base_profile_sha256']=export.base_profile_sha256(identity)
    a['context_bundle']['initial_messages'].insert(0,{**row,'content_sha256':'e'*64})
    with pytest.raises(ValueError,match='common ordered structure'):
        export.derive_session_context_identity(identity,box.session('session-01'),context_id='context',context_enrollment=a)


def finish_context(box,path,a,clock):
    state=box.session('session-01')
    assert call(box,'request_status',{'request_id':'task'})['result']['response']['status']=='ok'
    assert call(box,'seal_session',{'requests':[]})['status']=='ok'
    rows=provider._trace_records(path)
    for index,delivery in enumerate(box.deliveries('session-01')[1:],1):append_delivery(rows,box.identity,delivery,index)
    rows.extend([
        {'type':'response_item','payload':{'type':'message','role':'assistant','phase':'final_answer',
            'content':[{'type':'output_text','text':'SESSION_SEALED'}],'internal_chat_message_metadata_passthrough':{'turn_id':'turn-1'}}},
        {'type':'event_msg','payload':{'type':'task_complete','turn_id':'turn-1'}}])
    for index,row in enumerate(rows):row.setdefault('timestamp',datetime.fromtimestamp(1001+index,timezone.utc).isoformat())
    write_rows(path,rows);clock[0]=1040.
    projected=export.sanitize_admin_trace(path,box.identity,box.session('session-01'),context_id='context',
        prior_source=state['registered_context']['export_source'],complete=True,context_enrollment=state['registered_context']['context_enrollment'])
    return provider.service_request(box,{'admin':'accept_sanitized','session':'session-01','context_id':'context','export':projected})


def read_receipt(box,pointer):
    return provider.read_trusted_receipt(pointer,controller_run=box.root.parent,reservation_id='session-01',episode_id='episode',run_id='run')


def test_complete_receipt_uses_stored_attestation_and_closed_admission_cannot_overwrite_it(setup_provider,tmp_path,monkeypatch):
    box,path,a,clock=context_case(setup_provider,tmp_path,monkeypatch);body=admit_body(box,path,a)
    provider.service_request(box,body);pointer=finish_context(box,path,a,clock)
    receipt=read_receipt(box,pointer);assert receipt['context_enrollment_sha256']==provider._hash(a)
    audit=json.loads((box.root/'audits/session-01.json').read_bytes())
    assert audit['trace_export']['context_enrollment_sha256']==receipt['context_enrollment_sha256']
    frozen={name:(box.root/'sessions/session-01'/name).read_bytes() for name in ('native.jsonl','admitted-export.json','complete-export.json')}
    with pytest.raises(ValueError,match='closed'):provider.service_request(box,body)
    assert all((box.root/'sessions/session-01'/name).read_bytes()==raw for name,raw in frozen.items())
    assert read_receipt(box,pointer)==receipt


@pytest.mark.parametrize('tamper',['stored_review','effective_audit'])
def test_receipt_reader_rejects_attestation_or_effective_audit_substitution(setup_provider,tmp_path,monkeypatch,tamper):
    box,path,a,clock=context_case(setup_provider,tmp_path,monkeypatch)
    provider.service_request(box,admit_body(box,path,a));pointer=finish_context(box,path,a,clock)
    assert read_receipt(box,pointer)['status']=='completed'
    if tamper=='stored_review':
        with box.transaction() as db:
            state=box._session(db,'session-01');state['registered_context']['context_enrollment']['review_sha256']='f'*64
            box._save_session(db,state)
    else:
        audit_path=box.root/'audits/session-01.json';audit=json.loads(audit_path.read_bytes())
        audit['trace_export']['binding']['initial_metadata'][0]['payload_sha256']='f'*64
        audit_path.write_bytes(provider.canonical_bytes(audit))
        receipt_path=Path(pointer['receipt_path']);receipt=json.loads(receipt_path.read_bytes())
        receipt['trusted_audit_sha256']=provider.digest_file(audit_path);receipt_path.write_bytes(provider.canonical_bytes(receipt))
        pointer['receipt_sha256']=provider.digest_file(receipt_path)
        with box.transaction() as db:
            state=box._session(db,'session-01');state['receipt_sha256']=pointer['receipt_sha256'];box._save_session(db,state)
    with pytest.raises(ValueError,match='context enrollment|effective context'):read_receipt(box,pointer)


def test_admission_snapshot_holds_write_lock_until_atomic_release_then_receipt_survives(setup_provider,tmp_path,monkeypatch):
    box,path,a,clock=context_case(setup_provider,tmp_path,monkeypatch);body=admit_body(box,path,a)
    snapshot,release=threading.Event(),threading.Event();original=box._session;paused=[False]
    def controlled(db,identifier):
        state=original(db,identifier)
        if threading.current_thread().name.startswith('admission-race') and not paused[0]:
            paused[0]=True;snapshot.set();assert release.wait(5)
        return state
    monkeypatch.setattr(box,'_session',controlled)
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='admission-race') as pool:
        future=pool.submit(provider.service_request,box,body)
        try:
            assert snapshot.wait(5)
            with sqlite3.connect(box.database,timeout=0) as db:
                with pytest.raises(sqlite3.OperationalError,match='locked'):db.execute('BEGIN IMMEDIATE')
                assert db.execute('SELECT response FROM requests WHERE id=?',('task',)).fetchone()[0] is None
            assert not (box.root/'sessions/session-01/admitted-export.json').exists()
        finally:release.set()
        assert future.result(timeout=5)['status']=='initial_context_admitted'
    pointer=finish_context(box,path,a,clock)
    assert read_receipt(box,pointer)['context_enrollment_sha256']==provider._hash(a)


@pytest.mark.parametrize('mutation',['missing_delivery','task_read','fit_job'])
def test_pristine_waiting_state_is_rechecked_inside_admission_transaction(setup_provider,tmp_path,monkeypatch,mutation):
    box,path,a,_=context_case(setup_provider,tmp_path,monkeypatch);body=admit_body(box,path,a)
    with box.transaction() as db:
        if mutation=='missing_delivery':db.execute('DELETE FROM deliveries WHERE session=?',('session-01',))
        else:
            state=box._session(db,'session-01')
            if mutation=='task_read':state['task_read']=True
            else:state['fit_jobs']={'unapproved':'running'}
            box._save_session(db,state)
    with pytest.raises(ValueError):provider.service_request(box,body)
    with box.transaction() as db:
        assert box._session(db,'session-01')['registered_context'] is None
        assert db.execute('SELECT response FROM requests WHERE id=?',('task',)).fetchone()[0] is None
