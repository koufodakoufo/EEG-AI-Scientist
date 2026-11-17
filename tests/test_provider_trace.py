"""Exact coding transport grammar and chunk recovery over synthetic native records."""
import json,hashlib
from datetime import datetime, timedelta, timezone
import pytest
from eegfm.agent import provider,provider_trace

IDENTITY={'model':'gpt-6.1-sol','effort':'high','parent_thread':'parent','gateway':{'script':'X:/owned/gateway.py','workdir':'X:/owned'}}
WAIT = 'await new Promise(resolve=>setTimeout(resolve,15000)); '


def test_exact_call_and_native_poll_templates_reject_extra_code():
    request={'request_id':'one','operation':'task','payload':{}}
    code=provider.call_template(IDENTITY,'session-01',json.dumps(request))
    assert provider_trace.parse_tool(code+'\n',IDENTITY,'session-01')==('call',request)
    assert provider_trace.parse_tool(provider.poll_template(345),IDENTITY,'session-01')==('poll',345)
    for bad in (code+'; text("hint")',code.replace('text(result)','text(result.output)'),code.replace('9000','9001'),'/*x*/'+code):
        with pytest.raises(ValueError):provider_trace.parse_tool(bad,IDENTITY,'session-01')
    assert provider_trace.parse_tool(provider.call_template(IDENTITY,'session-01',provider.canonical_bytes(request).decode().strip()),IDENTITY,'session-01')==('call',request)


def test_wait_is_one_literal_prefix_for_request_status_only():
    request={'request_id':'task-status-01','operation':'request_status','payload':{'request_id':'task'}}
    code=provider.call_template(IDENTITY,'session-01',json.dumps(request))
    assert provider_trace.parse_tool(WAIT+code,IDENTITY,'session-01')==('call',request)
    task=provider.call_template(IDENTITY,'session-01',json.dumps({'request_id':'task','operation':'task','payload':{}}))
    for rejected in (WAIT.replace('15000','14999')+code,WAIT.replace('15000','24000')+code,WAIT.replace('15000','15_000')+code,
                     WAIT+WAIT+code,WAIT+' '+code,WAIT+task,WAIT+provider.poll_template(345),
                     WAIT+'text("extra"); '+code,WAIT+code+' text("extra");'):
        with pytest.raises(ValueError):
            provider_trace.parse_tool(rejected,IDENTITY,'session-01')


def test_bootstrap_supplies_exact_wait_status_template():
    text=provider.bootstrap(IDENTITY,'session-01')
    code=text.split('\nWAIT STATUS TEMPLATE',1)[1].splitlines()[1]
    request={'request_id':'task-status-01','operation':'request_status','payload':{'request_id':'task'}}
    assert code==WAIT+provider.call_template(IDENTITY,'session-01',provider.canonical_bytes(request).decode().strip())
    assert provider_trace.parse_tool(code,IDENTITY,'session-01')==('call',request)


def trace(tmp_path,chunks=True,extra=None,*,wait_status=False):
    memory='========= MEMORY_SUMMARY BEGINS =========\ncommon\n========= MEMORY_SUMMARY ENDS ========='
    environment='<environment_context>synthetic</environment_context>'
    initial=[{'role':'developer','kinds':['memories.instructions'],'content_sha256':provider._hash([{'type':'input_text','text':memory}])},{'role':'user','kinds':['environments.environment_context'],'content_sha256':provider._hash([{'type':'input_text','text':environment}])}]
    identity={**IDENTITY,'inherited_context':{'memory_summary_sha256':hashlib.sha256(b'\ncommon\n').hexdigest(),'disclosure':'Known common history','initial_messages':initial}}
    request=({'request_id':'one','operation':'request_status','payload':{'request_id':'task'}} if wait_status
             else {'request_id':'one','operation':'task','payload':{}})
    response={'request_id':'one','status':'ok','result':{'fixture':True}}
    stdout=provider.canonical_bytes(response).decode()+'\n'
    encoded=provider_trace.percent_encode(request)
    command=provider.command(identity,'session-01')+encoded
    rows=[{'type':'session_meta','payload':{'id':'context','agent_path':'/root/actor','parent_thread_id':'parent'}},
          {'type':'response_item','payload':{'type':'message','role':'developer','content':[{'type':'input_text','text':'========= MEMORY_SUMMARY BEGINS =========\ncommon\n========= MEMORY_SUMMARY ENDS ========='}],'internal_chat_message_metadata_passthrough':{'content_item_kinds':['memories.instructions']}}},
          {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':environment}],'internal_chat_message_metadata_passthrough':{'content_item_kinds':['environments.environment_context']}}},
          {'type':'response_item','payload':{'type':'agent_message','author':'/root','recipient':'/root/actor','content':[{'type':'input_text','text':'Message Type: NEW_TASK\nTask name: /root/actor\nSender: /root\nPayload:\n'},{'type':'encrypted_content','encrypted_content':'gAAAAAsynthetic'}]}},
          {'type':'turn_context','payload':{'turn_id':'turn','model':'gpt-6.1-sol','effort':'high'}}]
    def call(code,id,envelope):
        rows.extend([{'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':id,'input':code}},{'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':id,'output':[{'type':'input_text','text':'Script completed\nWall time 0.1 seconds\nOutput:\n'},{'type':'input_text','text':json.dumps(envelope)}]}}])
    code=(WAIT if wait_status else '')+provider.call_template(identity,'session-01',json.dumps(request))
    if chunks:
        call(code,'a',{'output':stdout[:10],'session_id':345,'wall_time_seconds':10.0})
        call(provider.poll_template(345),'b',{'output':stdout[10:],'exit_code':0,'wall_time_seconds':1.0})
    else:call(code,'a',{'output':stdout,'exit_code':0,'wall_time_seconds':0.1})
    # Real native completion precedes the terminal whole-result output, including
    # when the preceding response returned a running session for later polling.
    rows.insert(len(rows)-1,{'type':'event_msg','payload':{'type':'item_completed','item':{'type':'CommandExecution','command':provider_trace.SHELL_PREFIX+[command],'aggregated_output':stdout,'status':'completed','exit_code':0}}})
    if extra:rows.append(extra)
    rows.extend([{'type':'response_item','payload':{'type':'message','role':'assistant','phase':'final_answer','id':'final','content':[{'type':'output_text','text':'SESSION_SEALED'}],'internal_chat_message_metadata_passthrough':{'turn_id':'turn'}}},{'type':'event_msg','payload':{'type':'task_complete','turn_id':'turn'}}])
    start=datetime(2026,11,8,20,tzinfo=timezone.utc)
    elapsed_wait=0
    for i,row in enumerate(rows):
        row['timestamp']=(start+timedelta(seconds=i+elapsed_wait)).isoformat()
        if wait_status and row['payload'].get('type')=='custom_tool_call' and row['payload'].get('call_id')=='a':
            elapsed_wait=15
    path=tmp_path/'native.jsonl';path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    session={'session_id':'session-01','agent_path':'/root/actor','started_epoch':start.timestamp(),'timeout_seconds':240,'registered_context':{'context_id':'context','trace_path':str(path.resolve())}}
    return path,identity,session,[{'request':request,'response':response}]


