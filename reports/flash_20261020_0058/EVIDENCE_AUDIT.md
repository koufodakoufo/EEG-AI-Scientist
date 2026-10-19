# EVIDENCE AUDIT — flash_20261020_0058

Auditor: dsh (developer), not the Scientist. Method: loaded every fetched evidence JSON and the append-only `injections.jsonl`; for each quoted number/claim, found its character offset in the source and checked whether that offset fell inside a range actually passed to the model through `read_evidence`. HTML escaping (`44\.97`) was normalized before matching. No new model calls were made for this audit.

## 1. Numbers that are confirmed inside read ranges

All of the following occur in `ev_825214c78a59` at offsets covered by injected ranges (`78000–83500`, `89500–94500`, `99000–104200`):

| Claim in final answer | Source offset | In injected range | Verdict |
|---|---:|---|---|
| BNCI2014001 cross-subject full fine-tune: CSP+LDA 38.19 | 80,945 | yes | confirmed |
| EEGNet 44.97±0.57 | 81,035 | yes | confirmed |
| ShallowConv 44.80 | 81,2xx | yes | confirmed |
| LaBraM 46.93±1.43 | 82,021 | yes | confirmed |
| CBraMod 53.03±0.22 | 82,385 | yes | confirmed |
| BENDR linear probe 32.18±0.41 vs fine-tune 51.11±0.25 | 83,263 / 81,783 | yes | confirmed |
| BIOT 30.88±1.00 vs 34.27±0.93 | 83,381 / 81,901 | yes | confirmed |
| TUAB: ShallowConv 79.81, DeFormer 81.48, LUNA-Base 81.92, LaBraM 76.23, EEGNet 77.03 | 81,256 / 81,616 / 83,201 / 82,117 / 81,131 | yes | confirmed |
| CBraMod rank 5.96, EEGNet 6.84 (2K), ShallowConv 7.00 | 100,162 / 101,051 / 101,020 | yes | confirmed |
| Specialist models: 15 first-place, 47 top-3 | 99,620 | yes | confirmed |
| 13 datasets; 12 foundation models listed | 100,039 / 79,909 | yes | confirmed |

Other confirmed numbers:

| Claim | Evidence | Offset | In read range | Verdict |
|---|---|---:|---|---|
| MOABB within-session is an upper bound vs online; cross-session/cross-subject outside scope | `ev_f42fa7111e36` | 22,359 | yes (20,000–25,000) | confirmed |
| Banville PC18 72.3% (5-class, chance 20%); TUHab 79.4% | `ev_b63c716fd707` | 47,651 | yes (46,500–51,700) | confirmed |
| Banville AE never >53.0% on TUHab | `ev_b63c716fd707` | 50,405 | yes (46,500–51,700) | confirmed |
| Banville clusters follow channel count and measurement date | `ev_b63c716fd707` | 55,145–55,382 | yes (51,700–56,700) | confirmed |
| Banville embeddings show pathology/age/gender/apnea gradients | `ev_b63c716fd707` | 52,625–55,035 | yes (51,700–56,700) | confirmed |
| LaBraM ~2,500 h pretraining; TUAB/TUEV follow BIOT patient split | `ev_2085e5b7ba26` | 25,522 | yes (24,000–29,300) | confirmed |
| Fallahi EER 6.7% after 1 day → 14.3% after 1 year | `ev_2f5e3fadf9f0` | 1,383 / 1,405 | yes (1,200–6,700) | confirmed |
| Hebart & Baker: predictive voxels can sit in ventricles/physiological noise | `ev_200bb34828cd` | 7,282 | yes (2,500–8,000) | confirmed |
| Yin et al.: current cross-subject splits leak validation/test into training and overestimate | `ev_9da221287269` | abstract page | 100% of the 8,579-char page | confirmed (abstract only) |

## 2. Claims that are true in the source but outside the recorded read range

These are not fabrications — the text exists — but the Scientist could not have read them through `read_evidence` in this run. The final answer cites the evidence ID as if it had.

