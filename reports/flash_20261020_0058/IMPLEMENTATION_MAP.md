# IMPLEMENTATION MAP — flash_20261020_0058

This maps the task book's suggested boundaries onto the actual repository. The existing synthetic-case study code is reused where it fits; the new DeepSeek research loop is additive and does not rewrite the frozen 2026-10-19 study.

## Boundaries

| Task-book boundary | Actual module | Responsibility |
|---|---|---|
| ModelClient | `src/eeg_scientist/deepseek_api.py` | Typed DeepSeek Chat Completions client: thinking, native tool calls, `reasoning_content` continuation, usage, retries, Search/Fetch calls. No silent fallback. |
| Credential loading | `src/eeg_scientist/credentials.py` | Explicit read of `credentials/deepseek.env`; validates one `DEEPSEEK_API_KEY`; never prints the value; reports file/environment conflicts. |
| Budget / spend control | `src/eeg_scientist/ledger.py` | Persistent CNY + attempt + token ledger. Reserves worst-case cost before every paid request; settles on usage; keeps timeout reservations as UNKNOWN; survives resume. |
| EvidenceStore | `src/eeg_scientist/evidence.py` | Saves fetched full text with URL/title/hash/time, page or char offsets, and an append-only injection log of exactly which excerpt range entered the Scientist context. `read_evidence` accepts only registered IDs and ranges. |
| ToolExecutor | `src/eeg_scientist/research.py` | Executes `search_sources`, `fetch_source`, `read_evidence`, `run_experiment`, `finish_study`; validates arguments, records every call/result, returns typed envelopes. |
| ResearchRunner | `src/eeg_scientist/research.py` | Persists exact wire messages, state, events, request/response files, heartbeat; resumes without re-paying completed calls; detects interrupted tool-call messages and repairs them without pretending success. |
| Diagnostic regression | `src/eeg_scientist/diagnostic.py` | Task C: raw 99%/50% table explanation with rule-based checks, and neutral-ID synthetic case episodes through the existing decision state machine. |
| DeepSeek adapter for the old decision loop | `DeepSeekDecisionProvider` in `deepseek_api.py` | Implements the existing `decide(ModelRequest) -> ProviderResponse` protocol so `runner.py` can run case diagnostics with Flash without changing the frozen study. |
| Dataset entry (E2) | `src/eeg_scientist/dataset_io.py` | Minimal documented feature-table format, fixture writer, and split/label integrity checks. Artificial fixture only; not EEG evidence. |
| CLI | `src/eeg_scientist/cli.py` | `overnight-flash` subcommands: `capability`, `diagnose`, `research`, `status`, `report`; plus top-level `check-dataset`. Resume is the same `research` command, not a separate subcommand. |

## Reused existing code

- `cases.py`, `splits.py`, `experiments.py`, `runner.py`, `storage.py`, `scientist.py`: the previous fixed-classifier synthetic diagnostic loop. Used for Task C only, with neutral case aliases and no development facts.
- `schema.py`: typed Pydantic/dataclass models. New models live in the new modules to avoid touching frozen study schema.
- Hash-chained `events.jsonl`, atomic JSON writes, sealed predictions: reused for diagnostics; the research runner uses the same event log helpers.

## Non-goals in this run

- No Meta outer loop, no S0/S1 rewrite, no Claude adapter, no Ollama/Qwen fallback.
- No real EEG preprocessing/training; Task E uses the E2 fallback.
- No push and no history rewrite. Commits are local and scoped.

## Run directories

| Path | Contents | Git |
|---|---|---|
| `runs/flash_20261020_0058/budget.json` | global spend/attempt/token ledger | ignored |
| `runs/flash_20261020_0058/capability/` | real model/Search/Fetch/tool-cycle check traces | ignored |
| `runs/flash_20261020_0058/diagnostics/` | regression and two neutral-case episodes | ignored |
| `runs/flash_20261020_0058/research/` | literature research run: messages, requests, responses, tools, sources, evidence, final | ignored |
| `reports/flash_20261020_0058/` | English/Chinese reports for the human | committed after review |
| `configs/models/`, `configs/studies/` | non-secret configuration | committed |

## Start / resume / inspect

```powershell
cd X:\projects\EEG-AI-Scientist
$env:PYTHONPATH='src'
$py = 'C:\Users\14090\anaconda3\python.exe'

# status (reads state + ledger; no paid calls)
& $py -m eeg_scientist.cli overnight-flash status

# real capability check (model, tool cycle, Search, Fetch)
& $py -m eeg_scientist.cli overnight-flash capability

# Task C regression + neutral case diagnostics
& $py -m eeg_scientist.cli overnight-flash diagnose

# Task D literature run (new run; resume with the same command)
& $py -m eeg_scientist.cli overnight-flash research --name literature_v1

# re-render reports from persisted state
& $py -m eeg_scientist.cli overnight-flash report
```

Resume semantics: the ledger and `runs/.../research/state.json` are authoritative. A request reserved but not settled is marked `UNKNOWN` and remains charged; completed tool calls and experiments are reused by ID; exact wire messages are restored from `messages.json`.
