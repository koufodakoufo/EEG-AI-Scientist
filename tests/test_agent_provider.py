"""Delegated provider state/contracts; synthetic traces, no real model invocation."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import hashlib,json
import pytest
from eegfm.agent import provider
from eegfm.agent.controller import ResearchController,ResearchDriver
from eegfm.evaluation.bundle import canonical_bytes,create_public_bundle,digest_file

MEMORY='\nSynthetic common inherited history.\n'
MEMORY_TEXT='========= MEMORY_SUMMARY BEGINS ========='+MEMORY+'========= MEMORY_SUMMARY ENDS ========='
ENV_TEXT='<environment_context>synthetic</environment_context>'
INITIAL=[{'role':'developer','kinds':['memories.instructions'],'content_sha256':provider._hash([{'type':'input_text','text':MEMORY_TEXT}])},{'role':'user','kinds':['environments.environment_context'],'content_sha256':provider._hash([{'type':'input_text','text':ENV_TEXT}])}]


class Evaluator:
    sandboxed=True
    def submit(self,spec):raise AssertionError('No scientific execution in provider tests')
    def poll(self,job_id):raise AssertionError('No scientific execution')


@pytest.fixture
def setup_provider(tmp_path):
    case=tmp_path/'case';(case/'output').mkdir(parents=True)
    source=tmp_path/'source';source.mkdir();(source/'TASK.md').write_text('Synthetic coding task only')
    public=case/'public';create_public_bundle(source,public,['TASK.md'],task_id='synthetic',tier='synthetic_mechanism')
    controller=ResearchController(trusted_root=tmp_path/'trusted',case_root=case,episode_id='episode',run_id='run',public_manifest_sha256=digest_file(public/'PUBLIC_MANIFEST.json'),split_manifest_sha256='a'*64,evaluator=Evaluator())
    enrollment={'episode_id':'episode','run_id':'run','model':'gpt-6.1-sol','effort':'high','parent_thread':'parent','agent_prefix':'/root/coding_run','session_limit':6,'session_timeout_seconds':240,'gateway':{'script':'X:/owned/gateway.py','workdir':'X:/owned'},'inherited_context':{'memory_summary_sha256':hashlib.sha256(MEMORY.encode()).hexdigest(),'disclosure':'Common inherited history; workflow development, not a blind or memory-free context.','initial_messages':INITIAL}}
    box=provider.ProviderMailbox(root=controller.run/'provider',case_root=case,public_root=public,enrollment=enrollment)
    return controller,box,enrollment


def open_session(box,timeout=240,*,register=True,projection=None):
    if projection is None:
        projection={'episode_id':'episode','run_id':'run','state':{'status':'brief','version':0},'lock':None}
    session=box.publish('session-01',projection,timeout_seconds=timeout)
    path=box.root/'synthetic-native-prefix.jsonl'
    records=[{'type':'session_meta','payload':{'id':'context','parent_thread_id':'parent','agent_path':session['agent_path']}},
             {'type':'response_item','payload':{'type':'message','role':'developer','content':[{'type':'input_text','text':'========= MEMORY_SUMMARY BEGINS ========='+MEMORY+'========= MEMORY_SUMMARY ENDS ========='}],'internal_chat_message_metadata_passthrough':{'content_item_kinds':['memories.instructions']}}},
             {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':ENV_TEXT}],'internal_chat_message_metadata_passthrough':{'content_item_kinds':['environments.environment_context']}}},
             {'type':'response_item','payload':{'type':'agent_message','author':'/root','recipient':session['agent_path'],'content':[{'type':'input_text','text':f"Message Type: NEW_TASK\nTask name: {session['agent_path']}\nSender: /root\nPayload:\n"},{'type':'encrypted_content','encrypted_content':'gAAAAAsynthetic'}]}},
             {'type':'turn_context','payload':{'turn_id':'turn-1','model':'gpt-6.1-sol','effort':'high'}}]
    start=datetime.fromtimestamp(box.session('session-01')['started_epoch']+1,timezone.utc)
    for index,row in enumerate(records):row['timestamp']=(start+timedelta(seconds=index)).isoformat()
    path.write_text(''.join(json.dumps(row)+'\n' for row in records))
    if register:box.register_context('session-01',context_id='context',trace_path=path)
    return session


def call(box,operation,payload=None,request_id=None):
    call.n+=1
    return box.handle('session-01',{'request_id':request_id or f'gateway-{call.n}','operation':operation,'payload':payload or {}})
call.n=0


def test_reservation_binds_budget_projection_context_and_inherited_history(setup_provider):
    _,box,enrollment=setup_provider
    session=open_session(box)
    assert session['timeout_seconds']==240 and session['agent_path']=='/root/coding_run_session_01'
    assert open_session(box)==session
    with pytest.raises(ValueError):open_session(box,180)
    task=call(box,'task')['result']
    assert task['inherited_context']['memory_summary_sha256']==enrollment['inherited_context']['memory_summary_sha256']
    assert 'not a blind' in task['inherited_context']['disclosure']
    assert 'private' not in json.dumps(task['files'])


@pytest.mark.parametrize('deferred', [False, True])
def test_large_projection_is_read_losslessly_through_bounded_gateway_pages(setup_provider,deferred):
    _,box,_=setup_provider
    projection={'episode_id':'episode','run_id':'run','state':{'status':'report','version':8},'lock':{'candidate':'selected'},
                'cohorts':{f'cohort-{group}':{'subjects':{
                    f'subject-{subject}':{'original_accuracy':(group+subject)/333,'accuracy':subject/137,
                                         'loss':1/(subject+1),'mean_error':1/(subject+17),'label':'Δ accuracy'}
                    for subject in range(100)}} for group in range(3)},
                'notes':'🧠"\\' * 2000}
    expected=canonical_bytes(projection)
    assert len(expected)>44_000
    open_session(box,register=not deferred,projection=projection)
    if deferred:
        assert call(box,'task',request_id='initial-task')['status']=='awaiting_context_admission'
        box.register_context('session-01',context_id='context',trace_path=box.root/'synthetic-native-prefix.jsonl')
        envelope=call(box,'request_status',{'request_id':'initial-task'})
        task=envelope['result']['response']
    else:
        envelope=task=call(box,'task')
    assert len(canonical_bytes(envelope))<6000
    descriptor=task['result']['projection']
    assert descriptor=={'sha256':hashlib.sha256(expected).hexdigest(),'characters':len(expected.decode('utf-8')),
                        'page_chars':6000,'read_operation':'read_projection'}
    assert task['result']['operations']['read_projection']=={'offset':0}
    projection['cohorts'].clear()  # The caller's object can change after publication.
    offset=0
    parts=[]
    while offset is not None:
        envelope=call(box,'read_projection',{'offset':offset})
        assert envelope['status']=='ok' and len(canonical_bytes(envelope))<7000
        page=envelope['result']
        assert page['sha256']==descriptor['sha256'] and page['offset']==offset
        assert 0<len(page['text'])<=descriptor['page_chars']
        parts.append(page['text'])
        offset=page['next_offset']
    assert ''.join(parts).encode('utf-8')==expected
    terminal=call(box,'read_projection',{'offset':descriptor['characters']})
    assert terminal['result']=={'sha256':descriptor['sha256'],'offset':descriptor['characters'],
                                'text':'','next_offset':None}
    for payload in ({'offset':False},{'offset':-1},{'offset':'0'},{'offset':1.5},
                    {'offset':descriptor['characters']+1},{'offset':10**8},{'offset':0,'path':'TASK.md'},{}):
        assert call(box,'read_projection',payload)['status']=='rejected'


def test_projection_requires_admitted_context_and_task(setup_provider):
    _,box,_=setup_provider
    open_session(box,register=False)
    assert call(box,'read_projection',{'offset':0})['error_type']=='ContextNotAdmitted'
    box.register_context('session-01',context_id='context',trace_path=box.root/'synthetic-native-prefix.jsonl')
    assert call(box,'read_projection',{'offset':0})['status']=='rejected'
    assert call(box,'task')['status']=='ok'
    assert call(box,'read_projection',{'offset':0})['status']=='ok'
    assert call(box,'seal_session',{'requests':[]})['status']=='ok'
    assert call(box,'read_projection',{'offset':0})['status']=='rejected'


@pytest.mark.parametrize('receipt_at', [None, 1350, 1355])
def test_launcher_keeps_dispatch_and_receipt_windows_outside_actor_budget(tmp_path,monkeypatch,receipt_at):
    from eegfm.agent import budget

    clock=[1000.]
    timing={'started_epoch':1100,'actor_deadline_epoch':1340,'receipt_deadline_epoch':1355}
    calls=[]
    def state(identifier):
        assert identifier=='session-01'
        registered={'context_id':'context','native_timing':timing} if receipt_at is not None and clock[0]>=1120 else None
        return {'started_epoch':1000,'dispatch_deadline_epoch':1180,'registered_context':registered,
                'receipt_sha256':'a'*64 if registered and clock[0]>=receipt_at else None}
    mailbox=SimpleNamespace(root=tmp_path, session=state, publish=lambda *args,**kwargs:None)
    monkeypatch.setattr(provider.time,'time',lambda:clock[0])
    monkeypatch.setattr(provider.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    monkeypatch.setattr(budget,'reserve_call',lambda path,id,role,seconds:calls.append((id,role,seconds)))
    monkeypatch.setattr(budget,'mark_call',lambda path,id,status,**details:calls.append((status,details)))
    launch=provider.ProviderLaunch(mailbox,poll_seconds=10,budget_path=tmp_path/'budget.json',call_ids=['actor-1'])
    projection={'provider_session':{'provider':provider.PROVIDER,'reservation_id':'session-01','timeout_seconds':240}}
    if receipt_at==1350:
        assert launch(projection)['receipt_sha256']=='a'*64
        assert clock[0]==1350 and [call[0] for call in calls]==['actor-1','running','completed']
        assert calls[1][1]['native_timing']==timing
    else:
        with pytest.raises(RuntimeError,match='outcome unresolved'):launch(projection)
        assert clock[0]==(1180 if receipt_at is None else 1355)
        assert [call[0] for call in calls]==(['actor-1'] if receipt_at is None else ['actor-1','running'])
    assert calls[0]==('actor-1','actor',240)


def test_chunk_replay_is_exact_paths_bounded_and_staging_never_executes(setup_provider):
    controller,box,_=setup_provider;open_session(box);call(box,'task')
    text='raise RuntimeError("must not execute on host")\n'
    payload={'path':'candidate/main.py','offset':0,'text':text}
    first=call(box,'write_chunk',payload,'chunk-one')
    assert first['result']['sha256']==hashlib.sha256(text.encode()).hexdigest()
    assert call(box,'write_chunk',payload,'chunk-one')==first
    with pytest.raises(ValueError):call(box,'write_chunk',{**payload,'text':'changed'},'chunk-one')
    sealed=call(box,'seal_file',{'path':'candidate/main.py','sha256':hashlib.sha256(text.encode()).hexdigest()})
    assert sealed['status']=='ok'
    assert not (controller.case/'output/candidate/main.py').exists()
    for path in ('../escape','/absolute','.hidden/a','candidate/../../escape'):
        result=call(box,'write_chunk',{**payload,'path':path})
        assert result['status']=='rejected'
    assert call(box,'write_chunk',{**payload,'path':'huge.py','text':'x'*4097})['status']=='rejected'


def test_seal_batch_does_not_ingest_or_accept_self_certification(setup_provider):
    controller,box,_=setup_provider;open_session(box);call(box,'task')
    batch=[{'request_id':'brief-1','episode_id':'episode','operation':'brief','payload':{'path':'brief.md'}}]
    result=call(box,'seal_session',{'requests':batch})
    assert result['status']=='ok' and controller.projection()['state']['status']=='brief'
    assert call(box,'accept_audit',{'valid':True})['status']=='rejected'
    assert call(box,'write_chunk',{'path':'later.py','offset':0,'text':'pass'})['status']=='rejected'


def test_missing_inherited_binding_and_enrollment_drift_rejected(setup_provider):
    controller,box,enrollment=setup_provider
    with pytest.raises(ValueError):provider.ProviderMailbox(root=box.root,case_root=controller.case,public_root=box.public,enrollment={**enrollment,'effort':'medium'})
    bad={k:v for k,v in enrollment.items() if k!='inherited_context'}
    with pytest.raises(ValueError):provider.ProviderMailbox(root=controller.run/'other',case_root=controller.case,public_root=box.public,enrollment=bad)


def test_native_reservation_default_unchanged_delegated_allocation_honest(setup_provider):
    controller,_,_=setup_provider
    first=controller.reserve_session(6)
    native=json.loads((controller.run/'sessions.jsonl').read_text().splitlines()[0])
    assert native['allocated_timeout_seconds']==900 and 'provider' not in native
    controller.record_session({'status':'completed','exit_code':0,'stdout':'{"type":"turn.completed"}\n','stderr':'','process_cleanup':{'surviving_owned_pids':[]}},reservation_id=first)
    second=controller.reserve_session(6,provider=provider.PROVIDER,timeout_seconds=180)
    delegated=json.loads((controller.run/'sessions.jsonl').read_text().splitlines()[1])
    assert delegated['provider']==provider.PROVIDER and delegated['allocated_timeout_seconds']==180
    with pytest.raises(ValueError):controller.record_session({'provider':provider.PROVIDER,'receipt_path':str(controller.case/'output/forged.json'),'receipt_sha256':'a'*64},reservation_id=second)


def test_forged_success_receipt_cannot_use_outside_trusted_root(setup_provider,tmp_path):
    controller,_,_=setup_provider
    forged=tmp_path/'forged.json';forged.write_text('{"status":"completed","requests":[],"audit_valid":true}')
    pointer={'provider':provider.PROVIDER,'receipt_path':str(forged),'receipt_sha256':digest_file(forged)}
    with pytest.raises(ValueError):provider.read_trusted_receipt(pointer,controller_run=controller.run,reservation_id='session-01',episode_id='episode',run_id='run')


def test_task_waits_for_prospectively_bound_native_initial_history(setup_provider):
    _,box,_=setup_provider
    box.publish('session-01',{'episode_id':'episode','run_id':'run','state':{'status':'brief','version':0},'lock':None},timeout_seconds=240)
    response=call(box,'task',request_id='first-task')
    assert response['status']=='awaiting_context_admission' and 'result' not in response
    open_session(box)
    status=call(box,'request_status',{'request_id':'first-task'})
    assert status['result']['response']['result']['inherited_context']['memory_summary_sha256']==box.identity['inherited_context']['memory_summary_sha256']


def complete_trace(box,path=None):
    from eegfm.agent import provider_trace
    session=box.session('session-01');path=path or Path(session['registered_context']['trace_path'])
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    for index,item in enumerate(box.deliveries('session-01')):
        stdout=provider.canonical_bytes(item['response']).decode()+'\n'
        rows.extend([{'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':f'call-{index}','input':provider.call_template(box.identity,'session-01',json.dumps(item['request']))}},
            {'type':'event_msg','payload':{'type':'item_completed','item':{'type':'CommandExecution','command':provider_trace.SHELL_PREFIX+[provider.command(box.identity,'session-01')+provider_trace.percent_encode(item['request'])],'aggregated_output':stdout,'status':'completed','exit_code':0}}},
            {'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':f'call-{index}','output':[{'type':'input_text','text':'Script completed\nWall time 0.1 seconds\nOutput:\n'},{'type':'input_text','text':json.dumps({'output':stdout,'exit_code':0,'wall_time_seconds':0.1})}]}}])
    rows.extend([{'type':'response_item','payload':{'type':'message','role':'assistant','phase':'final_answer','id':'final','content':[{'type':'output_text','text':'SESSION_SEALED'}],'internal_chat_message_metadata_passthrough':{'turn_id':'turn-1'}}},{'type':'event_msg','payload':{'type':'task_complete','turn_id':'turn-1'}}])
    start=datetime.fromtimestamp(session['started_epoch']+1,timezone.utc)
    for index,row in enumerate(rows):row.setdefault('timestamp',(start+timedelta(seconds=index)).isoformat())
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows));return path


def test_passive_complete_trace_authorizes_sealed_source_and_typed_controller_receipt(setup_provider,monkeypatch):
    controller,box,_=setup_provider
    reservation=controller.reserve_session(6,provider=provider.PROVIDER,timeout_seconds=240)
    open_session(box);call(box,'task')
    text='Independent synthetic plan.\n'
    call(box,'write_chunk',{'path':'brief.md','offset':0,'text':text})
    call(box,'seal_file',{'path':'brief.md','sha256':hashlib.sha256(text.encode()).hexdigest()})
    request={'request_id':'brief-1','episode_id':'episode','operation':'brief','payload':{'path':'brief.md'}}
    call(box,'seal_session',{'requests':[request]})
    path=complete_trace(box)
    state=box.session('session-01')
    monkeypatch.setattr(provider.time,'time',lambda:state['started_epoch']+3600)
    pointer=box.accept_trace('session-01',path)
    assert box.session('session-01')['started_epoch']==state['started_epoch']
    audit=json.loads((box.root/'audits/session-01.json').read_text())
    assert audit['timing']['completion_epoch']<=audit['timing']['deadline_epoch']
    verified=provider.read_trusted_receipt(pointer,controller_run=controller.run,reservation_id=reservation,episode_id='episode',run_id='run')
    assert verified['requests']==[request] and (controller.case/'output/brief.md').read_text()==text
    record=controller.record_session(pointer,reservation_id=reservation)
    assert record['ok'] and record['summary']['provider']==provider.PROVIDER
    assert 'stdout' not in verified and 'process_cleanup' not in verified
    # Crash after the session record, before ingestion: replay the verified
    # batch without launching another model or rerunning an existing request.
    assert provider.recover_completed_reservations(controller)==1
    assert controller.projection()['state']['status']=='awaiting_review'
    before=controller.projection()['state']['version']
    provider.recover_completed_reservations(controller)
    assert controller.projection()['state']['version']==before


def test_late_native_completion_retains_unresolved_reservation(setup_provider):
    controller,box,_=setup_provider
    controller.reserve_session(6,provider=provider.PROVIDER,timeout_seconds=240)
    open_session(box);call(box,'task');call(box,'seal_session',{'requests':[]})
    path=complete_trace(box)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    state=box.session('session-01')
    rows[-1]['timestamp']=datetime.fromtimestamp(state['started_epoch']+241,timezone.utc).isoformat()
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError,match='reservation remains unresolved'):
        box.accept_trace('session-01',path)
    assert box.session('session-01')['status']=='sealed'
    assert box.session('session-01')['receipt_sha256'] is None
    assert not (box.root/'receipts/session-01.json').exists()
    assert provider.recover_completed_reservations(controller)==0
    records=[json.loads(line) for line in (controller.run/'sessions.jsonl').read_text().splitlines()]
    assert records[-1]['status']=='reserved'


def test_request_batch_can_be_sealed_from_uploaded_file_without_long_cli_payload(setup_provider):
    _,box,_=setup_provider;open_session(box);call(box,'task')
    batch=[{'request_id':'brief-one','episode_id':'episode','operation':'brief','payload':{'path':'brief.md'}}]
    text=json.dumps(batch);sha=hashlib.sha256(text.encode()).hexdigest()
    call(box,'write_chunk',{'path':'requests.json','offset':0,'text':text})
    call(box,'seal_file',{'path':'requests.json','sha256':sha})
    result=call(box,'seal_session',{'requests_path':'requests.json','sha256':sha})
    assert result['status']=='ok' and box.session('session-01')['sealed']['requests']==batch


def test_control_character_sources_and_oversized_native_payload_are_rejected(setup_provider):
    _,box,_=setup_provider;open_session(box);call(box,'task')
    assert call(box,'write_chunk',{'path':'nul.py','offset':0,'text':'\x00'})['status']=='rejected'
    with pytest.raises(ValueError):call(box,'unknown',{'text':'x'*9000})


def test_undeclared_initial_user_hint_rejected_before_task_admission(setup_provider):
    _,box,_=setup_provider;open_session(box)
    session=box.session('session-01');path=Path(session['registered_context']['trace_path'])
    with path.open('a') as stream:stream.write(json.dumps({'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'Private answer hint'}]}})+'\n')
    with pytest.raises(ValueError):box.register_context('session-01',context_id='context',trace_path=path)


def test_fit_ownership_reserved_before_crash_and_recovery_only_polls(setup_provider):
    _,box,_=setup_provider;open_session(box);call(box,'task')
    text='raise RuntimeError("never execute in host test")\n'
    call(box,'write_chunk',{'path':'candidate/fit.py','offset':0,'text':text})
    call(box,'seal_file',{'path':'candidate/fit.py','sha256':hashlib.sha256(text.encode()).hexdigest()})
    class Bench:
        private=box.root/'fake-workbench'
        def submit(self,job_id,path):raise RuntimeError('crash after gateway reservation')
        def poll(self,job_id):raise ValueError('unknown reserved public job')
    box.workbench_factory=lambda case:Bench()
    with pytest.raises(RuntimeError):call(box,'fit_submit',{'job_id':'fit-one','candidate_dir':'candidate'})
    assert box.session('session-01')['fit_jobs']=={'fit-one':'waiting'}
    result=call(box,'fit_poll',{'job_id':'fit-one'})
    assert result['result']['status']=='waiting'
    with box.transaction() as db:assert db.execute('SELECT COUNT(*) FROM fits').fetchone()[0]==1


def test_allowed_kind_does_not_admit_changed_initial_scientific_text(setup_provider):
    _,box,_=setup_provider;open_session(box)
    path=Path(box.session('session-01')['registered_context']['trace_path'])
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    rows.insert(1,{'type':'response_item','payload':{'type':'message','role':'developer','content':[{'type':'input_text','text':'Extra scientific hint'}],'internal_chat_message_metadata_passthrough':{'content_item_kinds':['model.base_instructions']}}})
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError):box.register_context('session-01',context_id='context',trace_path=path)
