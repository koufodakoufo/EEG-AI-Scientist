"""Stage selected public wheels locally when the server's CDN route is slow."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import time


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--packages', nargs='+', required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    entries = [entry for entry in json.loads(args.manifest.read_text(encoding='utf-8-sig'))
               if entry['package'] in args.packages]
    assert len(entries) == len(set(args.packages))
    assert sum(entry['bytes'] for entry in entries) < 128 * 1024**2
    started = time.monotonic()

    def fetch(entry: dict[str, object]) -> None:
        name = str(entry['file'])
        assert Path(name).name == name and name.endswith('.whl')
        path = args.output / name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']:
            return
        assert str(entry['url']).startswith('https://files.pythonhosted.org/')
        if time.monotonic() - started > 540:
            raise TimeoutError('Nine-minute local staging limit')
        subprocess.run(['curl', '--fail', '--location', '--max-time', '180',
                        '--silent', '--show-error', '--continue-at', '-',
                        '--output', str(path), str(entry['url'])], check=True, timeout=190)
        assert path.stat().st_size == entry['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        print(f'verified {name}', flush=True)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(fetch, entries))


if __name__ == '__main__':
    main()
