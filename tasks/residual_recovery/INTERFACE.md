# Residual recovery coding interface

Use the audited delegated coding interface in your launch prompt. Native
isolated episodes are not supported for this task. Only `public/` and the
trusted projection are authoritative; save source and notes in `output/`.

Start your substantive research brief with this fenced JSON. The contract
protocol includes these same fields plus `"research_mode":"analysis"` and
your decisions and limitations.

```json
{"task":"eegmat-cached-residual-recovery","public_resources_only":true,"backbone_frozen":true,"head_frozen":true,"selection_split":"validation","test_after_lock_only":true,"gpu":0,"cached_inputs_only":true,"train_only_readouts":true}
```

Write the requested JSON array of at most 16 requests to the exact filename
in the launch prompt. Each request is at most 64 KiB, the file at most 1 MiB.
Envelopes have exactly `request_id`, `episode_id`, `operation`, `payload`.
Use unique IDs; identical repeated requests replay rather than execute again.
Paths below are relative to `output/`, with no links or path escapes.

| Operation | Exact payload | Gate |
| --- | --- | --- |
| brief | `{"path":"brief.md"}` | Initial brief |
| contract | `{"protocol":{...}}` | Approved brief; once |
| baseline | `{"candidate_dir":"baseline","split":"validation","title":"..."}` | Frozen contract; once; two models |
| attempt | `{"candidate_dir":"final","split":"validation","title":"..."}` | Successful baseline; once; four models |
| lock | `{"attempt_id":"A2","candidate_digest":"FROM_RESPONSE"}` | Actual successful jobs and identical trusted baseline fingerprint |
| test | `{"candidate_digest":"FROM_RESPONSE","split":"test"}` | Matching lock; once |
| report | `{"path":"REPORT.md"}` | Successful baseline, final validation and test; negative results allowed |

At most six contexts, each at most 1,200 seconds, fit inside the enrolled
10,800-second episode ceiling. These are upper bounds, not automatic allocations.
The launch records the exact allocation; existing 240-second/2,700-second and
480-second/4,200-second registrations keep their original deadlines. Timing still
starts at the verified native turn start, including initial-context review and
task delivery. Exactly two public-fit reservations (at most
90 seconds each), one baseline validation, one final validation, one locked
test (scientific workers at most 120 seconds each), and two independent replay
slots (at most 90 seconds each) are available. `max_attempts=1`; no retries or extra fits. Failed or
uncertain jobs consume their original reservations. Poll the same job.

When the enrollment selects `manifest_text_bundle_v1`, the task response supplies
the exact seven manifest-bound public text resources together. Read that bundle
and the trusted projection; separate file reads are only needed for other declared
resources or your own saved work. The first session submits the research brief
only, then ends before fitting. Continue with the controller's current stage in
each fresh context.

Small controller batches can use gateway operation `seal_session` directly with
`{"requests":[...]}` when the complete gateway envelope fits its 8,192-byte limit.
Larger batches use the sealed request-file path shown in the launch. Finish each
stage and seal promptly. One clean `{"requests":[]}` checkpoint may preserve
sealed notes and source for the next fresh context; it consumes an existing
context slot and grants no extra fitting or evaluation. All uploads and fitting
jobs must be terminal before sealing. Only accepted, completely audited sessions
promote files for continuation; failed unaccepted work remains separate evidence.

Workers allow one process, four CPU threads, 12 GiB RAM and no GPU/network.
Do not spawn child processes. Candidates contain at most 256 regular files
and 64 MiB. Scientific output contains only `results.npz`. The worker invokes:

```text
python -B /candidate/main.py --split validation|test --input /inputs/evaluation.npz --train /inputs/train.npz --public /public --output /out
```

The working directory is `/candidate`. Predict from frozen numeric parameters;
fixed public B support inputs may be read without refitting. Do not fit or
compute preprocessing statistics on evaluation rows. Public fitting uses:

```text
python -B /candidate/fit.py --public /public --output /out
```

The workbench stages text source only, excluding `parameters.npz` at every
depth. Fit writes only numeric `parameters.npz`. Rebuild the linear baseline
deterministically in both fits; copying old fitted artifacts is forbidden.
Keep all source dependencies in the candidate. `method.json` is authored
before submission and describes the archive schema and recipe selection.

The public allowlist is exactly `train.npz`, `validation.npz`, `eeg_api.py`,
`resources/CACHE_SCHEMA.json` and these four trusted task documents, with
`resources/PAPER_TASK.json` only when bound to a frozen paper question and
the enrolled skill only in the skill condition. Private paper references,
hidden truth, historical results, old fitted probes and raw cache stay private.
