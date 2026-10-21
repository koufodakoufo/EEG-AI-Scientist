# EXPERIMENT PROTOCOL — flash_20261020_0058

Status labels are strict:

- **EXECUTED:** the artificial fixture split check only (`fixture_split_check`, 256 rows, 4 subjects, `real_eeg_experiment_executed: false`).
- **PLANNED:** the protocol below. It was **not** run; no real EEG features were available to this repository.
- **BLOCKED:** the multi-device identity experiment (needs a DUA and data not present here).

## Why this experiment

The priority question is whether the cross-subject drop is **missing information** or **limited readout**. The literature gives a large linear-probe vs fine-tune gap (BENDR 32.18 → 51.11 on BNCI2014001; chance 25%) but no intermediate condition that separates "information is there but not linearly readable" from "fine-tuning fits nuisance". The smallest discriminating design is a readout ladder on the **same frozen encoder and the same folds**, including a shuffled-label capacity control.

## Priority M1-A (reduced, staged)

### Stage 1 — one dataset, one encoder, four readouts

| Item | Choice |
|---|---|
| Data | BNCI2014001 (9 subjects, 2 sessions, 4-class MI, chance 25%); public |
| Encoder | one public checkpoint (CBraMod 4.0M preferred; LaBraM-Base as fallback) |
| Splits | (i) trial-disjoint within session; (ii) leave-one-subject-out (LOSO); (iii) leave-one-session-out within subject if session labels are usable |
| Readouts | R1 linear probe on frozen features; R2 R1 + **label-free** per-subject whitening/recentering estimated only from unlabeled test-session features; R4 full fine-tune; R5 full fine-tune with trial-level shuffled labels (capacity control) |
| Fixed | encoder initialization, folds, trial counts, early-stopping budget, metric (balanced accuracy), random seeds |
| Primary endpoint | BCA on the same LOSO fold for R1, R2, R4, R5; report the recovery fraction (R2−R1)/(R4−R1) with subject-level bootstrap CI (n=9; unstable, report it as such) |
| Secondary | same ladder on a clinical dataset (TUAB) to see whether the pattern is task-specific; per-subject identity decodability from the same features |

**Predictions on the same observable:**

- *Information missing:* R1 ≈ R2 ≈ low; R4's gain ≈ R5's gain (capacity/overfit, not information).
- *Readout-limited:* R1 low; R2 recovers a substantial part of R4; R4 ≫ R5.
- *Nuisance-fitting:* R4 gain tracks identity decodability; R2 recovers little; R4 ≫ R5 but the gain concentrates on subjects with high identity separability.

**Falsifier:** if R2 barely improves and R4 ≈ R5, the "information present, readout-limited" explanation loses support.

**Resource estimate (rough, not measured):** 9 LOSO folds × {R4, R5} = 18 fine-tunes; at 10–20 min per fold on one 24 GB GPU, ≈ 3–6 GPU-hours for one encoder, plus minutes for R1/R2. A second dataset/encoder doubles it. This is an estimate, not a measured run.

**Leakage controls:** R2 uses only unlabeled test-session features; labels are never used for alignment. R5 shuffles labels at the **trial** level, shared by all windows of a trial, and retrains from the same initialization. Report the exact subject/session/trial intersections for every split.

### Stage 2 — only if Stage 1 is informative

Add one more encoder and one clinical dataset; test whether the R2 recovery fraction correlates with identity decodability and with the linear/fine-tune gap. Do not add a full 5×5×3 factorial up front.

## Backup M2 (cheapest, CPU-only)

**Zero-task-information confound audit.** On one public dataset, train a classifier on features that cannot contain the task label:

- per-trial pre-stimulus baseline channel log-variance;
- recording time-of-day/block index, session index;
- device/channel-count metadata;
- class balance per session/block.

If these predict the task label above chance, any within-session score must be discounted by that baseline before interpretation. This is a **falsification/audit** experiment, not a positive result generator. Estimated cost: a few CPU-hours.

## Second branch (blocked)

Card 2 (identity/device) needs same-subject multi-device or multi-year data (PEERS-like). PEERS requires a data-use agreement and is not present. The protocol is: same subjects, different headsets, fixed preprocessing/model/task; measure cross-device EER and task BCA after removing the identity subspace. This is **BLOCKED**, not executed.

## What would change the judgment

| Result | Update |
|---|---|
| R2 recovers most of R4, R4 ≫ R5, across two datasets | "Readout-limited" becomes the leading explanation; invest in alignment/geometry, not a larger FM |
| R1 ≈ R2 ≈ low, R4 ≈ R5 | "Information missing / capacity artifact" gains support; do not claim fine-tuning reveals task information |
| R2 recovers little, R4 ≫ R5, gain tracks identity | Nuisance-fitting becomes the leading explanation; prioritize de-confounding |
| Metadata-only M2 predicts labels | Every within-session number needs a nuisance baseline; the priority question shifts to collection design |
| All effects vanish under subject-held-out splits | The literature's high scores are protocol artifacts; report that as the main result |

## Executed engineering check (not EEG evidence)

`fixture_split_check` on a 256-row artificial table:

- window split: every test trial overlaps training (trial overlap 64/64), sessions and subjects also overlap;
- trial split: trial overlap 0, but sessions (8) and subjects (4) still overlap;
- subject split: zero subject/session/trial overlap.

This only validates the loader/split audit. It cannot support an EEG claim.

## Commands

```powershell
cd X:\projects\EEG-AI-Scientist
$env:PYTHONPATH='src'
$py='C:\Users\14090\anaconda3\python.exe'

# executed: artificial fixture only
& $py -m eeg_scientist.cli check-dataset --path runs\flash_20261020_0058\fixture\artificial.csv --write-fixture

# planned: once a real feature table exists (NOT run tonight)
& $py -m eeg_scientist.cli check-dataset --path data\processed\features_v1.csv --split-seed 20261020
```

## Unresolved design issues

- Nine subjects is a small n for a recovery-fraction estimate; subject-level CIs will be wide. Do not turn a single LOSO mean into a population claim.
- Unsupervised alignment uses test-session distribution information (transductive). It is label-free but not assumption-free; report it explicitly.
- A shuffled-label fine-tune is a capacity control, not a perfect null: it can still fit subject identity. The R5 comparison is informative only together with the identity-decodability probe.
- "Task-related artifact" (eye movement, muscle, effort) remains confounded with task information even after all readout controls.
