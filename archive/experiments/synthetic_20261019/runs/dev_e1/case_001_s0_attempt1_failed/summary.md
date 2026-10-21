# Episode dev_e1_case_001_s0

- case: case_001
- rule: S0
- backend: real_llm / ollama_local / qwen3.5:9b
- status: failed
- actions: 3; calls: 4; attempts: 5; tokens: 24555
- predictions: 0/2
- stop reason: 

## Scores

- `trial_random_labels`: {"status": "scored", "hit": false, "observed_direction": "positive", "metric_key": "trial_random_trial_ba_mean", "value": 0.5079608552991515}
- `trial_shuffle_within_subject`: {"status": "scored", "hit": false, "observed_direction": "positive", "metric_key": "trial_shuffle_trial_ba_mean", "value": 0.4953856313208771}
- `split_audit`: {"status": "not_applicable", "hit": null, "observed_direction": null, "metric_key": null, "value": null}
