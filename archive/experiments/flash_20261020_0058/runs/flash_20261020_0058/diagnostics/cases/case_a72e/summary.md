# Episode diag_case_a72e

- case: case_a72e
- rule: DIAGNOSTIC_v2
- backend: real_llm / deepseek_flash / deepseek-flash
- status: completed
- actions: 2; calls: 3; attempts: 3; tokens: 25763
- predictions: 2/2
- stop reason: Seen-subject window and trial scores are near ceiling, but within-subject label permutation and metadata-only both collapsed to chance. This pattern favors a genuine subject/context-specific feature-label mapping and weakens identity/collection and label-permutation artifact explanations.

## Scores

- `trial_shuffle_within_subject`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "trial_shuffle_trial_ba_mean", "value": 0.47918276188924247, "reference": 0.5, "delta": -0.02081723811075753}
- `metadata_only`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "metadata_only_ba_minus_chance", "value": 0.0, "reference": 0.0, "delta": 0.0}
