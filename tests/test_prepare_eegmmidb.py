"""Safety and scientific-input checks for the independent EEGMMIDB adapter."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest


def adapter() -> ModuleType:
    from eegfm.eeg import eegmmidb
    return eegmmidb


def test_subject_boundary_prevents_cross_split_rows() -> None:
    module = adapter()
    assert [module.split_for_subject(n) for n in (1, 24, 25, 30, 31, 36)] == [
        'train', 'train', 'validation', 'validation', 'test', 'test']
    for invalid in (0, 37, -1):
        with pytest.raises(ValueError):
            module.split_for_subject(invalid)


def test_channel_selection_is_measured_and_refuses_missing_channel() -> None:
    module = adapter()
    source = ['Fp1.', 'Fp2.', 'F3..', 'F4..', 'F7..', 'F8..', 'T7..', 'T8..',
              'C3..', 'C4..', 'P7..', 'P8..', 'P3..', 'P4..', 'O1..', 'O2..',
              'Fz..', 'Cz..', 'Pz..', 'FCz.', 'Oz..']
    assert module.select_channels(source) == source[:20]
    with pytest.raises(ValueError, match='missing'):
        module.select_channels(source[:19])
    with pytest.raises(ValueError, match='duplicate'):
        module.select_channels(source + ['fp1'])


def test_locked_metadata_rejects_changes_and_preserves_existing_bytes(tmp_path: Path) -> None:
    module = adapter()
    target = tmp_path / 'lock.json'
    module.write_once_json(target, {'split': 'train'})
    before = target.read_bytes()
    module.write_once_json(target, {'split': 'train'})
    with pytest.raises(FileExistsError):
        module.write_once_json(target, {'split': 'test'})
    assert target.read_bytes() == before


def test_corrupt_original_is_never_replaced(tmp_path: Path) -> None:
    module = adapter()
    original = tmp_path / 'source.edf'
    original.write_bytes(b'original bytes')
    with pytest.raises(ValueError, match='hash'):
        module.verify_file(original, '0' * 64)
    assert original.read_bytes() == b'original bytes'


def test_owned_root_rejects_unmarked_nonempty_directory(tmp_path: Path) -> None:
    module = adapter()
    root = tmp_path / 'existing'
    root.mkdir()
    (root / 'other-owner').write_text('preserve', encoding='utf-8')
    with pytest.raises(ValueError, match='ownership'):
        module.initialize_root(root, tmp_path)
    assert (root / 'other-owner').read_text(encoding='utf-8') == 'preserve'
    with pytest.raises(ValueError, match='child'):
        module.initialize_root(tmp_path, tmp_path)


def test_windows_preserve_units_and_nonoverlap_without_padding() -> None:
    module = adapter()
    signal = np.full((20, 12000), 100.0)
    signal[:, 1000:2000] = 200.0
    result = module.to_windows(signal)
    assert result.shape == (12, 20, 5, 200)
    assert result.dtype == np.float32
    assert np.all(result[0] == 1.0)
    assert np.all(result[1] == 2.0)
    with pytest.raises(ValueError, match='60'):
        module.to_windows(signal[:, :-1])
