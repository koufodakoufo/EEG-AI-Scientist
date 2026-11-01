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
