# 数据集

来源：`docs/research/REVE_ISA_RSI_TASK_BRIEF.md` §3；release 目录于 2026-10-21 核实存在。机器可读版本：`registry/datasets.yaml`。

数据根：`/mnt/omni-eeg-01/downstream_preprocess/wzf_dataset`。统一格式：lance，200 Hz，10 s 窗，60 个 mdJPT 通道，shape `(N, 60, 2000)`，已做坏导处理，**NoClip**（不做 ±100 µV 裁剪）。不要覆盖原始 release。

| 数据集 | release（相对数据根） | 样本 | 被试 | 类别 | 每折 train/val 被试 |
|---|---|---:|---:|---:|---|
| SEED | `SEED/derived/lance_mdjpt60_badch` | 14895 | 15 | 3 | 4/4 |
| SEED-IV | `SEED-IV_10s_v1/derived/lance_mdjpt60_badch` | 14655 | 15 | 4 | 4/4 |
| SEED-V | `SEED-V_10s_v1/derived/lance_mdjpt60_badch` | 11424 | 16 | 5 | 4/4 |
| SEED-VII | `SEED-VII/derived/lance_mdjpt60_badch` | 27340 | 20 | 7 | 5/5 |
| FACED | `FACED/derived/lance_mdjpt60_badch` | 10332 | 123 | 9 | 31/31 |
| DEAP | `DEAP/derived/lance_mdjpt60_badch` | 7680 | 32 | 2 | 8/8 |

## 已知注意事项

- **SEED session**：按每个被试的日期排序，映射为 1/2/3，核对每人恰好三个 session；其余五个数据集不改写 session。只改元数据解释，不改信号、标签或行顺序。
- **DEAP 标签**：二分类所用维度和阈值必须从 release 与 loader 读取，不能凭经验假设。
- **SEED 家族**（SEED / SEED-IV / SEED-V / SEED-VII）之间的被试与刺激独立性**未被证明**；LODO 不能声称完全跨家族无重叠。
- 通道顺序、单位、标签值的语义必须从 release 和 loader 查证后记录。
- 每个 release 的实际样本数、被试数应在 setup 时重新核对；与上表不一致时以实际文件为准，并写入记忆。
