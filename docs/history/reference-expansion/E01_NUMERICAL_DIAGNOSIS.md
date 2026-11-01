# E01 A2 validation: intervention precision diagnosis

Date: 2026-10-30, R53 Builder diagnostic. **The evidence supports a candidate
pooling-precision defect; it does not justify changing the frozen evaluator.**
Float64 accumulation on the existing public validation token cache satisfies the
current norm and span thresholds while retaining float32 model tokens. E01 A2's
submitted evidence remains invalid and its blocked result remains preserved.

## Scope and preserved evidence

Only A2 validation evidence, its frozen candidate source/fit parameters, the public
contract, and the public validation layer-token cache were inspected. No final
test, private gold, frozen reference implementation, downstream model replay, or
scientific scoring was used. No original evidence or evaluator was changed.

The worker completed with exit code 0 in 8.941 seconds. Trusted aggregation then
raised `ValueError: Control strength must match each individual window` at
`real_aggregate.py:495`. The D02 diagnostic copy of `interventions.npz` is identical
to the worker output (SHA-256
`7b10ee6dcdc4f8dae217d232859894bf12995ab9b48a23d8b96936143fb57399`).
The public result contract requires matching control strength per window and
membership in each declared direction span; accepting floats up to 64 bits does
not guarantee those properties after lower-precision arithmetic.

The read-only script is
[`diagnose_intervention_precision.py`](../../../scripts/research/diagnose_intervention_precision.py).
It reads only directions, centers, pooled evidence, and selected layer tokens;
it does not import or execute candidate/model/scorer code. Machine paths, hashes,
environment, execution record, and full numeric summaries are kept in ignored
`.local/research/2026-10-30-extension/E01/` (`precision-diagnosis.json`,
`provenance.json`, and `REPRODUCE.md`).

## What actually failed

Both selected pairs use layer 6, 144 windows, and rank-6 directions. Each control
has the same rank and a distinct span. The frozen checks use
`1e-8 + 1e-6 * learned_shift_norm` for strength and the corresponding shift norm
for span residuals.

| Saved worker evidence | Group 5 | Group 7 |
| --- | ---: | ---: |
| Learned shift norm, min–max | 0.00523–0.07691 | 0.00243–0.03451 |
| Norm failures by control, out of 144 each | 1 / 1 / 2 | 9 / 11 / 6 |
| Distinct windows with a norm failure | 3 | 21 |
| Maximum absolute norm mismatch | 3.293e-8 | 3.417e-8 |
| Span failures, four variants × 144 | 576 / 576 | 576 / 576 |
| Maximum span residual L2 | 1.643e-7 | 1.689e-7 |
| Maximum span residual / allowed error | 8.54 | 10.01 |

Merely bypassing the norm exception would reveal the second failure: all 1,152
variant-window span checks fail. Independently reconstructing the intended
float64 shifts from saved pooled values, centers, and directions gives zero norm
or span failures. The maximum intended norm mismatch is 1.388e-17 and maximum
intended span residual is 5.400e-17. Thus the projection and norm-matching algebra
does not explain the observed discrepancy.

## Where the error enters

Candidate `main.py` computes original and altered pooled values using
`tokens.mean(axis=(1,2)).astype(np.float64)`. `analysis_core.altered_tokens`
subtracts the intended float64 shift and casts each altered token to float32.
Consequently both means accumulate in float32; converting their results to
float64 cannot recover the lost precision. The saved pooled arrays are float64
containers whose values round-trip through float32 exactly.

The controlled experiment keeps intended shifts fixed and changes only averaging
precision over the public validation cache and its calculated altered tokens:

| Float32 tokens, float64 means | Group 5 | Group 7 |
| --- | ---: | ---: |
| Norm failures | 0 / 432 | 0 / 432 |
| Span failures | 0 / 576 | 0 / 576 |
| Maximum norm mismatch | 2.934e-9 | 2.933e-9 |
| Maximum span residual L2 | 1.191e-8 | 1.215e-8 |
| Maximum span residual / allowed error | 0.676 | 0.884 |
| Maximum L2 error from float32 accumulation | 1.621e-7 | 1.614e-7 |
| Maximum L2 error remaining from token rounding | 1.206e-8 | 1.226e-8 |

Both original and altered means use `dtype=np.float64`; token values passed to
model continuation remain float32. Removing token rounding as a diagnostic
control reduces span residuals further to at most 1.057e-15. The script also
records the directly measured token-cast error and its absolute-error envelope,
separately from accumulation error.

**Replay limitation:** cached public tokens differ numerically from the worker's
unretained live activations: original pooled components differ by at most
1.155e-7; altered pooled components by at most 1.416e-7. The cache experiment is a
controlled arithmetic test on actual validation representations, not a bit-exact
replay of the worker. It establishes that the current thresholds are attainable
with this representation and method; it does not certify a repaired worker job.

An independent synthetic reproduction (seed 20261030; 144 × 20 × 5 × 200 float32
tokens; four independently generated rank-6 bases) also fails: float32 averaging
produces 2 / 432 norm failures and 576 / 576 span failures. Float64 averaging
produces zero failures of either kind. No EEG labels, targets, selected feature
values, or model weights are needed to reproduce the numerical mechanism.

## Principled correction and version boundary

1. For a future candidate, accumulate original and altered pooled activations in
   float64 (`mean(..., dtype=np.float64)`), and use that convention consistently
   for probe fitting, validation selection, intervention construction, residual
   refitting, and inference evidence. Retain the actual float32 altered tokens
   for continuation through the frozen model and head. Verify evidence from
   those actual tokens before submission.
2. Do not replace recorded altered pooled values with ideal `original - shift`
   values: that would hide execution error rather than document the intervention
   actually applied. A float64 cast after a float32 mean is also insufficient.
3. Preserve E01 A2 and the frozen evaluator. A candidate correction requires a
   newly identified candidate/attempt and its own authorized lifecycle; it cannot
   rewrite A2's files, digest, or failed result. The current episode's failed-job
   rule and exhausted session allocation must be respected by the controller.
4. Publish general accumulator-precision guidance and executable numerical
   constraints prospectively and symmetrically for future conditions. Do not
   inject this Builder diagnosis into an ongoing isolated Actor. Any change to
   evidence semantics, tolerances, schema, or evaluation requires a separately
   frozen task/evaluator version and cannot retroactively rescue E01.

No tolerance increase is proposed. Float32 token rounding is nonzero, but it
passes the current thresholds in both controlled examples. This is numerical
evidence validation only; no Q1/Q2/Q3 scientific success follows from it.
