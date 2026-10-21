# CORE CODE WALKTHROUGH

This is a reading guide, not a line-by-line transcript. LLM = Large Language Model, EEG = Electroencephalography, RSI = Recursive Self-Improvement. The project does **not** train an EEG foundation model and does **not** demonstrate RSI.

## 1. `schema.py`: a scientific claim as a structured object

- Input: model JSON, case JSON, experiment results.
- Output: Pydantic `Decision`, `ExperimentRequest`, `Prediction`, `ExperimentResult`; frozen dataclasses for numpy arrays and splits.
- Core logic: `Decision` requires exactly one of `action` and `stop`; numeric predictions require a metric key and direction; `not_applicable` requires check facts; arrays are validated for shape, labels, and global IDs.
- Why: the controller, not the model, decides what is executable. Types encode the minimum traceability fields.
- How to check: read `Decision`, `Prediction`, `FeatureDataset.__post_init__`, and `ExperimentResult._finite_metrics` in `src/eeg_scientist/schema.py`.

Self-test:
1. Which fields make a prediction auditable before the result? (Answer: `metric_key`, `primary_direction`, `threshold`, `update_rule_if_opposite`, and the sealed event in `storage.py`.)
2. What happens to a `not_applicable` prediction in the numeric hit-rate denominator? (Answer: it is reported separately and excluded from the numeric denominator in `score_prediction`.)

## 2. `splits.py`: why a shuffle does not remove identity

- Input: `FeatureDataset`, split level, seed.
- Output: `SplitIndices` with train/test row indices and `SplitAudit`.
- Core logic: window split keeps some windows of the same trial on both sides; trial split removes trial overlap; subject split removes subject overlap. The audit reports sample/trial/session/subject intersections and single-class invalidity.
- Why: a high random-shuffle score can still share trial identity; the estimand depends on which unit is held out.
- How to check: `build_split`, `audit_split`, and `tests/test_core.py::test_subject_split_disjoint`.

Self-test:
1. Which intersections are allowed for a window split? (Answer: subject/session/trial overlap is allowed; sample overlap is not.)
2. Which split is the strictest for a new participant? (Answer: subject split.)

## 3. `experiments.py`: trial random labels versus window random labels

- Input: dataset, sealed experiment request, fixed context (splits, random label seeds, classifier).
- Output: `ExperimentResult` with metrics, audit, randomization distribution, and validity.
- Core logic: every fit creates a new `StandardScaler` + `KNeighborsClassifier(n_neighbors=1)` pipeline on training rows only. `trial_random_labels` reassigns labels at trial level and shares them across windows; `window_random_labels` reassigns independently per window. `metadata_only` uses one-hot subject/session, not the feature matrix.
- Why: each fit on test rows would leak scaling; the random-label level changes the estimand.
- How to check: `fit_and_score`, `make_trial_random_labels`, `make_window_random_labels`, `_metadata_only`, and `tests/test_core.py`.

Self-test:
1. Why is `StandardScaler` inside the pipeline? (Answer: it is fit on training rows only; see `tests/test_core.py::test_scaler_fit_uses_training_rows_only`.)
2. Why does a window-random-label result not get a trial-aggregated score? (Answer: there is no trial-level true label after independent window randomization.)

## 4. `runner.py`: why the prediction is written first

- Input: `EpisodeConfig`, provider, public case.
- Output: `EpisodeSummary`, run directory with requests, predictions, results, events, state, final.
- Core logic: the controller builds a public request, calls the model, validates the decision, seals the prediction, executes the experiment, saves the result, and only then asks for the next decision. Up to three actions and four normal calls per episode; after three actions it forces a conclusion.
- Why: a prediction written after the result is not a prediction. The seal is an audit record, not external notarization.
- How to check: `run_episode`, `seal_prediction`, `run_sealed_experiment`, and the event-order test.

Self-test:
1. What happens if the model requests an experiment without a valid sealed prediction? (Answer: `run_sealed_experiment` refuses.)
2. Where is the action budget enforced? (Answer: the runner checks `state.actions_used` and sets `force_stop` after the third action.)

## 5. `scientist.py` and `provider.py`: what the model actually receives

- Input: `PublicCase`, rule text, public development facts, action history, tool specifications.
- Output: messages, parsed `Decision`, optional one-shot format repair.
- Core logic: the model never receives `CaseSpec`, family, seeds, hidden mechanism, other cases, or holdout results. The provider calls local Ollama native `/api/chat` with `think=false`, `format=json`, temperature 0. The repair call sees only the malformed output and validation error, not an unexecuted experiment result.
- Why: a model with repository access could read answers; the local model has no tools. The provider is a real_llm call, not a mock.
- How to check: `build_request`, `parse_decision`, `build_repair_request`, `OllamaProvider.decide`, and the secret-redaction test.

Self-test:
1. Which private fields are absent from the public request? (Answer: family, data seed, generator parameters, hidden answer, other cases, and holdout results.)
2. What is the difference between backend `real_llm` and `mock`? (Answer: `real_llm` records an actual provider response and usage; `mock` is only a test double and cannot satisfy E1/E2.)

## 6. `study.py`: what S0 and S1 share

- Input: study config, provider, private case specs.
- Output: development facts, Meta update, frozen S0/S1/facts/tools/model hashes, paired holdout runs.
- Core logic: S0 runs the two development cases; the Meta call sees only public development facts and event IDs; S1 adds up to three method rules; the freeze manifest records hashes; each holdout case runs S0 and S1 in pre-registered order with the same facts, tools, data, and model. The only allowed difference is the rule text.
- Why: if S1 sees holdout results or different tools, the comparison is contaminated.
- How to check: `freeze_study`, `_meta_update`, `_pair_order`, `tests/test_scientist_provider.py::test_s0_s1_share_same_public_facts_and_tools`, and `tests/test_scientist_provider.py::test_meta_request_uses_only_supplied_facts`.

Self-test:
1. What is frozen besides the rule text? (Answer: development facts, tool specs, model info, case-spec hashes, code hashes, seeds, classifier, and pair order.)
2. What happens if S1 is changed after freeze? (Answer: the study refuses to continue; a new version is required.)
