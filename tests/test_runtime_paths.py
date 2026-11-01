"""Runtime configuration and source-freeze relocation regressions."""
from __future__ import annotations
import pytest
from eegfm.evaluation import calibration


def test_calibration_freeze_tracks_installed_source() -> None:
    hashes = calibration.core_hashes()
    assert set(hashes) == {"arguments.py", "evaluation/claims.py", "evaluation/evidence.py", "agent/actor.py", "evaluation/bundle.py", "improvement/trace.py", "agent/budget.py"}
    assert all(len(value) == 64 for value in hashes.values())


def test_calibration_runtime_requires_explicit_paths() -> None:
    assert hasattr(calibration, "validate_runtime"), "Native runtime must be explicitly validated"
    with pytest.raises(ValueError):
        calibration.validate_runtime({})
    with pytest.raises(ValueError):
        calibration.validate_runtime({"workspace": "relative/path"})


def test_tione_requires_configured_helper_before_loading() -> None:
    from eegfm.agent.jobs import TioneBackend
    with pytest.raises(ValueError, match="helper_path"):
        TioneBackend({"backend": "tione"}).helper()
