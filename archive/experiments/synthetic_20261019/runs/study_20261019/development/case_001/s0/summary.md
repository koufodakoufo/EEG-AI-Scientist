# Episode study_20261019_case_001_dev_s0

- case: case_001
- rule: S0
- backend: real_llm / ollama_local / qwen3.5:9b
- status: completed
- actions: 3; calls: 4; attempts: 4; tokens: 21053
- predictions: 2/2
- stop reason: Both H1 and H3 are supported by the evidence. The window split is high, indicating session overlap matters (supporting H3). However, both req_2 (shuffling within subject) and req_3 (randomizing labels at trial level) result in near-zero gaps for trial splits, which contradicts H1's prediction of task-specific transfer but aligns with the null hypothesis that no specific mechanism drives performance beyond chance. Since neither permutation test supports H1 or H3 over a random baseline, we must conclude that the high window split is likely due to session overlap (H3) while the trial-level performance suggests no robust trial-specific learning exists in this setup.

## Scores

- `split_audit`: {"status": "not_applicable", "hit": null, "observed_direction": null, "metric_key": null, "value": null}
- `trial_shuffle_within_subject`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "trial_shuffle_trial_ba_mean", "value": 0.4953856313208771, "reference": 0.5, "delta": -0.004614368679122904}
- `trial_random_labels`: {"status": "scored", "hit": true, "observed_direction": "near_zero", "metric_key": "trial_random_trial_ba_mean", "value": 0.5079608552991515, "reference": 0.5, "delta": 0.00796085529915147}
