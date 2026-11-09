"""Trusted reservations and Linux process limits; no reliance on Actor promises."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator, Mapping, Sequence


class BudgetExceeded(RuntimeError):
    """A launch is rejected before model or compute work starts."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked_state(path: Path) -> Iterator[dict[str, Any]]:
    lock_path = path.with_suffix(path.suffix + '.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            if handle.tell() == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            state = json.loads(path.read_text(encoding='utf-8-sig'))
            yield state
            write_atomic(path, state)
        finally:
            if os.name == 'nt':
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def reserve_call(path: Path, call_id: str, role: str, timeout_seconds: int) -> dict[str, Any]:
    with locked_state(path) as state:
        calls = state.setdefault('calls', [])
        if any(call['id'] == call_id for call in calls):
            raise BudgetExceeded('Call ID already consumed; resume does not launch again')
        if len(calls) >= state['extra_model_calls_max']:
            raise BudgetExceeded('Model call budget exhausted')
        active = sum(call['status'] in {'reserved', 'running'} for call in calls)
        if active >= state['max_parallel_model_workers']:
            raise BudgetExceeded('Concurrent model worker limit')
        deadline = datetime.fromisoformat(state['stop_new_research_at'])
        if datetime.now(timezone.utc) >= deadline:
            raise BudgetExceeded('No new research after cutoff')
        maximum = state['preflight_timeout_seconds'] if role == 'preflight' else state['per_call_timeout_seconds']
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0 or timeout_seconds > maximum:
            raise BudgetExceeded('Invalid call timeout')
        if datetime.now(timezone.utc).timestamp() + timeout_seconds > datetime.fromisoformat(state['deadline_at']).timestamp():
            raise BudgetExceeded('Call could overrun hard deadline')
        record = {'id': call_id, 'role': role, 'status': 'reserved', 'reserved_at': utc_now(),
                  'timeout_seconds': timeout_seconds, 'cost_usd': 'unknown'}
        calls.append(record)
        state['extra_model_calls_reserved'] = len(calls)
        return dict(record)


def mark_call(path: Path, call_id: str, status: str, **details: Any) -> None:
    transitions = {'reserved': {'running', 'blocked', 'cancelled'}, 'running': {'completed', 'failed', 'timed_out', 'cancelled'}}
    with locked_state(path) as state:
        record = next((item for item in state['calls'] if item['id'] == call_id), None)
        if record is None or status not in transitions.get(record['status'], set()):
            raise BudgetExceeded('Invalid call state transition')
        if any(key in details for key in ('id', 'status', 'role', 'reserved_at', 'timeout_seconds')):
            raise ValueError('Cannot replace reservation identity')
        record.update(details, status=status, updated_at=utc_now())


def _group_rss_bytes(pgid: int) -> int:
    total = 0
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            stat = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(stat[2]) == pgid:
                total += int(stat[21]) * os.sysconf('SC_PAGE_SIZE')
        except (OSError, ValueError, IndexError):
            continue
    return total


def tree_bytes(root: Path, *, stop_above: int = 10 * 1024**3) -> int:
    """Count only regular files below an owned scope, without following links."""
    total = 0
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories if not Path(current, name).is_symlink()]
        for name in files:
            path = Path(current, name)
            try:
                if not path.is_symlink(): total += path.stat().st_size
            except FileNotFoundError:
                continue
            if total > stop_above: return total
    return total


