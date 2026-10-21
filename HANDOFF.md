# HANDOFF — 2026-10-21

This is the single current handoff. Old handoffs are in `archive/history/`.

## 1. Where the old experiments went

| old | new | status |
|---|---|---|
| `runs/dev_e1`, `runs/study_20261019` | `archive/experiments/synthetic_20261019/runs/` | read-only |
| `runs/flash_20261020_0058` | `archive/experiments/flash_20261020_0058/runs/flash_20261020_0058/` | read-only |
| `runs/flash_emotion_20261021` | `archive/experiments/emotion_20261021/runs/flash_emotion_20261021/` | read-only |
| `reports/*` (three studies) | `archive/experiments/*/reports/` | read-only |
| `artifacts/review_bundle*.zip` | `archive/experiments/*/artifacts/` | distinct bundles, kept |
| `PROGRESS/NEXT_ACTION/DECISIONS/FREEZE_MANIFEST` | `archive/history/` | read-only |
| old plans | `archive/plans/` | read-only |
| old study configs | `archive/experiments/*/configs/` | `study.json` path-rewritten; `study.original.json` byte-identical |

The archived payload was moved without rewriting. `archive/MIGRATION_MAP.json`
contains old→new paths and SHA-256 hashes; `archive/README.md` is the human index.
Three review bundles were checked and are distinct studies, not duplicates.

## 2. Current start

```text
README.md              current entry
HANDOFF.md             this file
ENVIRONMENT.md         canonical .venv and commands
src/eeg_scientist/     harness (ResearchRunner, evidence, ledger, manifests)
tests/                 offline suite
configs/               active models/materials/prompts/rules/rubric/version
studies/               new study workspaces (currently empty)
archive/plans/         historical design notes
archive/               read-only history
```

Old synthetic code (`runner.py`, `study.py`, `provider.py`) and legacy fixtures
remain under `src/`/`archive/` for compatibility; they are not the new entry.

## 3. How to start and view a study

```powershell
cd X:\projects\EEG-AI-Scientist
$py = ".\.venv\Scripts\python.exe"

& $py -m eeg_scientist.cli study init --id my_study
# edit studies\my_study\study.json and task.md
& $py -m eeg_scientist.cli study validate --study my_study
& $py -m eeg_scientist.cli study status  --study my_study
& $py -m eeg_scientist.cli study report  --study my_study
```

`study validate/status/report` never call a model. `study run` requires verified
backends and `--confirm-cost`; it has not been used in this round.

## 4. How to hand a proposal to 师哥 and import feedback

```powershell
& $py -m eeg_scientist.cli review export --study my_study
# send reviews\packets\<packet>\review_packet.md + proposals\ (NOT reviews\keys\)
& $py -m eeg_scientist.cli review import --study my_study --file .\feedback\reviewer_A.md
& $py -m eeg_scientist.cli review select --study my_study --reviews r_xxx --version v1
```

Each proposal is bound to `proposal_id`, `run_id`, and full body SHA-256; blind
labels (`B01`) are only per packet. Imported feedback preserves raw Markdown and
writes a separate `review_record.json`; human, ChatGPT-manual, and model-API
sources are distinguished. Conflicting reviews are kept side by side; only
explicitly selected reviews enter a feedback set. `review select` does not call a
model.

## 5. Model adapters and archive rules

- Claude uses the Anthropic Messages protocol; Gemini uses `generateContent`.
  Both map tool calls to the existing `ResearchRunner` loop and preserve raw
  usage/response. Offline tests use mocked HTTP transports only.
- Model IDs, real credentials, and prices are **not verified**; statuses remain
  `unverified`. A real connectivity call is required before changing them.
- Old `emotion-study run/evaluate/retry-failed` and `overnight-flash
  capability/diagnose/research`, and old `overnight/resume/episode/preflight`,
  refuse with a migration hint. `status`/report display can read the archive.
- Original answers, trajectories, ledgers, and review text were not edited.
- User's staged `.gitignore` and untracked files were not touched.

## 6. Verification

```powershell
& $py -m pytest -q
```

Expected: all offline tests pass (currently 77 after the new study/review and
adapter tests). No network/paid call is made. The review bundle and archive
hashes are listed in `archive/MIGRATION_MAP.json`.
