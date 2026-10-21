# RESUME AND COST CHECK — flash_20261020_0058

This verifies two claims that are easy to fake: the run resumes without re-paying completed calls, and the ledger is not reset.

## Resume check (executed 2026-10-20 01:24 +08:00)

The literature runner had already finished with:

- phase: `completed`
- stop reason: `finish_study`
- model calls: 16; tool calls: 42; searches: 8; fetches: 10
- final: `runs/flash_20261020_0058/research/literature_v1/final.json`

I re-ran the same resume command as a real subprocess:

```powershell
cd X:\projects\EEG-AI-Scientist
$env:PYTHONPATH='src'
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli overnight-flash research --name literature_v1
```

Result: the runner loaded `state.json` + `messages.json`, saw `phase=completed`, returned the summary, and made **no model, search, or fetch request**.

| Ledger field | Before resume | After resume |
|---|---:|---:|
| model attempts | 30 | 30 |
| spend CNY (peak-rate accounting) | 1.650076 | 1.650076 |
| input tokens | 560,786 | 560,786 |
| output tokens | 52,938 | 52,938 |
| pending reservations | 0 | 0 |

The command output is in `runs/flash_20261020_0058/resume_check.txt`.

## Cost accounting check

The ledger `runs/flash_20261020_0058/budget.json` is the authoritative counter. Every paid attempt reserves worst-case cost before the HTTP call and settles against reported usage. The final position:

- CNY 1.650076 spent of the CNY 20 cap, with CNY 2 reserved for wrap-up; CNY 0 unknown.
- 30 model attempts of 120; 10 search attempts of 60; 18 fetch attempts of 90.
- 560,786 input tokens of 2,000,000; 52,938 output tokens of 500,000.
- No pending reservation at exit.

The spend is computed at **peak** rates (2 CNY/M input, 8 CNY/M output) even though this run occurred in the off-peak window, so the real bill should be lower, not higher. This is a conservative project-API number only; it excludes dsh's own development-agent usage.

## Interruption behavior (code-level, not re-tested live)

- A request that times out or has an unparseable 200 response is marked `unknown`; its reservation is not released.
- A crash after `pending_attempt` is written is handled on resume by `mark_all_pending_unknown`.
- A crash between an assistant `tool_calls` message and its tool results is repaired with explicit `error` tool messages; the runner does not guess or silently re-execute.
- Completed searches/fetches/experiments are reused by ID; the run never resets the ledger or deadline.

The live test above only covers the completed-run path; the interruption paths are covered by offline tests (`tests/test_flash_stack.py`), not by a live kill during a paid call.
