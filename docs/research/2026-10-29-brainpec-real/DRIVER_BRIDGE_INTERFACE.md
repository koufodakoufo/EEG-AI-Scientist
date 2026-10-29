# R03 bridge interface

Implemented in `framework/eegfm/research_bench/driver_bridge.py`; `BridgeDriver` inherits the actual `Driver.loop`. The only legacy changes are optional explicit run/task inputs and narrow review/job/transition/completion hooks. Legacy adapter argv is never used by `BridgeDriver`.

## Controller and ownership

```python
controller = BridgeController(
    trusted_root=Path(".../trusted"), case_root=Path(".../case"),
    episode_id="E01", run_id="real-E01",
    public_manifest_sha256="<64 lowercase hex>",
    split_manifest_sha256="<64 lowercase hex>",
    evaluator=evaluator, max_attempts=4,
)
driver = BridgeDriver(controller, launch=launch, reviewer=reviewer,
                      max_sessions=6, poll=1.0)
driver.loop()
```

`trusted_root` and `case_root` must be disjoint. The controller journal is `trusted/runs/<run>/control.sqlite3`; this and the run mirrors must be outside every Actor filesystem grant. SQLite transactions serialize request/attempt/test reservation. Run/state/attempt/job/review/freeze/lock/audit/request/report files remain inspectable wzf artifacts; SQLite is authority. Resume by constructing with the same identities and budgets. The model/worker integration must be fixed before enrollment; this API does not itself seal its injected implementation.

`controller.projection()` returns only this episode's allowed state, responses, attempts, review, contract, lock and filtered job results. The caller must publish it read-only alongside the frozen public bundle. `sandbox_receipt`, raw logs and host paths from execution are not projected. Do not project the run directory, controller database, global memory, other episodes or Builder documents.

## Actor request schema

Every request has exactly `request_id`, `episode_id`, `operation`, `payload`. IDs match `[A-Za-z0-9][A-Za-z0-9_-]{0,99}`; requests are at most 64 KiB. Payloads have exactly the fields below. Paths resolve inside `case/output`; links, hidden candidate files and paths escaping that root are rejected.

| operation | payload | timing |
| --- | --- | --- |
| `brief` | `{"path":"brief.md"}` | Initial/rejected brief; transitions to awaiting_review |
| `contract` | `{"protocol":{"research_mode":"analysis","selection_split":"validation", ...}}` | After delegated approval; once only |
| `baseline` | `{"candidate_dir":"candidate","split":"validation","title":"..."}` | After contract; one allocation |
| `attempt` | Same fields as baseline | Successful baseline, before lock; bounded iteration allocations |
| `lock` | `{"attempt_id":"A2","candidate_digest":"..."}` | An evaluated candidate; one per episode |
| `test` | `{"candidate_digest":"...","split":"test"}` | Same locked digest, once per episode |
| `report` | `{"path":"REPORT.md"}` | Complete successful lifecycle; nonempty UTF-8 report |

Controller assigns attempt/job IDs and returns the candidate digest; Actor does not supply a host path, shell, cwd, environment or reviewer identity. Baseline/attempt return `status=accepted`, `attempt_id`, `candidate_digest`, `job_id`. Request response also includes `request_id` and `request_sha256`. Same ID/same content returns that original response without side effects; same ID/different content is rejected. Driver records invalid Actor requests as immutable `status=rejected,error_type=...` feedback when their episode and ID are valid. A corrected request needs a new ID. Direct `handle` raises validation errors; the Driver performs the rejection recording.

The candidate directory includes all submitted code/configuration/fit artifacts needed for that attempt, max 256 files and 64 MiB. The bridge copies and hashes the entire regular-file tree, checks both source and destination, and rechecks it at lock, test and evaluation completion. Large frozen model/data resources belong in the trusted evaluator contract and resource manifests, not the candidate directory.

## Delegated review

`reviewer(projection)` returns exactly the keyword arguments for:

```python
controller.review(approved=True, reviewer_id="protocol-reviewer",
                  policy_sha256="<frozen review rule hash>")
```

