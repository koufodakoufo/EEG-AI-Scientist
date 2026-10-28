# 评估协议与 test 隔离

来源：`docs/research/REVE_ISA_RSI_TASK_BRIEF.md` §3–§5；`registry/protocols.yaml`。外部经验见文末。

## LODO all-source 后训练

对每个目标数据集：从官方权重开始，用**其他五个源数据集的全部样本**后训练（显式 `posttrain_split=all`，不能沿用函数默认的 `train`）。目标数据集不参与它自己的后训练；六个目标之间不继承权重。

## 下游：六次重复被试划分

- 划分种子 42–47，每次划分内 train/val/test 被试互斥；**这是重复随机划分，不是 test 互斥的 K 折**，不同划分之间共享被试。
- 划分清单：`.../snapshots/round_1_base_0/source/split_manifest.json`（见 registry）。
- LP：冻结 encoder，新线性头，flatten，最多 100 epoch，LR 1e-3。
- FT：训练 encoder，新 MLP 头，flatten，最多 60 epoch，LR 1e-5。
- 共同：batch 128，weight decay 1e-4，early stop patience 10，min_delta 0.01，**按 validation 选 epoch**。

## 指标

- 主指标：每个数据集六次划分的 balanced accuracy 均值（按逐折样本预测计算，不要改成先逐被试再平均），以及六个数据集的等权宏平均。
- 辅助：macro-F1、LP、逐折表现、收敛、计算代价。
- 不确定性：paired fold bootstrap（5000 次，seed 20260713）。由于划分共享被试，区间描述的是划分稳定性，不是独立人群的显著性。

## test 隔离（详见 PROGRAM.md §7）

- 所有决策只用 validation；test 只对锁定候选评估一次。
- 常见泄漏：按 test 选 epoch 或超参；LODO 中目标数据集进入后训练；跨被试设定中 test 被试进入训练；归一化统计或通道选择在 test 上拟合；把 test 结果写进记忆或 brief 后影响后续选择。
- 外部证据：Meta AIRA-dojo 报告，在 MLE-bench 上按 validation 与按 test 选最终节点，奖牌率相差 9–13 个百分点，说明搜索会对验证集过拟合 [1]。AI Scientist-v2 被录用的论文中出现过 train/test 重叠 [2]；PNAS 的独立评估发现这类系统经常擅自替换指定的评估指标 [3]。

[1] https://www.alphaxiv.org/abs/2507.02554　[2] https://github.com/sakanaai/ai-scientist-v2　[3] https://www.pnas.org/doi/10.1073/pnas.2610214123 （均于 2026-10-21 检索）
