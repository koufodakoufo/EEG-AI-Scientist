# Cached numeric API

All NPZ archives use `allow_pickle=False`, exact member sets, finite numeric
values, unique opaque sample IDs and preserved row order. Features and targets
are float64. IDs are Unicode; they are alignment keys, never predictors.

| Archive | Exact members |
| --- | --- |
| Public `train.npz` (B, 288 rows) | `x[N,5,200]`, `y[N,6]`, `sample_ids[N]`, `subject_ids[N]` |
| Public `validation.npz` (144 rows) | Same keys and dimensions |
| Inference (validation/test; 144 rows) | `x[N,5,200]`, `sample_ids[N]`, `subject_ids[N]` |
| Scientific `results.npz` | `predictions:float64[N,5,M,6]`, `sample_ids:Unicode[N]` |

`M=2` for baseline and `M=4` for final. View/model order is fixed in TASK.md.
All splits have disjoint samples and participants. The training set has
12 participants with 24 windows each; validation and test each have six.

`method.json` is bounded to 64 KiB with no duplicate keys or nonfinite JSON.
Its exact keys are `schema_version` (`residual_recovery_method_v1`), `phase`
(`baseline`/`final`), `baseline_sources`, `families`, `parameter_schema`.
`baseline_sources` is a sorted nonempty unique list of safe relative UTF-8
paths covering every actor-authored dependency of linear fit/prediction,
including imported helpers. No links, binary parameters or path escapes.
Source audit checks that closure; a declaration alone cannot establish it.
Top-level orchestration wrappers may append flexible work without changing
baseline behavior.

`families` contains exactly `linear` at baseline, then `linear` and `flexible`.
Each family contains exactly a nonempty `description` and `recipes`, mapping
the five fixed view names to one to four objects. Each recipe contains
`preprocessing` and `hyperparameters` objects. Freeze all linear declarations
and baseline source paths/content across phases.

`parameter_schema` declares every numeric archive key with exactly `dtype`,
`shape`, `purpose`. Use namespaces `linear__`, `linear_shuffled__`, and at final
`flexible__`, `flexible_shuffled__`. Required keys are `linear__selected` and
at final `flexible__selected`, both int64[5], indexing the selected recipe in
each view. Shuffled fits reuse those indices and may not add selected keys.
Actual dtypes/shapes must match the declaration. Baseline numeric namespaces
remain identical across phases. Arrays are bounded to 128 total, rank <= 4,
1,000,000 elements each, 1 MiB compressed and 8 MiB expanded overall; no pickle.

Only the trusted scorer creates `baseline_identity.json`, binding baseline
source bytes, linear declarations, parameter schemas, selected indices,
dtype/shape/C-order numeric hashes and the two baseline validation prediction
arrays, plus ordered inference/public manifest identity. The researcher
receives only its path/hash, bound to the successful validation job. Never
emit a candidate fingerprint or try to supply one to lock. Matching numbers
on different rows or from a different job cannot establish parity.
