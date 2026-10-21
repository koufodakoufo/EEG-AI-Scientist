# Episode dev_e1_case_001_s0

- case: case_001
- rule: S0
- backend: real_llm / ollama_local / qwen3.5:9b
- status: completed
- actions: 3; calls: 4; attempts: 5; tokens: 24330
- predictions: 2/2
- stop reason: Permutation of labels at the trial level reduced performance to chance (~0.5), ruling out session identity (H3) and confirming that task-level content drives generalization within trials, supporting H1.

## Scores

- `split_audit`: {"status": "not_applicable", "hit": null, "observed_direction": null, "metric_key": null, "value": null}
- `trial_shuffle_within_subject`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "trial_shuffle_trial_ba_mean", "value": 0.4953856313208771, "reference": 0.5, "delta": -0.004614368679122904}
- `trial_random_labels`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "trial_random_trial_ba_mean", "value": 0.5079608552991515, "reference": 0.5, "delta": 0.00796085529915147}
