# HYPOTHESIS CARDS — flash_20261020_0058

These are the Scientist's three cards, condensed from `runs/flash_20261020_0058/research/literature_v1/final_answer.md` §2–§3. They are **literature-grounded proposals, not results**. No real EEG experiment was run. Bracketed claims are the Scientist's own inferences, not author conclusions.

## Card 1 — How much of a score is task, and how much is subject/session/collection?

- **Observation.** Literature fact: the common within-session protocol shuffles trials and the MOABB authors call it an upper bound; cross-session/cross-subject are outside that paper's scope [ev_f42fa7111e36]. Literature fact: cross-subject brain-to-text splits can leak and overestimate [ev_9da221287269]. **[Inference]** a substantial part of a within-session score may come from label-covarying subject/session/device signatures; no cited paper directly decomposes this proportion.
- **Why it matters.** If the nuisance share is large, investment should go to de-confounding/alignment, not a larger pretrained model. If it is small, the next investment is the objective/capacity.
- **Competing explanations.** (a) shared task information (supported by above-chance cross-subject scores, 45–53% with 25% chance) [ev_825214c78a59]; (b) nuisance signatures (supported by SSL clusters following channel count/date [ev_b63c716fd707] and identity decodability [ev_2f5e3fadf9f0]); (c) stimulus/label-prior confounds (not directly tested in the read literature).
- **Intervention / fixed conditions.** Reorder class order/position within a session, or balance classes within blocks; keep data, model, features, trial counts, folds, seeds fixed.
- **Same-observable predictions.** Δ = BCA(within-session trial-disjoint) − BCA(LOSO); BCA after removing subject/session means; BCA of a session-identity proxy predicting the task label. Shared task: moderate Δ, small drop after de-meaning, identity proxy ≈ chance. Nuisance: large Δ, LOSO near chance after de-meaning, identity proxy > chance. Stimulus/prior: within-session score itself drops after class-order reordering.
- **Falsifier.** Reordering classes leaves within-session performance almost unchanged, identity proxy stays at chance, and de-meaning costs little → the "nuisance-dominant" story loses support.
- **Minimal data.** ≥20 subjects, ≥2 sessions, class-balanced public data (BNCI multi-session or PEERS-like multi-device); PEERS requires a DUA.
- **Still indistinguishable.** Shared neural computation vs a stable task-related artifact (eye movement, muscle, effort) that also varies with the label.

> **dsh review note.** The intervention (class-order reordering) mainly tests temporal/block confounds; it does not itself separate task from subject/session signatures. The de-meaned LOSO and identity-proxy analyses carry most of the discriminative weight and should be pre-registered as primary, not secondary. Card 1 is therefore a useful framing, but its single "main intervention" is weaker than the card claims.

## Card 2 — Identity/environment is the main axis; task information is a smaller perturbation

- **Observation.** Identity is decodable (EER 6.7% after 1 day → 14.3% after 1 year) and embeddings form session/device clusters [ev_2f5e3fadf9f0]; SSL embeddings show pathology/age/gender gradients and channel-count/date clusters [ev_b63c716fd707]. **[Inference]** task information is smaller in amplitude/subspace than identity; no cited paper directly compares the two subspaces.
- **Why it matters.** If identity dominates, a subject-adversarial/alignment layer is warranted; if the subspaces are orthogonal, direct task readout is enough.
- **Competing explanations.** Identity-dominant (identity EER far below chance, stable across sessions); orthogonal/band-separated (a 2026 paper was found but not read, so it is a lead only); session/device-dominant (same-session/same-device embeddings cluster).
- **Intervention / fixed conditions.** Same subjects re-measured on a different headset; preprocessing, model, interval, and task fixed.
- **Same-observable predictions.** Cross-device EER + task BCA after removing the identity subspace. Identity-dominant: cross-device EER worsens but stays far below 50%; task BCA drops >30% after removing identity. Orthogonal: cross-device EER ≈ same-device; task BCA drops <5%. Session/device-dominant: cross-device EER collapses toward 50% and the "identity" effect disappears after controlling device.
- **Falsifier.** Cross-device EER ≈ same-device EER and removing the identity subspace barely hurts task BCA.
- **Minimal data.** Multi-device or multi-year data (PEERS-like), the largest permission gap; BNCI multi-session lacks device change, so this card can only be partially tested now.
- **Still indistinguishable.** Identity vs electrode placement/hair/impedance/amplifier; even cross-device failure cannot separate neural individual differences from wear differences.

