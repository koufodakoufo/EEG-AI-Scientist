"""Set this project's verified SSH proxy and the user's Codex IDE proxy.

Run on nccserver0 via ``python3 - PORT`` with this file on standard input.
Never reads authentication files or modifies source code or shell profiles.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import sys
import uuid

BASE = Path('/data/duandh/eegfm-stage-a-20261028')
MARKER = '# Managed by EEG-AI-Scientist Start-NccServer0Proxy.ps1\n'


def replace_proxy_exports(content: str, port: int) -> str:
    if not 1024 <= port <= 65535:
        raise ValueError('Invalid allocated proxy port')
    updated = content
    for name in ('HTTP_PROXY', 'HTTPS_PROXY'):
        pattern = rf'^export {name}=http://127\.0\.0\.1:\d+$'
        updated, count = re.subn(pattern, f'export {name}=http://127.0.0.1:{port}', updated, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f'Expected one managed {name} export; refusing to change other configuration')
    return updated


def dotenv_content(port: int) -> bytes:
    if not 1024 <= port <= 65535:
        raise ValueError('Invalid allocated proxy port')
    return (MARKER + f'HTTP_PROXY=http://127.0.0.1:{port}\n'
            f'HTTPS_PROXY=http://127.0.0.1:{port}\n'
            'NO_PROXY=127.0.0.1,localhost\n').encode('utf-8')


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    port = int(sys.argv[1])
    new_dotenv = dotenv_content(port)
    base = BASE.resolve(strict=True)
    if base != BASE or Path.home() != Path('/home/duandh'):
        raise ValueError('Unexpected workspace or user home; no changes made')
    environment = base / 'environment.sh'
    if environment.is_symlink() or environment.resolve().parent != base:
        raise ValueError('Unexpected environment path')
    old_environment = environment.read_bytes()
    new_environment = replace_proxy_exports(old_environment.decode('utf-8'), port).encode('utf-8')
    codex_dir = Path.home() / '.codex'
    if codex_dir.is_symlink() or (codex_dir.exists() and not codex_dir.is_dir()):
        raise ValueError('Unexpected Codex directory; no changes made')
    dotenv = codex_dir / '.env'
    if dotenv.is_symlink():
        raise ValueError('Refusing to replace a linked Codex environment file')
    old_dotenv = dotenv.read_bytes() if dotenv.exists() else None
    if old_dotenv is not None:
        expected = re.fullmatch(
            re.escape(MARKER) + r'HTTP_PROXY=http://127\.0\.0\.1:(\d+)\n'
            r'HTTPS_PROXY=http://127\.0\.0\.1:\1\nNO_PROXY=127\.0\.0\.1,localhost\n',
            old_dotenv.decode('utf-8'),
        )
        if expected is None:
            raise ValueError('Existing Codex .env is not managed by this helper; preserved without changes')
    backup_dir = base / 'network-backups'
    if backup_dir.is_symlink():
        raise ValueError('Unexpected backup path')
    backup_dir.mkdir(mode=0o700, exist_ok=True)
    backup = backup_dir / ('environment.' + uuid.uuid4().hex + '.sh')
    atomic_write(backup, old_environment, 0o600)
    codex_dir.mkdir(mode=0o700, exist_ok=True)
    mode = stat.S_IMODE(environment.stat().st_mode)
    try:
        atomic_write(environment, new_environment, mode)
        atomic_write(dotenv, new_dotenv, 0o600)
    except BaseException:
        atomic_write(environment, old_environment, mode)
        if old_dotenv is None:
            if dotenv.exists() and dotenv.read_bytes() == new_dotenv:
                dotenv.unlink()
        else:
            atomic_write(dotenv, old_dotenv, 0o600)
        raise
    print(f'Updated project CLI proxy and Codex IDE .env to loopback port {port}.')
    print('Restart pending CLI login; reload the VS Code window for its extension to read .env.')


if __name__ == '__main__':
    main()
