# R09 independent scientific implementation review

Review date: 2026-10-29. Builder review only, within the R09 allocation. No server operations, additional agents/model calls, commits, real EEG reads, checkpoint reads, or real reference-result reads were performed. Only the pinned public model **source code**, implementation, protocol, and artificial engineering fixtures were inspected.

## Findings and dispositions

1. **P1: representation caches were not bound to the frozen computation.** The original cache receipt checked its NPZ and prepared-input digests, but omitted producer code/model/runtime identity. The original reference lock also omitted the development representation files and receipts. Thus a cache from an earlier producer could be reused while later code was frozen, and post-freeze cache corruption was outside the reference lock. Root added producer provenance and froze development caches, receipts, and model resources. R09 independently verified rejection of changed producer identity and a tampered development cache before a test reservation is written.

2. **P1: the original participant-block negative control retained condition/window alignment.** A synthetic 24-participant fixture with 12 zeros followed by 12 ones per participant showed that every target remained identical after the original participant derangement, despite zero same-participant assignments. This could not serve as a general destroyed-association control for condition-linked features. Root changed the protocol and implementation before real outcomes: derange participants and independently permute rows inside each destination participant block, verify that each active target column changes, and identify the result as a diagnostic randomized-target control rather than a permutation significance test. R09 verified preserved destination-block distributions, no same-participant target assignment, and broken condition alignment.

3. **P2: unestimable panels could still report complete Q1–Q3 scope.** An empty eligible intervention list was compatible with the original unconditional `real_reference_complete` / `Q1-Q3` result. Root added explicit estimable-scope reporting. R09's final end-to-end fixture now requires `real_reference_partial`, 22 estimable feature-layer groups, and two nonzero-rank interventions because its deliberately constant feature contributes two unestimable groups. Empty and zero-rank intervention coverage tests also pass.

Evidence for the original code and synthetic reproduction is retained under `.local/research/2026-10-29-brainpec-real/review-R09/`. `initial-findings.json` distinguishes the initial synthetic lock's source hashes from hashes observed after the root patch; its negative-control boolean is explicitly marked post-fix. Old evidence has not been presented as current code behavior.

## Engineering verification

The new `framework/tests/test_real_reference_integration.py` runs a complete private prepare/test lifecycle using a dummy nonlinear 12-layer PyTorch model with a nontrivial final LayerNorm, artificial EEG-shaped arrays `(N,20,5,200)`, and artificial 62-column targets. There are exactly 24/6/6 synthetic participants and four rows per participant. These are **not EEG measurements**, pretrained CBraMod outputs, or scientific reference outcomes. Resource provenance is explicitly injected for this artificial model, and the official model resource list is empty only inside the test monkeypatch.

The fixture executes all 24 feature-layer probes, train-only transforms and ridge fits, validation-only selection, frozen logistic head application, two distinct intervention groups, learned and three rank/strength-matched controls, residual probes, and the full 2,000 participant-bootstrap loop. It creates its synthetic test file only after a test reservation exists and rejects a second evaluation. Assertions cover:

- JSON serialization/deserialization preserving predictions and train means;
- mixed constant and active target columns, including an entirely constant feature group;
- resumed versus uninterrupted model continuation at layers 6 and 12, including the final norm;
- replayed intervention logits and per-window float32 control-norm matching;
- erasure of the fitted readout directions while preserving the orthogonal complement;
- public/private feature definitions, activations, continuation, and sanitized-head prediction parity;
- producer-provenance changes and locked representation-cache tampering.

Initial integration run before production fixes: **6 passed in 32.02 s**, `synthetic-pytest-02.log`. After provenance/randomized-control fixes: **41 passed, 1 skipped in 14.28 s**, `synthetic-pytest-03.log`, across integration, reference, scientific primitives, data adapters and public-view tests. The skip is the preexisting Windows test that cannot create a symlink without host permission. An earlier test invocation failed to create its missing evidence-directory parent; no scientific code executed in that fixture setup, and the parent was created before the recorded successful runs.

