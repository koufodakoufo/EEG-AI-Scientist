# MORNING REPORT

## 1. 本次达到哪个等级
**E2 (engineering) / E1 (substantive)**。complete；配对完成 4/4；停止原因：``。
E2 is satisfied only as an engineering count (4 complete holdout pairs). Holdout actions = 0; Meta update = `no_update`. The S0/S1 table is therefore a behavioral/null-rule control, not an effective method-rule comparison. The substantive research evidence is E1.
这是受控合成数据的探索性结果，不是真实 EEG 发现，也不是 RSI 演示。

## 2. 真实 LLM / scripted / mock / S0-S1
- 真实 LLM episodes：11
- scripted/mock episodes：0
- 完整 S0/S1 配对：4/4
- 总 actions：13；总 calls：27；项目记录 token：151382

## 3. 模型、数据、代码版本、冻结时间
- 模型：{"provider": "ollama_local", "model": "qwen3.5:9b", "parameter_size": "9.7B", "quantization": "Q4_K_M", "context_length": 262144, "digest": "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"}
- 数据：`synthetic_features`（EEG 风格分层特征，不是实测脑电）
- 冻结时间：2026-10-18T17:49:52Z
- Meta 方法更新：`no_update`；规则数：0
- 代码哈希与依赖：见 `FREEZE_MANIFEST.json`
- post-freeze note：Post-freeze edits were limited to presentation/reporting code (`reporting.py`); the study/experiment code hashes are recorded in `FREEZE_MANIFEST.json`.

## 4. 最值得看的一条证据
`case_001` / S0 with 2/2 primary numeric hits and 3 actions。它支持“该固定模型的决策在该受控案例上可被执行和审计”；它不支持真实 EEG 机制、总体泛化或模型能力排序。

## 5. S1 改善/无变化/退步
见下方 paired 表。若 S1 与 S0 相同、变差或 `no_update`，都合法；4–8 个案例不支持统计确证。
- 9 episode(s) stopped with 0 actions: `case_003/S0`, `case_003/S1`, `case_004/S0`, `case_004/S1`, `case_005/S0`, `case_005/S1`, `case_006/S0`, `case_006/S1`, `case_001/case_001_s0_attempt3_failed`. These are valid behavioral failures but weak paired comparisons.


## 6. 成本
- 本地 Ollama：金额 $0；token 用量已记录。
- study episodes：82895 tokens
- E1 dev episodes（含失败尝试）：68487 tokens
- Meta：9309 tokens
- 合计（项目记录）：160691 tokens；上限 1,000,000。
- DSH 开发会话的 token/费用是另一账本，不由本项目统计。

## 7. 阻塞、风险、下一步
- 停止原因：``
- 当前风险：小样本、合成数据、单一 9B 模型、S1 可能无更新、`split_audit` 的 `not_applicable` 预测不进入数值命中率。
- 下次唯一最优先动作：先检查冻结是否成立和配对是否完整，再决定是否补第二数据种子；不要因为分数好看就直接扩成完整 RSI。

## Paired holdout
| case_id | S0 status | S1 status | S0 hits/total | S1 hits/total | S0 actions | S1 actions | S0 tokens | S1 tokens | paired |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| case_003 | completed | completed | 0/0 | 0/0 | 0 | 0 | 5053 | 5053 | True |
| case_004 | completed | completed | 0/0 | 0/0 | 0 | 0 | 5053 | 5053 | True |
| case_005 | completed | completed | 0/0 | 0/0 | 0 | 0 | 5053 | 5053 | True |
| case_006 | completed | completed | 0/0 | 0/0 | 0 | 0 | 5053 | 5053 | True |