def run_bounded(argv: Sequence[str], *, cwd: Path, output_dir: Path, timeout_seconds: float,
                env: Mapping[str, str] | None = None, memory_limit_bytes: int = 12 * 1024**3,
                threads: int = 4, stdout_limit_bytes: int = 64 * 1024**2,
                storage_scope: Path | None = None, storage_limit_bytes: int = 10 * 1024**3,
                minimum_free_bytes: int = 20 * 1024**3, limit_address_space: bool = True,
                stdin_path: Path | None = None) -> dict[str, Any]:
    """Linux only: affinity, address-space cap, aggregate group RSS, wall clock.

    A subreaper tracks and terminates owned descendants even across new process
    groups. RSS is sampled; this is not a kernel cgroup memory ceiling. V8 control
    processes require limit_address_space=False because virtual reservations are
    much larger than resident RAM. CPU affinity and RSS limits still apply.
    """
    if sys.platform != 'linux':
        raise RuntimeError('Bounded compute launcher requires Linux; fail closed')
    if not argv or not 0 < timeout_seconds <= 1800 or not 0 < threads <= 4 or not 0 < memory_limit_bytes <= 12 * 1024**3:
        raise ValueError('Requested resources exceed run limits')
    if output_dir.exists():
        raise FileExistsError('Run evidence directory already exists; no silent retry')
    if not 0 < storage_limit_bytes <= 10 * 1024**3:
        raise ValueError('Storage cap exceeds run allocation')
    if shutil.disk_usage(cwd).free < minimum_free_bytes:
        raise BudgetExceeded('Working disk below free-space safety floor')
    scope = (storage_scope or cwd).resolve(strict=True)
    if tree_bytes(scope, stop_above=storage_limit_bytes) > storage_limit_bytes:
        raise BudgetExceeded('Owned storage scope already exceeds cap')
    output_dir.mkdir(parents=True, mode=0o700)
    import resource
    from eegfm.agent.processes import OwnedProcessTree
    from eegfm.agent.processes import affinity_lock
    available = sorted(os.sched_getaffinity(0))[:threads]
    lock_affinity=affinity_lock()
    def limit_child() -> None:
        # An inherited lock denies even no-op affinity writes.
        if os.sched_getaffinity(0) != set(available):
            os.sched_setaffinity(0, available)
        lock_affinity()
        if limit_address_space:
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024**2, 512 * 1024**2))
    child_env = dict(os.environ if env is None else env)
    child_env.update({key: str(threads) for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')})
    start = time.monotonic()
    record: dict[str, Any] = {'schema_version': 'bounded_run_v1', 'argv': list(argv), 'cwd': str(cwd), 'started_at': utc_now(),
                              'status': 'starting', 'timeout_seconds': timeout_seconds, 'memory_limit_bytes': memory_limit_bytes,
                              'affinity_cpus': available, 'threads': threads, 'cost_usd': 'unknown', 'peak_group_rss_bytes': 0,
                              'storage_scope':str(scope),'storage_limit_bytes':storage_limit_bytes,
                              'storage_poll_seconds':1.0,'per_file_limit_bytes':512*1024**2,
                              'address_space_limited':limit_address_space,'rss_poll_seconds':0.1,
                              'peak_tree_rss_bytes':0,'affinity_widening':'denied_by_inherited_seccomp'}
    write_atomic(output_dir / 'status.json', record)
    process: subprocess.Popen[bytes] | None = None
    tree = OwnedProcessTree()
    try:
        with (output_dir / 'stdout.jsonl').open('wb') as stdout, (output_dir / 'stderr.log').open('wb') as stderr, (stdin_path or Path(os.devnull)).open('rb') as input_stream:
            process = subprocess.Popen(list(argv), cwd=cwd, env=child_env, stdout=stdout, stderr=stderr,
                                       stdin=input_stream, start_new_session=True, preexec_fn=limit_child)
            tree.attach(process.pid)
            record.update(status='running', pid=process.pid)
            write_atomic(output_dir / 'status.json', record)
            next_storage_poll = start
            while process.poll() is None:
                rss = tree.rss_bytes()
                record['peak_group_rss_bytes'] = max(record['peak_group_rss_bytes'], rss)
                record['peak_tree_rss_bytes'] = max(record['peak_tree_rss_bytes'], rss)
                if time.monotonic() - start >= timeout_seconds:
                    record['status'] = 'timed_out'; break
                if rss > memory_limit_bytes:
                    record['status'] = 'memory_exceeded'; break
                if stdout.tell() + stderr.tell() > stdout_limit_bytes:
                    record['status'] = 'output_exceeded'; break
                if time.monotonic() >= next_storage_poll:
                    used = tree_bytes(scope, stop_above=storage_limit_bytes)
                    record['last_scope_bytes'] = used
                    if used > storage_limit_bytes:
                        record['status'] = 'storage_exceeded'; break
                    if shutil.disk_usage(cwd).free < minimum_free_bytes:
                        record['status'] = 'disk_free_floor'; break
                    next_storage_poll = time.monotonic() + 1.0
                time.sleep(0.1)
            if record['status']=='running' and process.poll() is not None:
                record['status'] = 'completed' if process.returncode == 0 else 'failed'
    except BaseException as exc:
        record.update(status='launcher_failed', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        if process is not None:
            record['process_cleanup']=tree.terminate()
            process.wait(timeout=5)
            record['exit_code'] = process.returncode
        else:
            record['process_cleanup']=tree.terminate()
        record.update(finished_at=utc_now(), elapsed_seconds=round(time.monotonic() - start, 3))
        write_atomic(output_dir / 'status.json', record)
    return record
