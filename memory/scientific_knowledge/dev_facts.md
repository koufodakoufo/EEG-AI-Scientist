# Development facts

{
  "study_id": "study_20261019",
  "development_cases": [
    {
      "case_id": "case_001",
      "baseline": {
        "window_balanced_accuracy": 0.9931640625,
        "window_accuracy": 0.9931640625,
        "window_n_train": 3072.0,
        "window_n_test": 1024.0,
        "window_n_train_trials": 512.0,
        "window_n_test_trials": 512.0,
        "window_n_train_subjects": 16.0,
        "window_n_test_subjects": 16.0,
        "window_trial_aggregated_balanced_accuracy": 0.990234375,
        "window_trial_aggregated_n_trials": 512.0,
        "trial_balanced_accuracy": 0.49609375,
        "trial_accuracy": 0.49609375,
        "trial_n_train": 3072.0,
        "trial_n_test": 1024.0,
        "trial_n_train_trials": 384.0,
        "trial_n_test_trials": 128.0,
        "trial_n_train_subjects": 16.0,
        "trial_n_test_subjects": 16.0,
        "trial_trial_aggregated_balanced_accuracy": 0.515625,
        "trial_trial_aggregated_n_trials": 128.0,
        "subject_balanced_accuracy": 0.517578125,
        "subject_accuracy": 0.517578125,
        "subject_n_train": 3072.0,
        "subject_n_test": 1024.0,
        "subject_n_train_trials": 384.0,
        "subject_n_test_trials": 128.0,
        "subject_n_train_subjects": 12.0,
        "subject_n_test_subjects": 4.0,
        "subject_trial_aggregated_balanced_accuracy": 0.5546875,
        "subject_trial_aggregated_n_trials": 128.0,
        "gap_window_minus_trial": 0.4970703125,
        "gap_window_minus_subject": 0.4755859375,
        "gap_trial_minus_subject": -0.021484375
      },
      "structure_summary": {
        "n_rows": 4096,
        "n_subjects": 16,
        "n_sessions": 32,
        "n_trials": 512,
        "n_features": 32,
        "windows_per_trial": 8,
        "n_positive_rows": 2048,
        "n_negative_rows": 2048,
        "n_positive_trials": 256,
        "n_negative_trials": 256
      },
      "status": "completed"
    },
    {
      "case_id": "case_002",
      "baseline": {
        "window_balanced_accuracy": 0.9658203125,
        "window_accuracy": 0.9658203125,
        "window_n_train": 3072.0,
        "window_n_test": 1024.0,
        "window_n_train_trials": 512.0,
        "window_n_test_trials": 512.0,
        "window_n_train_subjects": 16.0,
        "window_n_test_subjects": 16.0,
        "window_trial_aggregated_balanced_accuracy": 0.96875,
        "window_trial_aggregated_n_trials": 512.0,
        "trial_balanced_accuracy": 0.9736328125,
        "trial_accuracy": 0.9736328125,
        "trial_n_train": 3072.0,
        "trial_n_test": 1024.0,
        "trial_n_train_trials": 384.0,
        "trial_n_test_trials": 128.0,
        "trial_n_train_subjects": 16.0,
        "trial_n_test_subjects": 16.0,
        "trial_trial_aggregated_balanced_accuracy": 1.0,
        "trial_trial_aggregated_n_trials": 128.0,
        "subject_balanced_accuracy": 0.5615234375,
        "subject_accuracy": 0.5615234375,
        "subject_n_train": 3072.0,
        "subject_n_test": 1024.0,
        "subject_n_train_trials": 384.0,
        "subject_n_test_trials": 128.0,
        "subject_n_train_subjects": 12.0,
        "subject_n_test_subjects": 4.0,
        "subject_trial_aggregated_balanced_accuracy": 0.640625,
        "subject_trial_aggregated_n_trials": 128.0,
        "gap_window_minus_trial": -0.0078125,
        "gap_window_minus_subject": 0.404296875,
        "gap_trial_minus_subject": 0.412109375
      },
      "structure_summary": {
        "n_rows": 4096,
        "n_subjects": 16,
        "n_sessions": 32,
        "n_trials": 512,
        "n_features": 32,
        "windows_per_trial": 8,
        "n_positive_rows": 2048,
        "n_negative_rows": 2048,
        "n_positive_trials": 256,
        "n_negative_trials": 256
      },
      "status": "completed"
    }
  ],
  "trajectories": [
    {
      "episode_id": "study_20261019_case_001_dev_s0",
      "case_id": "case_001",
      "status": "completed",
      "events": [
        {
          "event_id": "dev-case_001-action-1",
          "tool_id": "split_audit",
          "prediction": {
            "scoring_status": "not_applicable",
            "metric_key": null,
            "primary_direction": null,
            "threshold": 0.05,
            "check_facts": [
              "Inspect overlap counts for sample/trial/session/subject across splits.",
              "Verify label proportions in train vs test sets per group."
            ],
            "conditional_predictions": [],
            "update_rule_if_opposite": ""
          },
          "result_metrics": {
            "window_balanced_accuracy": 0.9931640625,
            "window_accuracy": 0.9931640625,
            "window_n_train": 3072.0,
            "window_n_test": 1024.0,
            "window_n_train_trials": 512.0,
            "window_n_test_trials": 512.0,
            "window_n_train_subjects": 16.0,
            "window_n_test_subjects": 16.0,
            "window_trial_aggregated_balanced_accuracy": 0.990234375,
            "window_trial_aggregated_n_trials": 512.0,
            "trial_balanced_accuracy": 0.49609375,
            "trial_accuracy": 0.49609375,
            "trial_n_train": 3072.0,
            "trial_n_test": 1024.0,
            "trial_n_train_trials": 384.0,
            "trial_n_test_trials": 128.0,
            "trial_n_train_subjects": 16.0,
            "trial_n_test_subjects": 16.0,
            "trial_trial_aggregated_balanced_accuracy": 0.515625,
            "trial_trial_aggregated_n_trials": 128.0,
            "subject_balanced_accuracy": 0.517578125,
            "subject_accuracy": 0.517578125,
            "subject_n_train": 3072.0,
            "subject_n_test": 1024.0,
            "subject_n_train_trials": 384.0,
            "subject_n_test_trials": 128.0,
            "subject_n_train_subjects": 12.0,
            "subject_n_test_subjects": 4.0,
            "subject_trial_aggregated_balanced_accuracy": 0.5546875,
            "subject_trial_aggregated_n_trials": 128.0,
            "gap_window_minus_trial": 0.4970703125,
            "gap_window_minus_subject": 0.4755859375,
            "gap_trial_minus_subject": -0.021484375
          },
          "valid": true,
          "score": {
            "status": "not_applicable",
            "hit": null,
            "observed_direction": null,
            "metric_key": null,
            "value": null
          }
        },
        {
          "event_id": "dev-case_001-action-2",
          "tool_id": "trial_shuffle_within_subject",
          "prediction": {
            "scoring_status": "numeric",
            "metric_key": "trial_shuffle_trial_ba_mean",
            "primary_direction": "near_zero",
            "threshold": 0.05,
            "check_facts": [],
            "conditional_predictions": [
              {
                "hypothesis_id": "H1",
                "direction": "positive",
                "rationale": "If trial content drives performance, shuffling labels within a subject should break the task mapping for each new label configuration, reducing BA to chance."
              },
              {
                "hypothesis_id": "H2",
                "direction": "negative",
                "rationale": "If identity effects drive performance, permuting labels while preserving class counts might still allow metadata-based prediction if identities are preserved; however, the tool permutes within subject so this is less clear. We expect near-zero gap as a baseline."
              }
            ],
            "update_rule_if_opposite": "If BA remains high after shuffling (positive direction), H2 gains support over H1 regarding identity effects persisting despite label permutation."
          },
          "result_metrics": {
            "trial_shuffle_window_ba_mean": 0.99267578125,
            "trial_shuffle_window_ba_std": 0.0010918300671385692,
            "trial_shuffle_window_ba_min": 0.990234375,
            "trial_shuffle_window_ba_max": 0.994140625,
            "trial_shuffle_trial_ba_mean": 0.4953856313208771,
            "trial_shuffle_trial_ba_std": 0.01588968644948103,
            "trial_shuffle_trial_ba_min": 0.47433035714285715,
            "trial_shuffle_trial_ba_max": 0.5229232933692195,
            "trial_shuffle_gap_mean": 0.4972901499291229,
            "trial_shuffle_gap_std": 0.01618661000619954,
            "trial_shuffle_gap_min": 0.4712173316307805,
            "trial_shuffle_gap_max": 0.5198102678571428
          },
          "valid": true,
          "score": {
            "status": "scored",
            "hit": true,
            "observed_direction": "near_zero",
            "metric_key": "trial_shuffle_trial_ba_mean",
            "value": 0.4953856313208771,
            "reference": 0.5,
            "delta": -0.004614368679122904
          }
        },
        {
          "event_id": "dev-case_001-action-3",
          "tool_id": "trial_random_labels",
          "prediction": {
            "scoring_status": "numeric",
            "metric_key": "trial_random_trial_ba_mean",
            "primary_direction": "near_zero",
            "threshold": 0.05,
            "check_facts": [],
            "conditional_predictions": [
              {
                "hypothesis_id": "H1",
                "direction": "positive",
                "rationale": "If trial content drives performance, randomizing labels at the trial level should break any task mapping for each new label configuration, reducing BA to chance."
              },
              {
                "hypothesis_id": "H3",
                "direction": "negative",
                "rationale": "If session identity effects drive performance, permuting labels within trials while preserving class counts might still allow metadata-based prediction if sessions are preserved; however, the tool randomizes at trial level so this is less clear. We expect near-zero gap as a baseline."
              }
            ],
            "update_rule_if_opposite": "If BA remains high after shuffling (positive direction), H3 gains support over H1 regarding identity effects persisting despite label permutation."
          },
          "result_metrics": {
            "trial_random_window_ba_mean": 0.99189453125,
            "trial_random_window_ba_std": 0.0015160326851816426,
            "trial_random_window_ba_min": 0.9892578125,
            "trial_random_window_ba_max": 0.994140625,
            "trial_random_trial_ba_mean": 0.5079608552991515,
            "trial_random_trial_ba_std": 0.012052657632144298,
            "trial_random_trial_ba_min": 0.4826490713587488,
            "trial_random_trial_ba_max": 0.5273194271481942,
            "trial_random_gap_mean": 0.4839336759508486,
            "trial_random_gap_std": 0.01131378619893426,
            "trial_random_gap_min": 0.46682119785180576,
            "trial_random_gap_max": 0.5075853036412512
          },
          "valid": true,
          "score": {
            "status": "scored",
            "hit": true,
            "observed_direction": "near_zero",
            "metric_key": "trial_random_trial_ba_mean",
            "value": 0.5079608552991515,
            "reference": 0.5,
            "delta": 0.00796085529915147
          }
        }
      ],
      "stop_reason": "Both H1 and H3 are supported by the evidence. The window split is high, indicating session overlap matters (supporting H3). However, both req_2 (shuffling within subject) and req_3 (randomizing labels at trial level) result in near-zero gaps for trial splits, which contradicts H1's prediction of task-specific transfer but aligns with the null hypothesis that no specific mechanism drives performance beyond chance. Since neither permutation test supports H1 or H3 over a random baseline, we must conclude that the high window split is likely due to session overlap (H3) while the trial-level performance suggests no robust trial-specific learning exists in this setup."
    },
    {
      "episode_id": "study_20261019_case_002_dev_s0",
      "case_id": "case_002",
      "status": "completed",
      "events": [
        {
          "event_id": "dev-case_002-action-1",
          "tool_id": "split_audit",
          "prediction": {
            "scoring_status": "not_applicable",
            "metric_key": null,
            "primary_direction": null,
            "threshold": 0.05,
            "check_facts": [
              "Inspect overlap counts for sample/trial/session/subject in window and trial splits.",
              "Verify label proportions per group (train/test) to see if imbalance correlates with performance gaps."
            ],
            "conditional_predictions": [],
            "update_rule_if_opposite": ""
          },
          "result_metrics": {
            "window_balanced_accuracy": 0.9658203125,
            "window_accuracy": 0.9658203125,
            "window_n_train": 3072.0,
            "window_n_test": 1024.0,
            "window_n_train_trials": 512.0,
            "window_n_test_trials": 512.0,
            "window_n_train_subjects": 16.0,
            "window_n_test_subjects": 16.0,
            "window_trial_aggregated_balanced_accuracy": 0.96875,
            "window_trial_aggregated_n_trials": 512.0,
            "trial_balanced_accuracy": 0.9736328125,
            "trial_accuracy": 0.9736328125,
            "trial_n_train": 3072.0,
            "trial_n_test": 1024.0,
            "trial_n_train_trials": 384.0,
            "trial_n_test_trials": 128.0,
            "trial_n_train_subjects": 16.0,
            "trial_n_test_subjects": 16.0,
            "trial_trial_aggregated_balanced_accuracy": 1.0,
            "trial_trial_aggregated_n_trials": 128.0,
            "subject_balanced_accuracy": 0.5615234375,
            "subject_accuracy": 0.5615234375,
            "subject_n_train": 3072.0,
            "subject_n_test": 1024.0,
            "subject_n_train_trials": 384.0,
            "subject_n_test_trials": 128.0,
            "subject_n_train_subjects": 12.0,
            "subject_n_test_subjects": 4.0,
            "subject_trial_aggregated_balanced_accuracy": 0.640625,
            "subject_trial_aggregated_n_trials": 128.0,
            "gap_window_minus_trial": -0.0078125,
            "gap_window_minus_subject": 0.404296875,
            "gap_trial_minus_subject": 0.412109375
          },
          "valid": true,
          "score": {
            "status": "not_applicable",
            "hit": null,
            "observed_direction": null,
            "metric_key": null,
            "value": null
          }
        },
        {
          "event_id": "dev-case_002-action-2",
          "tool_id": "trial_shuffle_within_subject",
          "prediction": {
            "scoring_status": "numeric",
            "metric_key": "trial_shuffle_trial_ba_mean",
            "primary_direction": "near_zero",
            "threshold": 0.05,
            "check_facts": [],
            "conditional_predictions": [
              {
                "hypothesis_id": "H1",
                "direction": "positive",
                "rationale": "If trial-specific signatures exist and are preserved within subjects but shuffled across trials, performance should drop significantly if the shuffle breaks the trial-task relation."
              },
              {
                "hypothesis_id": "H2",
                "direction": "near_zero",
                "rationale": "Identity effects persist regardless of label permutation within a subject; shuffling labels per window while keeping class counts constant might not destroy identity-based prediction, but this tool permutes at the trial level? Wait: 'permute labels within each subject'. If H2 is true (identity), performance should remain high even if we shuffle labels as long as the underlying feature-label mapping for that subject remains. However, the tool description says 'permute labels within each subject while preserving class counts; window and trial splits.' This breaks any specific label-to-trial association but keeps identity intact? Actually, H2 relies on ID predicting label. If we permute labels per subject (keeping count), does the model still predict based on ID? Yes, if it's purely ID-based. So performance should remain high for H2."
              }
            ],
            "update_rule_if_opposite": "If trial_shuffle_trial_ba_mean is positive (>0.5+epsilon) or near 1.0, this supports H2 (identity effects). If it drops to chance (~0.5), this supports H1 (trial-specific signatures)."
          },
          "result_metrics": {
            "trial_shuffle_window_ba_mean": 0.50283203125,
            "trial_shuffle_window_ba_std": 0.011104078186331546,
            "trial_shuffle_window_ba_min": 0.4873046875,
            "trial_shuffle_window_ba_max": 0.529296875,
            "trial_shuffle_trial_ba_mean": 0.47918276188924247,
            "trial_shuffle_trial_ba_std": 0.017458940412799964,
            "trial_shuffle_trial_ba_min": 0.4510337655982383,
            "trial_shuffle_trial_ba_max": 0.5085025691216051,
            "trial_shuffle_gap_mean": 0.023649269360757508,
            "trial_shuffle_gap_std": 0.01589028700952168,
            "trial_shuffle_gap_min": -0.007729347626620919,
            "trial_shuffle_gap_max": 0.03759049670087977
          },
          "valid": true,
          "score": {
            "status": "scored",
            "hit": true,
            "observed_direction": "near_zero",
            "metric_key": "trial_shuffle_trial_ba_mean",
            "value": 0.47918276188924247,
            "reference": 0.5,
            "delta": -0.02081723811075753
          }
        },
        {
          "event_id": "dev-case_002-action-3",
          "tool_id": "trial_random_labels",
          "prediction": {
            "scoring_status": "numeric",
            "metric_key": "trial_random_trial_ba_mean",
            "primary_direction": "near_zero",
            "threshold": 0.05,
            "check_facts": [],
            "conditional_predictions": [
              {
                "hypothesis_id": "H1",
                "direction": "positive",
                "rationale": "If trial-specific signatures exist and are preserved by randomization (which they shouldn't be if labels change), performance should drop. Wait, this tool reassigns labels at the trial level. If H1 is true (trial content matters), changing labels destroys signal -> near_zero."
              },
              {
                "hypothesis_id": "H3",
                "direction": "near_zero",
                "rationale": "If session identity drives performance, and we reassign labels at the trial level within sessions? No, 'trial_random_labels' reassigned at trial level. If H3 is true (session ID), changing label assignment per trial should break it if trials are distinct units of signal but not session. Actually, if H3 relies on Session ID predicting Label, and we shuffle Labels *within* Trials (or across?), the tool description says 'labels reassigned at the trial level'. This breaks any specific mapping between Trial content and Label. If performance remains high (>0.5), it implies labels are predictable from something else preserved by this shuffling? Or maybe H3 is about Session ID, but if we shuffle labels per trial, does that break session prediction? Yes, because label count changes or assignment becomes random relative to features."
              }
            ],
            "update_rule_if_opposite": ""
          },
          "result_metrics": {
            "trial_random_window_ba_mean": 0.51103515625,
            "trial_random_window_ba_std": 0.017681175799734952,
            "trial_random_window_ba_min": 0.4814453125,
            "trial_random_window_ba_max": 0.54296875,
            "trial_random_trial_ba_mean": 0.4874650654260623,
            "trial_random_trial_ba_std": 0.030155314011579722,
            "trial_random_trial_ba_min": 0.43880496192581675,
            "trial_random_trial_ba_max": 0.5458984375,
            "trial_random_gap_mean": 0.02357009082393769,
            "trial_random_gap_std": 0.029611614018305497,
            "trial_random_gap_min": -0.0234375,
            "trial_random_gap_max": 0.060546875
          },
          "valid": true,
          "score": {
            "status": "scored",
            "hit": true,
            "observed_direction": "near_zero",
            "metric_key": "trial_random_trial_ba_mean",
            "value": 0.4874650654260623,
            "reference": 0.5,
            "delta": -0.012534934573937673
          }
        }
      ],
      "stop_reason": "Both H1 and H3 are supported by evidence. Trial shuffling (H1) broke performance, while session-based effects (H3) remain plausible but less likely given the lack of subject overlap in other splits."
    }
  ],
  "validation_failures": [],
  "note": "Public development facts only; no generator mechanism, hidden answer, or holdout result."
}
