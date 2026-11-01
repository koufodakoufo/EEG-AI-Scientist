"""Export only tracked program source plus three owned, pinned upstream files."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

COMMIT = '0b24164977e82619de5ce0ab3d5e8f46f80d8a98'
UPSTREAM = 'b9e961003214326972c567eff390e75b0287e32a'
FILES = {
    'models/cbramod.py': 'caa7c5a0e4acd488a6f625b56f7b54dc4e7190d6b68ef5b76dff2cef86874a14',
    'models/criss_cross_transformer.py': '90e90b8c98ca7eb543c44e32afc29674d3f71cb090692ad9f82db3a43edf334c',
    'LICENSE': 'eb839b706e4d7219842e96d7dc33285844abc794292602deb3498be7b699537c',
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--owned-cbramod-source', type=Path, required=True,
                        help='Previously downloaded vendor directory owned by this project')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'source.tar'
    subprocess.run(['git', 'archive', '--format=tar', f'--output={archive}', COMMIT,
                    'framework/eegfm', 'framework/tasks/reve_isa/src/vendor/reve'],
                   cwd=repo, check=True)
    with tarfile.open(archive, 'a') as bundle:
        for relative, expected in FILES.items():
            payload = (args.owned_cbramod_source / relative).read_bytes()
            if hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError(f'Pinned upstream source mismatch: {relative}')
            info = tarfile.TarInfo('cbramod/' + relative)
            info.size, info.mode, info.mtime = len(payload), 0o600, 0
            bundle.addfile(info, io.BytesIO(payload))
    file_hashes: dict[str, str] = {}
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            if 'controls' in Path(member.name).parts or member.issym() or member.islnk():
                raise ValueError(f'Forbidden source member: {member.name}')
            if member.isfile():
                stream = bundle.extractfile(member)
                assert stream is not None
                file_hashes[member.name] = hashlib.sha256(stream.read()).hexdigest()
    manifest = {'source_commit': COMMIT, 'kind': 'selected_tracked_source_archive',
                'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'archive_bytes': archive.stat().st_size, 'files': file_hashes,
                'cbramod_upstream_commit': UPSTREAM,
                'cbramod_source': 'previously downloaded own project vendor, verified pinned hashes',
                'excluded': ['credentials', 'controls', 'datasets', 'weights', 'runtime state', 'archive']}
    (output / 'source-provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in manifest.items() if key != 'files'}))


if __name__ == '__main__':
    main()
