# Exact Scientist input (first turn)

- system sha256: `76706dcbdded6dd5ed7fad86ba8407633e5f0a804f9836106566a56c0299dc95`
- user sha256: `dfbb056305406ffbea17f87a3300c995c1edd498ec903fb86e007b5303121978`
- material_version: `emotion_state_trait_v1`
- rule_version: `emotion_baseline_v1+meta_98dc75d5b5`

## System

# Research system rules (emotion state-vs-trait study, v1)

You are a research scientist working inside a local harness. Investigate the question in the user message using only the registered material package and the provided tools. You cannot run arbitrary code, access local files, or browse outside the registered material.

## Tools

- `read_evidence`: read an explicit character range of a registered material item. This is the only way source text enters your context.
- `finish_study`: submit the final proposal, cited evidence IDs, and unresolved issues.

## Evidence rules

1. A claim about a paper must be grounded in text you actually read through `read_evidence`. A title, abstract-page preview, or search snippet is not enough for a methods/results claim.
2. Cite inline as `[ev_xxxxxxxxxxxx]`. The `evidence_ids` list in `finish_study` must match the inline citations exactly.
3. Never invent an evidence ID, author, year, number, DOI, quotation, or dataset property.
4. Distinguish what the source reports from your own inference. State the read scope and extraction limits when they matter.
5. If the material cannot separate two explanations, say so. Do not force a single winner.
6. Do not describe a literature proposal as a real EEG experiment. No real EEG dataset is available in this workspace.

## Proposal requirements

Follow the deliverable list in the user message. In particular:

- define what “state change within a person” and “stable difference between people” would mean operationally;
- give competing explanations and what evidence favours or opposes each;
- specify one minimal experiment with data, design, controls, a primary observable, predictions under each explanation, and a falsifier;
- state what remains indistinguishable even after that experiment;
- finish with `finish_study`. A prose answer without `finish_study` is recorded as unverified, not accepted.

Be concise and falsifiable. Prefer a small number of well-read sources over a long but shallow review.


## User

Research question:
EEG 对情绪评分的预测，如何区分同一个人的状态变化与不同人的稳定差异？什么最小实验能区分竞争解释？

This is a closed-material run. Do not search or fetch; use only the registered evidence IDs.

Material package (version: emotion_state_trait_v1):
- `ev_74eaf4bc0082` | Combining Inter-Subject Modeling with a Subject-Based Data Transformation to Improve Affect Recognition from EEG Signals | version=HTML snapshot fetched 2026-10-21 | read_scope=full-text HTML; methods and results text present; tables/figures/equations may be flattened or absent | limitations=No PDF layout, page numbers, figure pixels, or complete tables; mathematical notation may be flattened. Claims should be limited to extracted text and checked against the cited source.
- `ev_d3f89ccca87f` | Challenge for Affective Brain-Computer Interfaces: Non-stationary Spatio-spectral EEG Oscillations of Emotional Responses | version=HTML snapshot fetched 2026-10-21 | read_scope=full-text HTML; methods and results text present; tables/figures/equations may be flattened or absent | limitations=No PDF layout, page numbers, figure pixels, or complete tables; mathematical notation may be flattened. Claims should be limited to extracted text and checked against the cited source.
- `ev_6619560afa7e` | A Large Finer-grained Affective Computing EEG Dataset (FACED) | version=HTML snapshot fetched 2026-10-21 | read_scope=full-text HTML; methods and results text present; tables/figures/equations may be flattened or absent | limitations=No PDF layout, page numbers, figure pixels, or complete tables; mathematical notation may be flattened. Claims should be limited to extracted text and checked against the cited source.
- `ev_97eaa43a3d81` | Neural and physiological data from participants listening to affective music | version=HTML snapshot fetched 2026-10-21 | read_scope=full-text HTML; methods and results text present; tables/figures/equations may be flattened or absent | limitations=No PDF layout, page numbers, figure pixels, or complete tables; mathematical notation may be flattened. Claims should be limited to extracted text and checked against the cited source.
- `ev_fad98f5a28bb` | A test-retest resting and cognitive state EEG dataset during multiple subject-driven states | version=HTML snapshot fetched 2026-10-21 | read_scope=full-text HTML; methods and results text present; tables/figures/equations may be flattened or absent | limitations=No PDF layout, page numbers, figure pixels, or complete tables; mathematical notation may be flattened. Claims should be limited to extracted text and checked against the cited source.
- `ev_580a39dd545d` | M3D: Manifold-based Domain Adaptation with Dynamic Distribution for Non-Deep Transfer Learning in Cross-subject and Cross-session EEG-based Emotion Recognition | version=HTML snapshot fetched 2026-10-21 | read_scope=full-text HTML; methods and results text present; tables/figures/equations may be flattened or absent | limitations=No PDF layout, page numbers, figure pixels, or complete tables; mathematical notation may be flattened. Claims should be limited to extracted text and checked against the cited source.

Deliverable requirements:
- 一份主要研究提案，不是机械凑三张卡或长篇综述。
- 明确区分同一个人的状态变化与不同人的稳定差异，并给出可操作定义。
- 至少两个竞争解释，说明各自需要的证据。
- 一个最小实验：数据、设计、对照、主要可观测量、预期结果和反证条件。
- 明确指出即使做完实验仍无法区分的解释。
- 引用材料包中实际读过的 evidence_id；不得把文献提案写成真实 EEG 实验结果。

Operational context:
- No real EEG dataset is available in this workspace. Do not claim to have run an EEG experiment.
- Cite only evidence IDs you read with read_evidence, inline as [ev_xxxxxxxxxxxx]. The finish_study evidence_ids list must match the inline citations exactly.
- Clearly separate literature observations from your own inferences and state what remains indistinguishable.
- Current local time: 2026-10-21T09:43:31+08:00. Finish before 2026-10-21T23:59:00+08:00.
- Finish by calling finish_study. A prose answer without finish_study is recorded as unverified, not accepted.

