# Evidence-guided EEG research

Status: implementation verified; Builder experiments and independent decision diagnostics underway. Completed evidence is tracked in [the results report](evidence-guided-results.md). These are separate from the native coding-track pilot, whose model authentication failed qualification.

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

- [x] Write failing tests for old behavior, policy validation, identity binding, latest-attempt selection, missing/failed/test metrics and post-lock advice.
- [x] Add task-specific evidence policy files and frozen `session_guidance` enum. Expose derived validation status only to the adaptive arm; bind it into enrollment/resume identity.
- [x] Run targeted regressions and inspect actual public projection. Advisory coverage never asserts scientific validity.
- [x] Obtain independent review, fix issues and commit.

### Task 2 — Paper task and operational assessment

Files: `src/eegfm/evaluation/paper.py`, `assessment.py`, corresponding tests. Consume existing `claims.py`; do not modify the runner or CLI in this parallel task.

- [x] Write failing tests for allowlisted public export, anchors/provenance, scoped claims, incomplete output, exact spans and raw response retention.
- [x] Implement strict private-task validation/public export and provider-driven segmented extraction plus directional judging. Providers are callables with explicit request/response records, not embedded credentials.
- [x] Test deterministic boundaries and run an explicitly context-separated real-model development calibration. The OS-isolated provider remains unavailable; the calibration does not substitute for its qualification.
- [x] Obtain independent review, fix issues and commit.

### Task 3 — Executable study and empirical selection

Files: a parameterized study entry under `scripts/`, `src/eegfm/improvement/selection.py` only when the pilot supplies its concrete needs, tests and this study's private config.

- [ ] Requalify live isolation/model control and cloud runtime. Benchmark existing full EEG interface on development data under worker caps.
- [ ] Replace expired/hardcoded enrollment helpers with the smallest current parameterized entry. Bind code, inputs, policy, model, budgets and machines; test rejection of identity drift.
- [ ] Freeze pilot registration; execute independent cases, collect failures and independently replay numerical artifacts. Do not repair a failed scientific candidate after final test.
- [ ] Select at most two trace-derived method candidates plus declared controls on selection tasks; freeze before transfer. Test target exclusion, missing results, ties, failures and identity retention.
- [ ] Execute the justified next experimental cycle; report negative/null findings without overstating RSI or paper replication.

### Task 4 — Review and synchronize

- [x] Run supported tests for `446e6a2` on Windows, NCC and huoshanyun with explicit skips; later source changes require relevant checks.
- [ ] Obtain whole-branch review of boundary integrity and scientific claims.
- [ ] Update README, architecture/workspaces and one results report with concrete entry points. Merge reviewed work into main; synchronize owned code and verified result copies without changing old artifacts.

## Execution record

- Baseline: `6c69c18`; development branch `feat/evidence-guided-research` in the one formal checkout. Existing user preference for a single understandable workspace takes precedence over creating another worktree.
- Fresh offline native isolation passed. First model-control qualification failed without a tool call: the backend returned routing HTTP 401 and the native client reported a revoked refresh token. Network transport was reachable. Retain this infrastructure failure; do not retry an unchanged credential or silently replace the isolated researcher with an ordinary subagent. Builder EEG work and explicitly labeled evaluator development continue independently.
- Baseline portable suite: 380 passed, 83 skipped on Windows. Linux isolation/execution skips are not counted as passes.
- Shared cloud disk was 99% full with about 82 GB free at preflight. Reuse existing EEG resources; new work is CPU bounded and storage monitored.

### Development extension: intervention reliability

