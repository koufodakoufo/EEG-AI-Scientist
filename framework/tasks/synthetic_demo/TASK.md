# 任务：合成演示（验证研究程序本身）

这是一个**合成**任务，形状模仿 EEG FM 的 LODO 评估：三个"数据集"分片 `dsA / dsB / dsC`，每个有六个被试划分，主指标为 FT balanced accuracy（%），每个分片的评估作业约 2 秒。**结果不是科学证据**，只用来验证 brief → 审阅 → setup/freeze → baseline → 迭代 → 锁定 → test → 报告 → 记忆 的完整流程。

## 问题
调整 `method.yaml` 中的三个参数，使三个分片的 validation FT balanced accuracy 宏平均尽量高。

## 可编辑
`method.yaml`：`posttrain_lr_log10` ∈ [−6, −3.7]，`temperature` ∈ [0.03, 0.3]，`warmup_epochs` ∈ {0..8}（整数）。`run_eval.py` 是评估器，setup 时检查后冻结。

## 评估契约
`python3 -B run_eval.py --phase val --target <shard> --out <dir>` 写 `metrics.json`（键 `ft_bacc`）；`--phase test --from <val_out>` 读取 validation 选中的配置后评估一次。

## 流程要求
- Brief：不需要网页检索（`task.yaml: research.web_search: false`）；根据本文件和评估器源码写 2–3 个假设即可。
- Setup：阅读 `run_eval.py`，用一次 setup attempt 跑通，然后 `bin/eegfm freeze`。
- Baseline：`method.yaml` 保持初始值。
- 迭代：至少 2 个有效轮次，最多 4 个 iteration attempt。
- 收尾：锁定 baseline 与最终候选，各跑一次 test，写 `FINAL_REPORT.md`，整理记忆。
- **不要**为了"猜到最优值"去推算 `run_eval.py` 中的隐藏常数；像对待真实实验一样，只根据 validation 结果决定下一步。
