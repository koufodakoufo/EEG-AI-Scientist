# Episode study_20261019_case_002_dev_s0

- case: case_002
- rule: S0
- backend: real_llm / ollama_local / qwen3.5:9b
- status: completed
- actions: 3; calls: 4; attempts: 4; tokens: 21418
- predictions: 2/2
- stop reason: Both H1 and H3 are supported by evidence. Trial shuffling (H1) broke performance, while session-based effects (H3) remain plausible but less likely given the lack of subject overlap in other splits.

## Scores

- `split_audit`: {"status": "not_applicable", "hit": null, "observed_direction": null, "metric_key": null, "value": null}
- `trial_shuffle_within_subject`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "trial_shuffle_trial_ba_mean", "value": 0.47918276188924247, "reference": 0.5, "delta": -0.02081723811075753}
- `trial_random_labels`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "trial_random_trial_ba_mean", "value": 0.4874650654260623, "reference": 0.5, "delta": -0.012534934573937673}
