# MANUAL REVIEW — dsh initial, not a scientific score

Scope: the four primary proposals selected by the frozen rule **first accepted
attempt per arm/repeat**. The separate machine-readable file
`reviews/FORMAT_INTEGRITY_CHECK.md` only checks format/trace integrity. This file
contains dsh's initial qualitative review; it is not independent expert review
and does not establish correctness. No real EEG data were collected or analyzed.

## 1. Selection and counts

- Attempts: **10**; accepted: **6**; primary proposals: **4**.
- Failed attempts: **4**. Two later accepted retries are recorded as secondary
  and are not used as additional evidence.
- Primary selection: `baseline__01`, `baseline__02__retry`,
  `meta_rule__01__retry2`, `meta_rule__02__retry`.
- Baseline primary cost: 0.236454 + 0.21853 = **0.454984 CNY**.
- Meta-rule primary cost: 0.198848 + 0.22541 = **0.424258 CNY**.
- Primary total: **0.879242 CNY**. Whole study (including failed/retry/material/
  Meta attempts): **2.253552 / 10 CNY**.
- Meta decision: one rule accepted (citation verification against the actual read
  range). Meta saw only the old `literature_v1` trajectory and labelled review
  feedback, not the new question/materials/answers/scores.

## 2. Scores (dsh 0–2, subjective)

| proposal | arm | citation support | reasoning | discriminability | executability | cost | note |
|---|---|---|---|---:|---:|---:|---:|
| proposal_01 (`baseline__02__retry`) | baseline | 2 | 2 | 2 | 2 | 2 | strong ICC/permutation model; DEAP 0.62/0.64 and class-imbalance numbers are source-supported if attributed correctly |
| proposal_02 (`baseline__01`) | baseline | 2 | 2 | 2 | 2 | 2 | strongest experiment design: person × session × fixed stimulus, 2×2 generalization matrix |
| proposal_03 (`meta_rule__02__retry`) | meta_rule | 2 | 1 | 2 | 2 | 2 | good variance decomposition; “1-s adjacent epoch” detail is an inference, and “≈0 → all hypotheses falsified” is too strong |
| proposal_04 (`meta_rule__01__retry2`) | meta_rule | 2 | 1 | 2 | 2 | 2 | explicit read-range section; person/session centering steps conflate components; otherwise clear |

These scores are a working aid, not a measurement.

## 3. Did the Meta rule change anything?

**Behavioral signature:** partially. `proposal_04` ends with an explicit list of
the evidence IDs and character ranges actually read. `proposal_03` has a read
scope/limitations section. The baseline proposals also contain “读法” and
“提取范围” caveats, so this is not unique.

**Coverage:** the Meta group cites 4 sources in each primary proposal; the
baseline group cites 6 in each. Fewer sources is not automatically better.

**Conclusion:** the rule changed citation/reporting style, but there is **no
clear improvement in scientific quality**. `proposal_02` remains the strongest
design; the Meta proposals are comparable, not better. With 2+2 primary runs,
this is descriptive only.

## 4. Common design that survives review

All four proposals converge on the same literature-grounded structure:

1. A single-session dataset cannot separate a person’s stable level from a
   session/state offset; repeated sessions with a fixed stimulus set are needed.
2. Estimate person, session, and trial-level variance jointly rather than
   relying on pooled decoding accuracy.
3. Include identity decoding, within-person permutation, and session/state
   covariates as controls.
4. Use trial-level ratings and both within-person and between-person predictions.
5. Even then, stable non-emotional individual signatures and rating-scale habits
   remain confounded with “trait”.

This is a proposal, **not an EEG result**.

## 5. Specific flags for human review

1. **Absence of evidence vs falsification.** `proposal_03` treats a near-zero
   within-person effect as simultaneously falsifying H1/H2/H3; this requires an
   equivalence margin and adequate power. See `PROPOSAL_CORRECTIONS.md` §2.
2. **Individual vs session centering.** `proposal_04` subtracts a person-session
   mean under the label “个体中心化”; the two components are not separable by
   sequential centering. See §3.
3. **Identity ≠ emotional trait.** H2 in `proposal_01`/`proposal_02` and the
   trait language in `proposal_03` need an external anchor; identity decoding can
   reflect anatomy, impedance, hardware, or response style. See §4.
4. **Numeric qualification.** The 1-s/adjacent-epoch detail is not located in the
   extracted FACED text; “30–40% valence commonality” is a broad summary of 30%
   and 40% specific tendencies. See `PROPOSAL_CORRECTIONS.md` §1.
5. **No external criterion.** None of the proposals distinguishes emotional trait
   from response-style trait with an independent measure.

## 6. Cost

Primary-run costs (peak-rate accounting): baseline 0.2365 + 0.2185 CNY; Meta
0.1988 + 0.2254 CNY. Whole-study spend is **CNY 2.253552 / 10** with no unknown
cost. Including failed/retry attempts, the baseline arm cost 0.8523 CNY and the
Meta arm 1.3008 CNY; retries make the Meta arm more expensive overall.

## 7. What a human should do next

1. Read `PROPOSAL_CORRECTIONS.md` before reusing any claim.
2. Score the four blinded proposals in `reviews/blinded/` before opening `KEY.json`.
3. Check the flagged numeric details against source snapshots.
4. Decide whether the citation-discipline Meta rule is worth keeping; current
   evidence does not justify claiming improvement.
5. Do not treat the proposals as real EEG findings.
