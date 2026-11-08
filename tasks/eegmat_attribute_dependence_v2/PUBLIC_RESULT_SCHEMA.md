# Candidate output contract

The trusted worker runs `main.py` with the documented `--split`, `--input`,
`--train`, `--public`, and `--output` arguments. Save NumPy NPZ files under the
output directory. Do not submit metric scalars, labels, subject identifiers,
target values, JSON claims, pickle objects, structured dtypes, nested archives,
or extra arrays inside these files. Metrics are calculated by the trusted
aggregator against separately held truth. No candidate file is executed there.

All numeric evidence must be finite; floats of at most 64 bits are accepted.
Integer index arrays must use integer dtypes. Preserve the evaluation input's
`sample_ids` values and order exactly. NPZ headers, array shapes, archive members,
and decompressed byte lengths are checked before allocation. Each archive is
limited to 512 MiB, arrays to 4,096 rows, and headers to 10,000 bytes.

## Baseline stage

Write only the following arrays in `results.npz`:

| Array | Shape | Meaning |
| --- | --- | --- |
| `sample_ids` | `(N,)` | Exact evaluation row identifiers |
| `logits` | `(N,)` | Original binary task logits; nonnegative predicts class 1 |

The baseline stage measures the task and reports zero completed scientific
groups. A baseline result alone does not answer Q1, Q2, or Q3.

## Q1 analysis stage

Keep `results.npz` and add `analysis.npz` with exactly these arrays:

| Array | Shape | Meaning |
| --- | --- | --- |
| `sample_ids` | `(N,)` | Exact evaluation row identifiers |
| `feature_predictions` | `(N,2,62)` | Target predictions for layers 6 and 12, in that order |
| `negative_predictions` | `(N,2,62)` | Predictions from the diagnostic randomized-training-target control |
| `negative_train_permutation` | `(T,)` | Training row indices used for target randomization |

`N` is the evaluation row count and `T` the training row count. The 62 target
columns follow the public feature registry order: the first ten entries each
have mean, standard deviation, median, q25, q75, and maximum columns; the final
two entries have one column each. Group indices 0–11 follow that registry order.
Fit all transformations and learned parameters on training rows; validation may
select choices. Never use evaluation targets as predictions.

The negative control must bijectively derange complete participant blocks and
change within-block row alignment. Every active target column must change.
Its predictions are evaluated against the original held-out targets. This is a
diagnostic randomized-target control, not a permutation significance test. The
numeric permutation is inspected; source review is still needed to verify that
the model was actually fitted using it.

The aggregator computes raw, unclipped column R² and group means. Columns
constant in training are excluded and counted. Constant evaluation columns have
undefined R² and are counted; undefined scalars are omitted rather than replaced
by zero. Participant bootstrap resamples retain all that participant's rows
together. Reports contain marginal 95% intervals and approximate family-adjusted
intervals over 24 feature/layer groups. Q1 without intervention evidence is an
honest partial result and reports `q1_only=1`.

## Q2 and Q3 evidence obligations

The two distinct feature groups and their layers are selected by the best
validation group R², never by task accuracy or test scores. Ties use ascending
group index and then ascending layer. Selection must be frozen before test:
either the trusted controller enrolls a private validation selection binding, or
the frozen candidate contains `validation_selection.npz` with only
`sample_ids (V,)` and `feature_predictions (V,2,62)` for validation rows.
For the latter route, the same candidate digest must pass validation; the file
must exactly match the submitted validation predictions. The trusted controller
recomputes selection from those frozen predictions and private validation truth.
Candidate-supplied selection scores are never accepted.

Add `interventions.npz` with exactly these arrays. The first axis indexes the two
selected feature/layer pairs. The four-variant axis orders the learned
intervention, then the three random controls declared with seeds 1301, 1302,
1303. This contract specifies evidence, not an intervention implementation.

| Array | Shape | Meaning |
| --- | --- | --- |
| `sample_ids` | `(N,)` | Exact evaluation row identifiers |
| `selected_groups` | `(2,)` | Validation-selected group indices |
| `selected_layers` | `(2,)` | Corresponding layers, 6 or 12 |
| `directions` | `(2,200,6)` | Learned directions; active target columns first, remainder zero padded |
| `control_directions` | `(2,3,200,6)` | Three control direction sets |
| `original_pooled` | `(2,N,200)` | Original pooled activation for each selected pair |
| `altered_pooled` | `(2,4,N,200)` | Pooled activation after each intervention/control |
| `altered_logits` | `(2,4,N)` | Resulting task logits after the remaining frozen model and head |
| `residual_predictions` | `(2,4,N,62)` | Residual feature predictions after each intervention/control |

Directions must have positive numerical rank. Controls must have the same actual
rank, have distinct spans, and match the learned intervention's shift norm in
every window. The aggregator derives shifts from original minus altered pooled
activations and verifies their membership in the respective direction spans.
Both norm matching and span residuals use an absolute tolerance of `1e-8` plus
`1e-6` times the relevant learned/recorded shift norm. Compute pooled evidence
from the actual original and modified token arrays with float64 accumulation
(for example, `tokens.mean(axis=(1, 2), dtype=np.float64)`). Converting an already
computed float32 mean to float64 does not recover its rounding error. The model
tokens may remain float32; do not substitute intended shifts for measured pooled
values. Validate both constraints locally before requesting evaluation.
It computes task changes and the primary paired contrast: learned balanced
accuracy change minus the mean change across the three controls. It also
evaluates residual recovery for each selected feature group and variant.
Residual models must be refitted on altered training representations, with any
choice made on altered validation representations before test.

The numeric checks establish evidence consistency. They cannot prove training
provenance, random seed use, application of the same shift to every token,
execution of the remaining frozen layers/head, or residual refitting. Those
claims require source review and independent replay. A supplied scalar claim
never substitutes for the required arrays. An unestimable group or missing
Q2/Q3 evidence must be reported as partial. Representation sensitivity does not
establish physiological causation; recoverability alone does not establish
prediction reliance.

## Released results

Only predetermined finite scalar metric names are released. Original task
metrics use `accuracy`, `balanced_accuracy`, and `auroc`. Q1 prefixes are
`q1_l6_g00_` through `q1_l12_g11_`; suffixes include `r2`, `negative_r2`,
`r2_minus_negative`, column counts, and interval endpoints. Q2 prefixes are
`q2_s0_` and `q2_s1_`; Q3 prefixes are `q3_s0_` and `q3_s1_`.
Coverage fields include `baseline_only`, `q1_only`, `q1_groups`,
`q2_interventions`, `q3_residual_groups`, and `numeric_scope_complete`.
Undefined estimates are absent and coverage/count fields explain the scope.

Candidate arrays and the trusted detailed analysis remain private. The public
artifact is the worker's `released_metrics.json`. Do not create
`trusted_analysis.json`; that filename is reserved for trusted aggregation.

The executable schema permits partial results, but the v2 task advisory
obligations in `EVIDENCE_POLICY.json` request Q1 groups >=24, matched
interventions >=2 and residual-refit groups >=2. Report omissions explicitly.
These counts are evidence coverage, never independent validation of scientific
claims. A completed episode may still be scientifically incomplete.
