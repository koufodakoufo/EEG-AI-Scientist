# Released residual evidence

Successful validation results release finite numeric `metrics` and artifact
path/SHA records for `released_metrics.json` and trusted `baseline_identity.json`.
Test results release only the metrics artifact. Artifact records are hashes,
not downloads or file bodies. Predictions, truths, report bytes and other
private aggregate artifacts remain private. Test metrics remain sealed until
the existing reporting stage. Undefined scalar values are omitted, never zero.

R² is `1 - SSE / evaluation-centered SST`, unclipped, with equal weight over
a fixed target mask: B-training-active AND evaluation-estimable. Estimability
uses centered second moment `> 1e-12 * max(1, mean(y**2))`. The same mask applies
to all views/models/draws; an empty mask fails. B-training-mean predictions are
a separately reported comparator and generally differ from evaluation-mean
R² zero.

Uncertainty uses 10,000 paired sorted-participant bootstrap draws with PCG64
seed 230419 and linear percentile quantiles .025/.975. A non-estimable retained
column invalidates the entire common draw. Any invalid draw makes intervals
null and useful-effect gates inconclusive. Intervals condition on frozen fits;
the fixed shuffle is a diagnostic control, not a permutation p-value.

Available finite scalar fields:

- Schema/lifecycle: `model_count`, `view_count`, `target_count`, `baseline_only`,
  `numeric_scope_complete`, `included_target_count`; `target_column{i}_included`
  for i=0..5 (original columns 12–17).
- Scores: `{view}__{model}__r2` for present models and `train_mean`;
  `{view}__{model}__column{i}_r2` for authored models. The B-mean column scores
  appear once as `train_mean__column{i}_r2`.
- Bootstrap: `bootstrap_requested`, `bootstrap_valid`, `bootstrap_invalid`,
  `intervals_valid`. Primary final contrast: `primary_delta`, and when defined,
  `primary_ci95_low`, `primary_ci95_high`.
- Existing shuffled comparisons: `{view}__{contrast}__delta`, `__ci95_low`,
  `__ci95_high` for `leace/linear_minus_shuffled`,
  `leace/flexible_minus_shuffled`, `identity/flexible_minus_shuffled`.
  Flexible contrasts are absent at baseline; null intervals are absent.
- Leave-one-participant-out diagnostics: `loo_p{i}__valid` for i=0..5, then
  if valid `loo_p{i}__leace_linear_r2`, and at final
  `loo_p{i}__leace_flexible_r2`, `loo_p{i}__primary_delta`. Ordinals refer to
  omitted participants in fixed sorted-ID order within that cohort. No
  participant IDs are released; undefined omissions have only `valid=0`.
- Registered gate flags `registered_useful_effect`, `registered_linear_recovery`
  and `identity_gate_passed` are 1 only when passed; use interval validity and
  the numerical evidence to distinguish negative from inconclusive results.

Per-column and omission diagnostics cannot select new primary claims. A valid
negative/inconclusive scientific result can satisfy lifecycle completion.
Review source/fit/replay validity and the six-participant, prior-exposure
limitations separately; workflow completion is not scientific resolution.
