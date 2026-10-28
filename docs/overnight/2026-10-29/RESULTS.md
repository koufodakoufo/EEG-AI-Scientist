# Frozen synthetic comparison results

This is a synthetic mechanism study, not real EEG or a reproduction of BrainPEC. Inputs, skill and condition order were frozen before holdout. All four launched holdout episodes are retained. M16's provider capacity interruption is an external failure; it is not evidence of lower baseline research ability.

| Episode | Condition | Launch result / seconds | Extracted claims | Reference P / R / F1 | Interpretation |
|---|---|---|---:|---|---|
| M12 | Dev baseline | completed / 419.031 | 30 | .0667 / 1.0000 / .1250 | Dev-only feedback for distillation; not a holdout comparison. |
| M16 | Pair 1 baseline | external capacity failure / 115.394 | 0 | 0 / 0 / 0 | Empty-submission rule retained; no complete first pair. |
| M17 | Pair 1 skill | completed / 406.549 | 30 | .1000 / .4286 / .1622 | Two unresolved coverage edges; provisional score. |
| M20 | Pair 2 skill | completed / 612.691 | 30 | 0 / .7143 / 0 | At extraction cap; complete second pair only. |
| M21 | Pair 2 baseline | completed / 522.988 | 30 | .0333 / .7143 / .0637 | At extraction cap; no evidence of skill improvement. |

M19 scores pair 1; M23 scores pair 2. Both complete-pair reports cover 5/7 reference claims. Do not average the external interruption into an apparent treatment advantage, select M17 as the best treatment result, or treat the small negative second-pair F1 difference as an estimated general effect. There is one complete pair and no uncertainty estimate for between-run skill benefit.

## Why low F1 does not imply the experiments failed

M23 marks M20's compound fixed-head claim unsupported because it adds confidence intervals and majority-baseline details absent from the short reference, despite matching the core accuracy estimates. M21's corresponding claim has the same issue. A/B recovery and additional fitted models are also outside the reference's scope. These judgments can follow the frozen closed-reference rule while yielding an unsuitable measure of broad research quality.

The extractor also joins several statements into one long quote to fit the 30-claim limit. A separate Builder-labeled toy control with identical report content changes F1 from .8 to 0 solely by packing an unsupported interval into otherwise supported claims. This is not a rescoring of the holdout and does not establish semantic judge calibration. Preserve the original scores; revise the metric only for a new version and new evaluation.

Independent arithmetic recounts 173 accuracy entries from saved predictions; all agree with public validation labels. Both completed conditions recover 97.92% quadratic property prediction versus 54.17% for the supplied fixed head, with fixed-head accuracy 95.83% / 12.50% across the two contexts. Both notice that template-preserving group permutations fail as a discriminating null. These are conclusions about invented data. No clinical or physiological claim follows.

## Separate evidence and execution outcomes

| Episode | Independent replay | Evidence binding |
|---|---|---|
| M12 | Original failed; supplemental commands all finish, 7/8 artifact hashes match. Final runtime/size diagnostic differs. | Original 2/3; supplemental 3/3, including one seeded code artifact explicitly distinguished from generated results. |
| M16 | No complete report/command manifest. | Empty/invalid submission; partial files retained. |
| M17 | Supplemental commands all finish, 9/10 hashes match; verification diagnostic differs. | 4/5 valid; mixed train/validation audit split mismatch remains. |
| M20 | Primary blocked by undisclosed 8-command and `-B` restrictions. Post-hoc core diagnostic reproduces 5/6 artifacts; final follow-up needs unseeded AMENDMENTS.json. | Primary 0/7; supplemental core binds 5/7. Neither is a full audit pass. |
| M21 | All four commands finish; 6/7 hashes match, final verification diagnostic differs. | 2/3 valid; training-labeled part of mixed artifact fails evaluator split binding. |

Hash agreement, evidence binding, semantic agreement and scientific validity are separate outputs. No episode is silently relabeled as a full exact replay pass. The replay interface needs explicit dependency declarations, options and command limits; timings and diagnostic file inventories need separate artifact semantics. Those changes must be applied uniformly in a future protocol.

## Levels, resources and limits

- **L1 passed:** implemented pipeline and scripted original-framework smoke; final Linux tests 79 + 14 passed.
- **L2 partially achieved:** sealed task/claim/evidence chain and live isolation checks are auditable; extraction granularity, semantic calibration and replay dependencies remain material gaps.
- **L3 blocked:** compatible real data/checkpoint/head/split/loader not verified; GPU allocation zero. No substitution is labeled a real pilot.
- **L4 synthetic comparison executed:** one complete frozen pair, one externally interrupted pair, same-source mechanism transfer. It does not establish leakage-free pretraining, causal skill benefit or RSI.

24/24 extra worker reservations consumed (18 CLI invocations and 6 Builder workers, including failed/cancelled work); no active model workers remain. Seventeen invocations report usage totaling 2,965,914 input tokens (2,486,272 cached) and 119,584 output tokens. These are provider totals across repeated contexts, not unique prompt size or a bill. Monetary cost and Builder-worker token usage are unknown. Largest sampled process-tree RSS was 352,153,600 bytes; each episode's enforced ceiling was 12 GiB with four-core affinity. Sampling is not a kernel cgroup ceiling.

Server nightly scope used about 505 MiB at the recorded snapshot, below 10 GiB; /data had about 326 GiB free and home about 5.58 GiB free. Known added binary download was the 28,137,324-byte code-mode host archive, plus small bubblewrap/source documents. Network-wide byte accounting was not available. Installation and all writes stayed inside the owned stage; no GPU, dataset copy, dataset mutation or GitHub push occurred.
