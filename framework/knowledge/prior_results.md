# 本项目已有的实测结果

这些是**已结束运行**的结果。其中的 test 数字已被看过，意味着以后使用同一套划分的任务，其 test 不再是"完全未见"的；最终报告中应注明这一点。

## 1. CBraMod + stimulus ISA（历史主参照，2026-08-16）

来源：`docs/research/REVE_ISA_RSI_TASK_BRIEF.md` §2；工程根 `/mnt/cfs-omni/wzf/cross paradigm/60ch_again`；结果根 `results/tencent_lodo_allsource_seedfix/20260816160135`（ISA）与 `results/tencent_cbramod_official_baseline/20260816123039`（baseline）。10 s Lance，60ch，all-source，SEED session-fix，NoClip，seeds 42–47。

| 数据集 | baseline FT bAcc (%) | ISA FT bAcc (%) | 差值 (pp) |
|---|---:|---:|---:|
| SEED | 47.86 | 54.48 | +6.62 |
| SEED-IV | 32.85 | 38.51 | +5.66 |
| SEED-V | 25.06 | 31.03 | +5.97 |
| SEED-VII | 20.97 | 24.02 | +3.04 |
| FACED | 35.15 | 51.59 | +16.44 |
| DEAP | 51.36 | 55.51 | +4.15 |
| 宏平均 | 35.54 | 42.52 | +6.98 |

LP 宏平均 35.74 → 38.01（+2.27 pp），并非每个数据集都提升。后训练参照：full encoder，seed 42，batch 64，40 epoch，Adam，LR 2e-4，warmup 3，cosine，weight decay 1e-4，梯度裁剪 1；目标为纯 L_ISA（同 source 内同刺激、不同被试为正对，flatten + L2 normalize，InfoNCE，temperature 0.1）。

## 2. REVE-base R0 与 R1（stimulus ISA 忠实迁移，2026-10-17/18）

来源：`docs/research/REVE_ISA_R1_RESULTS_20261018.md`；原始报告 `logs/research_controller/reve_isa_recovery_20261017/runs/reve_isa_recovery_20261017/reports/round_1.json`（SHA-256 `3f97ab20…a5e695`）。R1：每个 LODO 目标独立从官方权重开始，用其余五个 source 后训练 40 epoch。**方案在锁定之后才跑 test**。

| 数据集 | FT R0 | FT R1 | 变化 | LP R0 | LP R1 | 变化 |
|---|---:|---:|---:|---:|---:|---:|
| SEED | 56.55 ± 3.49 | 50.26 ± 2.64 | −6.29 | 51.19 ± 2.68 | 46.56 ± 1.10 | −4.63 |
| SEED-IV | 32.60 ± 1.28 | 32.14 ± 1.16 | −0.46 | 32.91 ± 1.04 | 31.54 ± 0.74 | −1.37 |
| SEED-V | 25.85 ± 0.94 | 26.01 ± 0.84 | +0.16 | 25.18 ± 0.61 | 24.99 ± 0.71 | −0.19 |
| SEED-VII | 20.55 ± 1.51 | 20.27 ± 0.84 | −0.28 | 20.50 ± 0.76 | 18.95 ± 0.67 | −1.55 |
| FACED | 36.73 ± 1.54 | 39.07 ± 0.35 | +2.33 | 28.57 ± 0.72 | 32.36 ± 0.83 | +3.78 |
| DEAP | 52.04 ± 1.35 | 52.42 ± 1.18 | +0.38 | 51.55 ± 0.82 | 51.78 ± 0.99 | +0.23 |
| 宏平均 | 37.39 | 36.69 | −0.69 | 34.99 | 34.36 | −0.62 |

（test balanced accuracy，均值 ± 六次划分标准差，%）

要点：
- 直接把 CBraMod 上有效的 stimulus ISA 迁移到 REVE，**六集等权平均下降**；FACED 的 LP 与 FT 都提升，SEED 明显退化（FT −6.29）。
- paired fold bootstrap：FACED FT 约 +1.38 至 +3.51 pp，SEED FT 约 −8.03 至 −3.89 pp（描述划分稳定性）。
- 后训练 loss 在 40 epoch 内下降（例如 SEED 留出：4.343 → 2.550），epoch 35–40 改善已较小。
- 注意：REVE R0 的 SEED FT（56.55）明显高于 CBraMod baseline（47.86），两个模型的起点不同，不能直接比较增幅。

## 3. 耗时（R1 后训练，每个目标一个 6 GPU worker，六个并行）

| 留出目标 | 后训练耗时（小时） |
|---|---:|
| SEED | 3.50 |
| SEED-IV | 3.54 |
| SEED-V | 3.33 |
| SEED-VII | 1.92 |
| FACED | 3.59 |
| DEAP | 3.10 |

另见 `infrastructure.md` 的整体估算。
