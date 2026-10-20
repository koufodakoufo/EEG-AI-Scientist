# DATA REQUIREMENTS — minimal real-EEG extension (Task E2)

Status: **not executed on real EEG.** This repository contains synthetic EEG-style feature tables and an artificial fixture only. No recorded EEG dataset is configured here, and the task did not authorise scanning other projects or the X: drive. `X:\projects\daily-emo-eeg` was not read.

The purpose of this file is to define the smallest dataset and metadata that would let the priority experiment be run without changing the scientific question.

## 1. Minimum viable table

One row per analysis window (or per chosen sample unit), stored as a UTF-8 CSV:

| column | required | meaning |
|---|---|---|
| `sample_id` | yes | unique row/window identifier; never reused across subjects |
| `subject_id` | yes | anonymised subject key (e.g. `sub-01`); no names, student IDs, or birth dates |
| `session_id` | yes | recording session key (e.g. `sub-01_ses-01`) |
| `trial_id` | yes | trial key unique within subject/session; all windows of a trial share it |
| `label` | yes | binary label `-1` or `1` only, constant within a trial; decimal labels such as `1.0` or `1.5` are rejected, not rounded |

**Current entry is binary-only.** The loader does not accept multi-class labels and does not silently convert decimal or floating-point label text to integers. Supporting another label domain would be a separate, reviewed change, not part of this handoff.
| `f_00 … f_NN` | yes, ≥ 2 columns | numeric features; no strings, no NaNs |

Feature columns must be produced by a versioned, training-independent preprocessing pipeline. If a learned transform, ICA unmixing, channel selection, or normalization was fitted, record which data it was fitted on. Any transform fitted on the full dataset before cross-validation is a leakage risk and must be declared.

## 2. Required metadata (separate JSON, no raw EEG)

- dataset name/version and local file hash;
- sampling rate, channel list, reference, filter band, window length/overlap, ICA status;
- label definition and event/trigger mapping, with the trigger file version;
- subject/session/trial counts, class counts, and exclusions (bad trials/channels);
- split seed(s) and the exact grouping rule (window / trial / session / subject);
- preprocessing config hash and code commit.

Do not store participant names, exact dates of birth, contact details, or raw EEG in this repository or any model message. The project table can be built locally; only aggregated, non-identifying features and split audits should leave the local machine.

## 3. Sample hierarchy and minimum pilot size

The inferential unit is the **subject**, not the window. Windows are repeated measurements nested in trials, sessions, and subjects.

A defensible pilot (not a power calculation) would need at least:

- ≥ 12 subjects, ≥ 2 sessions per subject;
- ≥ 40 trials per session with both classes represented;
- ≥ 4 windows per trial (more windows increase precision but not the number of independent subjects);
- labels balanced within session; report per-subject and per-session class counts;
- enough test subjects (≥ 4) and test sessions to estimate between-subject/session variability.

With fewer subjects/sessions, confidence intervals will be unstable. Do not report a single held-out split as if it estimated population performance.

## 4. Splits and controls: required by the protocol vs implemented now

The research protocol would eventually need four split levels:

1. **Window split:** some windows of a trial in train, other windows of the same trial in test. This is a seen-trial control, not a generalization estimate.
2. **Trial split:** all windows of a trial on one side only; subjects/sessions may still overlap.
3. **Session split:** test sessions unseen; subjects may overlap.
4. **Subject split:** test subjects unseen; no subject/session/trial overlap.

**Current implementation status (deliberately not expanded in this handoff):**

| split level | implemented in `dataset_io.check_feature_table` | note |
|---|---|---|
| window | yes | same-trial windows can cross train/test |
| trial | yes | trial overlap zero; subject/session may still overlap |
| subject | yes | subject/session/trial overlap zero |
| **session** | **no** | `session_id` is retained for audit only; there is **no** session-held-out split |

Do not describe a run as “session-held-out” merely because the table contains `session_id`. The current `check_feature_table` output says `session_split_supported: false` and lists `split_levels_supported: ["window", "trial", "subject"]`. Expanding to session-level splitting is a separate data-system change and was intentionally **not** done now.

Every run must save the subject/session/trial intersection audit. A trial-level permutation must be applied at the trial level and shared by all windows of that trial; a window-level permutation is a different control and must not be described as trial-level.

## 5. What is missing right now

- No recorded EEG table with the columns above exists in this repository.
- No trigger mapping file or preprocessing provenance is configured here.
- No data-permission statement covers `X:\projects\daily-emo-eeg` or any other project.
- Therefore no real-data split, classifier, or scientific claim was produced.

## 6. What was implemented instead

- `src/eeg_scientist/dataset_io.py`: strict **binary** CSV loader (decimal labels rejected), label/sample/trial validation, fixture writer, and split/overlap audit for window/trial/subject. Session-level splitting is not implemented.
- `eeg_scientist.cli check-dataset --path <csv> [--write-fixture]`: runnable entry point.
- `tests/test_flash_stack.py::test_dataset_fixture_roundtrip`: verifies the loader and split audit on an artificial fixture.

The fixture is **not** EEG evidence. It only proves that a real table with these columns would be read and split correctly.

## 7. Commands

```powershell
cd X:\projects\EEG-AI-Scientist
$env:PYTHONPATH='src'
$py='C:\Users\14090\anaconda3\python.exe'

# create and check the artificial fixture (engineering only)
& $py -m eeg_scientist.cli check-dataset --path runs\flash_20261020_0058\fixture\artificial.csv --write-fixture

# check a real table once it exists (not run tonight)
& $py -m eeg_scientist.cli check-dataset --path data\processed\features_v1.csv --split-seed 20261020
```

A `check-dataset` exit code of 0 means the format and split audits passed; it does **not** mean an EEG hypothesis was tested.
