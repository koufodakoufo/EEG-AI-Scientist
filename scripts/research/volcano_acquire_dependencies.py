"""Bounded parallel official PyPI wheel acquisition, checked against PyPI SHA256."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

PINS = {'filelock':'3.18.0', 'typing_extensions':'4.14.0', 'networkx':'3.4.2',
        'Jinja2':'3.1.6', 'fsspec':'2025.5.1', 'sympy':'1.13.1', 'setuptools':'80.9.0',
        'mpmath':'1.3.0', 'MarkupSafe':'3.0.2', 'numpy':'2.2.6', 'einops':'0.8.1',
        'transformers':'4.56.2', 'huggingface-hub':'0.34.4', 'packaging':'25.0',
        'PyYAML':'6.0.2', 'regex':'2025.9.1', 'requests':'2.32.5', 'tokenizers':'0.22.0',
        'safetensors':'0.6.2', 'tqdm':'4.67.1', 'hf-xet':'1.1.9',
        'charset-normalizer':'3.4.3', 'idna':'3.10', 'urllib3':'2.5.0', 'certifi':'2025.8.3'}


def main() -> None:
    from pip._vendor.packaging.tags import sys_tags
    from pip._vendor.packaging.utils import parse_wheel_filename
    root = Path('/home/duandh/projects/EEG-AI-Scientist-20261030')
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--verify-plan', action='store_true')
    args = parser.parse_args()
    assert root.resolve() == root and root.stat().st_uid == os.getuid() == 1027
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
    destination = root / 'downloads' / 'dependencies'
    destination.mkdir(mode=0o700, exist_ok=True)
    if args.verify_plan:
        manifest = json.loads((root / 'evidence/dependency-plan.json').read_text())
        assert len(manifest) == len(PINS)
        assert {entry['package']: entry['version'] for entry in manifest} == PINS
        for entry in manifest:
            assert Path(entry['file']).name == entry['file']
            path = destination / entry['file']
            assert path.stat().st_size == entry['bytes']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        (root / 'evidence/dependency-sources.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print(f'All {len(manifest)} frozen PyPI wheels verified offline')
        return
    ordered_tags = list(sys_tags())
    rank = {tag: index for index, tag in enumerate(ordered_tags)}
    started = time.monotonic()

    def fetch(item: tuple[str, str]) -> dict[str, object]:
        package, version = item
        metadata_url = f'https://pypi.org/pypi/{package}/{version}/json'
        with urllib.request.urlopen(metadata_url, timeout=30) as response:
            metadata = json.load(response)
        candidates = []
        for entry in metadata['urls']:
            if entry['packagetype'] != 'bdist_wheel':
                continue
            tags = parse_wheel_filename(entry['filename'])[3]
            compatible = tags & rank.keys()
            if compatible:
                candidates.append((min(rank[tag] for tag in compatible), entry))
        entry = min(candidates, key=lambda pair: pair[0])[1]
        path = destination / entry['filename']
        expected = entry['digests']['sha256']
        record = {'package':package, 'version':version, 'file':path.name, 'url':entry['url'],
                  'sha256':expected, 'bytes':entry['size'], 'metadata_url':metadata_url}
        if args.plan_only:
            return record
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            with urllib.request.urlopen(entry['url'], timeout=45) as response, path.open('wb') as output:
                for block in iter(lambda: response.read(65536), b''):
                    if time.monotonic() - started > 300:
                        raise TimeoutError('Five-minute acquisition budget reached')
                    output.write(block)
        assert path.stat().st_size == entry['size']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        print(f'verified {package}=={version}', flush=True)
        return record

    with ThreadPoolExecutor(max_workers=8) as executor:
        manifest = list(executor.map(fetch, PINS.items()))
    filename = 'dependency-plan.json' if args.plan_only else 'dependency-sources.json'
    (root / 'evidence' / filename).write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
