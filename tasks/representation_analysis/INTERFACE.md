# Isolated episode interface

Every session starts a fresh model conversation and control home. Your case
directory persists. Only `public/` and the session prompt's trusted projection
are authoritative. The projection contains this episode's approved state,
responses, attempts, review, contract, lock, and released job metrics. It is
embedded in the immutable launch prompt; there is no editable trusted state
file. Your own notes and candidate code may persist in `output/`.

The launch prompt gives the current request filename and scientific Python
executable. Write a JSON array to that exact `output/requests-session-NN.json`
file, with at most 16 requests and 1 MiB total. Every request has exactly:

```json
{"request_id":"unique-id","episode_id":"FROM_PROMPT","operation":"brief","payload":{"path":"brief.md"}}
```

Use unique request IDs. Each request is at most 64 KiB. Reusing an ID with the
same content replays its response; changing its content is rejected. Paths are
relative to `output/`, contain no links, and cannot leave that directory. Do not
edit prior requests to retry. Submit a new ID when correcting a rejected request.
Requests are ingested only after a clean completed model session and process
cleanup. End the session once its batch is written; the controller runs jobs.

| Operation | Exact payload | Prerequisite |
| --- | --- | --- |
| brief | `{"path":"brief.md"}` | Initial or rejected brief |
| contract | `{"protocol":{...}}` | Delegated brief approval; once |
| baseline | `{"candidate_dir":"baseline","split":"validation","title":"..."}` | Frozen contract; once |
| attempt | `{"candidate_dir":"candidate","split":"validation","title":"..."}` | Successful baseline; before lock |
| lock | `{"attempt_id":"A2","candidate_digest":"FROM_RESPONSE"}` | Successfully evaluated candidate |
| test | `{"candidate_digest":"FROM_RESPONSE","split":"test"}` | Matching lock; exactly once |
| report | `{"path":"REPORT.md"}` | Successful baseline, iteration, final test |

The brief starts with a fenced `json` object containing this scope declaration,
followed by your substantive research questions and proposed protocol:

```json
{"task":"eegmat-arithmetic-background","public_resources_only":true,"backbone_frozen":true,"head_frozen":true,"selection_split":"validation","test_after_lock_only":true,"gpu":0}
```

The delegated reviewer validates that declaration and a nonempty research plan.
This is a mechanical scope review, not human approval or scientific endorsement.
The contract protocol must contain those same fields plus
`"research_mode":"analysis"`; add your complete scientific decisions and
planned limitations. It becomes immutable. No automatic scientific recipe is
provided by the reviewer.

A normal episode uses five sessions: brief; contract plus baseline; scientific
attempt; lock plus test; report. A sixth session is available for a correction.
Limits are at most six model sessions, at most 900 seconds per session, at most
90 minutes total episode wall time, four CPU threads, 12 GiB RAM, no GPU and no
tool network. Every session, including a failed one, consumes its allocation.
Each candidate tree is limited to 256 regular files and 64 MiB. Large frozen
resources stay in `public/`. Worker jobs are capped at 900 seconds. Do not leave
background processes running. This task uses `validation-recovery-v1`: a failed
validation iteration with an eligible trusted diagnostic may be corrected by a
new iteration before lock. Failed attempts remain recorded and consume the
budget of two scientific iterations (in addition to one baseline). They do not
receive extra model sessions. A baseline, integrity, or final-test failure still
prevents completion. Inspect code and numeric evidence locally before submission.
Completion also requires `q1_groups > 0` in both the locked scientific iteration's
validation result and its final test result. Lock an iteration candidate. Merely
repeating baseline predictions cannot satisfy the analysis stage. Partial Q1
coverage must still be disclosed; this threshold does not certify all questions.

The trusted worker invokes exactly:

```text
python -B /candidate/main.py --split validation|test --input /inputs/evaluation.npz --train /inputs/train.npz --public /public --output /out
```

`main.py` and every fit artifact must be inside the submitted directory. The
worker starts in `/candidate`. Import the helper by adding the supplied
`--public` path to `sys.path`; use no host absolute paths. `--input` contains only
`x`, `sample_ids`, and `subject_ids`. Public validation resources remain allowed
for frozen choices; test truth is never available to submitted code. Preserve
input row order exactly. Write result files under `--output`; consult the frozen
result schema for mandatory arrays and supported optional analyses. Do not
return labels or scalar metrics as substitutes for per-row predictions.

The case is for this episode only. Do not read other cases, prior conversations,
Builder materials, global memory, private scorer/reference files, or external
papers. The supplied API and resource manifests identify permitted resources.
