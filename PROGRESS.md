# PROGRESS

Updated: 2026-10-19 01:59 +08:00 (Asia/Shanghai)

## Final status

**E2 (engineering) / E1 (substantive).** All planned study runs are complete, but the holdout S0/S1 comparison is a weak null-rule control: every holdout arm stopped before any experiment, and the Meta update was `no_update`.

## Execution contract

- T0: 2026-10-19 01:14:21 +08:00.
- Deadline D = 09:14:21 +08:00; report reserve 60 min; stop-new R = 08:14:21.
- Goal `goal-1d1d5d3f-371c-4d10-9f4b-1a1025d48cea`, active/armed, max 80 rounds at creation.
- Research direction fixed: synthetic EEG-style hypothesis-diagnosis loop; no real EEG, no EEG-FM training, no RSI claim.

## Environment and model

- Actual directory: `X:\projects\EEG-AI-Scientist` (the plan's `eeg-ai-scients` spelling is stale; no rename).
- `uv sync --extra dev` was blocked by a build-backend network timeout; the read-only Anaconda Python 3.12.4 fallback was used with `PYTHONPATH=src`.
- Model: local Ollama 0.32.1, `qwen3.5:9b`, parameter size 9.7B, Q4_K_M, context 262144, digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` (from `/api/tags`).
- Cloud API: no `SCIENTIST_*` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`; Desktop login is separate and was not extracted.
- Preflight: `reports/PREFLIGHT.md`; local structured probe passed.
- Power: AC standby timeout 0; the machine stayed powered during the run.

## Completed

- T1: schema, cases, global trial UIDs, four families, 3072/1024 splits.
- T2: fixed StandardScaler + KNN(1), five tools, 10 random-label seeds, calibration. T: 0.997/0.508; G: 0.951/0.950/0.952; D: 0.974/0.981/0.657; N: 0.517/0.485/0.492.
- T3: append-only event hash chain, atomic state, sealed predictions, idempotent result reuse, partial-tail quarantine, middle-corruption failure.
- T4: local Ollama provider, S0, flat/nested decision normalization, format/constraint repair, duplicate-action rejection, chance-relative prediction scoring.
- E1: `runs/dev_e1/case_001_s0` completed, real_llm, 3 actions, 4 calls, 5 attempts, 24,330 tokens, 2/2 numeric hits. Three earlier failed attempts are preserved in `runs/dev_e1/*_failed`.
- T5: study `runs/study_20261019` complete:
  - development S0 case_001 and case_002: both real_llm, 3 actions, 2/2 numeric hits each.
  - freeze `2026-10-18T17:49:52Z`, hash `d8b54d165fe50ea96a1c7e036d1a8185ea9f342d32d46aa8648fa56b0b6fd553`.
  - Meta: `no_update`; the first rule proposal exceeded 600 characters and its repair returned invalid JSON (recorded in `FREEZE_MANIFEST.json` and `FAILURE_CASES.md`).
  - holdout: 4/4 pairs have complete S0/S1 states, but all 8 arms stopped with **0 actions** and 0/0 predictions. S1 is identical to S0 in rule content.
- T6: `reports/MORNING_REPORT.md`, `reports/RESULTS_TABLE.md`, `reports/FAILURE_CASES.md`, `reports/CORE_CODE_WALKTHROUGH.md`, `reports/CALIBRATION.md`, `reports/PREFLIGHT.md`, `reports/REPRODUCE.md`, `artifacts/review_bundle.zip`.
- Tests: 43 passed, exit code 0 (`reports/test_output.txt`, `reports/test_summary.json`).

## Budget

- StudyState: 18 attempts, 92,204 tokens; E1 dev: 68,487 tokens; Meta: 9,309 tokens; total recorded 160,691 tokens (cap 1,000,000). Attempts well under 96. Local monetary cost $0.
- DSH development token/cost is a separate ledger and is not counted here.

## Honest limits

- E2 is an engineering count, not an effective method-rule comparison. The substantive research evidence is E1.
- All holdout arms stopped without an experiment. This is a real failure mode of the frozen prompt/facts/model, not a success.
- The S1 rule update is `no_update`; the S0/S1 paired table is a null-rule control.
- The E1 final text occasionally mentions an H3 that is not in the current hypothesis list; this is a reviewer finding.
- The study is synthetic, single-model, and small; no population-level EEG inference, no RSI claim.
- E3 (second seed / real EEG) was not run; it was optional and time did not require it.

## Deliverables

- `reports/MORNING_REPORT.md` — start here.
- `reports/RESULTS_TABLE.md` — episodes, baselines, tools, paired holdout.
- `reports/FAILURE_CASES.md` — zero-action arms, Meta failure, early E1 failures.
- `reports/CORE_CODE_WALKTHROUGH.md` — six-module reading guide with self-test questions.
- `FREEZE_MANIFEST.json` — frozen hashes, model/dependency/code versions, Meta cost.
- `artifacts/review_bundle.zip` — reports, configs, prompts, memory, run records, source, tests, and review-only case specs.
- `PROGRESS.md`, `NEXT_ACTION.md`, `DECISIONS.md`, `reports/PREFLIGHT.md`, `reports/CALIBRATION.md`, `reports/test_output.txt`.

## Next action for the user

Read `reports/MORNING_REPORT.md`, then inspect one complete trajectory (`runs/dev_e1/case_001_s0` or `runs/study_20261019/development/case_001/s0`) and the freeze manifest. Do not start a second seed or real EEG until the E2 caveat and the zero-action failure are reviewed.

---

# 2026-10-20 Flash overnight run (complete, wrapped up early)

Updated: 2026-10-20 01:30 +08:00.

## Contract

- Run ID: `flash_20261020_0058`; branch `overnight/flash-20261020-0058` (created from `main` at `d0bbb6e`; the user's staged `.gitignore` change and untracked `docs/` were preserved).
- T0: 2026-10-20 00:58 +08:00. Deadline 08:58; stop-new-research 08:13; 45-minute report reserve. The run finished early because the planned A–F tasks were complete; no artificial waiting was used.
- Scientist: `deepseek-flash` (DeepSeek-V4.1-Flash-1017) via official Chat Completions, thinking high. No Claude, Ollama, Qwen, or Meta loop.
- Project API cap: CNY 20, CNY 2 wrap-up reserve, peak-rate accounting. Model attempts 120; Search 60; Fetch 90.

## Completed

- **A:** `reports/flash_20261020_0058/PRECHECK.md`, `IMPLEMENTATION_MAP.md`, model/study configs, branch.
- **B:** typed DeepSeek client, persistent budget ledger, evidence store, resumable native-tool research loop, dataset loader, CLI. Real capability check PASS for model, JSON/thinking, native tool cycle, Search, and Fetch+read. 8 new offline tests; 51 total passing.
- **C:** explanation regression 6/6 rule checks (raw 99.3/49.6 → 99.2/50.8 table; no answer template). Two neutral synthetic cases both completed with real tool executions (3/3 and 2/2 prediction hits); no real EEG claim. Artifacts under `runs/flash_20261020_0058/diagnostics/`.
- **D:** literature run completed at 01:18 with `finish_study`: 16 model calls, 42 tool calls, 8 searches, 10 successful fetches, 7 cited papers, 19 read slices, 10 evidence items (3 irrelevant, uncited). The Scientist's answer is `runs/flash_20261020_0058/research/literature_v1/final_answer.md`. No task book/reference answers/generator internals were in its input.
- **E:** no real EEG dataset is configured; E2 fallback applied. `DATA_REQUIREMENTS.md`, strict CSV feature-table loader, split audit, and an artificial fixture check (exit 0). Explicitly not EEG evidence.
- **F:** evidence audit checked every load-bearing number against the injection log; two Fallahi details are true in the source but outside the read range; one top-line synthesis claim is an inference. Reduced experiment protocol, second-branch handoff, code reading guide, resume/cost check, and method lessons written.
- **G:** reports rendered, tests re-run (51 passed), local commits `4b902c6` (code/configs/docs) and `e0d1c7e` (reports/state). No push.

## Final budget

- Project spend CNY 1.650076 of CNY 20 (peak-rate accounting; CNY 2 reserve untouched); CNY 0 unknown.
- 30 model attempts / 120; 10 Search / 60; 18 Fetch / 90.
- 560,786 input tokens / 2,000,000; 52,938 output tokens / 500,000.
- Resume test after completion: 0 new attempts, 0 new spend (see `RESUME_CHECK.md`).

## Honest limits

- No recorded EEG experiment was run; all case data are synthetic and the fixture is artificial.
- Prediction hits are not scientific correctness; they are reported separately from explanation quality.
- The literature target was 8–12 papers; only 7 relevant papers were confirmed. Two fetches failed (EEGManyPipelines 504; one 404) and three successful fetches were irrelevant and uncited.
- No paper was read end-to-end; read coverage was 5–21% of fetched text (Yin: abstract page only). Two 2026 papers are preprints.
- The Scientist's top-line "low-dimensional spectral/rhythmic structure" is an inference, not a measured result. The evidence audit flags it.
- `case_*` diagnostics are synthetic; no population-level EEG inference is made.

## Next action

Read `reports/flash_20261020_0058/MORNING_REPORT.md`, then the Scientist's `final_answer.md` and `EVIDENCE_AUDIT.md`. Decide whether to run the reduced M1 in `EXPERIMENT_PROTOCOL.md` on public data. Do not start a new paid run without a new decision; the existing run resumes completed with no new spend.

---

# 2026-10-20 Handoff and small fixes (complete, no paid calls)

Updated: 2026-10-20 21:40 +08:00.

- Branch `overnight/flash-20261020-0058`; HEAD before handoff `cca1e77`. User's staged `.gitignore` and untracked `src.zip`/`tests.zip` preserved.
- Read current `PROGRESS.md`, `NEXT_ACTION.md`, `reports/flash_20261020_0058/RUN_INDEX.md`, and the relevant code; did not rely on the old morning report alone.
- Added `HANDOFF_SYSTEM.md` (one-page role/capability explanation), `REASONING_REVIEW.md` (three inference corrections; original Scientist answer untouched), and `COVERAGE_RECHECK.md` plus `coverage_union.json`.
- Code fixes: finish_study inline/listed evidence-ID consistency; coverage by interval union; missing/invalid usage as UNKNOWN cost; strict integer binary CSV labels. Documented binary-only entry and unimplemented session split; did not expand the data system.
- Tests: 61 offline tests pass; no model call, no new data, no rerun.
- Review bundle: `artifacts/review_bundle_20261020.zip` (no credentials/private raw data; original run files unchanged). Exact contents and SHA-256 are in its `MANIFEST.json`.
- No push.

## Next action after handoff

Read `reports/flash_20261020_0058/HANDOFF_SYSTEM.md` for the system map, then `REASONING_REVIEW.md` before reusing the Scientist's priority claim. The next scientific step remains a separate decision; no paid run was started.

