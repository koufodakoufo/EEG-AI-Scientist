"""Credential material stays outside Actor files and is never copied in bind mode."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from eegfm.agent import actor
from eegfm.evaluation.bundle import create_public_bundle


def test_readonly_mode_requires_transport_and_auth_denial_certificate():
    keys = ('native_binary_sha256', 'code_mode_host_sha256', 'bwrap_sha256', 'profile_template_sha256')
    metadata = {key: 'a' * 64 for key in keys}
    metadata.update(auth_mode='readonly_bind', transport_template_sha256='b' * 64)
    names = ('private_absolute','private_parent','private_symlink','other_case','control_config','ancestor_agents',
             'host_controller_proc','gold.txt','scorer.py','budget.json','events.jsonl','public_write',
             'direct_socket','generic_proxy','live_local_service','https')
    probes = {name: {'allowed': False} for name in names}
    probes.update(public_read={'allowed': True}, own_write={'allowed': True}, proxy_environment_present=False)
    report = {**metadata, 'schema_version':'isolation_report_v2','status':'passed','probes':probes,
              'model_control_succeeded':True,'tool_surface_verified':True}
    with pytest.raises(RuntimeError, match='Authentication'):
        actor.validate_isolation_gate(metadata, report)
    for name in ('auth_source','auth_mounted','private_test','private_split','private_driver'):
        probes[name] = {'allowed':False}
    actor.validate_isolation_gate(metadata, report)
    report['transport_template_sha256'] = 'wrong'
    with pytest.raises(RuntimeError, match='transport'):
        actor.validate_isolation_gate(metadata, report)


@pytest.mark.skipif(os.name != 'posix', reason='Native Linux file permissions and mounts')
@pytest.mark.parametrize('auth_mode', [None, 'readonly_bind'])
def test_prepare_readonly_mode_never_opens_source_and_mounts_only_named_file(tmp_path, auth_mode):
    case = tmp_path / 'case'; case.mkdir()
    source = tmp_path / 'public-source'; source.mkdir()
    (source / 'task.txt').write_text('benign fixture')
    create_public_bundle(source, case/'public', ['task.txt'], task_id='auth-test',tier='synthetic_mechanism')
    binary_dir = tmp_path/'bin'; binary_dir.mkdir()
    for name in ('codex','codex-code-mode-host','bwrap'):
        (binary_dir/name).write_bytes(b'fixture')
    credentials = tmp_path/'credentials'; credentials.mkdir()
    auth = credentials/'auth.json'; auth.write_bytes(b'fake auth fixture'); auth.chmod(0o600)
    original_open = Path.open
    def guarded_open(path, *args, **kwargs):
        if path == auth:
            raise AssertionError('Credential source must never be opened by preparation')
        return original_open(path, *args, **kwargs)
    options = {} if auth_mode is None else {'auth_mode':auth_mode}
    with patch.object(Path, 'open', guarded_open):
        metadata = actor.prepare_control(case=case, public=case/'public',control_home=tmp_path/'control',
            native_binary=binary_dir/'codex', bwrap_dir=binary_dir, auth_source=auth,
            model='gpt-6.1-sol',**options)
    assert metadata['auth_copied'] is False
    assert (tmp_path/'control/auth.json').stat().st_size == 0
    argv = actor.readonly_auth_argv(metadata, ['codex','exec'], tmp_path/'output',binary_dir)
    assert ['--ro-bind',str(auth),str(tmp_path/'control/auth.json')] in [argv[i:i+3] for i in range(len(argv))]
    assert str(credentials) not in argv
    assert ['--ro-bind','/','/'] not in [argv[i:i+3] for i in range(len(argv))]
    legacy = actor.prepare_control(case=case, public=case/'public',control_home=tmp_path/'explicit-copy',
        native_binary=binary_dir/'codex', bwrap_dir=binary_dir, auth_source=auth,
        model='gpt-6.1-sol',auth_mode='copy')
    assert legacy['auth_copied'] is True
    assert (tmp_path/'explicit-copy/auth.json').read_bytes() == b'fake auth fixture'
    auth.chmod(0o644)
    with pytest.raises(ValueError, match='Authentication source'):
        actor.readonly_auth_argv(metadata,['codex','exec'],tmp_path/'output',binary_dir)

@pytest.mark.parametrize('violation', ['none', 'undeclared_history', 'extra_tool', 'broader_fs', 'tool_call'])
def test_ordinary_context_gates_science_on_actual_rollout(tmp_path, violation):
    import json

    home = tmp_path / 'home'
    work = tmp_path / 'empty-workspace'
    work.mkdir()
    thread = '00000000-0000-4000-8000-000000000001'
    tree = home / 'sessions/2026/11/24'
    tree.mkdir(parents=True)
    source = tree / ('rollout-2026-11-24-' + thread + '.jsonl')
    tool = 'unexpected_command' if violation == 'extra_tool' else 'wait'
    entry = {'type': 'path', 'path': str(tmp_path if violation == 'broader_fs' else work)}
    rows = [
        ('session_meta', {'id': thread, 'source': 'exec', 'cwd': str(work)}),
        ('response_item', {'type': 'additional_tools', 'tools': [
            {'type':'namespace', 'name':'functions', 'tools':[{'name':tool}]}]}),
        ('response_item', {'type':'message', 'role':'developer', 'content':[
            {'text':'You are Codex, an agent with ordinary platform instructions.'}]}),
        ('turn_context', {'cwd':str(work), 'approval_policy':'never',
            'permission_profile':{'network':'restricted', 'file_system':{
                'type':'restricted','entries':[{'path':entry,'access':'read'}]}}}),
        ('response_item', {'type':'message', 'role':'user', 'content':[{'text':'bootstrap'}]})
    ]
    if violation == 'undeclared_history':
        rows.append(('response_item', {'type':'message','role':'user','content':[{'text':'earlier research answer'}]}))
    if violation == 'tool_call':
        rows.append(('response_item', {'type':'function_call','name':'read_results'}))
    source.write_text(''.join(json.dumps({'type': k, 'payload': v}) + '\n' for k,v in rows), encoding='utf-8')
    if violation == 'none':
        evidence = actor._ordinary_context(home,thread,work,['bootstrap'])
        assert evidence['declared_user_messages_verified'] == 1
        assert evidence['visible_tools'] == ['functions.wait']
    else:
        with pytest.raises(ValueError):
            actor._ordinary_context(home,thread,work,['bootstrap'])
