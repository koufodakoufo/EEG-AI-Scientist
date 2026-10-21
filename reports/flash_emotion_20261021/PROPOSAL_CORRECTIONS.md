# PROPOSAL CORRECTIONS — separate note, original answers untouched

This note audits the four **primary** proposals selected by the frozen rule
(“first accepted attempt per arm/repeat”). It does **not** modify any
`final_answer.md` or `final.json`. It records corrections and uncertainties for
human review. No real EEG experiment was run.

Primary runs:

| label | arm | run | cost CNY |
|---|---|---|---:|
| proposal_01 | baseline | `baseline__02__retry` | 0.21853 |
| proposal_02 | baseline | `baseline__01` | 0.236454 |
| proposal_03 | meta_rule | `meta_rule__02__retry` | 0.22541 |
| proposal_04 | meta_rule | `meta_rule__01__retry2` | 0.198848 |

## 1. Key-number audit

| Claim in proposal(s) | Source check | Verdict |
|---|---|---|
| FACED: 123 subjects, 28 videos, 9 categories; intra-subject 78.8±1.0%, cross-subject 69.3±1.5% | Source text has 123 subjects, 28 clips, 9 categories, 10-fold CV, and 78.8/69.3 with SE | **confirmed** |
| FACED evaluation uses 1-s **adjacent** epochs / specifically 10-fold within same session | Source has 10-fold but the exact “1-s adjacent epoch” wording was not found in the extracted text | **inference / unverified detail**; proposal_03 labels the leakage risk as its own inference, which is appropriate, but the 1-s/adjacent detail should not be presented as source fact |
| 8-day study: 10 subjects, 30 channels, 80 sessions; 2–4 subjects with >6-day stable source; arousal 25% (2/8); 76.03±10.40%; 71.11±18.33% | Source text confirms these values | **confirmed** |
| “Valence cross-person commonality about 30–40%” | Source reports 30% for specific valence-related spatio-spectral tendencies and 40% for central midline beta; not one global valence commonality | **partially supported / wording too broad**; say “specific tendencies 30–40%” |
| DEAP intra-subject 0.62/0.64; DREAMER/MAHNOB z-score values | Source Table 4 has DEAP 0.62/0.64; source also reports a previous DREAMER result of 0.62 under class imbalance, and DREAMER z-score 0.50–0.52 | **confirmed if attributed correctly**; do not merge “DEAP 0.62” with “DREAMER 0.62” |
| Class imbalance 56–44% arousal, 61–39% valence | Source text confirms this for a previous study discussed by the authors | **confirmed as reported prior work**, not as this dataset’s own imbalance |
| M3D +4.47% average over non-deep methods | Source abstract/results text confirms the 4.47% claim | **confirmed** |
| Test–retest dataset: 60 participants, 3 sessions, short- and long-term design | Source text confirms | **confirmed** |

Automatic exact-string matching is unreliable because the HTML snapshots escape
punctuation (`0\.62`, `78\.8`, `%`). The verdicts above are based on normalized
source text, not only on the answer text.

## 2. Reasoning correction 1: “unobserved difference” is not automatically falsification

**Where it appears.** `proposal_03` says that if within-session/within-person
`r_state ≈ 0` while a pooled model is above chance, then H1/H2/H3 are “同时被否证”.
`proposal_01` uses an explicit falsifier with a confidence-interval upper bound,
but still treats a near-zero estimate as a decisive rejection. `proposal_03` also
calls an all-zero pattern a “strong negative result”.

**Correction.** A non-detected effect is not, by itself, evidence that the effect
is absent. “≈0” needs an equivalence margin and a power/sensitivity analysis;
a CI that includes zero is compatible with both no effect and an effect smaller
than the design can detect. The valid statement is: *this design did not detect
an effect larger than X; under the pre-specified equivalence margin, the effect
is not supported*. It is not “the hypothesis is falsified” unless the study was
designed with an equivalence test and adequate sensitivity. This matters more
here because the proposals use small N and short sessions.

## 3. Reasoning correction 2: individual-mean and session-mean centering are not interchangeable

**Where it appears.** `proposal_04` writes “C1 个体中心化（减去该人该会话的 f̄ 与 ȳ）→ 去掉稳定成分；C2 会话中心化”. Subtracting a **person-session mean** is session centering, not person centering. `proposal_01` similarly says “个体内中心化（x − x̄_s，并控制会话固定效应)”, where the notation and the session control can remove different variance components depending on the model. `proposal_03` proposes person demeaning followed by session demeaning as separate steps.

**Correction.** Person mean, session mean, and trial-level deviation are nested
components. Subtracting a person mean removes both stable between-person
differences and the person’s average session level; subtracting a session mean
afterward removes a different, non-orthogonal part. Sequential centering changes
the estimand and can manufacture or hide a state/trait contrast, especially with
unbalanced sessions. Use one explicit multilevel model with crossed person and
session random effects (and trial-level residuals), estimate variance components
jointly, and pre-specify which contrast is within-person and which is
between-person. Do not present “subtract person mean, then session mean” as if
the two components were independent.

## 4. Reasoning correction 3: identity decoding is not an emotional trait

**Where it appears.** `proposal_01`’s H2 lists “基线情感水平、人格、alpha 峰频、解剖/技术签名” together as stable individual differences and uses high identity decoding as support for H2. `proposal_02` similarly treats person-level EEG means as trait evidence. `proposal_03` says EEG individual differences are stable traits co-varying with rating style/baseline affect.

**Correction.** Identity decoding or a stable person-level mean shows that the
features carry **stable individual information**, not that the information is an
emotional trait. Anatomy, skull/scalp conductivity, electrode impedance, alpha
peak frequency, recording hardware, and response-scale habits can all produce
identity-level separability. A trait claim needs an external, independent
anchor (e.g., repeated validated affect measures, informant/behavioral measures,
or measurement invariance across occasions), and it must predict change or
stability out of sample. Until then, call it “stable non-emotion individual
difference” or “person-level offset”, not “emotional trait”.

## 5. What remains uncertain

- The four proposals agree on a repeated-session, fixed-stimulus design, but that
  is a literature-based design proposal, not an executed experiment.
- The Meta rule improved citation/read-scope wording in one proposal, but not
  consistently; with 2+2 primary runs this is not evidence of better science.
- The `1 s adjacent epoch` detail and the broad `30–40%` commonality phrasing are
  not fully supported by the extracted text.
- No proposal has an external criterion that distinguishes emotional trait from
  response style, anatomy, or hardware signature.

## 6. Preservation

Original files were not edited. See:

- `runs/flash_emotion_20261021/runs/baseline/repeat_01/final_answer.md`
- `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/final_answer.md`
- `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/final_answer.md`
- `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/final_answer.md`

This note is a reviewer correction, not a replacement for those answers.
