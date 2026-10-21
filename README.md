# EEG-AI-Scientist

Current entry point for a small, traceable EEG research harness. It produces
literature-based research proposals, not real EEG findings, unless a study
explicitly says otherwise.

## Start here

- **Current handoff:** [`HANDOFF.md`](HANDOFF.md)
- **Environment:** [`ENVIRONMENT.md`](ENVIRONMENT.md) — canonical interpreter is
  `.venv\Scripts\python.exe` (Python 3.12.4); bare `python` on PATH is not this
  project's environment.
- **Architecture:** [`docs/architecture.md`](docs/architecture.md)
- **Archived experiments:** [`archive/README.md`](archive/README.md) — read-only
  history with old-to-new path map and hashes.
- **New studies:** [`studies/README.md`](studies/README.md).

## What is active

```text
src/eeg_scientist/    active harness modules
tests/                offline tests
configs/              active models, materials, prompts, rules, rubric, version policy
studies/              new studies (empty until you create one)
docs/                 architecture and design notes
archive/              completed experiments and old plans/handoffs (read-only)
```

No paid model call was made during the archive/refactor round. Claude and Gemini
adapters exist, but their model IDs/credentials have not been verified; their
backend entries remain `unverified` until a real paid connectivity check.

## Commands

```powershell
cd X:\projects\EEG-AI-Scientist
$py = ".\.venv\Scripts\python.exe"

& $py -m eeg_scientist.cli --help
& $py -m eeg_scientist.cli study init --id my_study
& $py -m eeg_scientist.cli study validate --study my_study
& $py -m eeg_scientist.cli study status --study my_study
& $py -m eeg_scientist.cli study report --study my_study
& $py -m eeg_scientist.cli review export --study my_study
& $py -m eeg_scientist.cli review import --study my_study --file .\feedback\reviewer_A.md
& $py -m eeg_scientist.cli review select --study my_study --reviews r_xxx --version v1
```

`study run` is the only paid entry and requires both configured verified backends
and `--confirm-cost`:

```powershell
& $py -m eeg_scientist.cli study run --study my_study --confirm-cost
```

Old completed experiments are read-only. Old paid commands print a migration
hint; old `status`/report display remains available through the archived configs.

## Current limits

- No active real EEG dataset and no new paid run in this round.
- Claude/Gemini real-network verification is still pending; offline contract tests
  use mocked transports only.
- Old synthetic/legacy code remains in `src/` for backward compatibility; it is
  not the recommended entry for new work.
