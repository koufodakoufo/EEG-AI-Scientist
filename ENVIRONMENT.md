# Project environment — canonical interpreter

Canonical interpreter: `.venv\Scripts\python.exe` (project-local uv environment).

- Base Python: 3.12.4 (CPython; uv venv home `C:\Users\14090\anaconda3`).
- Dependencies: resolved from `pyproject.toml` + `uv.lock` by `uv sync --extra dev`.
- Do not use the Windows `python` on PATH for this project: on this machine it is
  `C:\Python314\python.exe` and has none of the project dependencies.
- VS Code is pointed at `.venv\Scripts\python.exe` by `.vscode/settings.json`.
- Terminal/test commands should use the venv explicitly (below), not bare `python`.

## Verified commands

```powershell
cd X:\projects\EEG-AI-Scientist

# one-time environment sync
uv sync --extra dev

# versions actually used
.\.venv\Scripts\python.exe -c "import sys,numpy,sklearn,pydantic,httpx,pytest; print(sys.executable); print(numpy.__version__, sklearn.__version__, pydantic.__version__, httpx.__version__, pytest.__version__)"

# tests
.\.venv\Scripts\python.exe -m pytest -q

# type check of the requested module (mypy 1.10 is the external base-env tool;
# package-wide mypy still has legacy findings outside this module)
C:\Users\14090\anaconda3\python.exe -m mypy src\eeg_scientist\scientist.py

# CLI
.\.venv\Scripts\python.exe -m eeg_scientist.cli emotion-study status
```

## Declared versus installed

`pyproject.toml` declares `numpy>=2.0`, `scikit-learn>=1.5`, `pydantic>=2.9`,
`httpx>=0.27`, and dev extras `pytest>=8.3`. The venv satisfies these. The base
Anaconda interpreter does **not** (it has older versions), which is why it is
not the project environment.

`mypy` is not a runtime dependency and was not added to `pyproject.toml`
because its download timed out during environment setup. The type check in this
handoff used the already-installed `mypy 1.10.0` from the base Anaconda
environment; the project runtime and tests use the venv. If a later environment
has network access, add `mypy` as an explicit dev tool rather than relying on
the base environment.

## Scope

This unifies the project environment; it does not change the Windows system
Python, the user's global shell profile, or the base Anaconda installation.
