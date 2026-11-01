"""Explicit public exports and independently stored immutable experiment seals."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any, Iterable


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(name: str) -> Path:
    pure = PurePosixPath(name)
    if not name or '\\' in name or pure.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')) or ':' in name:
        raise ValueError(f'Invalid public relative path: {name!r}')
    return Path(*pure.parts)


def checked_file(root: Path, name: str) -> Path:
    relative = safe_relative(name)
    current = root.resolve(strict=True)
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError(f'Symlinks cannot be exported: {name}')
    current.resolve(strict=True).relative_to(root.resolve(strict=True))
    if not current.is_file():
        raise ValueError(f'Not a regular file: {name}')
    return current


def create_public_bundle(source: Path, destination: Path, allowlist: Iterable[str], *, task_id: str, tier: str) -> dict[str, Any]:
    """Copy only named regular files. Refuse ambiguous/hidden/control exports."""
    names = list(allowlist)
    if not names or len(names) != len(set(names)):
        raise ValueError('A nonempty unique allowlist is required')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    if tier not in {'real_eeg', 'intermediate_features', 'synthetic_mechanism'}:
        raise ValueError('Unknown resource tier')
    forbidden = {'auth.json', 'reference_private.json', 'agents.md', 'claude.md', 'config.toml', 'budget.json'}
    entries: list[dict[str, Any]] = []
    sources: dict[str, Path] = {}
    for name in sorted(names):
        relative = safe_relative(name)
        if any(part.startswith('.') for part in relative.parts) or relative.name.lower() in forbidden:
            raise ValueError(f'Private/control file cannot be public: {name}')
        if name == 'PUBLIC_MANIFEST.json':
            raise ValueError('Manifest is generated, not an input')
        file = checked_file(source, name)
        sources[name] = file
        entries.append({'path': name, 'bytes': file.stat().st_size, 'sha256': digest_file(file)})
    manifest = {'schema_version': 'public_bundle_v1', 'task_id': task_id, 'resource_tier': tier, 'files': entries}
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.public-export-', dir=destination.parent))
    try:
        for entry in entries:
            target = stage / safe_relative(entry['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sources[entry['path']], target)
            if digest_file(target) != entry['sha256']:
                raise ValueError('Source changed during export')
        (stage / 'PUBLIC_MANIFEST.json').write_bytes(canonical_bytes(manifest))
        os.rename(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return manifest


def verify_public_bundle(root: Path) -> dict[str, Any]:
    manifest_path = checked_file(root, 'PUBLIC_MANIFEST.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 'public_bundle_v1':
        raise ValueError('Unsupported public bundle version')
    expected = {'PUBLIC_MANIFEST.json'}
    for entry in manifest['files']:
        name = entry['path']
        if name in expected:
            raise ValueError('Duplicate manifest path')
        expected.add(name)
        file = checked_file(root, name)
        if file.stat().st_size != entry['bytes'] or digest_file(file) != entry['sha256']:
            raise ValueError(f'Changed bundle file: {name}')
    actual: set[str] = set()
    for file in root.rglob('*'):
        if file.is_symlink():
            raise ValueError('Symlink added to public bundle')
        if file.is_file():
            actual.add(file.relative_to(root).as_posix())
    if actual != expected:
        raise ValueError(f'Unmanifested or missing files: {sorted(actual ^ expected)}')
    return manifest


def freeze_experiment(public_root: Path, private_reference: Path, scoring_policy: dict[str, Any], budgets: dict[str, Any], routes: list[str], seal_path: Path) -> dict[str, Any]:
    """The trusted seal must live outside the Actor mount. Never silently replace it."""
    verify_public_bundle(public_root)
    if not routes or not scoring_policy or not budgets:
        raise ValueError('Freeze policy, budgets and fallback routes before development')
    try:
        seal_path.resolve().relative_to(public_root.resolve())
    except ValueError:
        pass
    else:
        raise ValueError('Reference seal must remain outside the public bundle')
    reference = json.loads(private_reference.read_text(encoding='utf-8'))
    if not reference:
        raise ValueError('Empty private reference')
    seal = {'schema_version': 'experiment_seal_v1', 'public_manifest_sha256': digest_file(public_root / 'PUBLIC_MANIFEST.json'),
            'reference_sha256': digest_file(private_reference), 'scoring_policy': scoring_policy,
            'budgets': budgets, 'fallback_routes': routes}
    seal['seal_sha256'] = hashlib.sha256(canonical_bytes(seal)).hexdigest()
    seal_path.parent.mkdir(parents=True, exist_ok=True)
    with seal_path.open('xb') as handle:
        handle.write(canonical_bytes(seal))
    return seal


def verify_seal(public_root: Path, private_reference: Path, seal_path: Path) -> dict[str, Any]:
    verify_public_bundle(public_root)
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    expected = seal.pop('seal_sha256')
    if hashlib.sha256(canonical_bytes(seal)).hexdigest() != expected:
        raise ValueError('Experiment seal changed')
    if digest_file(public_root / 'PUBLIC_MANIFEST.json') != seal['public_manifest_sha256'] or digest_file(private_reference) != seal['reference_sha256']:
        raise ValueError('Frozen public task or private reference changed')
    return {**seal, 'seal_sha256': expected}
