"""Manifest producers preserve Linux component ordering on every host."""
import builtins
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from eegfm.agent import controller
from eegfm.evaluation import replay, worker


@pytest.mark.parametrize("names", [
    ("README.md", "a.py"),
    ("a.py", "a/b.py"),
])
@pytest.mark.parametrize("producer", ["worker", "controller", "replay"])
def test_manifest_identity_preserves_linux_component_order(tmp_path, monkeypatch, names, producer):
    source = tmp_path / "source"
    source.mkdir()
    for name in names:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(("fixture:" + name + "\n").encode("utf-8"))

    # Independent reference: Linux Path compares case-sensitive components,
    # including a/b.py before a.py. Full POSIX-string sorting is different.
    expected_names = [str(path) for path in builtins.sorted(map(PurePosixPath, names))]
    entries = [{"path": name, "bytes": len((source / name).read_bytes()),
                "sha256": hashlib.sha256((source / name).read_bytes()).hexdigest()}
               for name in expected_names]
    serialized = (json.dumps(entries, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    expected_digest = hashlib.sha256(serialized).hexdigest()

    # Reproduce Windows pathlib comparison even when this test runs on Linux.
    # An explicit production key is honored normally; absent keys case-fold.
    def windows_path_sorted(values, *, key=None, reverse=False):
        return builtins.sorted(values, key=key if key is not None else
                               lambda path: PureWindowsPath(path.as_posix()), reverse=reverse)

    module = {"worker": worker, "controller": controller, "replay": replay}[producer]
    monkeypatch.setattr(module, "sorted", windows_path_sorted, raising=False)
    if producer == "worker":
        actual_entries = worker._tree(source)
        actual_digest = worker.candidate_digest(source)
    elif producer == "controller":
        actual_entries, actual_digest = controller._manifest(source)
    else:
        destination = tmp_path / "frozen"
        manifest = replay.freeze_submission(source, destination)
        expected_manifest = {"schema_version": "submission_freeze_v1", "files": entries,
                             "bytes": sum(entry["bytes"] for entry in entries)}
        assert manifest == expected_manifest
        assert json.loads((tmp_path / "frozen-manifest.json").read_bytes()) == expected_manifest
        assert all((destination / name).read_bytes() == (source / name).read_bytes() for name in names)
        return
    assert [entry["path"] for entry in actual_entries] == expected_names
    assert actual_digest == expected_digest
