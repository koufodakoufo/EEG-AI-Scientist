# Explanation regression: rule-based review

- returned_model: `deepseek-flash`
- checks passed: 6/6

- [PASS] `recognizes_trial_baseline_near_chance` — 49.6% must be described as already near chance, not as a post-randomization collapse.
- [PASS] `recognizes_window_stays_high` — window-level values 99.3% and 99.2% should be compared; the change is about 0.1 percentage point.
- [PASS] `mentions_both_deltas` — Expected deltas: window -0.1 pp; trial +1.2 pp. This checks arithmetic presence, not correctness of interpretation.
- [PASS] `rejects_trial_collapse_claim` — No sentence should claim that randomization moved trial performance from ~99% to chance.
- [PASS] `mentions_split_or_shared_trial` — The window/trial split distinction or shared-trial structure should be named.
- [PASS] `states_a_limit_on_generalization_claim` — The answer should say what cannot be concluded about semantic generalization or leakage.

See `regression_answer.md` for the verbatim answer. These are rule checks, not a scientific score.