The actual reviewer must check allowed scope/resources/protocol. It must not supply target-method or gold feedback. The recorded identity is `approval_mode=delegated_protocol_review`, never human. Actor has no approve operation; no task-wide standing brief is created. If no reviewer callback is provided, driver waits at awaiting_review.

## Isolated launch callback

`launch(projection) -> dict` must prepare a fresh control home and invoke the existing `research_bench.actor.launch_actor` with its passing live isolation gate. No fallback to `Adapter.argv`, no resumed global conversation, no unrestricted filesystem or environment inheritance. The callback must return these bounded receipt fields plus parsed Actor requests:

```python
{"status": "completed", "exit_code": 0,
 "stdout": "<Codex JSONL events>", "stderr": "<stderr>",
 "process_cleanup": {"surviving_owned_pids": []},
 "requests": [{"request_id": "...", "episode_id": "E01",
               "operation": "...", "payload": {...}}]}
```

Requests are ingested only for a clean completed model event stream with no failed events and no surviving owned processes. A zero exit code alone is insufficient. At most 16 requests can be processed per session. Requests may sequence contract then baseline, or lock then test, without an extra model call. Long jobs return `waiting`, and the inherited driver waits/polls without an Actor session. The callback must enforce the already allocated session wall time and preserve actual call IDs/trace evidence externally.

## Sandboxed evaluator callback

The trusted object declares `sandboxed=True` and implements `submit(spec)` plus side-effect-free `poll(job_id)`. `EvaluationSpec` is immutable and has: `job_id`, `episode_id`, `run_id`, `attempt_id`, `split` (`validation` or `test`), `candidate_dir: Path`, `candidate_digest`, `split_manifest_sha256`, `public_manifest_sha256`.

The object **must launch submitted code only in a separate restricted worker**. Do not import/exec submitted code inside the controller. Only the fixed test worker may receive sealed test tensors after reservation. Never mount mixed datasets, source database roots, labels/gold, credentials or controller storage into the candidate process. Validate output schema, actual split rows, input/output hashes and expected shards in the trusted aggregator. Worker stdout and private sample metadata must not be returned to Actor.

Both methods return exactly:

```python
{"job_id": spec.job_id, "candidate_digest": spec.candidate_digest,
 "split": spec.split, "status": "waiting",  # or succeeded / failed
 "metrics": {},                           # finite numeric scalar values only
 "artifacts": [{"path": "metrics.json", "sha256": "<hash>"}],
 "sandbox_receipt": "<private evidence identifier/path>"}
```

Succeeded requires at least one finite metric. The private receipt may locate full immutable evidence and is excluded from Actor projection. The artifact entries are a schema-checked manifest; the **trusted evaluator must verify the actual files/hashes** before returning it. Detailed numerical arrays remain private; only predetermined aggregate metrics and permitted artifact identifiers are released. `sandboxed=True` and the receipt are an interface requirement, not a proof of real isolation.

Test reservation and immutable response commit before calling `submit`. Same-request replay returns the saved response; another test request is rejected. A crash/unknown submit is never automatically reexecuted. `poll(job_id)` must only recover/query that job; it must not launch missing work. Same-digest technical retries are not exposed by this minimum bridge and need a separately reviewed extension if later required.

## Analysis and completion limits

Successful negative metrics are retained with `retention=retained_valid`; no accuracy frontier exists in this mode. Completion requires delegated review, frozen contract, baseline, at least one successful iteration, unique lock and successful final test, successful latest model session, nonempty frozen report. The minimum implementation conservatively requires every allocated job to succeed; it does not yet support recovering a failed optional attempt into a completed episode. Failure records are preserved.

This is lifecycle plumbing, not scientific or live-isolation acceptance. Root integration still owns actual isolated launch, worker sandbox/cleanup, data split and row validation, result-release schema, task/resource/model/protocol freeze, public documentation, model-call accounting, richer final deliverable validation and independent replay. No live Actor or scientific data was run by R03.

Verification evidence is under `.local/research/2026-10-29-brainpec-real/verification/R03-*.log`: explicit RED followed by GREEN, including output-root symlink rejection. The full `tests` collection was attempted but scientific modules require Linux NumPy unavailable in local WSL. Legacy program + research_bench + bridge tests were run separately; see the final log for the exact count/version.
