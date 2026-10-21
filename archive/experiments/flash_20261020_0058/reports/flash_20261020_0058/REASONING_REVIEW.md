# REASONING REVIEW — separate note, original answer untouched

Scope: this note reviews inference wording in the Scientist's `literature_v1` answer. It does **not** modify, overwrite, or replace `runs/flash_20261020_0058/research/literature_v1/final_answer.md` or `final.json`. It does not run M1 or any training. Its purpose is to prevent a reader from turning a plausible interpretation into a stronger claim than the evidence supports.

Original answer: `runs/flash_20261020_0058/research/literature_v1/final_answer.md` (frozen as the Scientist's own output).
Reviewer: dsh (developer), 2026-10-20.

## 1. Full-model fine-tuning changes the representation; it does not prove information was already in the frozen representation

**What the original answer implies.** Card 3 treats the linear-probe vs full-fine-tune gap (for example BENDR 32.18 → 51.11) as evidence that the information may already be present but not linearly readable. The five-arm plan then uses R4 (full fine-tuning) as an upper reference for “information present”.

**Why that is too strong.** Full fine-tuning updates the encoder weights. The gain can come from (a) re-weighting a representation that was already present, (b) learning a new, task-specific representation, (c) fitting subject/session/collection structure, or (d) optimization/capacity effects. A fine-tuned model's accuracy does not identify which of these happened. The frozen representation's information content must be tested with frozen readouts (R1/R2/R3), not inferred from R4.

**Revised wording.** “Full fine-tuning shows that a fine-tuned model can reach a higher score; it does not establish that the information was already linearly accessible in the frozen encoder. The frozen-readout arms and the capacity controls are what can speak to readout; R4 is a different representation, not a readout of the old one.”

## 2. “Information missing” does not imply normal-label fine-tuning ≈ shuffled-label fine-tuning

**What the original answer implies.** The falsifier says that if R4 (normal labels) is approximately equal to R5 (shuffled labels), then the “information missing” explanation gains support.

**Why that is too strong.** R4 vs R5 tests whether the label structure adds predictive value beyond a capacity/optimization baseline under this particular training recipe. A small R4−R5 difference is compatible with several states: no usable label information, information present but not exploited by that recipe, optimization variance, or label noise. It does not measure the information content of the input, and it does not establish “no information”. Conversely, a large R4−R5 difference does not prove the information is neural task information rather than a label-correlated artifact.

**Revised wording.** “R4 ≈ R5 weakens the claim that the observed gain is driven by label information under this recipe; it does not prove that no information exists. Missing information, optimization differences, and capacity can produce the same pattern. Frozen readouts and explicit null/permutation controls are needed before using this as a falsifier.”

## 3. Pre-stimulus EEG and similar baseline features are not automatically “zero task information”

**What the original answer implies.** Backup M2 proposes features “that cannot contain the task label” (pre-trial baseline channel variance, recording time, device/channel metadata) and treats them as a zero-task-information confound audit.

**Why that is too strong.** A pre-stimulus period can carry anticipation, arousal, attention, preparation, previous-trial effects, session/time-of-day, impedance, and artifact. Those can be correlated with the upcoming label or with the subject/session. “Pre-stimulus” means “before the measured stimulus”, not “independent of the task”. If such features predict the label, that is evidence of a confound or a label-correlated state; it is not automatically a pure artifact baseline, and calling it “zero task information” begs the question.

**Revised wording.** “Task-label-independent proxy features (pre-stimulus/baseline, recording time, device/channel metadata) are candidate nuisance proxies. They are not assumed to be task-free. Their independence from the label must be tested; if they predict the label, that is a confound signal, not proof that the task information is zero.”

## What remains unchanged

- All cited papers, evidence IDs, numeric values, and the priority/backup experiment choices remain the Scientist's answer. This note only narrows three inference claims.
- No M1/M2 training, no new data, and no new paid model call was performed for this review.
- The corrected character-coverage arithmetic (interval union) is in `COVERAGE_RECHECK.md`; it is a separate reporting fix.
