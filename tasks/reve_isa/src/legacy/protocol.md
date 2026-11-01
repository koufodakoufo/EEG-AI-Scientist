# REVE stimulus ISA: 1 requested research round(s)

The authorized launch brief and task.yaml research.protocol are the frozen launch contract. The original task brief is preserved as historical_brief.md when replaced.

Fresh official-weight R0 covers all six targets and 72 LP/FT validation units before R1. Every research round uses independent official initialization per target, the frozen six subject splits, five all-sample LODO sources, 40 epochs, real per-source contrastive batch 64 and 62 negatives. NoClip input, stimulus pairing, losses, training seeds, downstream budgets and validation checkpoint selection stay fixed.

R1 is the single common candidate; finish after its complete validation and locked test evaluation.

After all requested validation rounds, lock the method before any test calls. Evaluate R0, R1: 6 targets x 2 modes x 6 splits x 2 conditions = 144 actual test calls. Never reselect from test. Report paired bootstrap intervals and the historical-split limitations.

Normal execution requires 18 full workers and 18 phase-specific canaries. Each worker requests six GPUs: five source replicas in posttraining and six independent downstream folds. The broker owns cloud admission, budget and deadlines. Forecasts above 12h require engineering review; both the worker and recovery deployment hard limits are 12h. GPU training is TiONE-only; CPU tests are not GPU success.

This run's local R1 means the second cross-run candidate H2. The previous candidate is H1. H2 must materially change at least one of the five allowed posttrain parameters. Scientist compares a few parameter ideas from previous_validation_summary.json validation/loss/gradient evidence, chooses exactly one common set, and records all five values and an opposite-result explanation in candidate_plan.json. Temperature may vary within [0.03, 0.3]. No smoke-loss ranking, per-dataset tuning, sweep or extra candidate. Previously viewed historical test results prevent an independent confirmatory claim.

Recovery restores the saved Scientist decision: posttrain_lr 1e-5 -> 5e-6; temperature 0.1, weight decay 1e-4, warmup 3 and gradient clip 1.0 stay fixed. candidate_plan.json cites the exact saved decision and H1 validation source hash. Local round 1 is H2, not a third candidate. Prior deployment had zero GPU jobs/rounds; six prior Agent calls and two prior bootstrap repairs remain recorded. The new broker deadline is 1792443639.981201; preparation and queue time consume that same recovery window.
