# Validation recovery policy v1

This is a prospective Builder change for freshly enrolled episodes. It does not
revise E01, reinterpret its failed evidence, change any scientific acceptance
tolerance, or authorize another test invocation for an existing episode.

## Enrollment

The trusted `real_episode_config_v1` configuration may explicitly set:

```json
{"recovery_policy": "validation-recovery-v1", "max_attempts": 2}
```

`max_attempts` is the total number of validation **iterations**, excluding the
single baseline. Every submitted iteration consumes one slot, including a failed
iteration. Recovery does not add slots, sessions, wall time, or worker time. A
successful first iteration and an additional failed iteration still consume two
slots. Correcting a failed first iteration requires a new candidate submission
and the remaining slot.

Omitting `recovery_policy`, or specifying `strict-v1`, retains the rule that any
failed job prevents completion. The new policy is part of the controller identity
and the complete config is hashed by episode enrollment. Policy or budget changes
on resume fail identity verification. Updated source hashes require new episode
enrollment; old frozen source and evidence must be retained.

## State and completion rules

1. A successful baseline is required before iterations. A failed baseline cannot
   be replaced, treated as successful, or bypassed.
2. A failed validation iteration remains `failed` with its immutable job response,
   candidate digest and retained evidence. It is never changed into a success.
3. For recognized candidate execution/output failures, the Actor may submit a
   corrected candidate as a **new** attempt before lock, within the existing
   iteration and session budgets. Request replay never launches another job.
4. Lock requires a successful validated attempt and its matching immutable
   candidate digest. A failed or incomplete attempt is not eligible for lock.
5. Completion requires the successful baseline, at least one successful analysis
   iteration, the selected candidate's successful validation job, the successful
   matching final-test job, a completed model session and the frozen report.
   The real EEG controller additionally requires Q1 evidence from the selected
   validation iteration and final test.
6. Historical failures are exempted from the completion gate only when they are
   validation iterations with recognized candidate execution/output diagnostics.
   Pending jobs, incomplete evidence, unknown failures, setup/integrity failures,
   and invalid worker responses remain blocking.
7. Final test is reserved durably before dispatch and remains one-shot. Failure,
   interruption or rejected results consume the reservation and block completion.
   Neither request replay nor a new request ID can execute another test. Lock
   also prevents further validation iterations.

## Public diagnostics

The worker may return a `diagnostic_code` on a failed response only. The bridge
validates it against a finite vocabulary and generates a static public message.
The Actor cannot submit a diagnostic code as a request field. Candidate files,
stdout, stderr, arbitrary JSON, exception messages and private paths never supply
public diagnostic text. No partial failed metrics or artifact paths are projected.

The new policy exposes each failed job's `diagnostic` containing `code`, `message`
and `eligible_for_new_iteration`. Eligibility describes the failure category;
the Actor must also check the projected `recovery.remaining_iterations`, lock,
and remaining session/wall budgets. The `recovery` projection identifies the policy,
used/remaining iteration counts and whether final test is consumed.

| Code | Meaning | Candidate correction eligible |
|---|---|---|
| `candidate_execution_failed` | Candidate exit/timeout/resource failure with confirmed process cleanup | Yes, validation iteration only |
| `candidate_outputs_rejected` | Missing required output or rejected scientific output schema | Yes, validation iteration only |
| `intervention_strength_mismatch` | Per-window control strength differs | Yes, validation iteration only |
| `direction_span_mismatch` | Recorded shifts fall outside their recorded direction spans | Yes, validation iteration only |
| `control_rank_mismatch` | Control numerical rank differs | Yes, validation iteration only |
| `control_subspace_mismatch` | Controls do not use distinct subspaces | Yes, validation iteration only |
| `nonfinite_evidence` | Nonfinite scientific values or derived overflow | Yes, validation iteration only |
| `evaluation_failed` | No recognized candidate diagnostic | No |
| `evaluation_setup_failed` | Trusted setup or evidence persistence failure | No |
| `evaluation_integrity_failed` | Integrity check, cleanup, or unexpected aggregator failure | No |
| `evaluation_interrupted` | Lost/interrupted evaluation | No |
| `evaluator_unavailable` | Evaluator call failed | No |
| `worker_result_rejected` | Controller rejected response identity/schema | No |
| `final_test_failed` | Final-test reservation consumed without success | No |

Specific scientific codes are selected by exact matches against fixed trusted
validator error messages; messages containing added values or paths cannot match.
No numeric threshold or scientific evaluator code is changed. All final-test
failure categories collapse to `final_test_failed` in the public projection, so
validation diagnostic detail does not become a final-test feedback channel.

## Verification scope

Regression tests use temporary synthetic episode roots and controlled worker
callbacks. They cover failure then corrected validation completion, immutable
failed evidence and bounded slots, rejected failed locks, restart identity,
strict-default behavior, terminal test reservations, public diagnostic filtering,
missing-output failure, and nonrecoverable cleanup/integrity faults. These tests
verify lifecycle and disclosure contracts; they are not live EEG/model evidence.
