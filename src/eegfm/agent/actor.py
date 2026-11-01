"""Fresh Codex control homes and narrow Linux permission profiles.

This is a trusted Builder launcher, never an Actor-editable module. It does not
assert isolation merely because config parses: require a passing live report.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Any

from eegfm.agent.budget import run_bounded
from eegfm.agent.budget import write_atomic
from eegfm.evaluation.bundle import digest_file
from eegfm.evaluation.bundle import verify_public_bundle


def _quote(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def build_profile(*, case: Path, public: Path, control_home: Path, runtime: Path,
                  native_binary: Path, bwrap_dir: Path, model: str | None = None,
                  read_only_roots: tuple[Path, ...] = ()) -> str:
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
    extra_reads = ''
    for root in read_only_roots:
        if not root.is_absolute() or len(root.parts) < 3 or '..' in root.parts:
            raise ValueError('Scientific runtime must be a narrow absolute directory')
        if any(root == protected or root in protected.parents or protected in root.parents
               for protected in (case, control_home, runtime, public)):
            raise ValueError('Scientific runtime cannot overlap writable or control paths')
        extra_reads += f'{_quote(root)} = "read"\n'
    extra_environment = '' if not read_only_roots else f'''PYTHONDONTWRITEBYTECODE = "1"
CUDA_VISIBLE_DEVICES = ""
XDG_CACHE_HOME = {_quote(case / 'tmp/cache')}
TORCH_HOME = {_quote(case / 'tmp/torch')}
MPLCONFIGDIR = {_quote(case / 'tmp/matplotlib')}
'''
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
{extra_reads}{_quote(control_home / 'auth.json')} = "deny"
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
{extra_environment}[features]
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


def profile_template_sha256(model: str | None, *, read_only_roots: tuple[Path, ...] = ()) -> str:
    """Fingerprint policy independently of each fresh run's path names."""
    from pathlib import PurePosixPath
    text=build_profile(case=PurePosixPath('/BENCH/case'),public=PurePosixPath('/BENCH/case/public'),
                       control_home=PurePosixPath('/BENCH/control'),runtime=PurePosixPath('/BENCH/runtime'),
                       native_binary=PurePosixPath('/BIN/codex'),bwrap_dir=PurePosixPath('/BIN/bwrap'),model=model,
                       read_only_roots=read_only_roots)
    return hashlib.sha256(text.encode()).hexdigest()


