# LITERATURE MAP — flash_20261020_0058

Scientist: `deepseek-flash`. The papers below were selected and fetched by the Scientist through its own `search_sources` / `fetch_source` tools, then read only through `read_evidence`. `read coverage` is the fraction of the fetched text that actually entered the model context (injection log), **not** a claim that the paper was read end-to-end. All seven cited papers were read in part; none was read in full.

## Cited evidence (7 papers)

| # | Paper | Status | Fetched source | Read coverage | What was used | Evidence ID |
|---|---|---|---|---|---|---|
| 1 | Chevallier, Carrara, Aristimunha, Guetschel, Sedlar, Lopes, Velut, Khazem, Moreau. *The largest EEG-based BCI reproducibility study for open science: the MOABB benchmark.* J. Neural Eng. (preprint/HTML) | preprint/HTML | ar5iv `2404.15319` | 15,500 / 120,604 chars (12.9%) | within-session shuffling is an upper bound vs online; cross-session/cross-subject are outside the paper's scope; the paper focuses on within-session | `ev_f42fa7111e36` |
| 2 | Yin, Yu, Fang, Peng, Li. *Rethinking Cross-Subject Data Splitting for Brain-to-Text Decoding.* EMNLP 2025, pp. 5675–5689. doi:10.18653/v1/2025.emnlp-main.289 | peer-reviewed (ACL) | ACL Anthology page | 5,100 / 8,579 chars by interval union (59.4% of the page; two overlapping read ranges; **not** the PDF body) | current cross-subject splits leak validation/test into training and overestimate performance | `ev_9da221287269` |
| 3 | Liu, Chen, Chen, Cui, Wen, An, Luo, Wu. *EEG Foundation Models: Progresses, Benchmarking, and Open Problems.* arXiv:2601.17883v1 | preprint | ar5iv mirror `2601.17883` | 26,700 / 148,770 chars (17.9%) | 12 FM / 13 datasets; cross-subject LOSO full fine-tune table; linear-probe vs fine-tune table; average-rank table; 2K-parameter EEGNet ranks 2nd | `ev_825214c78a59` |
| 4 | Jiang, Zhao, Lu. *Large Brain Model for Learning Generic Representations with Tremendous EEG Data in BCI (LaBraM).* arXiv:2405.18765v1 | preprint | ar5iv mirror `2405.18765` | 16,300 / 85,799 chars (19.0%) | ~2,500 h pretraining; vector-quantized neural spectrum prediction; TUAB/TUEV follow BIOT patient split; supervised fine-tuning on training patients | `ev_2085e5b7ba26` |
| 5 | Banville, Chehab, Hyvärinen, Engemann, Gramfort. *Uncovering the structure of clinical EEG signals with self-supervised learning.* arXiv:2007.16104 | preprint | ar5iv `2007.16104` | 21,300 / 101,545 chars (21.0%) | PC18 72.3% (5-class, chance 20%); TUHab 79.4%; embeddings encode pathology/age/gender/apnea; clusters follow channel count and recording date; split holds out recordings, not necessarily subjects; MSE autoencoder never >53.0% on TUHab | `ev_b63c716fd707` |
| 6 | Fallahi, Arias-Cabarcos, Strufe. *Advancing Brainwave-Based Biometrics: A Large-Scale, Multi-Session Evaluation.* arXiv:2501.17866v3 | preprint | ar5iv mirror `2501.17866` | 5,500 / 97,933 chars (5.6%) | 345 subjects, 6,007 sessions, 5 years, 3 headsets; EER 6.7% after 1 day → 14.3% after 1 year; session- and device-based embedding clusters | `ev_2f5e3fadf9f0` |
| 7 | Hebart & Baker. *Deconstructing multivariate decoding for the study of brain function.* NeuroImage 180(Pt A):4–18, 2018. doi:10.1016/j.neuroimage.2017.08.005 | peer-reviewed | PMC `PMC5797513` | 5,500 / 113,435 chars (4.8%) | prediction ≠ explanation; highly predictive voxels can sit in ventricles/physiological-noise regions | `ev_200bb34828cd` |

## Fetched but not cited

| Source | Why not used |
|---|---|
| PMC `PMC4269250` — *Mindfulness and Emotional Outcomes…* (36,843 chars) | irrelevant; wrong paper returned for the intended query/URL |
| ar5iv `2205.11408` — *Zeros of Dynamical Zeta Functions…* (92,049 chars) | irrelevant; fetched by mistake |
| ar5iv `2211.00391` — *Optimization of Oblivious Decision Tree Ensembles…* (2,802 chars) | irrelevant; fetched by mistake |

## Failed fetches (recorded, not replaced by mock success)

| URL | Result | Effect |
|---|---|---|
| `https://europepmc.org/article/PPR/PPR1186524` (*Many Pipelines, One Dataset: Analytic Flexibility…*, the EEGManyPipelines preprint) | HTTP 504 after retries | no evidence about analytic flexibility; final answer records the gap |
| `https://arxiv-org.ezproxy.obspm.fr/html/2211.00391v2` | HTTP 404 | switched to the ar5iv URL, which was irrelevant |

## What the map does and does not support

Supported by the cited text:
- within-session / trial-shuffled evaluation is an upper bound and is common; cross-session and cross-subject are separate, harder evaluations;
- cross-subject splits can leak and inflate scores;
- a large FM benchmark finds linear probing often insufficient and a 2K-parameter EEGNet highly competitive;
- SSL embeddings carry collection-condition information (channel count, recording date) as well as clinical variables;
- identity is decodable and drifts across sessions/years;
- decoding accuracy is not an explanation.

Not supported by a direct experiment in this run:
- the exact proportion of a within-session score that is task vs subject/session/device;
- whether cross-subject loss is missing information or limited readout;
- whether "low-dimensional spectral/rhythmic structure" is the main transferable component (this is the Scientist's inference, not a measured result);
- analytic flexibility (EEGManyPipelines) — fetch failed;
- any real EEG result from this repository.

## Citation status

Two of the seven (arXiv:2601.17883, arXiv:2501.17866) are 2026 preprints; no peer-reviewed version was seen. LaBraM and Banville are preprints of published work; the fetched HTML was the arXiv version. Yin et al. is peer-reviewed but only its abstract/metadata page was read. MOABB was read as an ar5iv HTML version, not the journal PDF.
