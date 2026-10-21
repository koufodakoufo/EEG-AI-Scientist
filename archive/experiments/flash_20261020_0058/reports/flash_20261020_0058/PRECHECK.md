# PRECHECK — flash_20261020_0058

Checked at 2026-10-20 00:58–01:02 +08:00 (Asia/Shanghai). No secret values are reproduced here.

## Repository state before changes

| Item | Value |
|---|---|
| Repository | `X:\projects\EEG-AI-Scientist` (the task book's `eeg-ai-scients` spelling is stale; no rename) |
| Original branch / HEAD | `main` / `d0bbb6e` — `Add EEG-style hypothesis-diagnosis loop, frozen S0/S1 study, reports, and tests` (2026-10-19 01:57 +08:00) |
| Work branch created | `overnight/flash-20261020-0058` |
| User changes at start | `.gitignore` staged (`/.env.*`, `!/.env.example`, `/credentials/`); `docs/` untracked (the task book). Both preserved; nothing was reset, checked out over, or cleaned. |
| Pre-existing runs | `runs/study_20261019` and `runs/dev_e1` exist and are gitignored. They are the previous Qwen synthetic study and are **not** being re-run or overwritten. |

## Credentials (status only)

- Selected source: `credentials/deepseek.env`, explicitly loaded by the program (not by an implicit root `.env` search).
- Format: one `DEEPSEEK_API_KEY=<value>` line plus trailing newline; 54 bytes; ASCII; value length 35. No format repair was needed.
- Variable name: `DEEPSEEK_API_KEY`.
- Git: file is ignored by `/credentials/` and is not tracked (`git ls-files` returns nothing; `git check-ignore` matches `.gitignore:66`).
- Environment: `DEEPSEEK_API_KEY` is **not** set in the process environment, so there is no file/environment conflict.
- Key validity: `GET https://api.deepseek.com/models` returned HTTP 200. The returned list contains `deepseek-flash` (DeepSeek-V4.1-Flash, context 1,048,576, max output 393,216, effort levels low/high/max). No chat tokens were spent on this check.
- The key was never printed, logged, or placed in a model message. A local helper compared file/environment presence only.

## Model and tool routes

- Scientist model: `deepseek-flash` via `https://api.deepseek.com` Chat Completions (OpenAI-compatible).
- Thinking: enabled, effort `high` (request body `thinking: {"type": "enabled"}`, `reasoning_effort: "high"`).
- Tools are executed by **this repository**, not by a model vendor's built-in agent.
- Search / Fetch: official `POST /v1/tools/search` and `POST /v1/tools/fetch`, same key. Docs checked at 00:59 +08:00:
  - `https://api-docs.deepseek.com/zh-cn/guides/search/`
  - `https://api-docs.deepseek.com/zh-cn/guides/thinking_mode/`
  - `https://api-docs.deepseek.com/zh-cn/guides/tool_calls/`
- No Claude, no Ollama/Qwen fallback, no Meta loop is configured for this run.
- Pricing checked at 00:59 +08:00 from `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/`: Flash peak input ¥2/M (cache miss), output ¥8/M; off-peak half. Search/Fetch ¥5 per 1,000 successful requests. The run reserves at **peak** rates for the whole night and keeps a ¥2 wrap-up reserve; it will not raise the ¥20 cap.

## Environment

| Item | Value |
|---|---|
| Python | 3.12.4 (Anaconda, `C:\Users\14090\anaconda3\python.exe`) |
| Project `.venv` | present but contains no project dependencies; it is not used |
| Working dependency set | Anaconda base, read-only, with `PYTHONPATH=src`: numpy 1.26.4, scikit-learn 1.4.2, pydantic 2.5.3, httpx 0.27.0, pytest 7.4.4 |
| Disk free on X: | ≈ 499 GB |
| Test baseline | 43 tests passed in the previous run (`reports/test_summary.json`); this run will re-run them after changes |
| PDF/OCR tooling | `pypdf`, `PyPDF2`, `PyMuPDF` are **not** installed. Prefer HTML full texts; a PDF fallback will be added only if it can be done without a large toolchain. |

## Data availability (Task E decision)

- `data/private/case_specs.json` contains **synthetic EEG-style feature-table generators** (family codes T/G/D/N), not recorded EEG.
- No BDF/EDF/FIF/SET raw EEG is configured in this repository; `data/raw`, `data/interim`, and `data/processed` are empty or absent.
- The task book does not authorise scanning other projects or the whole X: drive. `X:\projects\daily-emo-eeg` is a separate project and was **not** scanned or read.
- Therefore the honest branch is **E2**: write `DATA_REQUIREMENTS.md`, implement a minimal feature-table entry point plus a small artificial fixture to validate input/split logic, and state explicitly that no real EEG experiment was run. The fixture will not be described as EEG evidence.

## Network and tool caveats

- The model endpoint responded. Search/Fetch have not yet been proven in this run; they will be tested with real requests and reported separately in `CAPABILITY_CHECK.md`.
- A PDF fetched as a URL may not be converted by the vendor Fetch endpoint. If a core paper is only available as a PDF, the run will record the gap rather than claim it was read.
- The previous study's zero-action holdout failure and Meta `no_update` are treated as history, not as evidence for the new method.

## Blockers / limits at start

1. No real EEG dataset is available to this repository (Task E → E2). This is not a credential or network blocker.
2. PDF text extraction is not yet available locally; open-access HTML is the primary full-text route.
3. The 8-hour wall clock starts at 00:58 +08:00. New research stops at 08:13; 08:13–08:58 is reserved for reports and commits.

## Start / resume commands (verified during this run)

```powershell
cd X:\projects\EEG-AI-Scientist
$env:PYTHONPATH='src'
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli overnight-flash status
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli overnight-flash research --name literature_v1
```

The second command is both the start and the resume command: it loads `state.json` / `messages.json` and the shared ledger. Re-running it after completion made no new request (see `RESUME_CHECK.md`).