def prepare_control(*, case: Path, public: Path, control_home: Path, native_binary: Path,
                    bwrap_dir: Path, auth_source: Path, model: str | None = None,
                    read_only_roots: tuple[Path, ...] = (), auth_mode: str = 'readonly_bind') -> dict[str, Any]:
    """Fresh control state; readonly_bind never reads or copies credential bytes.

    The historical copy mode requires an explicit, authorized opt-in.
    In bind mode only the trusted native client sees the original file through a
    read-only mount; model tools are separately denied the whole control home.
    """
    if os.name != 'posix':
        raise RuntimeError('Linux control preparation only')
    if auth_mode not in {'copy', 'readonly_bind'}:
        raise ValueError('Unknown authentication mode')
    verify_public_bundle(public)
    case = case.resolve(strict=True)
    public = public.resolve(strict=True)
    native_binary = native_binary.resolve(strict=True)
    read_only_roots = tuple(path.resolve(strict=True) for path in read_only_roots)
    if control_home.exists() or control_home.is_symlink():
        raise FileExistsError('Each run requires a fresh control home')
    if auth_source.is_symlink() or not auth_source.is_file():
        raise ValueError('Authentication must be an explicit regular file')
    if stat.S_IMODE(auth_source.stat().st_mode) & 0o077:
        raise ValueError('Authentication source must not be group/world accessible')
    auth_source = auth_source.resolve(strict=True)
    if auth_source.is_relative_to(case) or any(auth_source.is_relative_to(root) for root in read_only_roots):
        raise ValueError('Authentication source cannot be inside Actor-accessible paths')
    control_home.mkdir(mode=0o700, parents=True)
    runtime = control_home.parent / (control_home.name + '-runtime')
    runtime.mkdir(mode=0o700)
    for name in ('codex-linux-sandbox', 'apply_patch', 'applypatch'):
        (runtime / name).symlink_to(native_binary)
    profile = build_profile(case=case, public=public, control_home=control_home, runtime=runtime,
                            native_binary=native_binary, bwrap_dir=bwrap_dir, model=model,read_only_roots=read_only_roots)
    (control_home / 'actor.config.toml').write_text(profile, encoding='utf-8')
    os.chmod(control_home / 'actor.config.toml', 0o600)
    # No config, plugin, memory, session, hooks or old research directories copied.
    fd = os.open(control_home / 'auth.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as destination:
        if auth_mode == 'copy':
            with auth_source.open('rb') as source:
                shutil.copyfileobj(source, destination)
    for directory in (case / 'home', case / 'tmp', case / 'output'):
        directory.mkdir(mode=0o700, exist_ok=True)
    metadata = {'schema_version': 'actor_control_v1', 'case': str(case), 'public': str(public),
                'control_home': str(control_home), 'runtime': str(runtime), 'native_binary': str(native_binary),
                'native_binary_sha256': digest_file(native_binary), 'profile_sha256': hashlib.sha256(profile.encode()).hexdigest(),
                'code_mode_host_sha256':digest_file(native_binary.parent/'codex-code-mode-host') if (native_binary.parent/'codex-code-mode-host').is_file() else None,
                'bwrap_sha256':digest_file(bwrap_dir/'bwrap'),'profile_template_sha256':profile_template_sha256(model,read_only_roots=read_only_roots),
                'read_only_roots':[str(path) for path in read_only_roots],
                'model_requested': model, 'auth_mode':auth_mode, 'auth_copied':auth_mode=='copy', 'auth_contents_logged': False,
                'context': 'fresh exec; no parent conversation; no resumed session',
                'isolation_status': 'requires_live_canary_validation'}
    if auth_mode == 'readonly_bind':
        metadata.update(auth_source=str(auth_source), auth_source_identity=_auth_identity(auth_source),
                        transport_template_sha256=readonly_transport_sha256())
    write_atomic(control_home / 'launcher-metadata.json', metadata)
    return metadata


def _auth_identity(path: Path) -> dict[str, int]:
    """Filesystem identity only. Never inspect, hash, or copy credential bytes."""
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Authentication source must remain a private regular file')
    value = path.stat()
    return {name: getattr(value, name) for name in ('st_dev','st_ino','st_uid','st_size','st_mtime_ns','st_mode')}


def readonly_transport_sha256() -> str:
    return hashlib.sha256(inspect.getsource(readonly_auth_argv).encode()).hexdigest()


def readonly_auth_argv(metadata: dict[str, Any], argv: list[str], output_dir: Path,
                       bwrap_dir: Path) -> list[str]:
    """Outer trusted-client namespace; the inner CLI profile governs Actor tools.

    Explicit mounts omit the original home, repository, private evaluation files,
    other cases and host processes. The native client retains network for its
    scoped proxy; Actor tool network is disabled by the inner permission profile.
    """
    if metadata.get('auth_mode') != 'readonly_bind':
        raise ValueError('Read-only authentication mode required')
    source = Path(metadata['auth_source'])
    if _auth_identity(source) != metadata.get('auth_source_identity'):
        raise ValueError('Authentication source changed after preparation')
    if metadata.get('transport_template_sha256') != readonly_transport_sha256():
        raise ValueError('Read-only authentication transport changed after preparation')
    control = Path(metadata['control_home'])
    native = Path(metadata['native_binary'])
    command = [str(bwrap_dir/'bwrap'),'--die-with-parent','--new-session','--unshare-pid',
               '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib',
               '--symlink','usr/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp']
    for path in ('/etc/ssl','/etc/pki','/etc/resolv.conf','/etc/hosts','/etc/nsswitch.conf',
                 '/etc/passwd','/etc/group','/etc/ld.so.cache'):
        if Path(path).exists(): command += ['--ro-bind',path,path]
    for path in dict.fromkeys([str(native.parent),str(bwrap_dir),metadata['runtime'],*metadata.get('read_only_roots',[])]):
        command += ['--ro-bind',path,path]
    for path in dict.fromkeys([metadata['case'],str(control),str(output_dir)]):
        command += ['--bind',path,path]
    command += ['--ro-bind',str(source),str(control/'auth.json'),
                '--chdir',metadata['case'],'--',*argv]
    return command


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
                 prompt_via_stdin: bool = False, case_storage_limit_bytes: int = 64*1024**2) -> dict[str, Any]:
    if role not in {'preflight', 'isolation_canary', 'diagnostic', 'actor', 'distiller', 'judge'}:
        raise ValueError('Unknown model role')
    if digest_file(Path(metadata['control_home'])/'actor.config.toml')!=metadata['profile_sha256']:
        raise RuntimeError('Control profile changed after preparation')
    binary_paths = {'native_binary_sha256':Path(metadata['native_binary']),
                    'bwrap_sha256':bwrap_dir/'bwrap'}
    if metadata.get('code_mode_host_sha256'):
        binary_paths['code_mode_host_sha256'] = Path(metadata['native_binary']).parent/'codex-code-mode-host'
    for key, path in binary_paths.items():
        if digest_file(path) != metadata.get(key):
            raise RuntimeError('Runtime binary changed after preparation: '+key)
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
    if metadata.get('auth_mode') == 'readonly_bind':
        argv = readonly_auth_argv(metadata, argv, output_dir, bwrap_dir)
    report = run_bounded(argv, cwd=Path(metadata['case']), output_dir=output_dir, timeout_seconds=timeout_seconds, env=env,
                         limit_address_space=False,storage_limit_bytes=case_storage_limit_bytes,stdin_path=input_path)
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
    if metadata.get('auth_mode') == 'readonly_bind':
        if report.get('auth_mode') != 'readonly_bind' or report.get('transport_template_sha256') != metadata.get('transport_template_sha256'):
            raise RuntimeError('Blind launch blocked: readonly authentication transport mismatch')
        if any(probes.get(name,{}).get('allowed') is not False for name in
               ('auth_source','auth_mounted','private_test','private_split','private_driver')):
            raise RuntimeError('Authentication/private-data boundary has not passed live probes')
    if metadata.get('read_only_roots') and (
            probes.get('scientific_runtime_read',{}).get('allowed') is not True or
            probes.get('scientific_python',{}).get('allowed') is not True or
            probes.get('scientific_runtime_write',{}).get('allowed') is not False):
        raise RuntimeError('Scientific runtime boundary has not passed live probes')
    denied=('private_absolute','private_parent','private_symlink','other_case','control_config','ancestor_agents',
            'host_controller_proc','gold.txt','scorer.py','budget.json','events.jsonl','public_write',
            'direct_socket','generic_proxy','live_local_service','https')
    if any(probes.get(name,{}).get('allowed') is not False for name in denied):
        raise RuntimeError('Blind launch blocked: incomplete denial canaries')
    if any(probes.get(name,{}).get('allowed') is not True for name in ('public_read','own_write')):
        raise RuntimeError('Blind launch blocked: positive canaries missing')
    if probes.get('proxy_environment_present') is not False or not report.get('tool_surface_verified') or not report.get('model_control_succeeded'):
        raise RuntimeError('Blind launch blocked: tool/control boundary unverified')
