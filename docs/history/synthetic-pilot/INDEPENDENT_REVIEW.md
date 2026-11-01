# Independent Builder review — 2026-10-29

Review started at approximately 02:33 Asia/Shanghai and delivered within the ten-minute limit. This was a Builder-only, read-only audit of `research/overnight-20261029`, initially assigned at `b08e898`. The working branch advanced concurrently to `a1cd731` during review. Findings below identify the inspected implementation; the root worker was notified immediately and may have subsequent fixes in progress. This reviewer changed only this report, apart from temporary files created and removed by bounded local tests. No model, server, dataset, credential, live holdout-output, or Git mutation was performed.

**Conclusion:** No P1 was demonstrated. Four P2 implementation/reporting issues merit attention. The M14 dev arithmetic is reproducible: precision 2/30, recall 10/10, F1 0.125. It measures agreement under the frozen extraction/judgment policy, not scientific error rate or a skill benefit. The first two defects were reproduced with mocked local execution, not observed in M12's actual run.

## Confirmed findings

### P2 — Preserve a resource-limit failure when the child exits during status finalization

- Evidence: `framework/eegfm/research_bench/budget.py:195–210`. The monitor sets `timed_out`, `memory_exceeded`, `output_exceeded`, `storage_exceeded`, or `disk_free_floor`, breaks, and then overwrites that status from a new `process.poll()` whenever the child has exited.
- Reproduction: a mocked child returned running for the loop condition, then exit code 0 after the timeout branch. Mock monotonic time was 0 at launch and 2 at the timeout check, with a 1-second limit. The actual `run_bounded` implementation returned `elapsed_seconds=2.0`, `timeout_seconds=1`, `status="completed"`. No subprocess or Linux sandbox was launched for this probe.
- Impact: a run that triggered an enforced limit can be admitted as a normal completion; both budget accounting and episode outcome interpretation lose the termination reason. This is a race, not evidence that M12 exceeded its limit.
- Smallest remedy: only map the child return code to completed/failed if the monitor status is still `running`. Retain the limit status and separately record the exit code. Add a deterministic regression for the above interleaving. The existing Linux timeout test does not exercise this race.

### P2 — Replay can bind an earlier command's artifact to a later no-op command

- Evidence: inspected `framework/eegfm/research_bench/replay.py:101–120`. Commands share one replay output directory. After each command, the collector hashes declared paths without establishing that this command produced them; `independently_regenerated` is simply `name not in seeded`. `validate_commands` checked uniqueness only within each command's artifact list.
- Reproduction: two commands declare the same `metrics.json`. A mocked first command writes it; the second command does nothing and exits 0. The actual replay collector returns `status="passed"`, marks the second command's artifact `independently_regenerated=true`, and attaches its hash to the second command's trusted ledger entry.
- Impact: command-specific provenance can be false even when the final bytes are reproducible. `audit_evidence` trusts the resulting binding, so it cannot repair this later. M12's declared command artifact lists are disjoint, so this probe does not invalidate its metrics or predictions.
- Smallest remedy for this protocol: require unique output ownership across commands and reject duplicates before replay. For future workflows that intentionally rewrite outputs, define explicit input/output roles and clear or separately stage each command's declared outputs before execution. Do not treat pre-existing seeded code as an independently generated result.
- Root worker was notified before report delivery; a replay change appeared in the shared working tree during review and was not reviewed as part of this original reproduction.

### P2 — Extraction truncation and compound-claim warnings disappear from the scored result

- Evidence: `.local/overnight-20261029/private/jobs/M13/VALIDATED.json:600–605` explicitly says the 30-claim cap limits exhaustive coverage and that S01_C30 retains a whole concluding limitation paragraph to fit the cap. `scripts/overnight/prepare_evaluation.py:94–99` passes only claims and judgment edges into the scorer and summarizes only the scorer's review items. M14's `SUMMARY.json:4–12` consequently says `status="scored"`, `review_items=0`.
- Impact: an evaluator or downstream summary can mistake a truncated, partly compound extraction for an exhaustive atomic-claim evaluation. The observed precision depends on which assertions were retained and bundled. Several supported numerical conclusions are bundled with additional uncertainty estimates absent from the shorter reference, so strict support of the entire compound claim fails; that is consistent with the frozen judgment rule but materially limits interpretation of the number.
- Smallest remedy now: preserve the frozen score, extraction, and judgment outputs, and propagate extraction notes plus an explicit extraction-limited/compound-claim caveat into evaluation summaries and the final comparison. Do not describe 28 unsupported claims as 28 false findings. Do not silently change extraction, gold, or the current holdout policy after enrollment.
- Future version: define a bounded, reproducible overflow/atomization policy before enrollment, and validate/report extraction coverage. If sensitivity analysis is desired, label it separately rather than replacing the preregistered result.

