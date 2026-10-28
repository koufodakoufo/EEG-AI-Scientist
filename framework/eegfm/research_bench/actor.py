"""Fresh Codex control homes and narrow Linux permission profiles.

This is a trusted Builder launcher, never an Actor-editable module. It does not
assert isolation merely because config parses: require a passing live report.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Any

from .budget import run_bounded, write_atomic
from .bundle import digest_file, verify_public_bundle


def _quote(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def build_profile(*, case: Path, public: Path, control_home: Path, runtime: Path,
                  native_binary: Path, bwrap_dir: Path, model: str | None = None) -> str:
    values = [case, public, control_home, runtime, native_binary, bwrap_dir]
    if any(not path.is_absolute() for path in values):
        raise ValueError('Launcher paths must be absolute')
    public.relative_to(case)
    try:
        control_home.relative_to(case)
    except ValueError:
        pass
    else:
        raise ValueError('Authentication/control home must be outside Actor case')
    model_line = '' if model is None else f'model = {_quote(model)}\n'
    return f'''{model_line}approval_policy = "never"
model_reasoning_effort = "medium"
web_search = "disabled"
project_doc_max_bytes = 0
project_doc_fallback_filenames = []
default_permissions = "actor"
[permissions.actor.filesystem]
":minimal" = "read"
{_quote(native_binary)} = "read"
{_quote(runtime)} = "read"
{_quote(case)} = "write"
{_quote(public)} = "read"
{_quote(control_home / 'tmp/arg0-linux')} = "read"
{_quote(control_home / 'auth.json')} = "deny"
{_quote(control_home / 'actor.config.toml')} = "deny"
[permissions.actor.network]
enabled = false
[shell_environment_policy]
inherit = "none"
[shell_environment_policy.set]
PATH = {_quote(str(runtime)+':'+str(bwrap_dir)+':/usr/bin:/bin')}
HOME = {_quote(case / 'home')}
TMPDIR = {_quote(case / 'tmp')}
LANG = "C.UTF-8"
OMP_NUM_THREADS = "4"
OPENBLAS_NUM_THREADS = "4"
MKL_NUM_THREADS = "4"
NUMEXPR_NUM_THREADS = "4"
[features]
apps = false
plugins = false
hooks = false
memories = false
multi_agent = false
skill_search = false
skill_mcp_dependency_install = false
skip_host_skill_discovery = true
shell_snapshot = false
unbounded_connection_retries = false
browser_use = false
computer_use = false
image_generation = false
view_image = false
artifact = false
code_mode = false
code_mode_host = true
daemon_auto_start = false
[features.multi_agent_v2]
enabled = false
disable_native_tools = true
[agents]
enabled = false
[skills]
include_instructions = false
[skills.bundled]
enabled = false
[cloud.skills]
enabled = false
'''


def profile_template_sha256(model: str | None) -> str:
    """Fingerprint policy independently of each fresh run's path names."""
    from pathlib import PurePosixPath
    text=build_profile(case=PurePosixPath('/BENCH/case'),public=PurePosixPath('/BENCH/case/public'),
                       control_home=PurePosixPath('/BENCH/control'),runtime=PurePosixPath('/BENCH/runtime'),
                       native_binary=PurePosixPath('/BIN/codex'),bwrap_dir=PurePosixPath('/BIN/bwrap'),model=model)
    return hashlib.sha256(text.encode()).hexdigest()


