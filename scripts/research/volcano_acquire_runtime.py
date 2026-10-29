"""Acquire a pinned official standalone Linux Python into an owned directory.

Eight bounded range requests avoid a slow single-stream release download.
The signed redirect is kept in memory; only the stable public URL is recorded.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

URL = ('https://github.com/astral-sh/python-build-standalone/releases/download/20261026/'
       'cpython-3.12.16%2B20261026-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz')
SHA256 = 'ce4f6d0a6cfdb3bed6e44c2f9affd85943c76a42e25ad3a259002f31d6fb8a20'
SIZE = 34505639


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / 'python.tar.gz'
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256:
        print('Runtime archive already verified')
        return
    # curl follows the official GitHub redirect, not a mirror.
    resolved = subprocess.run(['curl', '--fail', '--location', '--head', '--max-time', '30',
                               '--silent', '--show-error', '--output',
                               'NUL' if __import__('os').name == 'nt' else '/dev/null',
                               '--write-out', '%{url_effective}', URL],
                              check=True, capture_output=True, text=True).stdout.strip()
    started = time.monotonic()

    def download(part: int) -> Path:
        start, end = SIZE * part // 8, SIZE * (part + 1) // 8 - 1
        path = args.output / f'python.tar.gz.part{part}'
        have = path.stat().st_size if path.exists() else 0
        if have == end - start + 1:
            return path
        if have > end - start + 1:
            raise ValueError('Unexpected partial size')
        request = urllib.request.Request(resolved, headers={'Range': f'bytes={start+have}-{end}'})
        with urllib.request.urlopen(request, timeout=45) as response, path.open('ab') as stream:
            if response.status != 206 or response.headers['Content-Range'] != f'bytes {start+have}-{end}/{SIZE}':
                raise RuntimeError('Official CDN range mismatch')
            while have < end - start + 1 and time.monotonic() - started < 540:
                block = response.read(min(65536, end - start + 1 - have))
                if not block:
                    break
                stream.write(block)
                have += len(block)
        if have != end - start + 1:
            raise TimeoutError('Download incomplete; partial retained')
        return path

    with ThreadPoolExecutor(max_workers=8) as executor:
        parts = list(executor.map(download, range(8)))
    assembled = args.output / 'python.tar.gz.verified'
    digest = hashlib.sha256()
    with assembled.open('wb') as output:
        for part in parts:
            with part.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    output.write(block)
                    digest.update(block)
    if digest.hexdigest() != SHA256:
        raise ValueError('Official GitHub release digest mismatch')
    assembled.replace(target)
    manifest = {'url': URL, 'sha256': SHA256, 'bytes': SIZE,
                'digest_source': 'GitHub release asset API 20261026',
                'elapsed_seconds': time.monotonic() - started}
    (args.output / 'python-source.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
