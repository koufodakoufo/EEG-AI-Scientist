"""Scientific runtimes are opt-in readonly capabilities, never broad host access."""
from pathlib import PurePosixPath as Path

import pytest

from eegfm.research_bench.actor import build_profile, profile_template_sha256


def profile(**extra: object) -> str:
    return build_profile(case=Path('/bench/case'), public=Path('/bench/case/public'),
        control_home=Path('/bench/control'), runtime=Path('/bench/runtime'),
        native_binary=Path('/bin/codex'), bwrap_dir=Path('/bin/bwrap'), **extra)


def test_science_runtime_is_explicit_readonly_and_bytecode_disabled() -> None:
    text = profile(read_only_roots=(Path('/bench/science-env'),))
    assert '"/bench/science-env" = "read"' in text
    assert 'PYTHONDONTWRITEBYTECODE = "1"' in text
    assert 'CUDA_VISIBLE_DEVICES = ""' in text
    assert '"/bench" = "read"' not in text
    assert profile_template_sha256(None, read_only_roots=(Path('/bench/science-env'),)) != profile_template_sha256(None)


@pytest.mark.parametrize('unsafe', ['/', '/data', '/home', '/bench/case', '/bench/control', 'relative/env'])
def test_science_runtime_refuses_broad_or_control_or_writable_mount(unsafe: str) -> None:
    with pytest.raises(ValueError):
        profile(read_only_roots=(Path(unsafe),))


def test_scientific_profile_requires_live_runtime_probes() -> None:
    from eegfm.research_bench.actor import validate_isolation_gate
    keys=('native_binary_sha256','code_mode_host_sha256','bwrap_sha256','profile_template_sha256')
    metadata={key:'a'*64 for key in keys}
    metadata['read_only_roots']=['/bench/science-env']
    denied=('private_absolute','private_parent','private_symlink','other_case','control_config','ancestor_agents',
        'host_controller_proc','gold.txt','scorer.py','budget.json','events.jsonl','public_write',
        'direct_socket','generic_proxy','live_local_service','https')
    probes={key:{'allowed':False} for key in denied}
    probes.update(public_read={'allowed':True},own_write={'allowed':True},proxy_environment_present=False)
    report={**metadata,'schema_version':'isolation_report_v2','status':'passed','probes':probes,
            'tool_surface_verified':True,'model_control_succeeded':True}
    with pytest.raises(RuntimeError,match='Scientific runtime'):
        validate_isolation_gate(metadata,report)
    probes.update(scientific_runtime_read={'allowed':True},scientific_runtime_write={'allowed':False},scientific_python={'allowed':True})
    validate_isolation_gate(metadata,report)