def prepare_control(*, case: Path, public: Path, control_home: Path, native_binary: Path,
                    bwrap_dir: Path, auth_source: Path, model: str | None = None) -> dict[str, Any]:
    """Copy only explicitly authorized authentication bytes; never log contents."""
    if os.name != 'posix':
        raise RuntimeError('Linux control preparation only')
    verify_public_bundle(public)
    case = case.resolve(strict=True)
    public = public.resolve(strict=True)
    native_binary = native_binary.resolve(strict=True)
    if control_home.exists() or control_home.is_symlink():
        raise FileExistsError('Each run requires a fresh control home')
    if auth_source.is_symlink() or not auth_source.is_file():
        raise ValueError('Authentication must be an explicit regular file')
    if stat.S_IMODE(auth_source.stat().st_mode) & 0o077:
        raise ValueError('Authentication source must not be group/world accessible')
    control_home.mkdir(mode=0o700, parents=True)
    runtime = control_home.parent / (control_home.name + '-runtime')
    runtime.mkdir(mode=0o700)
    for name in ('codex-linux-sandbox', 'apply_patch', 'applypatch'):
        (runtime / name).symlink_to(native_binary)
    profile = build_profile(case=case, public=public, control_home=control_home, runtime=runtime,
                            native_binary=native_binary, bwrap_dir=bwrap_dir, model=model)
    (control_home / 'actor.config.toml').write_text(profile, encoding='utf-8')
    os.chmod(control_home / 'actor.config.toml', 0o600)
    # No config, plugin, memory, session, hooks or old research directories copied.
    fd = os.open(control_home / 'auth.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as destination, auth_source.open('rb') as source:
        shutil.copyfileobj(source, destination)
    for directory in (case / 'home', case / 'tmp', case / 'output'):
        directory.mkdir(mode=0o700, exist_ok=True)
    metadata = {'schema_version': 'actor_control_v1', 'case': str(case), 'public': str(public),
                'control_home': str(control_home), 'runtime': str(runtime), 'native_binary': str(native_binary),
                'native_binary_sha256': digest_file(native_binary), 'profile_sha256': hashlib.sha256(profile.encode()).hexdigest(),
                'code_mode_host_sha256':digest_file(native_binary.parent/'codex-code-mode-host') if (native_binary.parent/'codex-code-mode-host').is_file() else None,
                'bwrap_sha256':digest_file(bwrap_dir/'bwrap'),'profile_template_sha256':profile_template_sha256(model),
                'model_requested': model, 'auth_copied': True, 'auth_contents_logged': False,
                'context': 'fresh exec; no parent conversation; no resumed session',
                'isolation_status': 'requires_live_canary_validation'}
    write_atomic(control_home / 'launcher-metadata.json', metadata)
    return metadata


def actor_argv(metadata: dict[str, Any], prompt: str, output_file: Path) -> list[str]:
    # CLI 0.165.0 applies --ignore-user-config to the selected profile too.
    # Fresh dedicated CODEX_HOME is the isolation mechanism for user config.
    # Persist only in this fresh protected home so the trusted collector can
    # retain actual nested tool events, then discard non-visible reasoning fields.
    return [metadata['native_binary'], 'exec', '--json', '--ignore-rules',
            '--strict-config', '--skip-git-repo-check', '-C', metadata['case'], '-p', 'actor',
            '--output-last-message', str(output_file), prompt]


def launch_actor(metadata: dict[str, Any], prompt: str, *, output_dir: Path, timeout_seconds: int,
                 bwrap_dir: Path, proxy_url: str, role: str, isolation_report: dict[str, Any] | None = None,
                 prompt_via_stdin: bool = False) -> dict[str, Any]:
    if role not in {'preflight', 'isolation_canary', 'diagnostic', 'actor', 'distiller', 'judge'}:
        raise ValueError('Unknown model role')
    if digest_file(Path(metadata['control_home'])/'actor.config.toml')!=metadata['profile_sha256']:
        raise RuntimeError('Control profile changed after preparation')
    verify_public_bundle(Path(metadata['public']))
    if role in {'actor', 'distiller'}:
        validate_isolation_gate(metadata,isolation_report)
    if role == 'preflight' and timeout_seconds > 90:
        raise ValueError('Preflight timeout exceeds 90 seconds')
    if not proxy_url.startswith('http://127.0.0.1:') or not proxy_url.rsplit(':', 1)[1].isdigit():
        raise ValueError('Use the verified scoped loopback model-control proxy')
    env = {'PATH': str(bwrap_dir)+':/usr/bin:/bin', 'HOME': metadata['control_home'],
           'CODEX_HOME': metadata['control_home'], 'LANG': 'C.UTF-8',
           'HTTP_PROXY': proxy_url, 'HTTPS_PROXY': proxy_url, 'http_proxy': proxy_url, 'https_proxy': proxy_url,
           'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'}
    input_path=None
    if prompt_via_stdin:
        input_path=Path(metadata['control_home'])/'prompt.txt'
        with input_path.open('x',encoding='utf-8') as handle: handle.write(prompt)
        os.chmod(input_path,0o600)
    argv = actor_argv(metadata, '-' if prompt_via_stdin else prompt, output_dir / 'final.txt')
    report = run_bounded(argv, cwd=Path(metadata['case']), output_dir=output_dir, timeout_seconds=timeout_seconds, env=env,
                         limit_address_space=False,storage_limit_bytes=64*1024**2,stdin_path=input_path)
    report.update(role=role, profile_sha256=metadata['profile_sha256'], context=metadata['context'])
    report.update(prompt_transport='stdin' if prompt_via_stdin else 'argv',prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
    write_atomic(output_dir / 'status.json', report)
    return report


def validate_isolation_gate(metadata: dict[str,Any],report: dict[str,Any] | None) -> None:
    if not report or report.get('status')!='passed' or report.get('schema_version')!='isolation_report_v2':
        raise RuntimeError('Blind launch blocked: live isolation not verified')
    for key in ('native_binary_sha256','code_mode_host_sha256','bwrap_sha256','profile_template_sha256'):
        if not metadata.get(key) or report.get(key)!=metadata[key]:
            raise RuntimeError(f'Blind launch blocked: isolation {key} mismatch')
    probes=report.get('probes',{})
    denied=('private_absolute','private_parent','private_symlink','other_case','control_config','ancestor_agents',
            'host_controller_proc','gold.txt','scorer.py','budget.json','events.jsonl','public_write',
            'direct_socket','generic_proxy','live_local_service','https')
    if any(probes.get(name,{}).get('allowed') is not False for name in denied):
        raise RuntimeError('Blind launch blocked: incomplete denial canaries')
    if any(probes.get(name,{}).get('allowed') is not True for name in ('public_read','own_write')):
        raise RuntimeError('Blind launch blocked: positive canaries missing')
    if probes.get('proxy_environment_present') is not False or not report.get('tool_surface_verified') or not report.get('model_control_succeeded'):
        raise RuntimeError('Blind launch blocked: tool/control boundary unverified')
