# Evidence index

Canonical root: `X:/projects/EEG-AI-Scientist`. In this index, **N** means `.local/overnight-20261029/`, which is intentionally ignored by Git and contains private evaluation material. Never mount this whole directory into an Actor or upload its recovery archive. Metadata and code are versioned in the root repository; no nested Git repository was created.

| Claim / outcome | Evidence and entry point |
|---|---|
| User scope, ceilings and all 24 reservations | Root taskbook; `PLAN.md`; `BUDGET.json`; `RUN_LEDGER.jsonl`. Taskbook hash and terminal-call check: `TASK_PACKAGE_INDEX.json`. |
| Source-grounded question tree and two task packages | `N/private/reference/research_tree.json`, `source_excerpts.json`, `candidate_slices.json`, `source_manifest.json`, `validation_report.json`; `TASK_PACKAGE_INDEX.json` indexes public files and private reference hashes. |
| Distinct synthetic dev / holdout mechanisms | `N/private/task-build/BUILD_AUDIT.md`, `CASE_DEFINITIONS_PRIVATE.json`, `generate.py`, `VALIDATION_REPORT.json`; `N/public-bundles/{dev,holdout}/PUBLIC_MANIFEST.json`. Seven public files each; private final test not exported. |
| Pre-Actor freezing and symmetric reference extraction | `N/private/reference-v2/FREEZE.json`, `SCORING_LINEAGE.json`, `N/private/seals-v2/`; original seals preserved under `seals/`. M11 extraction evidence. `verify_nightly_freeze.py` rechecks bytes without changing them. |
| Actual model and boundary checks | `ISOLATION_REPORT.json`, `ACTOR_LAUNCHER.md`; `N/evidence/server/M10/` and failed M05/M07/M09. M10 uses dummy canaries to test read/network boundaries. No proof against every exploit or pretraining contamination. |
| Runtime diagnosis and pinned binaries | `RUNTIME_REVIEW.md`; `N/evidence/runtime-review/`; each exported `launcher-metadata.json` and ledger hashes. Fresh home replaces the ineffective ignore-user-config/profile combination. |
| Dev run and dev-only distillation | `N/submissions/M12/`; `N/evidence/server/M12–M15/`; `N/private/jobs/M15/`; skill and provenance in `framework/benchmarks/brainpec_pilot/skills/distinguish-recovery-response-and-causation/`. Exact skill hash in package index. |
| Frozen condition order / actual injection | `N/private/HOLDOUT_PROTOCOL.json`; `N/private/jobs/M16,M17,M20,M21/`; per-episode PROMPT/status/hash records. Only treatment prompts contain frozen skill bytes. |
| All launched holdout episodes, including external failure | `N/submissions/M16,M17,M20,M21/`; `N/evidence/server/Mxx/status.json`, `stdout.jsonl`, `collection.json`, `trace/visible_trace.jsonl`. M16 records the capacity error and empty report. |
| Semantic P/R/F1 and review items | `N/private/evaluations/M14,M19,M23/`; corresponding judge `final.txt` and anonymous input mappings in `N/private/jobs/`. `RESULTS.md` retains denominators and provisional/empty statuses. |
| Original and supplemental replay | Per-run `replay/`, `replay-supplement/`, and M20 `supplemental-core/`; `evidence-audit*.json`. `supplemental_core_replay.py` records why it is post-hoc and does not replace primary results. |
| Selected independent arithmetic | `NUMERICAL_AUDIT.json`, produced by `scripts/overnight/audit_saved_results.py`. 173 reported accuracy entries match; no Actor code executed by that audit. |
| Five process dimensions | `PROCESS_AUDIT.md`; exact UTC tool timestamps in visible traces. Unblinded Builder review, no composite taste score. |
| Score and leakage counterexamples | `SCORING_COUNTEREXAMPLES.json`; `scripts/overnight/scoring_counterexamples.py`; 26 labeled graph cases, separate toy leak positive control and granularity counterexample. No semantic-calibration claim. |
| Independent review and repairs | `INDEPENDENT_REVIEW.md`; commits 30b405f and e6f1403. Red evidence `N/evidence/server/legacy-adapter-red.log`, `attempt-budget-red.log`; targeted fixes preserve failure/timeout states and enforce legacy iteration limits. |
| Final Linux verification | `N/evidence/server/final-research-bench-tests.log`: 79 tests, 3.443 s; `final-legacy-tests.log`: 14 passed, 44.87 s. Run from server integration/framework with base venv. Framework code was unchanged by later documentation/audit additions. |
| Original scripted lifecycle, not an LLM achievement | `N/evidence/server/legacy-smoke-report.json`; `scripts/overnight/legacy_smoke.py`. Real LLM episodes are separately M12/M16/M17/M20/M21. |
| Proxy identity repair and safe shutdown | Commit 45e3195; `N/evidence/proxy-timestamp-regression.json`, `proxy-powershell7-check.json`, `proxy-windows-powershell-check.json`, `PROXY_STOP.json`. JSON DateTime vs String tested on PowerShell 7.6.5 and Windows PowerShell 5.1. Only the recorded helper process was stopped. |
| Scope, resource and cleanup evidence | `N/evidence/server/RESOURCE_SNAPSHOT.json`; preserved server source HEAD fb6c37e and clean status; `CONTROL_RETIREMENT.json` records 18 temporary auth-copy removals and 15 native rollout removals after visible export. Base auth retained. |
| Future research queue | `RESEARCH_QUEUE.md`: eight primary-source candidates, two bounded deep dives, three priorities. Not supplied to Distiller/Actors. |
| Recovery | `N/recovery/private-evidence.tar.gz` (646 files, every member hash checked); `FILES.json`; final `repository.bundle` and `RECOVERY_MANIFEST.json`. Recovery excludes live control homes and base authentication. |

Reproducible offline checks from the canonical root:

```powershell
python scripts/overnight/verify_nightly_freeze.py
python scripts/overnight/audit_saved_results.py
python scripts/overnight/scoring_counterexamples.py
```

These regenerate metadata reports from frozen local evidence and do not call a model. Do not rerun `actor_job.py`, `export_cases.py`, `freeze_references.py`, collectors or recovery creation against consumed IDs/existing destinations. `RESUME.md` describes safe continuation.