## All episodes
| case_id | data | seed (review-only) | arm | rule | backend | status | actions | calls | attempts | tokens | predictions | stop | run |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---|---|---|
| case_001 | synthetic_features | 1101 | S0 | S0 | real_llm | completed | 3 | 4 | 4 | 21053 | 2/2 | Both H1 and H3 are supported by the evidence. The window split is high, indicating session overlap matters (supporting H3). However, both req_2 (shuffling within subject) and req_3 (randomizing labels at trial level) result in near-zero gaps for trial splits, which contradicts H1's prediction of task-specific transfer but aligns with the null hypothesis that no specific mechanism drives performance beyond chance. Since neither permutation test supports H1 or H3 over a random baseline, we must conclude that the high window split is likely due to session overlap (H3) while the trial-level performance suggests no robust trial-specific learning exists in this setup. | `runs\study_20261019\development\case_001\s0` |
| case_002 | synthetic_features | 1102 | S0 | S0 | real_llm | completed | 3 | 4 | 4 | 21418 | 2/2 | Both H1 and H3 are supported by evidence. Trial shuffling (H1) broke performance, while session-based effects (H3) remain plausible but less likely given the lack of subject overlap in other splits. | `runs\study_20261019\development\case_002\s0` |
| case_003 | synthetic_features | 1201 | S0 | S0 | real_llm | completed | 0 | 1 | 1 | 5053 | 0/0 | Evidence from both cases indicates that neither pure subject identity (H2) nor robust trial-specific content signatures (H1) consistently explain the high window split performance. In Case 1, randomization failed to drop BA significantly above chance in trials, while session overlap was noted. In Case 2, shuffling within subjects dropped BA to chance, refuting H2 for that setup and supporting a mechanism where specific trial content or subject-specific feature-label mappings are required but fragile (supporting aspects of H1/H3). The most consistent conclusion is that performance relies on specific data-feature-to-label associations tied to the training set's structure (subject/session), which vanish when labels are randomized, aligning with a modified view of H1 where 'trial content' implies the specific feature distribution within the subject/session context. | `runs\study_20261019\holdout\case_003\s0` |
| case_003 | synthetic_features | 1201 | S1 | S1 | real_llm | completed | 0 | 1 | 1 | 5053 | 0/0 | Evidence from both cases indicates that neither pure subject identity (H2) nor robust trial-specific content signatures (H1) consistently explain the high window split performance. In Case 1, randomization failed to drop BA significantly above chance in trials, while session overlap was noted. In Case 2, shuffling within subjects dropped BA to chance, refuting H2 for that setup and supporting a mechanism where specific trial content or subject-specific feature-label mappings are required but fragile (supporting aspects of H1/H3). The most consistent conclusion is that performance relies on specific data-feature-to-label associations tied to the training set's structure (subject/session), which vanish when labels are randomized, aligning with a modified view of H1 where 'trial content' implies the specific feature distribution within the subject/session context. | `runs\study_20261019\holdout\case_003\s1` |
| case_004 | synthetic_features | 1202 | S0 | S0 | real_llm | completed | 0 | 1 | 1 | 5053 | 0/0 | Evidence from both cases indicates that neither pure subject identity (H2) nor robust trial-specific content signatures (H1) consistently explain the high window split performance. In Case 1, randomization failed to drop BA significantly above chance in trials, while session overlap was noted. In Case 2, shuffling within subjects dropped BA to chance, refuting H2 for that setup and supporting a mechanism where specific trial content or subject-specific feature-label mappings are required but fragile (supporting aspects of H1/H3). The most consistent conclusion is that performance relies on specific data-feature-to-label associations tied to the training set's structure (subject/session), which vanish when labels are randomized, aligning with a modified view of H1 where 'trial content' implies the specific feature distribution within the subject/session context. | `runs\study_20261019\holdout\case_004\s0` |
| case_004 | synthetic_features | 1202 | S1 | S1 | real_llm | completed | 0 | 1 | 1 | 5053 | 0/0 | Evidence from both cases indicates that neither pure subject identity (H2) nor robust trial-specific content signatures (H1) consistently explain the high window split performance. In Case 1, randomization failed to drop BA significantly above chance in trials, while session overlap was noted. In Case 2, shuffling within subjects dropped BA to chance, refuting H2 for that setup and supporting a mechanism where specific trial content or subject-specific feature-label mappings are required but fragile (supporting aspects of H1/H3). The most consistent conclusion is that performance relies on specific data-feature-to-label associations tied to the training set's structure (subject/session), which vanish when labels are randomized, aligning with a modified view of H1 where 'trial content' implies the specific feature distribution within the subject/session context. | `runs\study_20261019\holdout\case_004\s1` |
| case_005 | synthetic_features | 1203 | S0 | S0 | real_llm | completed | 0 | 1 | 1 | 5053 | 0/0 | Evidence from both cases indicates that neither pure subject identity (H2) nor robust trial-specific content signatures (H1) consistently explain the high window split performance. In Case 1, randomization failed to drop BA significantly above chance in trials, while session overlap was noted. In Case 2, shuffling within subjects dropped BA to chance, refuting H2 for that setup and supporting a mechanism where specific trial content or subject-specific feature-label mappings are required but fragile (supporting aspects of H1/H3). The most consistent conclusion is that performance relies on specific data-feature-to-label associations tied to the training set's structure (subject/session), which vanish when labels are randomized, aligning with a modified view of H1 where 'trial content' implies the specific feature distribution within the subject/session context. | `runs\study_20261019\holdout\case_005\s0` |
| case_005 | synthetic_features | 1203 | S1 | S1 | real_llm | completed | 0 | 1 | 1 | 5053 | 0/0 | Evidence from both cases indicates that neither pure subject identity (H2) nor robust trial-specific content signatures (H1) consistently explain the high window split performance. In Case 1, randomization failed to drop BA significantly above chance in trials, while session overlap was noted. In Case 2, shuffling within subjects dropped BA to chance, refuting H2 for that setup and supporting a mechanism where specific trial content or subject-specific feature-label mappings are required but fragile (supporting aspects of H1/H3). The most consistent conclusion is that performance relies on specific data-feature-to-label associations tied to the training set's structure (subject/session), which vanish when labels are randomized, aligning with a modified view of H1 where 'trial content' implies the specific feature distribution within the subject/session context. | `runs\study_20261019\holdout\case_005\s1` |
| case_006 | synthetic_features | 1204 | S0 | S0 | real_llm | completed | 0 | 1 | 1 | 5053 | 0/0 | Evidence from both cases indicates that neither pure subject identity (H2) nor robust trial-specific content signatures (H1) consistently explain the high window split performance. In Case 1, randomization failed to drop BA significantly above chance in trials, while session overlap was noted. In Case 2, shuffling within subjects dropped BA to chance, refuting H2 for that setup and supporting a mechanism where specific trial content or subject-specific feature-label mappings are required but fragile (supporting aspects of H1/H3). The most consistent conclusion is that performance relies on specific data-feature-to-label associations tied to the training set's structure (subject/session), which vanish when labels are randomized, aligning with a modified view of H1 where 'trial content' implies the specific feature distribution within the subject/session context. | `runs\study_20261019\holdout\case_006\s0` |
| case_006 | synthetic_features | 1204 | S1 | S1 | real_llm | completed | 0 | 1 | 1 | 5053 | 0/0 | Evidence from both cases indicates that neither pure subject identity (H2) nor robust trial-specific content signatures (H1) consistently explain the high window split performance. In Case 1, randomization failed to drop BA significantly above chance in trials, while session overlap was noted. In Case 2, shuffling within subjects dropped BA to chance, refuting H2 for that setup and supporting a mechanism where specific trial content or subject-specific feature-label mappings are required but fragile (supporting aspects of H1/H3). The most consistent conclusion is that performance relies on specific data-feature-to-label associations tied to the training set's structure (subject/session), which vanish when labels are randomized, aligning with a modified view of H1 where 'trial content' implies the specific feature distribution within the subject/session context. | `runs\study_20261019\holdout\case_006\s1` |
| case_001 | synthetic_features | 1101 | case_001_s0 | S0 | real_llm | completed | 3 | 4 | 5 | 24330 | 2/2 | Permutation of labels at the trial level reduced performance to chance (~0.5), ruling out session identity (H3) and confirming that task-level content drives generalization within trials, supporting H1. | `runs\dev_e1\case_001_s0` |
| case_001 | synthetic_features | 1101 | case_001_s0_attempt1_failed | S0 | real_llm | initial | 3 | 4 | 5 | 24555 | 0/0 | action_budget_exceeded | `runs\dev_e1\case_001_s0_attempt1_failed` |
| case_001 | synthetic_features | 1101 | case_001_s0_attempt2_failed | S0 | real_llm | failed | 1 | 2 | 3 | 12791 | 0/0 | invalid_decision_after_repair | `runs\dev_e1\case_001_s0_attempt2_failed` |
| case_001 | synthetic_features | 1101 | case_001_s0_attempt3_failed | S0 | real_llm | failed | 0 | 1 | 2 | 6811 | 0/0 | invalid_decision_after_repair | `runs\dev_e1\case_001_s0_attempt3_failed` |

## Tests
- status: `passed`
- exit code: `0`
- command: `C:\Users\14090\anaconda3\python.exe -m pytest -q (PYTHONPATH=src)`
- output: `reports/test_output.txt`

## Artifacts
- `reports/RESULTS_TABLE.md`
- `reports/FAILURE_CASES.md`
- `reports/CORE_CODE_WALKTHROUGH.md`
- `artifacts/review_bundle.zip`
- `PREFLIGHT.md` and `FREEZE_MANIFEST.json`
