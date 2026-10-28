"""Project root discovery for commands started from any subdirectory.

The CLI used to treat ``Path(".")`` as the project root.  Running from
``group-meeting/`` then silently looked for ``group-meeting/studies/...``.
This module finds the real root by locating the directory that contains both
``pyproject.toml`` and ``src/eeg_scientist``.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT_ENV = "EEG_SCIENTIST_ROOT"


def _is_project_root(candidate: Path) -> bool:
    return (candidate / "pyproject.toml").is_file() and (candidate / "src" / "eeg_scientist").is_dir()


def project_root(start: Path | None = None) -> Path:
    """Return the absolute project root.

    Resolution order:
    1. ``EEG_SCIENTIST_ROOT`` if set (explicit override);
    2. ``start`` (default: current working directory) and its parents;
    3. the installed package location and its parents.

    Falling back to the current directory is deliberate: it keeps error
    messages local instead of guessing an unrelated directory.
    """

    override = os.environ.get(ROOT_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    bases: list[Path] = []
    if start is not None:
        bases.append(Path(start))
    else:
        bases.append(Path.cwd())
    bases.append(Path(__file__).resolve())
    for base in bases:
        candidate = base if base.is_dir() else base.parent
        for parent in (candidate, *candidate.parents):
            if _is_project_root(parent):
                return parent
    return Path.cwd().resolve()
