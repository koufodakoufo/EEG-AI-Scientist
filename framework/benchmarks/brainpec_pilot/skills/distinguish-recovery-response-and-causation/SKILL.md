---
name: distinguish-recovery-response-and-causation
description: Use when a study compares measured-property recovery from a representation with a fixed predictor’s response to permitted input edits, especially with grouped observations and limited validation data.
---

Treat recovery, target prediction, and fixed-predictor response as separate estimands. This procedure may help select discriminating controls and calibrate conclusions; its incremental benefit remains untested.

1. **Choose the claim before the control.** If asking whether information is recoverable, fit representation-to-property probes. If asking whether a measured property predicts the target, fit transparent property-to-target predictors separately. If asking whether the fixed predictor responds, evaluate documented edits with observed targets unchanged. Reserve causal interpretation for the manipulated computational input and fixed predictor; these experiments alone do not identify causes in the data-generating process.

2. **Bound the recovery question.** Compare a declared simple probe with a bounded nonlinear expansion, using training-only preprocessing and fitting. Define the regression reference explicitly: validation-centered \(R^2\) and error relative to a training-mean predictor use different baselines. If tested probes fail, conclude limited recovery under those families. Do not infer information-theoretic absence. If recovery approaches numerical precision, audit direct equality before describing the result as learned decoding.

3. **Choose controls that separate explanations.** Use dependence-preserving training-label permutations with refitting to assess accessibility or target prediction, provided group exchangeability and within-group correspondence are defensible. If class proportions differ across partitions, inspect null performance and class balance before interpreting improvement over a training-majority baseline. If recovery and fixed-predictor behavior differ, inspect permitted predictor code and localize associations before choosing targeted edits.

4. **Distinguish intervention mechanisms.** Replacement, sign reversal, and block permutation change inputs differently. If their results disagree, inspect score contributions and transformation definitions rather than pooling estimates. Record score changes, prediction flips, and paired corrected versus introduced errors alongside accuracy. Unchanged accuracy can conceal changed decisions; unchanged decisions can conceal changed scores. If retaining a subset produces constant scores, inspect threshold behavior before attributing predictive value to that subset.

5. **Interpret component subtraction narrowly.** If using property-associated subtraction, fit the property-to-representation map on training data, define centering, and retain approximation quality for every edited component. Describe the operation as removal of a fitted association. Correlated properties and incidental changes across inputs prevent unique attribution to a property’s causal mechanism.

6. **Let uncertainty determine the next step.** Use paired group resampling for comparisons on shared observations. State that validation resampling conditions on the fitted training sample. Keep edit-randomization intervals separate from sampling intervals. If an interval includes or touches no change, retain an inconclusive comparison. If only one context is observed, stop cross-context inference.

Freeze model families, selection policy, and computational allocations before comparisons. Disclose later changes. Within the task’s existing budget, prioritize unresolved distinctions over redundant edits; stop after planned controls and verification unless a specific discrepancy remains.

Require executed outputs, model settings, input hashes, commands, and claim-to-evidence links. Keep scientific artifacts deterministic and timing logs separate. Retain full negative and alternative findings even when claims are concise.

This procedure applies to permitted representation probes and artificial fixed-predictor interventions. It was distilled from one synthetic development episode and is not proven to improve performance.