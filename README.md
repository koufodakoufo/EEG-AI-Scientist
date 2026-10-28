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
- **Command reference:** [`docs/COMMAND_REFERENCE.md`](docs/COMMAND_REFERENCE.md)
- **2026-10-22 verification:** [`docs/VERIFICATION_20261022.md`](docs/VERIFICATION_20261022.md)
- **Old Meta-rule correction:** [`docs/CORRECTION_20261022_META_INJECTION.md`](docs/CORRECTION_20261022_META_INJECTION.md)
- **Archived experiments:** [`archive/README.md`](archive/README.md) — read-only
  history with old-to-new path map and hashes.
- **New studies:** [`studies/README.md`](studies/README.md).

## What is active

```text
src/eeg_scientist/    active harness modules + legacy/ (old code, shims)
tests/                offline tests
configs/              active models, materials, prompts, rules, rubric, version policy
studies/              new studies (empty until you create one)
docs/                 architecture, command reference, verification, corrections
archive/              completed experiments and old plans/handoffs (read-only)
```

No paid model call was made during this round. Claude and Gemini adapters now
have offline two-request protocol tests (native thinking/thought-signature replay,
tool-result merging, unique IDs, truncation, Gemini thinking usage), but their
model IDs, credentials, thinking parameters, and real connectivity remain
`unverified`.

## What a request actually contains

- `task.md` is the authoritative task body sent to the model. `question` in
  `study.json` is metadata only.
- Any arm rule is embedded as a labelled block in the system message.
- The first-turn system prompt, task, rule, material manifest, and full tool
  definitions are frozen in `runs/<arm>/repeat_XX/input_snapshot.json`; the
  rule text is also shown verbatim in `scientist_input.md`.
- A configured but missing/empty rule file is a hard error. Changing `task.md`
  or the rule after a run is frozen is refused on resume.
- `study preflight` shows per-arm model, task/material/rule hashes, prompt hashes,
  and the actual prompt diff. Distinct rule files with identical text are
  rejected as a rule contrast.

## Commands

```powershell
cd X:\projects\EEG-AI-Scientist
$py = ".\.venv\Scripts\python.exe"

& $py -m eeg_scientist.cli --help
& $py -m eeg_scientist.cli study init --id my_study
& $py -m eeg_scientist.cli study init --id old_material --template emotion_20261021
& $py -m eeg_scientist.cli study validate --study my_study
& $py -m eeg_scientist.cli study preflight --study my_study
& $py -m eeg_scientist.cli study status --study my_study
& $py -m eeg_scientist.cli study report --study my_study
& $py -m eeg_scientist.cli review export --study my_study
& $py -m eeg_scientist.cli review import --study my_study --file .\forms\B01.md
& $py -m eeg_scientist.cli review select --study my_study --reviews r_xxx --version v1
```

`study`/`review` resolve the project root from any subdirectory (for example
`group-meeting/`); they do not use the shell's current directory as the root.

`study run` is the only paid entry and requires both configured verified backends
and `--confirm-cost`:

```powershell
& $py -m eeg_scientist.cli study run --study my_study --confirm-cost
```

Old completed experiments are read-only. Old paid commands print a migration
hint; old `status`/report display remains available through the archived configs.

## Current limits

- No active real EEG dataset and no new paid run in this round.
- Claude/Gemini real-network verification is still pending; offline contracts use
  mocked transports only.
- Thinking configuration differs by model family; the adapter supports Claude
  `budget_tokens` and Gemini `thinkingBudget`/`thinkingLevel`, but the exact
  model-specific setting must be checked before a real call.
- Old archived review binding and directory consolidation are the separate B
  task; this round only supports new-study review roundtrips.
- Old synthetic/legacy code remains in `src/` for backward compatibility; it is
  not the recommended entry for new work.
