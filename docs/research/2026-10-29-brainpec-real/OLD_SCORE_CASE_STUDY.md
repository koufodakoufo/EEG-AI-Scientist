# 旧分数个案：M20/M21 固定分类头段落

2026-10-29，R05 Builder 的事后诊断；只核对旧合成任务这一组对应段落，没有重判整份报告，没有改旧分数，也没有读取本轮真实 EEG 测试结果。

M20 报告原句为 “The unedited fixed head has 54.17% validation accuracy overall, with 95.83% in context_0 and 12.50% in context_1.”，但抽取器把它与下一段的三个置信区间及多数类 baseline 一并装进 `S01_C06`；M21 的 `S02_C01` 同样把总体和两个 context 的点估计、计数和区间合成一条。两条都对照 `R_holdout_C02`，参考仅说明两个 context 的准确率 0.958333 与 0.125000 及其反差，未给置信区间或 majority baseline。M23 因而把 `reference_supports_agent` 判成 `not_supported`，理由是新增区间/计数或 baseline 不在参考内；反向 `agent_covers_reference` 却都判 `supported`，因为关键 context 数值确实被报告覆盖。这不是数值点估计错误：本次只对固定头重新读取旧公开 validation 标签及保存预测，M20/M21 均为总体 104/192、context_0 92/96、context_1 12/96，与原文的四舍五入一致；M20 按其 `analysis.py` 的原 CSV 行序对齐，M21 按 row_id 对齐。此次没有重新运行两份 bootstrap，因此区间应另列“参考未覆盖、统计实现待独立验证”，不能宣称区间为真或假；多数类 baseline 也不在本次重算范围。v3 应把三个点估计、三个区间及每个额外 baseline 拆开，点估计保留覆盖/数值有效性，其他部分独立审查。这个已看过旧结果的个案说明旧闭参考 precision 会因打包方式惩罚额外内容，并不证明新规则提高科研能力或 skill 优于 baseline。

## 可定位证据

| 内容 | 文件/位置 |
| --- | --- |
| M20 原文 | `.local/overnight-20261029/submissions/M20/output/REPORT.md`，48 行及后续段落 |
| M21 原文 | `.local/overnight-20261029/submissions/M21/output/REPORT.md`，7–11 行 |
| M20 抽取、参考与两向支持边 | `.local/overnight-20261029/private/evaluations/M23/M20-score.json`，claim `S01_C06` / reference `R_holdout_C02` |
| M21 抽取、参考与两向支持边 | 同目录 `M21-score.json`，claim `S02_C01` / reference `R_holdout_C02` |
| M20 保存预测和数值 | `.../submissions/M20/output/fit_results.json`：`predictions.fixed_head`、`accuracy.fixed_head` |
| M21 保存预测和数值 | `.../submissions/M21/output/metrics.json`：`predictions.fixed`、`classification.fixed.metrics` |
| 旧公开标签 | `.local/overnight-20261029/public-bundles/holdout/validation.csv`（旧 synthetic holdout task 的公开 validation，不是本轮最终测试） |
| 本次限定复算及输入哈希 | `.local/research/2026-10-29-brainpec-real/verification/R05-old-fixed-head-case.json` |

这份中文说明是面向 Builder/用户的评分诊断材料，不进入真实 Actor 的可读题包。
