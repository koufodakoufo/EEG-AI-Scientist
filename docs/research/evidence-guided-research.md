# Evidence-guided EEG research

Status: implementation and development qualification, not a new scientific result.

## Design

The next increment connects three existing gaps: a paper-derived task with explicit evidence requirements, an independent researcher that can revise its experiment after validation, and a method selector whose decisions are tested outside the traces used to propose changes. Keep the existing isolated researcher and trusted EEG worker. Do not introduce another manager hierarchy.

The first scientific question is whether a frozen EEG classifier depends on a recoverable feature more than on an equally disruptive random intervention. The existing interface can measure recovery, matched interventions and residual recovery after refitting. Earlier tasks explicitly allowed recovery-only completion; those runs do not test the full question.

### Literature and independent decisions

- [FIRE-Bench](https://arxiv.org/abs/2602.02905) motivates paper → private experimental claims → public parent question → independent experiment → claim comparison. Its inspected source is `a7017c95f680ea233b76445c53fd5e56b48cc159`. We independently implement the adapter; no FIRE-specific source or prompt is redistributed. Scope and numerical evidence remain visible, unlike the inspected broad-text preprocessing. This is an adaptation, not an official FIRE score.
- [GEPA](https://arxiv.org/abs/2507.19457) motivates trace-guided candidates and separate selection tasks. A small explicit selector is sufficient before importing a larger optimizer.
- [STOP](https://arxiv.org/abs/2310.02304) and [AIDE²](https://arxiv.org/abs/2609.26457) motivate measuring an updater through its descendants, from the same starting researcher and budget. The present increment is not yet an ignition test.
- [TasteVal](https://arxiv.org/abs/2610.06824) motivates distinguishing experiment choice from implementation failure. The normal coding track stays primary; validated EEG operators can later provide a diagnostic track.
- [Topic-disjoint reflective optimization](https://arxiv.org/abs/2610.12601) motivates a concise static expert method and answer-stripped learned methods as controls. More text or leaked task answers must not masquerade as transferable research skill.

### Boundaries

Preserve all v1 task documents, behavior, IDs and frozen evidence. New task IDs are `eegmat-attribute-dependence-v2` and `eegmmidb-attribute-dependence-v2`. Their shared public evidence obligations are Q1 groups ≥24, matched interventions ≥2 and residual-refit groups ≥2. These are advisory completeness requirements, not proof of scientific validity. Honest partial reports and valid negative results remain allowed.

Both pilot arms receive identical questions, resources, obligations, lifecycle gates and budgets. `fixed_stages_v1` keeps the existing session recipe. `adaptive_evidence_v1` additionally receives validation-only evidence gaps and state-dependent advice. This tests their combined effect, not either mechanism separately. Never expose final-test metrics in pre-lock feedback. Never revise after test.

Initial development uses EEGMAT. Any EEGMMIDB assessment is held out from this candidate's development only: the project has already studied that dataset. A later independent confirmation needs a different recording condition/cohort or task family. Freeze all prompts, scorer, selection and replay rules before enrollment. Keep failures in the denominator; no replacement runs disguised as independent repeats.

Use six native calls, at most 900 seconds each, at most two scientific iterations plus baseline per attribute episode. Benchmark the full development interface before study enrollment; change both arms prospectively if this is infeasible. Model remains `gpt-6.1-sol`, medium effort. Initial pilot is two contexts per condition, descriptive only. Record actual expenditure as well as caps.

Primary outcome: executed Q2 and Q3 plus independent control/refit/replay checks. Secondary outcomes: supported claim coverage, unsupported interpretations, report completeness and cost. Paper agreement, numerical validity and lifecycle completion are separate dimensions. No single LLM score is scientific truth.

### Paper assessment

Keep a private versioned task record containing source anchors, experimental scope and reference provenance. Export only an explicit public allowlist. An adapted independently computed reference is different from an original-paper claim. Source text is untrusted input, never execution instructions.

Operational report extraction and directional judging use the existing typed claim contracts. Retain exact source spans, numbers, uncertainty, scope, raw responses and failures. Calibrate on explicit numerical, scope, causality and omission contrasts before using a judge in method selection. An unmatched valid new finding is not automatically a scientific error.

### Method selection

After the capability pilot, propose at most two answer-stripped methods from development traces, alongside identity/no-change and a fixed expert recipe. Evaluate on declared selection tasks, freeze the winner under a preregistered validity-first rule, then compare on separate transfer tasks. A candidate file passing validation is not an empirical improvement. Whether an updater itself improves requires a subsequent same-start, equal-budget experiment.

## Implementation plan

> For agentic workers: use subagent-driven development or executing-plans task by task. User explicitly authorized autonomous implementation and decisions; no design approval pause is needed.

**Goal:** connect evidence-aware research, paper assessment and empirical method selection to existing EEG execution.

**Architecture:** small task-bound extensions to `episode.py`, independently authored paper/assessment modules around `claims.py`, and a deterministic method-selection record. Keep machine-specific secrets and study state outside Git.

**Tech stack:** Python 3.10+, existing standard-library contracts, pytest, current NumPy/SciPy/sklearn/PyTorch CPU environments.

**Spec:** Design sections above.

**Global constraints:** preserve v1 behavior; no new runtime dependency without need; no credentials/data/weights/private reference text in Git; no other users' file changes; huoshanyun for science; no GPU allocation inferred from visibility; task names carry purpose rather than execution time.

**Review focus:** failed latest attempts cannot inherit older success; missing values differ from zero; scope mismatch cannot become paper support; incomplete model output cannot become a complete score; selection must not accept target-derived feedback.

### Task 1 — Validation evidence and adaptive guidance

Files: `src/eegfm/eeg/episode.py`, a focused `evidence_policy.py` if needed, new v2 task documents and `tests/test_evidence_guidance.py`.

- [ ] Write failing tests for old behavior, policy validation, identity binding, latest-attempt selection, missing/failed/test metrics and post-lock advice.
- [ ] Add task-specific evidence policy files and frozen `session_guidance` enum. Expose derived validation status only to the adaptive arm; bind it into enrollment/resume identity.
- [ ] Run targeted regressions and inspect actual public projection. Advisory coverage never asserts scientific validity.
- [ ] Obtain independent review, fix issues and commit.

### Task 2 — Paper task and operational assessment

Files: `src/eegfm/evaluation/paper.py`, `assessment.py`, corresponding tests. Consume existing `claims.py`; do not modify the runner or CLI in this parallel task.

- [ ] Write failing tests for allowlisted public export, anchors/provenance, scoped claims, incomplete output, exact spans and raw response retention.
- [ ] Implement strict private-task validation/public export and provider-driven segmented extraction plus directional judging. Providers are callables with explicit request/response records, not embedded credentials.
- [ ] Test deterministic boundaries with fixtures, then root connects the real isolated model provider and runs calibration. Fixture success is not live semantic calibration.
- [ ] Obtain independent review, fix issues and commit.

### Task 3 — Executable study and empirical selection

Files: a parameterized study entry under `scripts/`, `src/eegfm/improvement/selection.py` only when the pilot supplies its concrete needs, tests and this study's private config.

- [ ] Requalify live isolation/model control and cloud runtime. Benchmark existing full EEG interface on development data under worker caps.
- [ ] Replace expired/hardcoded enrollment helpers with the smallest current parameterized entry. Bind code, inputs, policy, model, budgets and machines; test rejection of identity drift.
- [ ] Freeze pilot registration; execute independent cases, collect failures and independently replay numerical artifacts. Do not repair a failed scientific candidate after final test.
- [ ] Select at most two trace-derived method candidates plus declared controls on selection tasks; freeze before transfer. Test target exclusion, missing results, ties, failures and identity retention.
- [ ] Execute the justified next experimental cycle; report negative/null findings without overstating RSI or paper replication.

### Task 4 — Review and synchronize

- [ ] Run supported tests on Windows, NCC and huoshanyun as relevant, with explicit skips.
- [ ] Obtain whole-branch review of boundary integrity and scientific claims.
- [ ] Update README, architecture/workspaces and one results report with concrete entry points. Merge reviewed work into main; synchronize owned code and verified result copies without changing old artifacts.

## Execution record

- Baseline: `6c69c18`; development branch `feat/evidence-guided-research` in the one formal checkout. Existing user preference for a single understandable workspace takes precedence over creating another worktree.
- Fresh offline native isolation passed. First model-control qualification failed without a tool call: the backend returned routing HTTP 401 and the native client reported a revoked refresh token. Network transport was reachable. Retain this infrastructure failure; do not retry an unchanged credential or silently replace the isolated researcher with an ordinary subagent. Builder EEG work and explicitly labeled evaluator development continue independently.
- Baseline portable suite: 380 passed, 83 skipped on Windows. Linux isolation/execution skips are not counted as passes.
- Shared cloud disk was 99% full with about 82 GB free at preflight. Reuse existing EEG resources; new work is CPU bounded and storage monitored.
