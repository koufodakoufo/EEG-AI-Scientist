# Episode diag_case_c41a

- case: case_c41a
- rule: DIAGNOSTIC_v2
- backend: real_llm / deepseek_flash / deepseek-flash
- status: completed
- actions: 3; calls: 4; attempts: 4; tokens: 32798
- predictions: 3/3
- stop reason: Three diagnostic controls were executed. Window BA remained high under trial-level random labels while trial BA stayed near chance; independent window labels and metadata-only fell to chance. This pattern supports same-trial shared information and does not support a generalizable window signal or metadata identity effect.

## Scores

- `trial_random_labels`: {"status": "scored", "hit": true, "observed_direction": "positive", "metric_key": "trial_random_gap_mean", "value": 0.4839336759508486, "reference": 0.0, "delta": 0.4839336759508486}
- `window_random_labels`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "window_random_ba_mean", "value": 0.49117719845528185, "reference": 0.5, "delta": -0.00882280154471815}
- `metadata_only`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "metadata_only_balanced_accuracy", "value": 0.5, "reference": 0.5, "delta": 0.0}
