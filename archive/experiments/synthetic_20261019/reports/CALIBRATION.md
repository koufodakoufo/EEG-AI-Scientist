# CALIBRATION

Engineering calibration on separate development seeds. These numbers are not Scientist successes and are not holdout results.

| family | window BA | trial BA | subject BA | gap window-trial |
|---|---:|---:|---:|---:|
| T | 0.997 | 0.508 | 0.489 | +0.489 |
| G | 0.951 | 0.950 | 0.952 | +0.001 |
| D | 0.974 | 0.981 | 0.657 | -0.008 |
| N | 0.517 | 0.485 | 0.492 | +0.031 |

## T

| tool | valid | metrics | invalid |
|---|---|---|---|
| trial_random_labels | True | {"trial_random_window_ba_mean": 0.995, "trial_random_trial_ba_mean": 0.493, "trial_random_gap_mean": 0.502} |  |
| trial_shuffle_within_subject | True | {"trial_shuffle_window_ba_mean": 0.996, "trial_shuffle_trial_ba_mean": 0.509, "trial_shuffle_gap_mean": 0.487} |  |
| window_random_labels | True | {"window_random_ba_mean": 0.496, "window_random_ba_minus_chance": -0.004} |  |
| metadata_only | True | {"metadata_only_balanced_accuracy": 0.5, "metadata_only_ba_minus_chance": 0.0} |  |

## G

| tool | valid | metrics | invalid |
|---|---|---|---|
| trial_random_labels | True | {"trial_random_window_ba_mean": 0.497, "trial_random_trial_ba_mean": 0.494, "trial_random_gap_mean": 0.003} |  |
| trial_shuffle_within_subject | True | {"trial_shuffle_window_ba_mean": 0.5, "trial_shuffle_trial_ba_mean": 0.504, "trial_shuffle_gap_mean": -0.004} |  |
| window_random_labels | True | {"window_random_ba_mean": 0.497, "window_random_ba_minus_chance": -0.003} |  |
| metadata_only | True | {"metadata_only_balanced_accuracy": 0.5, "metadata_only_ba_minus_chance": 0.0} |  |

## D

| tool | valid | metrics | invalid |
|---|---|---|---|
| trial_random_labels | True | {"trial_random_window_ba_mean": 0.519, "trial_random_trial_ba_mean": 0.483, "trial_random_gap_mean": 0.036} |  |
| trial_shuffle_within_subject | True | {"trial_shuffle_window_ba_mean": 0.522, "trial_shuffle_trial_ba_mean": 0.476, "trial_shuffle_gap_mean": 0.046} |  |
| window_random_labels | True | {"window_random_ba_mean": 0.511, "window_random_ba_minus_chance": 0.011} |  |
| metadata_only | True | {"metadata_only_balanced_accuracy": 0.5, "metadata_only_ba_minus_chance": 0.0} |  |

## N

| tool | valid | metrics | invalid |
|---|---|---|---|
| trial_random_labels | True | {"trial_random_window_ba_mean": 0.489, "trial_random_trial_ba_mean": 0.495, "trial_random_gap_mean": -0.006} |  |
| trial_shuffle_within_subject | True | {"trial_shuffle_window_ba_mean": 0.498, "trial_shuffle_trial_ba_mean": 0.505, "trial_shuffle_gap_mean": -0.007} |  |
| window_random_labels | True | {"window_random_ba_mean": 0.5, "window_random_ba_minus_chance": -0.0} |  |
| metadata_only | True | {"metadata_only_balanced_accuracy": 0.5, "metadata_only_ba_minus_chance": 0.0} |  |