| Claim | Source | Offset | Read range | Finding |
|---|---|---:|---|---|
| Fallahi: 345 subjects, 6,007 sessions, 5 years, 3 headsets | `ev_2f5e3fadf9f0` | 1,069 / 13,176 | only 1,200–6,700 injected | **outside read range**; likely seen in the search summary or inferred from the abstract, but not in an injected slice |
| Fallahi: embeddings cluster by session and device | `ev_2f5e3fadf9f0` | 41,502 / 46,149 | only 1,200–6,700 injected | **outside read range**; true in source, but unsupported by the recorded trace |
| "two fetches hit irrelevant papers" | tool trace | — | — | inaccurate count: 2 fetches failed (504 EuropePMC/EEGManyPipelines; 404 arxiv 2211.00391) and **3** successful fetches were irrelevant (PMC4269250 mindfulness, arxiv 2205.11408 zeta, arxiv 2211.00391 CatBoost). None was cited. |

The Fallahi identity-drift claim (6.7% → 14.3%) is confirmed and is the load-bearing evidence; the scale and clustering details are not. The final's core argument does not depend on them, but the citation is broader than the read trace.

## 3. Interpretive overstatements (not numeric errors)

1. **"现有多数高分是同一会话内、试次随机打乱的分数"** — MOABB says within-session is common and is an upper bound versus online evaluation, and that the paper focuses on within-session. It does **not** quantify "most high scores" across the literature. This is a reasonable summary but should be marked as an inference / literature-scope claim, not a measured fact.
2. **"可迁移的信息主要是低维频谱/节律类结构 + 受试者层面的对齐信息"** — the cited evidence supports (a) a 2K EEGNet being highly competitive, (b) linear probe vs fine-tune gaps, (c) identity decodability. It does **not** measure "low-dimensional spectral/rhythmic structure" or a "subject-level alignment" component. The final later labels a related sentence as inference, but the one-sentence conclusion does not.
3. **"TUHab 的簇由通道数与记录日期解释"** — the source says each cluster was *predominantly composed* of examples with a given channel count and a specific date range, and suggests partial learning of collection noise. "Explained by" is stronger than "predominantly associated with".
4. **"跨被试掉分是信息缺失还是读不出来，公开证据无法区分"** — the benchmark's linear-vs-fine-tune gap is evidence that readout matters; the stronger claim is that no existing condition isolates the two. The final does state the missing intermediate condition, so this is acceptable but should be phrased as "not resolved by the available conditions".
5. **M1 is not minimal** — 3 datasets × 2 encoders × 5 splits × 5 readouts is a large factorial. The final calls it a "minimal experiment" but gives no resource estimate. This is a design-level issue, addressed in `EXPERIMENT_PROTOCOL.md`.

## 4. Citation metadata

Author lists were checked against the fetched headers:

- MOABB: Chevallier, Carrara, Aristimunha, Guetschel, Sedlar, Lopes, Velut, Khazem, Moreau — matches.
- Liu et al.: Liu, Chen, Chen, Cui, Wen, An, Luo, Wu — matches.
- LaBraM: Jiang, Zhao, Lu — matches.
- Banville et al.: Banville, Chehab, Hyvärinen, Engemann, Gramfort — matches.
- Fallahi et al.: Fallahi, Arias-Cabarcos, Strufe — matches.
- Yin et al.: Yin, Yu, Fang, Peng, Li — matches the ACL metadata.
- Hebart & Baker: matches the NeuroImage record (PMC page).

No invented DOI, author, or paper was found. Two 2026 items are preprints; Yin et al. is peer-reviewed but only its abstract page was read.

## 5. Verdict

- **No fabricated citation or fabricated numeric result was detected.** Every load-bearing benchmark number is inside a range the Scientist actually read.
- **Two Fallahi details are outside the read trace** (scale and embedding clustering). They are true in the fetched source, but the final should either read them properly or drop them.
- **The top-line synthesis contains at least one inference presented as fact** ("low-dimensional spectral/rhythmic structure"). The morning report must separate it.
- **The failure narrative undercounts irrelevant fetches** (three, not two), but none entered the citations.
- The final answer's own limitations section is unusually candid: 7 papers (<8–12 target), no full text, two preprints, no real EEG, no direct decomposition, EEGManyPipelines missing.

These findings do not overturn the priority experiment; they narrow what the report may claim.
