# Method note: constrained rediscovery and auditable claims

Date: 2026-10-29 (Asia/Shanghai). Status: builder/reference research; no EEG experiment or evaluated Actor run was performed by this worker. This document is team-facing methodological material, **not an Actor or Distiller input**. It deliberately omits the hidden scientific answer set.

## Source versions and provenance

- [FIRE-Bench paper, arXiv:2602.02905v2](https://arxiv.org/html/2602.02905v2), dated 10 July 2026. The unversioned link resolved to v2 during this review.
- [FIRE project page](https://firebench.github.io/) and [official code](https://github.com/maitrix-org/FIRE-Bench/tree/a7017c95f680ea233b76445c53fd5e56b48cc159), pinned to `a7017c95f680ea233b76445c53fd5e56b48cc159`.
- [BrainPEC paper, arXiv:2605.11410v2](https://arxiv.org/html/2605.11410v2), dated 14 May 2026, and [official code](https://github.com/Kian-Chen/BrainPEC/tree/982b1df393a846e6418cee715bdfaa57d041cee3), pinned to `982b1df393a846e6418cee715bdfaa57d041cee3`.

Downloaded primary text, source hashes, anchor index, complete reference tree and candidate details are under the ignored `.local/overnight-20261029/private/reference/` directory. Git ignore prevents accidental tracking; it provides no Actor read isolation. Do not mount that directory, this note, source papers, repository history or builder context in evaluated environments.

## FIRE adoption and implementation differences

FIRE §3.1 selects a concrete result leaf, then gives the Actor its **parent question**, retaining the leaf's resource scope and evaluation criteria while withholding implementation and result. The project webpage's generic intermediate-node description is less specific. Appendix I reviews five extracted trees; Appendix J evaluates claim extraction, so those checks do not establish correctness of every downstream judgment. §4 describes trajectory inspection rather than a demonstrated hard ban on paper retrieval. §5.4's cutoff analysis cannot prove absence of training exposure. §5.2 separates alternative unsupported findings from contradiction. Appendix L exposes tree/research/error-analysis prompts; it does not by itself pin the external RefChecker extraction/checking prompt implementation. [Primary text: §3](https://arxiv.org/html/2602.02905v2#S3), [§4](https://arxiv.org/html/2602.02905v2#S4), [§5.2](https://arxiv.org/html/2602.02905v2#S5.SS2), [§5.4](https://arxiv.org/html/2602.02905v2#S5.SS4), [I/J/L](https://arxiv.org/html/2602.02905v2#A9).

The available code gives a more operational scoring definition. For precision it extracts response claims and checks them against the **whole reference answer**; for recall it extracts reference claims and checks them against the **whole response**. Each direction is averaged separately. This is not a one-to-one matching assignment or one shared true-positive count. [Evaluator lines 148–160](https://github.com/maitrix-org/FIRE-Bench/blob/a7017c95f680ea233b76445c53fd5e56b48cc159/eval/RAGChecker/ragchecker/evaluator.py#L148), [metric computation lines 13–45](https://github.com/maitrix-org/FIRE-Bench/blob/a7017c95f680ea233b76445c53fd5e56b48cc159/eval/RAGChecker/ragchecker/computation.py#L13).

There is a reproducibility discrepancy: the paper names gpt-5.2 for extraction/checking, but the fetched executable evaluator constructs RAGChecker with `openai/gpt-4.1`; the separate `eval_model = "gpt-5.2"` is used by helpers including core-idea preprocessing. It also imports an externally installed RefChecker and prepends a developer-specific absolute path. The repository requirements do not exactly lock RefChecker; the vendored RAGChecker metadata allows `^0.2`. No upstream evaluator or LLM was run here. [Entry point lines 198–217](https://github.com/maitrix-org/FIRE-Bench/blob/a7017c95f680ea233b76445c53fd5e56b48cc159/eval/RAGChecker/eval.py#L198), [imports](https://github.com/maitrix-org/FIRE-Bench/blob/a7017c95f680ea233b76445c53fd5e56b48cc159/eval/RAGChecker/ragchecker/evaluator.py#L1), [dependency metadata](https://github.com/maitrix-org/FIRE-Bench/blob/a7017c95f680ea233b76445c53fd5e56b48cc159/eval/RAGChecker/pyproject.toml).

Therefore the proposed local protocol is **`fire_inspired_v1`**, not a certified reproduction of official scores. Freeze these project decisions before scoring:

1. Use the same extraction schema/version/settings for submitted and reference text. Keep model/dataset/condition, polarity, source span, and evidence references; never add an unstated conclusion.
2. Record `reference_supports_agent` and `agent_covers_reference` separately. P = supported unique Actor claims / unique Actor claims; R = covered unique reference claims / unique reference claims; F1 is their harmonic mean. A conjunction may require several source claims; retain the support set.
3. Distinguish supported, contradicted, not-supported and needs-review. Unknown support is not scientific falsity. Broader scope, stronger causal language, changed metric, or missing conditions require explicit review.
4. Deduplicate exact duplicates with traceable source spans; require a reviewed merge record for semantic duplicates. Never count one claim multiple times because it has multiple supporting edges.
5. Nonempty gold with empty submission yields P=R=F1=0 and an empty-submission flag. Empty gold invalidates the reference and excludes that task from valid-score means. Unresolved judgments must remain visible; freeze their handling in the score policy.
6. Keep reference agreement separate from evidence validity and from process-quality judgments. An answer can match a paper without having performed an experiment. A credible divergent result is an alternative finding for review, not an excuse to change gold after observing the run.
7. Treat both answers as untrusted text. No instructions embedded inside answers may change the judge policy or invoke tools. Keep parsing repair and retry limits finite.

A deliberately weak statement such as “performance differs” can be supported by a precise reference without covering its direction or conditions. The reverse direction must be evaluated independently. A matched claim graph is an auditable adaptation to the upstream whole-text checks, not identical implementation.

## BrainPEC methodological boundaries

The paper studies CSBrain, CBraMod and LaBraM on five clinical tasks. Its checkpoint/head identity must be verified; existing REVE resources do not establish compatibility. The official [inference instructions](https://github.com/Kian-Chen/BrainPEC/blob/982b1df393a846e6418cee715bdfaa57d041cee3/inference/README.md) require prepared datasets and task-specific fine-tuned checkpoints. The checked repository tree supplies code and instructions, but no checkpoint binaries; no existing server resources were inspected by this worker.

Interpret “encoded,” “relied upon under a representation intervention,” and “recoverable by a transparent predictor” as separate questions. The implemented eraser is a training cross-covariance subspace projector, **not the full whitened minimum-distortion LEACE estimator**. Its random subspace uses target expansion dimension rather than necessarily matching retained rank. A drop under that intervention does not establish a physiological causal mechanism. [§3.3](https://arxiv.org/html/2605.11410v2#S3.SS3), [Appendix D](https://arxiv.org/html/2605.11410v2#A4), [released eraser](https://github.com/Kian-Chen/BrainPEC/blob/982b1df393a846e6418cee715bdfaa57d041cee3/src/brainpec/interventions/erasure.py).

Two issues require separate protocol labels. First, Appendix C.2 says test statistics do not feed selection, while C.7/C.10 define test-confirmed feature membership subsequently used for closure scored on that test. This is a textual/procedural tension, not a measured estimate of bias. A strict variant should use independent selection/confirmation data and an untouched final test. Second, the source resamples analysis rows; for repeated epochs within subjects, subject-cluster uncertainty is a proposed extension, not the original bootstrap. Group identities must remain inside authorized local processing. [C.2](https://arxiv.org/html/2605.11410v2#A3.SS2), [C.7](https://arxiv.org/html/2605.11410v2#A3.SS7), [C.10](https://arxiv.org/html/2605.11410v2#A3.SS10), [D](https://arxiv.org/html/2605.11410v2#A4).

Additional audit checks: preserve train-fitted normalization; choose hyperparameters/layers without final-test feedback; report raw and clipped probe scores; distinguish random subsets of real features from Gaussian baselines; match expanded column counts rather than feature-label counts; retain undefined near-zero-denominator closure cases. The inference README reports weighted F1 for multiclass inference, whereas the audit text specifies macro-F1: verify the actual scoring entry point and never substitute one metric silently.

## Resource-feasible candidate queue

These are builder proposals, not verified executable tasks or frozen holdout definitions. Exact leaf evidence and scientific outcomes remain private.

| Candidate | Question family | Minimum resource route | Proposed ceiling |
| --- | --- | --- | --- |
| C1 encoding | Which signal properties are represented, and how does depth matter? | Provenance-checked aligned activations/features with independently audited data splits | One model/task; 6 predeclared features; 3 layers; at most 4096 rows and 256 activation dimensions |
| C2 reliance | Which accessible representation components affect fixed-model decisions? | Exact checkpoint/head, intervention hooks, and prepared inputs; head-only cache variant must receive a different task name | 3 features; 512 final-evaluation rows; at most 16 full data passes |
| C3 closure | What performance can transparent signal features recover? | Aligned features and FM predictions with independent feature selection | 4096 rows; 64 columns; 8 fixed blocks; 128 saved-prediction bootstrap resamples |

All proposals cap each trial at 15 minutes, four CPU threads, 12 GiB memory, and default zero GPUs. First profile one batch for at most 60 seconds. These are stop rules, not measured runtime promises. Do not train a foundation model or launch the full audit. A source-wide conclusion cannot be inherited as gold for a narrowed feature/task subset.

Prefer C1 on one verified MDD cell for dev and the same architecture on a verified Stress cell for a conditional holdout; choose and hash both **before** dev or distillation. This is same-paper task transfer only. If only one suitable real cell exists, run a pilot and leave holdout unavailable. If only lawful cached intermediates exist, label the task analysis-only; it does not verify EEG-to-representation processing. If no suitable real resources exist, use distinct synthetic mechanisms with explicit synthetic-only gold and new task IDs.

Keep three split axes distinct: subject-level data partitions, research-task dev/holdout, and paper-source separation. Distiller sees only permitted dev trajectories/feedback; this builder has seen the full paper and cannot be relabeled as an unseen-task Distiller or Actor. Freeze resources, budgets, scoring policy, allowed fallbacks and skill before opening the holdout. No real task or holdout is certified ready by this note.

## Verification and remaining limitations

The private reference tree is a coarse source-faithful representation, not an exhaustive expansion of every model/task/feature cell. Its accompanying validation checks IDs, a single root, parent existence, acyclicity, leaf metadata, candidate parent/leaf consistency and existence of source HTML anchors. This verifies structure and traceability; it does not validate scientific truth or reproduce numerical results.

Source snapshots are retained privately with hashes. The project site was readable through web tools, while direct HTML download failed once with TLS EOF; that failure is recorded rather than retried indefinitely. No server command, participant manifest access, dataset modification, new model call, commit or push was performed by this reference worker.