### P2 — The evaluation adapter cannot retain malformed or missing submissions under the frozen denominator rule

- Evidence: `scripts/overnight/prepare_evaluation.py:44–47` unconditionally JSON-parses an existing proposed `claims.json`, calls `.get`, and reads `REPORT.md`. A malformed optional annex aborts preparation even if the report is usable; a missing report raises rather than generating an empty-submission evaluation. This conflicts with the sealed policy set in `scripts/overnight/freeze_references.py:30`: failed launched episodes remain in the denominator, with no selective retry. The collector already records interface errors at `scripts/overnight/collect_episode.py:25–45`, but extraction does not consume them.
- Impact: one partial Actor output can block batch evaluation, and manual exclusion would bias comparisons by omitting failures. This is confirmed from the executable path, not an observed omission in the M12 result.
- Smallest remedy: preserve and surface annex parse errors, then use an empty proposed-claims list when a complete report can still be extracted. For absent reports, emit an explicit terminal episode record and apply the sealed empty-submission/failed-episode policy. Keep infrastructure-blocked cases distinct and retain all assigned/launched IDs in the results table. Add adapter tests; the CLI's existing empty-claim scoring test does not cover preparation.

## Checks and interpretation

- Ran `python -B -m unittest discover -s tests/research_bench -p 'test_*.py' -v` from `framework/`: 75 tests, 61 passed, 14 skipped. Skips were Linux-specific launcher/legacy-driver tests and unavailable Windows symlink operations. This is not a new Linux isolation certification.
- Recomputed the complete M14 score dictionary from its saved input and judge output; it exactly equals the stored M12 score. Full-report recall is intentional: the submitted report contains the single-coordinate results and intervention comparisons required by reference claims even where the capped extracted claim list points to related text. The independent directions and unique-claim arithmetic are sound for the supplied judgments.
- Verified the dev public bundle/reference seal and the extraction implementation hash against the v2 seal. Verified the current Actor launcher script hash against `HOLDOUT_PROTOCOL.json`. No live holdout outputs were opened.
- Rehashed all eight M12 frozen artifacts named by supplemental replay comparisons; each matches the submission hash recorded there. The supplemental replay itself correctly remains `failed`: seven artifact comparisons match, while `validation_checks.json` differs. Its `all_commands_completed=true` does not imply byte reproducibility of every artifact.
- The supplemental evidence audit's 3/3 valid result concerns its three selected artifact records, not every replay output. Two are regenerated metrics/predictions; the model snapshot is explicitly marked as a seeded input rather than independently regenerated. A concise final result should retain that distinction.
- Alternative findings are appropriately separated from contradiction and reference support. Reference silence cannot establish scientific falsity. Neither matching hashes nor this semantic audit validates all submitted analysis methods or empirical claims.
- The holdout protocol predeclares order, equal model/compute limits, and an outcome-independent second-pair rule. Its small synthetic same-source transfer scope, lack of a deterministic model seed, and potentially weakened blinding through report self-disclosure remain real inference limitations; no causal skill-benefit or RSI conclusion follows from a pair or two.

## Residual limitations and unverified concerns

The documented sampled RSS ceiling and prompted original-tool command limit remain limitations, not newly discovered violations. The inherited affinity seccomp implementation is present, but this Windows read-only audit did not rerun its Linux canary. No fresh security bypass was established.

Replay's split labels are inferred from file extensions and the validation default (`replay.py:119–120` in the inspected version); they do not establish which data a script read or which rows a metric actually evaluated. Treat split integrity as a separate code/data audit, not a conclusion of a valid hash ledger. Similarly, collection should refuse to freeze an output tree if cleanup reports surviving Actor processes; the current collector's terminal-status check alone does not establish that the tree is unwritable. These are bounded hardening recommendations, not claims that M12 had wrong splits or surviving processes.

The concurrent legacy-driver fix was outside this independent review's verification scope. No scientific winner was sought or inferred.
