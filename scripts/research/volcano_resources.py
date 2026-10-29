"""Standard-library-only, read-only resource identity and safetensors schema."""
from __future__ import annotations
import json
from pathlib import Path
import struct
from typing import Any
from volcano_probe import RESOURCES, sha256


def main() -> None:
    report: dict[str, Any] = {'access': 'read_only_in_place', 'copies_created': 0, 'resources': {}}
    for name, (filename, expected) in RESOURCES.items():
        path = Path(filename)
        stat = path.stat()
        observed = sha256(path)
        assert observed == expected
        entry: dict[str, Any] = {'path': filename, 'sha256': observed, 'bytes': stat.st_size,
                                 'uid': stat.st_uid, 'inode': stat.st_ino,
                                 'mtime_ns': stat.st_mtime_ns}
        if path.suffix == '.safetensors':
            with path.open('rb') as stream:
                header_bytes = struct.unpack('<Q', stream.read(8))[0]
                assert 0 < header_bytes < 8 * 1024 * 1024
                header = json.loads(stream.read(header_bytes))
            entry['schema'] = {key: {'shape': value['shape'], 'dtype': value['dtype']}
                               for key, value in header.items() if key != '__metadata__'}
        assert path.stat().st_mtime_ns == stat.st_mtime_ns
        report['resources'][name] = entry
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
