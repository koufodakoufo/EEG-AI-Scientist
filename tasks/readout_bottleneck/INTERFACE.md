# Isolated readout episode interface

Each session starts a fresh conversation and control home. Your case directory
persists. Only `public/` and the immutable launch prompt's trusted projection
are authoritative. Your notes and candidates may persist in `output/`.

Write a JSON array of at most 16 requests to the exact request filename in the
launch prompt, normally `output/requests-session-NN.json`. The total limit is
1 MiB and each request is at most 64 KiB. Each envelope has exactly:

```json
{"request_id":"unique-id","episode_id":"FROM_PROMPT","operation":"brief","payload":{"path":"brief.md"}}
```

Use unique IDs. Repeating identical content with the same ID replays its
response; changing that content is rejected. Correct a rejected request with a
new ID. Paths are relative to `output/`, contain no links, and cannot escape.
Requests execute only after the session ends cleanly and processes are cleaned
up. End the session after writing the batch.

| Operation | Exact payload | Prerequisite |
| --- | --- | --- |
| brief | `{"path":"brief.md"}` | Initial or rejected brief |
| contract | `{"protocol":{...}}` | Brief approved; once |
| baseline | `{"candidate_dir":"baseline","split":"validation","title":"..."}` | Frozen contract; once |
| attempt | `{"candidate_dir":"candidate","split":"validation","title":"..."}` | Successful baseline; before lock |
| lock | `{"attempt_id":"A2","candidate_digest":"FROM_RESPONSE"}` | Successfully evaluated candidate |
| test | `{"candidate_digest":"FROM_RESPONSE","split":"test"}` | Matching lock; exactly once |
| report | `{"path":"REPORT.md"}` | Successful baseline, iteration, and final test |

Start the brief with this fenced JSON scope followed by a substantive research
plan. The contract protocol contains the same fields plus
`"research_mode":"analysis"` and your scientific decisions and limitations.

```json
{"task":"eegmmidb-cached-readout-bottleneck","public_resources_only":true,"backbone_frozen":true,"head_frozen":true,"selection_split":"validation","test_after_lock_only":true,"gpu":0,"cached_inputs_only":true,"train_only_readouts":true}
```

Scope approval is mechanical, not scientific endorsement. The contract becomes
immutable. A normal flow is brief; contract plus baseline; scientific iteration;
lock plus test; report. A sixth session is available within the same budget.
Limits are six model sessions, 600 seconds per session, 2,700 seconds total
episode wall time, four CPU threads, 12 GiB RAM, no GPU, and no tool network.
Every session, including failure, consumes its allocation. There is one
baseline, at most two scientific iterations, and one final test. No extra budget
or outcome-dependent retry is available. Any permitted validation correction
uses the remaining iteration and session allocation and stays in the record.

Candidates contain at most 256 regular files and 64 MiB. Workers allow one
process with up to four active CPU threads; use in-process or threading
backends. Do not use multiprocessing, joblib process backends, subprocesses, or
background processes. `/tmp` is limited to 64 MiB. Worker jobs are capped at
900 seconds and must fit the remaining episode budget.

The trusted worker invokes exactly:

```text
python -B /candidate/main.py --split validation|test --input /inputs/evaluation.npz --train /inputs/train.npz --public /public --output /out
```

The working directory is `/candidate`. All candidate source and frozen numeric
parameters must be inside that tree; use no host absolute paths. `--input`
contains only `x`, `sample_ids`, and `subject_ids`. `--train` contains public
training data. Public validation is permitted for frozen choices. Preserve
evaluation row order exactly. Only `results.npz` is emitted for evaluation.

Include a deterministic replay entry point:

```text
python -B /candidate/fit.py --public /public --output /out/refit
```

It must reproduce all fitted numeric parameters from public training and
validation resources and candidate source, writing numeric `parameters.npz`.
Learn parameters on training rows; validation may select among fits. It may
not copy or read the candidate's existing fitted parameters as its fitting
result. Do not use pickle. The auditor can remove frozen parameter files,
rebuild them from source, and replay predictions. Keep the parameter archive
keys, shapes, dtypes, and inference usage documented in the candidate. Matching
numeric arrays is required across repeated fits; the ZIP container timestamp
does not establish a numeric difference.

An original-only baseline is allowed. Mechanical completion requires locking a
scientific iteration with at least two declared readouts including a
representation readout, followed by successful final-test evidence for those
readouts. It does not certify valid comparisons, genuine controls, or sufficient scientific
coverage. These require subsequent source, fit, prediction, and statistical
audit.
