# RUN INDEX — flash_20261020_0058

- rendered_at: 2026-10-19T17:28:46Z
- study_config: `configs\studies\overnight_flash_20261020.json`
- deadline: 2026-10-20T08:58:00+08:00
- stop_new_research_at: 2026-10-20T08:13:00+08:00

## Stage status

| stage | state | evidence location |
|---|---|---|
| A precheck | DONE | `reports/flash_20261020_0058/PRECHECK.md` |
| A implementation map | DONE | `reports/flash_20261020_0058/IMPLEMENTATION_MAP.md` |
| B capability | PASS | `runs/flash_20261020_0058/capability/CAPABILITY_CHECK.md` |
| C regression | DONE | `runs\flash_20261020_0058\diagnostics/regression/` |
| C neutral cases | DONE | `runs\flash_20261020_0058\diagnostics/cases/` |
| D literature | completed | `runs\flash_20261020_0058\research\literature_v1/` |
| E real-data branch | DONE (E2 fallback; no real EEG) | `reports/flash_20261020_0058/DATA_REQUIREMENTS.md` |
| F audit/extension | DONE | `reports/flash_20261020_0058/EVIDENCE_AUDIT.md`, `EXPERIMENT_PROTOCOL.md` |
| G reports/commit | DONE (reports + local commits) | `reports/flash_20261020_0058/` |

## Budget

| item | used | limit |
|---|---:|---:|
| project API spend (peak-rate accounting) | CNY 1.6501 | CNY 20.0 |
| unknown/timeout reservations | CNY 0.0000 | — |
| model attempts | 30 | 120 |
| search attempts | 10 | 60 |
| fetch attempts | 18 | 90 |
| input tokens | 560786 | 2000000 |
| output tokens | 52938 | 500000 |

## Capability checks

- `list_models`: PASS
- `chat_json_thinking`: PASS
- `native_tool_cycle`: PASS
- `search`: PASS
- `fetch_and_read`: PASS

## Deliverables

- `reports/flash_20261020_0058/MORNING_REPORT.md` — start here
- `reports/flash_20261020_0058/LITERATURE_MAP.md` — 7 cited papers, read scope, unread/failed sources
- `reports/flash_20261020_0058/HYPOTHESIS_CARDS.md` — three cards, priority/backup, dsh review notes
- `reports/flash_20261020_0058/EVIDENCE_AUDIT.md` — number/claim audit against the injection log
- `reports/flash_20261020_0058/EXPERIMENT_PROTOCOL.md` — reduced priority experiment and backup
- `reports/flash_20261020_0058/DATA_REQUIREMENTS.md` — E2 fallback, binary-only label entry, no session split
- `reports/flash_20261020_0058/HANDOFF_SYSTEM.md` — one-page role and capability explanation
- `reports/flash_20261020_0058/REASONING_REVIEW.md` — separate inference corrections; original answer untouched
- `reports/flash_20261020_0058/COVERAGE_RECHECK.md` — interval-union coverage correction
- `reports/flash_20261020_0058/coverage_union.json` — corrected coverage values
- `runs/flash_20261020_0058/research/literature_v1/final_answer.md` — the Scientist's own answer

## Handoff checks (2026-10-20)

- 61 offline tests pass, exit 0; no paid model call, no new data, no rerun.
- `finish_study` inline citations and `evidence_ids` must match exactly.
- Usage missing/invalid is UNKNOWN spend, not zero.
- Coverage is counted by interval union.
- CSV labels are integer `-1`/`1` only; decimal labels are rejected.
- Session split remains unimplemented; do not call any run session-held-out.

## Local commits

- `4b902c6` Add DeepSeek Flash research loop with evidence, budget, and diagnostics
- `e0d1c7e` Record Flash overnight results, evidence audit, and recovery state
- `843e15c` Record Flash run commit hashes in progress log
- `6ae034d` Clarify Scientist-attributed search/fetch counts in morning report
- `889e617` Copy capability markdown, not JSON, into the report bundle

Branch: `overnight/flash-20261020-0058`. Not pushed. The user's staged `.gitignore` change remains staged and was not included in these commits.

## Commands

```powershell
cd X:\projects\EEG-AI-Scientist
$env:PYTHONPATH='src'
$py='C:\Users\14090\anaconda3\python.exe'
& $py -m eeg_scientist.cli overnight-flash status
& $py -m eeg_scientist.cli overnight-flash research --name literature_v1
```
