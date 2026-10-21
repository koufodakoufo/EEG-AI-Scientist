# RUN INDEX — flash_emotion_20261021

Study: `emotion_state_trait_20261021`; branch `overnight/flash-20261020-0058`; no push.
Question: EEG 对情绪评分的预测，如何区分同一个人的状态变化与不同人的稳定差异？什么最小实验能区分竞争解释？

## Stage status

| stage | state | location |
|---|---|---|
| material search (DeepSeek Search) | DONE | `runs/flash_emotion_20261021/materials/searches/` |
| material fetch (DeepSeek Fetch) | DONE 7/8 attempts | `runs/flash_emotion_20261021/materials/evidence/` |
| material manifest + freeze | DONE, SHA-256 recorded | `configs/materials/emotion_state_trait_v1.json`, `runs/flash_emotion_20261021/study_lock.json` |
| Meta (Flash, independent context) | DONE, rule accepted | `runs/flash_emotion_20261021/meta/` |
| baseline repeat 01 | ACCEPTED | `runs/flash_emotion_20261021/runs/baseline/repeat_01/` |
| baseline repeat 02 | ACCEPTED after bounded retry | `.../baseline/repeat_02__retry2/` |
| Meta-rule repeat 01 | ACCEPTED after bounded retry | `.../meta_rule/repeat_01__retry2/` |
| Meta-rule repeat 02 | ACCEPTED after bounded retry | `.../meta_rule/repeat_02__retry2/` |
| evaluation + blinded packet | DONE (dsh initial) | `runs/flash_emotion_20261021/reviews/` |
| one-page summary | DONE | `reports/flash_emotion_20261021/RESULT_SUMMARY.md` |
| review bundle | DONE | `artifacts/review_bundle_emotion_20261021.zip` |

## Runs and attempts

Primary proposals are the accepted run in each arm/repeat cell; extra accepted retries are kept but not counted as additional evidence.

| run | arm | repeat | phase | accepted | model calls | tools | cost CNY |
|---|---|---|---:|---|---:|---:|---:|
| `...__baseline__01` | baseline | 1 | completed | yes | 6 | 11 | 0.2365 |
| `...__baseline__02` | baseline | 2 | failed (tool budget) | no | 6 | 14 | 0.1416 |
| `...__baseline__02__retry` | baseline | 2 | completed | yes | 6 | 10 | 0.2185 |
| `...__baseline__02__retry2` | baseline | 2 | completed | yes | 6 | 12 | 0.2558 |
| `...__meta_rule__01` | meta_rule | 1 | failed (tool budget) | no | 5 | 14 | 0.1374 |
| `...__meta_rule__01__retry` | meta_rule | 1 | failed (finalization) | no | 7 | 14 | 0.2282 |
| `...__meta_rule__01__retry2` | meta_rule | 1 | completed | yes | 5 | 10 | 0.1988 |
| `...__meta_rule__02` | meta_rule | 2 | failed (tool budget) | no | 7 | 14 | 0.2006 |
| `...__meta_rule__02__retry` | meta_rule | 2 | completed | yes | 5 | 11 | 0.2254 |
| `...__meta_rule__02__retry2` | meta_rule | 2 | completed | yes (primary) | 8 | 14 | 0.3104 |

The first three failures exposed a real runner bug: `finish_study` was counted against the evidence-tool budget and finalization aborted before the promised final call. Both were fixed; failed directories were preserved and a bounded retry was used. An earlier retry helper over-retried one baseline cell; that extra accepted run is retained but treated as a duplicate, not as a second independent repeat.

## Budget

- Project API spend: **CNY 2.253552 / 10** (peak-rate accounting; no unknown cost).
- 65 model attempts / 120; 7 Search / 30; 8 Fetch / 40.
- Input 771,852 / 1,000,000 tokens; output 79,981 / 300,000.
- Material preparation: CNY 0.07. Meta and Scientist runs use the same ledger and attributions.
- Old `runs/flash_20261020_0058/budget.json` is untouched.

## Key files

- Question, config, frozen lock: `configs/studies/flash_emotion_20261021.json`, `runs/flash_emotion_20261021/study_lock.json`.
- Material manifest: `configs/materials/emotion_state_trait_v1.json`; source snapshots: `runs/flash_emotion_20261021/materials/evidence/sources/`.
- Meta input/response/decision: `runs/flash_emotion_20261021/meta/`.
- Primary proposals: `runs/flash_emotion_20261021/runs/{baseline,meta_rule}/.../final_answer.md`.
- dsh review: `reports/flash_emotion_20261021/MANUAL_INITIAL_REVIEW.md`; automated checks: `runs/flash_emotion_20261021/reviews/INITIAL_REVIEW.md`.
- Blinded human packet: `runs/flash_emotion_20261021/reviews/blinded/`; key: `runs/flash_emotion_20261021/reviews/KEY.json`.

## Commands

```powershell
cd X:\projects\EEG-AI-Scientist
$env:PYTHONPATH='src'
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli emotion-study status
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli emotion-study run        # completed; reuses state
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli emotion-study retry-failed
C:\Users\14090\anaconda3\python.exe -m eeg_scientist.cli emotion-study evaluate
```

## Honest limits

- No real EEG data; all proposals are literature-based.
- Meta comparison: at most two primary runs per arm; no statistical significance claim.
- `n=2` cannot separate rule effect from run variance.
- Some numeric claims still need exact source/read-range checking; see manual review.
- Claude/Gemini/DeepSeek Pro were not called; their config entries are marked unverified.