With native model access unavailable, continue a real Builder experiment rather than substituting an unqualified Actor. Compare existing probe-direction removal with an independently implemented LEACE operator on EEGMAT train/validation pooled representations. [LEACE Theorems 4.2–4.3 and §4.3](https://arxiv.org/html/2306.03819v4) supply the affine zero-cross-covariance solution for continuous concepts under squared loss; this is a finite-training-distribution linear guarantee, not removal of all information or physiological causation. [Canby et al.](https://arxiv.org/html/2408.15510v2) motivate separately measuring target removal and collateral damage.

Fit transformations on training data only. Audit all 12 feature groups at layers 6 and 12, with refitted residual ridge probes and the unchanged feature definitions. Compare identity, existing probe-direction removal, LEACE, and fixed rank/damage-matched random controls where feasible. Keep every cell; do not pick favorable features after seeing results. Report training covariance residual, held-out validation recovery, displacement, non-target recovery and frozen-head behavior as separate quantities. The validation set is development evidence; no final test is opened for this extension.

Implementation: `eeg/erasure.py` provides only fitting/applying the independently derived affine operator; tests verify exact synthetic covariance removal, mean preservation, singular cases, finite inputs and a counterexample where removing a regression direction leaves recoverable information. A bounded private Builder script uses verified pooled caches. Independent numerical review precedes reporting. This adds a diagnostic experiment, not a fourth orchestration layer or a learned method gain.

The first all-cell run completed. Before interpreting its validation predictions, we identified a same-fit limitation: LEACE fitted on A forces empirical training covariance to zero, so a ridge probe also fitted on A can return near-constant predictions regardless of whether another cohort retains recoverable information. Its validation R² is not sufficient evidence of generalizing erasure. Preserve that run as an algebraic/same-fit diagnostic.

Follow-up fixed before execution: deterministically shuffle the 24 training participants with seed 230417, split into two 12-person halves, fit the eraser on one half and residual probes on the other, then evaluate on the six validation participants. Reverse the halves for sensitivity; these are two folds, not independent replication cohorts. Keep every 12-group × 2-layer cell, all operators, three fixed random controls per operator, and ridge penalties 1/10/100 (10 primary); do not select the best fold or penalty after results. This is a development analysis, not an untouched confirmation set.

### Separate research-decision diagnostic

Proceed with a fixed-executor diagnostic while native authentication is unavailable. This is a different protocol: fresh model contexts choose among frozen, precomputed real EEG operators; they do not write/run scientific code. Complete local child transcripts must verify zero tool calls. Context separation is not OS isolation. Retain protocol violations and never replace them silently.

All contexts use `gpt-6.1-sol`, high effort, four operator requests and one final report. Root mechanically forwards the frozen packet and exact operator result. No discretionary hints, parameter repair or per-condition extra information. Identical deterministic computations may be served from their independently verified cache; operator requests still consume budget. There is no test action.

Development question: whether attribute erasure generalizes beyond the samples used to fit it. Use Hjorth mobility at layer 6; two independent baseline contexts. Freeze one static expert method of at most 120 words before these trajectories. A fresh updater receives only the development trajectories and their audits, and proposes at most one answer-stripped method of at most 120 words. Record no-change or rejected proposals without replacing them.

Selection question: whether observed frozen-head changes support attribute-specific dependence rather than general representation damage. Use delta and theta log power at final layer 12. Compare baseline, expert recipe and trace-derived method, two contexts per task instance (12 episodes). These share already explored data and operators; this is selection within one platform, not independent confirmation. No winner gain is estimated without selection bias.

Pre-enrollment qualification changed the initially proposed first-attribute instances: Hjorth activity's unchanged-representation mean R² was negative in both participant halves, so it could not offer a useful positive recovery baseline. Before any decision context was created, retain the draft and choose by a declared baseline-only rule: first metadata-ordered groups with identity mean target R² above 0.25 in both halves at the requested layer. This yields mobility at 6, delta/theta at 12. No agent or method outcome was used for task choice. The two fit designs use the same frozen 12-participant eraser in each fold, with residual probes fitted on either that half or the other 12 participants; validation stays fixed.

Operators are `recovery` and `consequence`, each with exactly `method` (identity/probe_direction/leace), `fit_design` (same_sample/split_subjects), `penalty` (1/10/100); consequence additionally requires `controls` (boolean). Recovery returns target recovery, fitting provenance and covariance diagnostics. Consequence returns frozen-head behavior, other-attribute recovery and the requested matched-control results; available only at layer 12. Initial packets include scope, fit-partition roles, original baseline and these interface definitions. Counts and precision are identical for every method.

Score executed evidence and supported interpretation separately from fluent writing. A blinded audit receives each transcript and frozen rubric: supported bounded conclusion, discriminating comparison, unsupported extension, execution/protocol validity and actual requests. Root does not infer correctness from agreement with a paper. Candidate selection is validity-first: reject input/trace violations, maximize supported conclusions, minimize unsupported extensions, maximize discriminating comparisons, then minimize operator cost; ties retain baseline, otherwise prefer shorter method text. Preserve every cell and actual cost. This is researcher-method selection only, not updater improvement or ignition.

Implementation addition: a small `improvement/decision.py` validates requests, serves only exact registered catalog entries, journals immutable request/result hashes, enforces four-request budget and validates supplied source bindings. `improvement/selection.py` deterministically selects from complete, declared selection-task results and rejects target/development leakage. Unit tests cover malformed actions, budgets, catalog identity drift, incomplete score matrices, ties and excluded task roles. Root keeps actual packets, catalogs, transcripts and rubric private. No new model transport or scientist hierarchy is introduced.

Development execution completed: both baseline contexts used four operators and a final report, with zero actual tool calls in their complete traces. A condition-blinded independent audit rated both reports supported and discriminating, with no unsupported central extension. The fresh updater then returned **no_change**, explicitly because these successful traces did not establish a shared deficiency. Preserve that choice; do not request another candidate to force a change.

Before selection enrollment, freeze the resulting eight-cell comparison: baseline and the already frozen expert recipe × delta/theta tasks × two contexts. A fixed shuffle (seed 230418) sets execution order. One trusted mechanical coordinator forwards the same registered packets and exact dispatcher receipts to fresh nested contexts; its parent identity and private wrapper bytes are bound before each enrollment. This changes neither the scientific interface nor the tested methods. Complete traces verify actual model/effort/tool calls; collaboration message contents are encrypted in both sender and recipient logs, so exact input delivery cannot be independently decoded. Retain the supplied source text and this limitation. There is no learned-method arm, and this comparison cannot establish updater gain or ignition.

In parallel, a separate prospective Builder extension examines central and occipital mu/beta power contrasts in genuine motor-imagery windows. Its protocol and results stay outside every decision researcher/updater context. This adds domain-relevant measurements beyond the inherited global feature panel; it does not retroactively change the decision study or its selection rule.

The first eight-cell comparison was terminated after two observed controller transcription errors. Final disposition: two completed, two transport-failed/interrupted, one interrupted on termination, three unstarted. No selector is applied to this incomplete comparison. Both known incorrect strings, original sources, partial contexts and all failures remain retained. A separate direct-tool protocol will serve the exact public task and action receipts through a trusted gateway, with command/request/output bindings checked against complete native traces. It permits only that declared tool path and does not claim OS isolation. Qualify its actual transport before a completely new balanced comparison; do not replace only the failed cells or pool versions into a method-gain estimate.