Final verification after the estimable-scope patch: **42 passed, 1 skipped in 29.91 s**, `synthetic-pytest-04.log`. The skip reason was confirmed as Windows symlink creation privilege, `WinError 1314`. The full command was `python -m pytest framework/tests/test_real_reference_integration.py framework/tests/test_real_reference.py framework/tests/test_real_science.py framework/tests/test_real_data.py framework/tests/research_bench/test_real_public.py -q -rs --basetemp .local/research/2026-10-29-brainpec-real/review-R09/synthetic-pytest-04`, with `PYTHONPATH` set to this workspace's `framework` and numerical thread limits set to four. R09's end-to-end fixture artifacts stay under the explicitly named workspace evidence directory; existing unittest tests use their normal ephemeral temporary directories.

## Scientific and protocol assessment

The inspected official source puts temporal/spectral and positional embedding inside `patch_embedding`; the CPU adapter's subsequent encoder-layer traversal matches the model's forward path. `continue_from(layer=k)` starts at the following layer, applies the encoder norm once, and uses the Identity projection established after strict checkpoint loading. Source review and generic-model tests support this path; R09 did not load the real checkpoint.

Ridge transforms and logistic-head scaling are fitted on training rows only. The declared ascending grids make existing first-maximum selection prefer smaller regularization values on ties. Interventions are selected by validation feature recovery rather than task accuracy. Probe directions correctly undo representation scaling before the Euclidean SVD projection. Learned and random controls use the same actual rank and per-window shift norm; their bases are stable across splits for each fixed seed. Float32 realization error is measured and saved. The primary Q2 contrast is algebraically the declared learned accuracy change minus the mean random accuracy change, since the original accuracy cancels.

The bootstrap resamples whole participants with both conditions/all windows together. Q1's 24-group Bonferroni confidence level and Q2's two-group 97.5% confidence level match the protocol. These percentile intervals remain approximate, especially with six test participants; the Q1 extreme tails use roughly two order statistics among 2,000 resamples. A single randomized-target fit is a diagnostic baseline, not a permutation-derived p-value. Negative raw R2 and null/negative task effects remain legitimate outcomes.

Residual recovery is evaluated at the altered intervention layer with refitted train probes and validation-selected alpha. It does not show the absence of information under arbitrary nonlinear decoders, nor rule out recovery at later layers. Equal rank and shift norm control broad perturbation magnitude; they do not prove target-specific physiological mechanisms or equivalent off-distribution effects. Strong residual recovery must weaken any claim that the feature was removed.

This remains a new frozen-pretrained-backbone EEGMAT adaptation with a newly fitted head. It is not replication of a BrainPEC downstream task checkpoint, a clinical stress/depression diagnosis, or a demonstration of physiological causation. Fixed background-before-arithmetic acquisition can confound condition with order/session effects. The 30 Hz versus 45 Hz metadata issue requires actual EDF-header evidence from the trusted data audit; R09 has not read those headers. High-frequency feature interpretations and generalization beyond six held-out participants remain qualified.

The reference protocol is frozen by hash, while numerical settings are presently duplicated as constants in the implementation. They agree in this review; any subsequent protocol edit must be reflected in code and tested before a fresh freeze. Prepared-data correctness and exact subject membership ultimately rely on the trusted preprocessing/public-view validation path; this synthetic review does not independently certify the downloaded records.

## Final disposition

All three findings are fixed and independently exercised. No additional continuation, probe-direction, selection-leakage, serialization, per-row strength, or paired-contrast error was found in the inspected synthetic paths. No remaining blocking defect was identified within this review's scope. Passing these engineering tests provides no claim about real model accuracy, real feature recovery, or the outcome of the scientific questions. The authorized real-data execution, real checkpoint verification, final held-out evaluation, and scientific interpretation remain the main Builder's separate responsibility.
