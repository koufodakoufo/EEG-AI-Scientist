# Minimal executable emotion study using existing public data

Scope: literature/data description only. This plan does **not** scan private data,
does **not** assume new collection, and is not an executed EEG result.

## 1. What the existing material actually offers

| source | design | what it can support | what it cannot support |
|---|---|---|---|
| `ev_97eaa43a3d81` music/affective dataset | 19 healthy adults; calibration/training/testing sessions; trial-level affect ratings; EEG/GSR/ECG | within-person across-session variation **if** participants and stimuli can be linked | stable trait if session/stimulus overlap is absent |
| `ev_6619560afa7e` FACED | 123 subjects, 28 videos, 12 ratings per trial, single recording per subject | cross-subject benchmark; within-session rating prediction | within-person state-vs-trait separation (one session per subject) |
| `ev_fad98f5a28bb` test-retest | 60 participants, 3 sessions, short/long retest; cognitive states, not emotion trials | measurement reliability / session variance template | trial-level emotion prediction (no emotion-induction ratings) |
| `ev_d3f89ccca87f` 8-day ICA study | 10 subjects, 8 days, music ratings | evidence of session non-stationarity | public raw data / a simple reusable trial table |

The smallest **executable** study is therefore a secondary analysis of the music
dataset, conditional on metadata. FACED can be an external cross-subject
benchmark; the test-retest dataset can calibrate reliability, but cannot replace
the emotion-rating arm.

## 2. Minimal analysis (no new collection)

### Step 0 — metadata audit (first executable step)

Before any model training, check and record:

1. participant IDs that actually link calibration/training/testing sessions;
2. stimulus IDs and whether the same music excerpts recur across sessions;
3. exact rating items/scales and when they were collected;
4. session dates/intervals and time-of-day;
5. raw EEG availability, license, channel montage, sampling rate, preprocessing;
6. artifact rejection, interpolation, and bad-channel handling;
7. trial timestamps and alignment between EEG, music, and ratings;
8. available state/trait questionnaires (sleep, mood, personality, response style).

If items 1–3 are missing, the dataset cannot identify the state-vs-trait
contrast; the honest output is a metadata report, not a trained model.

### Step 1 — one multilevel analysis (if metadata pass)

For participant \(p\), session \(s\), trial \(t\):

- `trait_p` = participant mean of EEG features across sessions;
- `state_pt` = trial feature minus the participant-session mean (within-session
  deviation), with session random intercept;
- `rating_pt` = trial-level valence/arousal rating.

Fit one mixed model with crossed person and session random effects:

`rating = intercept + b_trait * trait_p + b_state * state_pt + session_random + person_random + error`

Do **not** sequentially subtract person means and then session means; estimate
the components jointly. Report variance components \(\sigma^2_{person}\),
\(\sigma^2_{session}\), \(\sigma^2_{trial}\).

### Step 2 — out-of-sample checks

- Fit on sessions 1–2, test on session 3 (participants with all three sessions).
- Compare three models: person-mean only, within-session state only, both.
- Baselines: identity-only classifier; within-person label permutation preserving
  each person’s mean; session/time covariates.
- Primary observable: held-out-session incremental \(R^2\) for trial ratings from
  `state_pt` after person/session terms.
- Secondary: between-person correlation of `trait_p` with person-mean rating, and
  identity decoding accuracy.

### Step 3 — interpretation rules

- No detection is not falsification: pre-specify an equivalence margin and report
  the confidence interval; say “not supported at this sensitivity”, not “proved
  absent”.
- Identity decoding is stable individual information, not an emotional trait;
  anatomy, impedance, hardware, and response style remain candidates.
- A stable person mean can be a rating-scale habit; it is not “trait affect”
  without an external anchor.

## 3. Missing metadata (must be listed, not guessed)

- exact participant/session/stimulus linkage across the three music datasets;
- whether the same excerpts are repeated across sessions;
- rating scale and collection timing;
- session intervals and time-of-day;
- raw EEG access/license and preprocessing provenance;
- artifact/interpolation/bad-channel records;
- trial timestamps and event markers;
- state/trait questionnaires and response-style measures;
- subject-level demographic/clinical covariates (only if consented and public).

## 4. What would count as executable now

**Conditional pass:** if the metadata audit confirms linked participants and
recurring stimuli with trial ratings, run Step 1–2 on the existing public data.
**Conditional stop:** if it does not, publish the metadata audit and request the
missing fields; do not collect new EEG and do not use FACED alone to claim
state-vs-trait separation.

## 5. What this cannot establish

Even a successful analysis would not separate emotional trait from stable
response-style/anatomical/hardware signatures without an independent anchor. It
would not establish a neural mechanism, and it would not be a new EEG finding.
