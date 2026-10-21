# Episode dev_e1_case_001_s0

- case: case_001
- rule: S0
- backend: real_llm / ollama_local / qwen3.5:9b
- status: failed
- actions: 1; calls: 2; attempts: 3; tokens: 12791
- predictions: 1/1
- stop reason: invalid_decision_after_repair

## Scores

- `trial_random_labels`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "trial_random_trial_ba_mean", "value": 0.5079608552991515, "reference": 0.5, "delta": 0.00796085529915147}
