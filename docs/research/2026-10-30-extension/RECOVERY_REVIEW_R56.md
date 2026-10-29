# R56 recovery and treatment-delivery review

Date: 2026-10-30. Scope: the prospective recovery-v1 changes in
`driver_bridge.py`, `real_worker.py`, `real_episode.py`, their focused tests,
`VALIDATION_RECOVERY_V1.md`, and a brief admission/seal review of
`scripts/research/enroll_real_comparison_v2.py`.

This is a Builder code review, not an Actor run, numerical replication, or live
Linux isolation certification. No model calls, dataset reads, credential access,
commits, or pushes were performed by this reviewer. The coordinator owns the
full Linux verification and new enrollment.

## Finding and disposition

**Important, fixed during review: aggregation failures were recoverable by
default.** The initial `real_worker.py` exception branch treated every plain
`ValueError` except a short integrity-message denylist, and every
`FileNotFoundError`, as `candidate_outputs_rejected`. Examples include
`ValueError("Bound input changed")`, an unrecognized trusted-validator defect,
the trusted aggregation response rejecting undeclared metrics, or a missing
private truth file. Because recovery-v1 exempts that diagnostic from its final
completion gate, a later successful iteration could forgive a failure that the
policy says must remain blocking.

With the coordinator's authorization, the review changed only the worker and
its tests:

- `real_worker.py::_output_failure_diagnostic` now recognizes a closed set of
  complete candidate-constraint messages. Unknown values and messages with
  appended private details fail closed as `evaluation_integrity_failed`.
- A missing file is recoverable only when the exception names one of the exact
  `results.npz`, `analysis.npz`, or `interventions.npz` paths under this job's
  output directory. Missing private files, unnamed exceptions, and other output
  names do not qualify.
- Validation of the trusted aggregation response is a separate integrity
  stage. Invalid metric/schema/artifact responses cannot inherit candidate
  recovery eligibility.
- Regressions cover the closed classification, exact missing-output paths, and
  the Linux submit path for an undeclared trusted metric. The previous
  missing-output test now reads an actually missing `out/results.npz`, rather
  than constructing an exception that names private truth.

The numerical aggregator, acceptance tolerances, and scientific source were not
modified. Unknown malformed-output errors may remain terminal; this is the
intentional fail-closed boundary, not an authorization to infer a recoverable
category from arbitrary exception text.

## Reviewed behavior

The controller records a request response and job reservation before submitting
work. Replay returns the original response, and the worker journal forbids a
second submission under a changed fingerprint. Recovery changes the completion
exception for recognized failed validation iterations; it does not convert them
to successes or replenish iteration slots.

Baseline success remains mandatory. A failed baseline cannot be replaced, and
failed/incomplete attempts cannot be locked. Lock rechecks the immutable snapshot
and binds the candidate digest. Final test is reserved once, uses that digest,
and prevents further iteration. Final-test failure details collapse to the
single public `final_test_failed` code; no failed metrics, artifact paths, raw
worker exceptions, or private receipts enter the public projection.

Controller state transactions, the lifetime driver lease, worker job ownership,
process-cleanup checks, read-only candidate/input mounts, and private truth
bindings remain intact. No new Actor capability or test diagnostic channel was
introduced. Historical failed evidence is retained and restart identity includes
the explicit recovery policy.

Inline skill delivery reads the frozen public bytes, checks the enrolled SHA256,
and appends the bytes and digest to the prompt passed to `launch_actor`. Legacy
mounted-only delivery and no-skill delivery inject no optional text. A synthetic
launch-boundary probe verified both completion and a launch exception: the exact
skill bytes reached the launch argument, the ledger prompt hash matched that
argument, the skill hash matched both the budget and own-session history, and
the ledger became `completed` or `failed` respectively. This verifies wiring,
not that a real model consumed the treatment. Actual treatment evidence must be
checked in the subsequent native run.

Frozen-skill validation intentionally precedes call reservation. Bad frozen
enrollment therefore does not consume a model-call reservation; outer episode
orchestration blocks the run. This was not treated as a defect.

## Verification evidence

- Eleven selected existing recovery, strict-default, skill-byte, failed-gate,
  and public-condition tests passed. The local host is Windows; the first direct
  import stopped at the existing Linux-only `fcntl` import. The selected tests
  were then run with an inert import shim, without invoking any lock operation.
  These results do not certify Linux locking or isolation.
- The two new portable diagnostic tests were observed failing before the
  classifier existed, then passed after the fix. Together with the two existing
  NPZ validation tests, the focused native Windows run passed **4/4**.
- The completed/exception synthetic `NativeEpisodeLaunch` boundary probes both
  passed, with no native model invocation or scientific worker execution.
- `git diff --check` passed at review time. The coordinator must run the Linux
  submit-path regression and full designated Linux checks before accepting the
  prospective protocol.

Core bytes at release to the coordinator:

| File | SHA256 |
|---|---|
| `driver_bridge.py` | `02456503c2869ea11232abd0844e51dcdf5260a9d579ee4f511ace471929d751` |
| `real_worker.py` | `0eeb29c31f582b3d0bdbdac44257f53d16301fad39f2f9a7a16535cd65641fb1` |
| `real_episode.py` | `ba2b7b0d67ab97a56b5575104b62f2a0d5c81497174ff2ddc333ff62b700cc4b` |

## Enrollment note and review limits

The v2 enrollment script uses new paths, exclusive config writes, frozen
Python/docs/config/input hashes, and verification before each run. E01's result
and original experiment seal are referenced rather than revised. No additional
blocking issue was identified in this brief inspection.

The coordinator must enforce protocol condition order and sufficient time for
both Pair 2 episodes: the script's admission check itself only requires E05 to
be done before any later episode. It also inherits several resource/model
settings from E01, so their equality to the explicit v2 protocol should be
checked before enrollment. These are operational checks, not claims that the
script independently enforces every protocol sentence.

Behaviors considered but not judged here:

- Live Linux namespace/process isolation: the coordinator's existing live gate
  and Linux verification own this evidence.
- Scientific correctness and the reported float64 correction: R53 and the
  independent numerical/reference reviews own that evidence; no data was read.
- Skill efficacy, scientific completion, semantic score calibration, and
  generalization: code wiring and synthetic tests cannot establish these claims.
- Additional cloud/runtime scripts and unrelated working-tree changes: outside
  this review's assigned source scope.

**Assessment:** the identified recovery-classification defect is corrected in
the shared tree. No remaining blocking code finding was identified in the
reviewed scope. New native enrollment remains conditional on the coordinator's
Linux checks and admission verification; E01's failed outcome stays unchanged.
