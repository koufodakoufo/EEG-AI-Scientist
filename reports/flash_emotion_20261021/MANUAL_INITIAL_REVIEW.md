# MANUAL INITIAL REVIEW — dsh (not a truth score)

Scope: four primary proposals from the controlled emotion state-vs-trait study. This is dsh's initial, non-blinded working review. The human-review packet is `runs/flash_emotion_20261021/reviews/blinded/`; the key is `reviews/KEY.json` and should be opened only after independent scoring. No real EEG data were collected or analyzed.

## 1. What was actually compared

- Meta decision: **rules accepted** (one citation-verification rule). Meta saw only the old `literature_v1` trajectory plus explicitly labelled `EVIDENCE_AUDIT` / `REASONING_REVIEW` feedback.
- Primary runs: baseline repeats 01 and 02; Meta-rule repeats 01 and 02. All four were accepted via `finish_study`.
- Attempts: 10 total (including failed attempts and bounded retries). Four *primary* proposals; extra accepted retries are preserved but not treated as additional evidence.
- The two groups used the same material package, system prompt, deliverables, Flash model, and per-run limits.

## 2. Scores (dsh 0–2, subjective)

| proposal | arm | citation support | reasoning | discriminability | executability | cost | note |
|---|---|---|---|---:|---:|---:|---:|
| proposal_01 | meta_rule | 2 | 2 | 2 | 2 | 1 | strong design and 6 cited IDs; read-range section present; highest primary-run cost |
| proposal_02 | baseline | 2 | 2 | 2 | 2 | 2 | strongest design: explicit within-person slope, session variance, 2×2 generalization matrix; a few numeric ranges need exact table check |
| proposal_03 | baseline | 2 | 2 | 2 | 2 | 2 | strong ICC/permutation logic; DREAMER 0.62 and class-imbalance numbers need exact source check |
| proposal_04 | meta_rule | 2 | 2 | 2 | 2 | 2 | explicit read-range section; fewer sources (4) but clear within-subject permutation control |

The scores are not a scientific quality metric. They only record whether the proposal (a) cites read material, (b) avoids obvious state/trait conflation, (c) proposes a discriminating experiment, (d) is executable, and (e) stays within budget.

## 3. Did the Meta rule change anything?

**Behavioral signature:** yes, partially.

- proposal_04 (Meta rule) ends with an explicit list of the evidence IDs and the character ranges actually read.
- proposal_01 (Meta rule) has a "提取范围与局限" section and is explicit about what was read, though it does not list exact ranges in the same format.
- The baseline proposals also contain "读法" / "提取范围" caveats, so this is not unique to the Meta group.
- The Meta group cited **4 and 6** sources in its two primary proposals; the baseline group cited **6** in each. Fewer citations is not automatically better or worse, and the Meta group is not uniformly broader.
- No proposal cites an unknown evidence ID; all cited IDs were read. No fabricated paper or DOI was found in a first pass.

**Verdict:** the rule changed citation/reporting style, but there is **no clear improvement in scientific quality**. Baseline proposal_01 is arguably the strongest design; baseline proposal_02 is also strong. The Meta group is comparable, not better. With n=2 per arm, this is descriptive only.

## 4. What the four proposals agree on

All four converge on the same structural insight:

1. A single-session dataset cannot separate a person's stable level from a session/state offset; repeated sessions with a fixed stimulus set are needed.
2. The analysis should decompose variance into person, session, and trial (or within-person) components, not just report pooled decoding accuracy.
3. Controls should include identity decoding, within-person label permutation, and session/state covariates.
4. The minimal experiment is a 3-session, fixed-stimulus, repeated-measures design with trial-level ratings and both within-person and between-person predictions.
5. Even then, stable non-emotional individual signatures and response-scale habits remain confounded with "trait".

This convergence is a literature-based proposal, **not an EEG result**.

## 5. Citation and reasoning flags for human review

- All cited IDs were read; this does not prove that every numeric detail is inside the read range. Spot checks found some numbers in the source that were not exact matches in the read slices (HTML escaping and table placement complicate automatic matching).
- `proposal_03`'s DREAMER 0.62 and class-imbalance percentages were not located exactly in the cited read text in a quick check; verify against the source before reuse.
- `proposal_01`'s claim about FACED's 1-s adjacent epochs and 10-fold within-session validation should be checked against the FACED methods/results; it may be an inference.
- `proposal_04` contains a well-scoped read-range statement, but it is not a substitute for a full source audit.
- The Meta rule itself is about citation verification, not about state/trait inference; an improvement in citation formatting would not establish an improvement in scientific reasoning.

## 6. Cost

Primary-run costs (peak-rate accounting): baseline 0.2365 + 0.2558 CNY; Meta rule 0.1988 + 0.3104 CNY. Total arm costs including failed/retry attempts: baseline 0.8523 CNY, Meta rule 1.3008 CNY. Whole-study spend at review time: **CNY 2.2536 / 10** (no unknown cost). The Meta arm's retries make it more expensive overall, so the rule group is not cheaper.

## 7. What a human should do next

1. Score the four blinded proposals independently before opening `KEY.json`.
2. Check the flagged numeric claims against the source snapshots.
3. Decide whether the Meta rule is worth keeping; the current evidence does **not** justify claiming improvement.
4. Do not treat these proposals as real EEG findings or as a test of the proposed experiment.