def test_full_result_session_id_chunks_recover_without_resubmission(tmp_path):
    args=trace(tmp_path)
    result=provider_trace.audit_native_context(*args)
    assert result['valid'] and result['gateway_calls']==1 and result['native_poll_calls']==1


def test_astra_trace_must_match_exact_registered_model_and_effort(tmp_path):
    path, identity, session, deliveries = trace(tmp_path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        if row['type'] == 'turn_context':
            row['payload'].update(model='gpt-6-astra', effort='ultra')
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    assert not provider_trace.audit_native_context(path, identity, session, deliveries)['valid']
    identity.update(model='gpt-6-astra', effort='ultra')
    assert provider_trace.audit_native_context(path, identity, session, deliveries)['valid']
    identity['effort'] = 'high'
    assert not provider_trace.audit_native_context(path, identity, session, deliveries)['valid']


def test_unowned_transport_poll_and_external_hint_reject(tmp_path):
    path,identity,session,deliveries=trace(tmp_path)
    path.write_text(path.read_text().replace('session_id:345','session_id:999'))
    assert not provider_trace.audit_native_context(path,identity,session,deliveries)['valid']
    extra={'type':'response_item','payload':{'type':'function_call','name':'read_file','call_id':'bad','arguments':'{}'}}
    assert not provider_trace.audit_native_context(*trace(tmp_path,extra=extra))['valid']


@pytest.mark.parametrize('mutation',['unknown_event','unknown_record','late_output','early_completion','failed','missing_status','missing_timestamp','naive_timestamp','late_final','late_complete','reversed_time','before_reservation'])
def test_complete_trace_requires_bounded_consistent_execution(tmp_path,mutation):
    path,identity,session,deliveries=trace(tmp_path)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    native=next(r for r in rows if r['payload'].get('item',{}).get('type')=='CommandExecution')
    output=next(r for r in reversed(rows) if r['payload'].get('type')=='custom_tool_call_output')
    if mutation=='unknown_event':rows.insert(-2,{'type':'event_msg','payload':{'type':'exec_command_begin'}})
    elif mutation=='unknown_record':rows.insert(-2,{'type':'unknown_execution','payload':{}})
    elif mutation=='late_output':rows.remove(output);rows.insert(-1,output)
    elif mutation=='early_completion':rows.remove(native);rows.insert(5,native)
    elif mutation=='failed':native['payload']['item'].update(status='failed',exit_code=1)
    elif mutation=='missing_status':del native['payload']['item']['status']
    elif mutation=='missing_timestamp':del output['timestamp']
    elif mutation=='naive_timestamp':rows[-1]['timestamp']='2026-11-08T20:00:20'
    elif mutation in {'late_final','late_complete'}:rows[-2 if mutation=='late_final' else -1]['timestamp']='2026-11-08T20:05:00Z'
    elif mutation=='reversed_time':rows[-1]['timestamp']=rows[5]['timestamp']
    else:session['started_epoch']+=6
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    assert not provider_trace.audit_native_context(path,identity,session,deliveries)['valid']


def test_passive_late_ingestion_uses_original_completion_proof(tmp_path,monkeypatch):
    args=trace(tmp_path)
    monkeypatch.setattr(provider.time,'time',lambda:args[2]['started_epoch']+3600)
    result=provider_trace.audit_native_context(*args)
    assert result['valid']
    assert result['timing']['completion_epoch']<=result['timing']['deadline_epoch']
    assert result['timing']['started_epoch']==args[2]['started_epoch']
