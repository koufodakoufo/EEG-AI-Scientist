# Cached readout evidence contract

Freeze `readouts.json` inside the candidate directory. It contains exactly
`schema_version`, `readouts`, and optionally `primary_contrast`:

```json
{"schema_version":"cached_readout_manifest_v1","readouts":[{"name":"original","role":"original","description":"Unchanged original classifier score"},{"name":"representation_fit","role":"representation","description":"Training-fitted representation readout"}],"primary_contrast":["representation_fit","original"]}
```

This example declares an interface, not a required method. There are one to six
records. Each record has exactly `name`, `role`, and `description`. Names are
semantic lowercase letters, digits, or underscores, at most 32 characters, and
unique. Descriptions contain 1 to 1,000 nonblank characters; the manifest is at
most 16 KiB. Exactly one readout has role `original`; it is first and named
`original`. Other roles are `representation`, `attributes`, `calibration`,
`random`, or `other`. Descriptions state what was fitted and which inputs were
used. Optional `primary_contrast` is a pair of distinct declared names in
left-minus-right order. Declare it before locking the candidate. Roles describe
claims that later source review must verify.

Write exactly one evaluation output file, `results.npz`, with exactly:

| Array | Shape | Meaning |
| --- | --- | --- |
| `sample_ids` | `(N,)` | Input sample identifiers in exact input order |
| `readout_names` | `(K,)` | Frozen manifest names in exact manifest order |
| `logits` | `(N,K)` | Finite binary decision scores for each declared readout |

The first score column must equal the bound input's `x[:,262]` exactly. Even a
small sign or ranking change is rejected. Original metrics use the canonical
bound scores. All readouts predict class 1 at a score greater than or equal to
zero. AUROC uses score ranking with half credit for ties; log loss uses the
logistic transform of scores. Supply logits consistent with that interpretation.

Do not emit labels, participant IDs, targets, scalar metrics, extra arrays,
pickle objects, structured dtypes, nested archives, or additional output files.
All scores must be finite floating-point values of at most 64 bits. IDs and names use
safe integer or string arrays as appropriate, never object arrays. Archives are
limited to 16 MiB including decompressed members, arrays to 4,096 rows, and
headers to 10,000 bytes. Shapes and byte lengths are checked before allocation.
The trusted scorer never executes candidate code.

The evaluator reports each readout's balanced accuracy, AUROC, and log loss.
Balanced-accuracy intervals and contrasts use 10,000 participant-bootstrap draws
with seed 161803; every readout shares the same draws. It reports marginal 95%
intervals, the declared primary contrast's 95% interval when present, all
pairwise balanced-accuracy differences with 95% intervals, and Bonferroni
intervals over the actual number of pairs. A useful balanced-accuracy margin is
0.03. Combined test evidence is primary. Diagnostic and confirmation subsets
are descriptive and released together after the same sealed evaluation.

Only predefined finite scalar metrics are released through
`released_metrics.json`. Per-readout prefixes identify manifest positions
(`readout_i0_` through `readout_i5_`); pairwise prefixes identify positions
(`contrast_i0_i1_`, and so on). Coverage scalars include `readout_count`,
`representation_readouts`, `baseline_only`, and `numeric_scope_complete`.
Undefined estimates are omitted. Coverage is about declared numerical evidence,
not verified scientific meaning. Detailed trusted analysis, per-row candidate
outputs, hidden truth, and cohort membership remain private.

Include `fit.py` and the frozen numeric `parameters.npz` in every candidate,
including an original-only candidate whose parameter archive may be empty.
The fitting replay ABI and audit requirements are in `INTERFACE.md`. Source
semantics, train-only provenance, deterministic refits, full-prediction replay,
and claim support must be checked independently before scientific coverage or
valid discrimination is credited.
