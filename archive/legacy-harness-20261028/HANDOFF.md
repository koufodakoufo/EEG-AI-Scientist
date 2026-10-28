# HANDOFF — 2026-10-22

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
docs/                  architecture, command reference, verification, corrections
src/eeg_scientist/     harness (ResearchRunner, evidence, ledger, manifests)
tests/                 offline suite (114 tests as of 2026-10-22)
configs/               active models/materials/prompts/rules/rubric/version
studies/               new study workspaces (currently empty)
archive/plans/         historical design notes
archive/               read-only history
```

Old synthetic code now lives in `src/eeg_scientist/legacy/`; the root module
names are compatibility shims. New code must use `study`/`review`.

## 3. What a new run sends and freezes

- `studies/<id>/task.md` is the authoritative task body; `question` is metadata.
- `system_prompt.md` (or an explicit template prompt) is the base system message.
- An arm's `rule_path` is read, snapshotted under `runs/<arm>/repeat_XX/rules/`,
  and embedded verbatim in a labelled system-message block.
- `input_snapshot.json` records the exact system/task/rule text, material
  manifest hash, full tool definitions, and hashes of the two first messages.
- `scientist_input.md` renders the exact first-turn system/user text and the rule
  package.
- A configured rule file that is missing, unreadable, or empty fails before any
  model call. If `task.md` or the rule changes after the run is frozen, resuming
  fails instead of silently switching inputs.

`study preflight` is the offline control check:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m eeg_scientist.cli study preflight --study my_study
```

It prints each arm's model, task/material/rule hashes, prompt hashes, and prompt
diff. Two distinct rule files whose effective text is identical are rejected as
a rule contrast, both by preflight and by `study run`.

## 4. How to start and view a study

```powershell
cd X:\projects\EEG-AI-Scientist
$py = ".\.venv\Scripts\python.exe"

& $py -m eeg_scientist.cli study init --id my_study
# generic draft: edit task.md, system_prompt.md, materials/manifest.json, study.json
& $py -m eeg_scientist.cli study validate --study my_study
& $py -m eeg_scientist.cli study preflight --study my_study
& $py -m eeg_scientist.cli study status  --study my_study
& $py -m eeg_scientist.cli study report  --study my_study
```

The generic `init` references no old experiment. Old material is available only
through the explicit `--template emotion_20261021` option, which points at the
archived material manifest/evidence and old system prompt.

`study validate/status/report/preflight` never call a model. `study run` requires
verified backends and `--confirm-cost`; it has not been used in this round.

## 5. How to hand a proposal to 师哥 and import feedback

```powershell
& $py -m eeg_scientist.cli review export --study my_study
# send the packet overview reviews\packets\<packet>\review_packet.md and forms\*.md
# (NOT reviews\keys\)
& $py -m eeg_scientist.cli review import --study my_study --file .\forms\B01.md
& $py -m eeg_scientist.cli review select --study my_study --reviews r_xxx --version v1
```

Each proposal gets one self-contained `forms/Bxx.md`: the proposal body is
verbatim before `<!-- BEGIN REVIEW -->`, and the reviewer only fills
`reviewer_id`, `reviewer_role`, `verdict`, the three answers, and unreviewed
items. The fields `packet_id`, `display_id`, `proposal_id`, and full
`body_sha256` must stay unchanged.

A review record is bound to packet + display + run_id + full body SHA; the import
verifies the body hash and the run's `state.json`, and rejects a packet from
another study, a swapped display, a changed body, or a mismatched run. Raw
Markdown and structured JSON are separate. Re-importing identical content is
idempotent. A feedback-set version cannot be overwritten with different content;
use a new version. Unknown per-run cost stays `null`/`unknown`, not 0.

Old archived review binding is part of task B and is not claimed here.

## 6. Model adapters and archive rules

- Claude uses the Anthropic Messages protocol; Gemini uses `generateContent`.
  Both map tool calls to the existing `ResearchRunner` loop.
- Vendor-native assistant blocks are preserved in `messages.json` and replayed:
  Claude thinking/redacted_thinking with signatures; Gemini parts with
  `thoughtSignature`. Rebuilding history from text/tool_calls alone is no longer
  the path when native blocks exist.
- Gemini tool-call IDs are unique across a conversation (`gcall_001`, ...);
  Claude tool-use IDs come from the provider. Truncation (`max_tokens` /
  `MAX_TOKENS`) marks `truncated` and partial tool arguments are not executed;
  one bounded retry is allowed.
- Gemini `thoughtsTokenCount` is counted into billable output and recorded
  separately; Anthropic cache read/creation tokens are included in prompt
  accounting. Unknown usage still becomes UNKNOWN spend, not zero.
- Model IDs, real credentials, prices, and exact thinking parameters are
  **not verified**; statuses remain `unverified`. Offline tests use mocked HTTP
  transports only. A real connectivity call is required before changing status.
- Old `emotion-study run/evaluate/retry-failed` and `overnight-flash
  capability/diagnose/research`, and old `overnight/resume/episode/preflight`,
  refuse with a migration hint. `status`/report display can read the archive.
- Original answers, trajectories, ledgers, and review text were not edited.

## 7. Correction: old Meta injection

The old emotion-study Meta rules were saved but never entered the system/user
messages or `scientist_input.md` (0/10 runs). The 10 archived attempts have one
identical normalized input pair. Causal claims about the Meta rule must be
withdrawn. See `docs/CORRECTION_20261022_META_INJECTION.md` and the append-only
note in `archive/experiments/emotion_20261021/CORRECTION_20261022.md`.

## 8. Verification

```powershell
& $py -m pytest
```

Expected as of 2026-10-22: **114 passed**, no network/paid call. The new tests
cover actual request capture, task/rule changes, preflight rejection, form
roundtrip and binding conflicts, immutable feedback sets, and two-request
Claude/Gemini tool roundtrips.

Evidence and limitations: `docs/VERIFICATION_20261022.md`,
`audit_20261022/probe_findings_after.json`,
`audit_20261022/historical_rule_absence.json`.
The archive hash baseline is `audit_20261022/before_hashes.json`.

## 9. Not done in this round

- No real Claude/Gemini call; `verified` remains unverified.
- No new EEG experiment and no paid study run.
- No directory migration (task B), no old archived review export/import, no
  PDF/skill/vector-memory system, no automatic Meta loop.