> **dsh review note.** This card is explicitly marked as inference and its data are blocked by a DUA. It is a reasonable second-branch plan, not an executable experiment in this repository.

## Card 3 — Is the cross-subject loss missing information or limited readout? (selected extension)

- **Observation.** With the same frozen weights, linear probing is often near chance while full fine-tuning is much higher: BENDR 32.18 → 51.11; BIOT 30.88 → 34.27 (chance 25%) [ev_825214c78a59]. The benchmark has **no intermediate condition** (e.g., unsupervised per-subject alignment followed by a linear readout), so the evidence is compatible with three explanations. **[Inference]** this is the most discriminative and cheapest next question.
- **Why it matters.** If the information is present but not linearly readable, alignment/geometry correction is the cheap lever; if it is absent, the pretraining objective or data scale must change.
- **Competing explanations.** (a) information missing: linear probe near chance; counter-evidence: fine-tuning is far above chance. (b) readout-limited: 19-point gap for BENDR; counter: fine-tuning may fit nuisance. (c) fine-tuning fits nuisance: identity is highly decodable [ev_2f5e3fadf9f0] and SSL embeddings encode collection conditions [ev_b63c716fd707].
- **Intervention / fixed conditions.** Same frozen encoder, same LOSO folds, same trial counts; compare R1 linear probe, R2 linear probe + **label-free** per-subject alignment (whitening/Riemannian recentering estimated from unlabeled test-session data), R3 LoRA, R4 full fine-tune, R5 full fine-tune with shuffled labels (capacity control). Fixed encoder weights, folds, early-stopping budget, metric.
- **Same-observable predictions.** R1–R5 BCA on the same LOSO fold. Missing information: R1≈R2≈R3≈low; R4 gain ≈ R5. Readout-limited: R1 low, R2 recovers most of R4, R4 ≫ R5. Nuisance-fitting: R4 gain correlates with identity decodability; R2 recovers little; R4 ≫ R5 but still depends on subject identity.
- **Falsifier.** R2 barely improves and R4 ≈ R5 → "information present, readout-limited" loses support.
- **Minimal data.** Public weights (CBraMod 4.0M or LaBraM) + public datasets (BNCI2014001/2014004, TUAB); no new collection; low permission barrier.
- **Still indistinguishable.** Even if R2 recovers most of the gap, it cannot tell neural task information from a cross-subject-stable task-related artifact; and unsupervised alignment uses test-session distribution information (transductive leakage), which must be declared and controlled.

> **dsh review note.** This is the strongest card: it has a clean capacity control (R5) and a feasible public-data path. But M1 as written is a large factorial (3 datasets × 2 encoders × 5 splits × 5 readouts), not a minimal experiment. See `EXPERIMENT_PROTOCOL.md` for a reduced, staged version.

## Selection and deleted experiments

The Scientist selected Card 3 because it is falsifiable, cheaper than retraining a large FM, and directly informs the priority question. Deleted: (1) retraining a large FM with a different objective to attribute time/spectral/cross-channel structure — the intervention changes several factors at once and has no discriminating power; (2) collecting a new multi-session/multi-device dataset — infeasible this round; (3) using cross-subject accuracy to argue a neural mechanism — unidentifiable regardless of result [ev_200bb34828cd].

## Priority vs backup

- **Priority M1:** five readouts × non-overlapping splits on public data (see protocol).
- **Backup M2:** a cheap "zero-task-information" confound audit using only metadata/baseline features (channel variance, recording time, device/channel count) to predict task labels. If such features predict the label, any within-session score must first be discounted.
- **Second-branch handoff:** Card 2 (identity/device) remains blocked on multi-device data with a DUA.
