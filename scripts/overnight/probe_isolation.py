"""Builder-only, non-model Linux sandbox canary. Writes only in nightly scope."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import time

BASE = Path('/data/duandh/eegfm-stage-a-20261028')
WORK = BASE / 'overnight-20261029'


def main() -> int:
    if sys.platform != 'linux' or not BASE.is_dir():
        raise SystemExit('Run only on the intended server via trusted builder transport')
    probe = WORK / 'isolation-probe-v4'
    probe.mkdir(mode=0o700, parents=True, exist_ok=False)
    case = probe / 'case'
    home = probe / 'control-home'
    outside = probe / 'private'
    runtime = probe / 'runtime'
    for directory in (case, home, outside, runtime, probe / 'other-case'):
        directory.mkdir(mode=0o700)
    for name in ('codex-linux-sandbox', 'apply_patch', 'applypatch'):
        (runtime / name).symlink_to(BASE / 'bin/codex-x86_64-unknown-linux-musl')
    (outside / 'gold.txt').write_text('CANARY_PRIVATE_GOLD_V1\n')
    (outside / 'budget.json').write_text('{"canary":"immutable"}\n')
    (probe / 'other-case' / 'task.txt').write_text('OTHER_CASE_CANARY\n')
    (home / 'auth-canary.txt').write_text('DUMMY_AUTH_CANARY_NOT_A_CREDENTIAL\n')
    (case / 'public.txt').write_text('PUBLIC_READ_OK\n')
    (case / 'escape').symlink_to(outside, target_is_directory=True)
    profile = f'''approval_policy = "never"
web_search = "disabled"
project_doc_max_bytes = 0
default_permissions = "actor"
[permissions.actor.filesystem]
":minimal" = "read"
"{BASE}/bin/codex-x86_64-unknown-linux-musl" = "read"
"{runtime}" = "read"
"{case}" = "write"
"{case}/public.txt" = "read"
"{home}" = "deny"
"{outside}" = "deny"
[permissions.actor.network]
enabled = false
[shell_environment_policy]
inherit = "none"
[shell_environment_policy.set]
PATH = "{runtime}:{WORK}/tools/bubblewrap/usr/bin:/usr/bin:/bin"
LANG = "C.UTF-8"
OMP_NUM_THREADS = "4"
OPENBLAS_NUM_THREADS = "4"
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
'''
    (home / 'actor.config.toml').write_text(profile)
    proxy_port = os.environ.get('HTTPS_PROXY', '').rsplit(':', 1)[-1]
    if not proxy_port.isdigit():
        raise SystemExit('Expected an existing scoped loopback proxy port')
    program = textwrap.dedent('''
        import json, os, pathlib, socket
        case = pathlib.Path.cwd()
        root = case.parent
        result = {}
        def read_case(name, path):
            try:
                value = pathlib.Path(path).read_text()
                result[name] = {'allowed': True, 'bytes': len(value)}
            except OSError as exc:
                result[name] = {'allowed': False, 'errno': exc.errno, 'error': type(exc).__name__}
        read_case('public_read', case/'public.txt')
        read_case('private_absolute', root/'private/gold.txt')
        read_case('private_parent', case/'../private/gold.txt')
        read_case('private_symlink', case/'escape/gold.txt')
        read_case('other_case', root/'other-case/task.txt')
        read_case('control_home', root/'control-home/auth-canary.txt')
        read_case('ancestor_agents', '/data/duandh/eegfm-stage-a-20261028/AGENTS.md')
        read_case('host_proc_environment', '/proc/1/environ')
        for name,path in [('current_run_write',case/'result.txt'),('gold_write',root/'private/gold.txt'),('budget_write',root/'private/budget.json'),('public_write',case/'public.txt')]:
            try:
                with open(path,'a') as f: f.write('CANARY_WRITE')
                result[name] = {'allowed':True}
            except OSError as exc:
                result[name] = {'allowed':False,'errno':exc.errno,'error':type(exc).__name__}
        for name,host,port in [('direct_https','1.1.1.1',443),('local_proxy','127.0.0.1',PROXY_PORT),('local_ssh','127.0.0.1',22)]:
            try:
                sock=socket.socket(); sock.settimeout(1); sock.connect((host,port)); sock.close()
                result[name]={'allowed':True}
            except OSError as exc:
                result[name]={'allowed':False,'errno':exc.errno,'error':type(exc).__name__}
        result['proxy_environment_present'] = any('proxy' in k.lower() for k in os.environ)
        print(json.dumps(result,sort_keys=True))
    ''').replace('PROXY_PORT', proxy_port)
    (case / 'probe.py').write_text(program)
    env = dict(os.environ)
    env.update(CODEX_HOME=str(home), HOME=str(home), PATH=str(WORK / 'tools/bubblewrap/usr/bin') + ':/usr/bin:/bin')
    # The control process needs its proxy for later inference; the tool environment
    # is stripped by configuration. This offline sandbox probe also strips it.
    tool_env = {k: v for k, v in env.items() if 'proxy' not in k.lower()}
    native = BASE / 'bin/codex-x86_64-unknown-linux-musl'
    argv = [str(native), 'sandbox', '-C', str(case), '-p', 'actor', '-P', 'actor', '--', '/usr/bin/python3', str(case / 'probe.py')]
    start = time.monotonic()
    completed = subprocess.run(argv, env=tool_env, text=True, capture_output=True, timeout=25)
    report = {'version': 1, 'mode': 'offline_native_sandbox', 'argv': argv,
              'elapsed_seconds': round(time.monotonic()-start, 3), 'exit_code': completed.returncode,
              'stdout': completed.stdout, 'stderr': completed.stderr,
              'profile_sha256': hashlib.sha256(profile.encode()).hexdigest(),
              'model_control_traffic': 'not_yet_tested', 'hosted_tools': 'not_yet_tested'}
    (WORK / 'evidence/isolation-probe-v4.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())
