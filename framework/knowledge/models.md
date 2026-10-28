# EEG 基础模型

来源：`registry/models.yaml`；路径于 2026-10-21 核实存在。

## 本地可用

| 模型 | 权重 | 注意事项 |
|---|---|---|
| REVE-base | `/mnt/omni-eeg-01/cx/EEG_FM/baseline/REVE/weights/reve-base`（位置资源：`reve-positions`，说明：`README.md`） | 核实实际 loader、配置、token 轴、特殊 token、位置编码与有效 token mask；不要假设 REVE token 与 CBraMod 的 `(C,10,200)` 相同；缺权重时禁止随机初始化 |
| REVE-large | 同目录 `reve-large` | 尚未在任务中使用 |
| CBraMod | 历史 ISA 参照使用（`/mnt/cfs-omni/wzf/cross paradigm/60ch_again`） | 历史后训练权重 `emotion_cbramod.pth` 在报告位置未找到；使用前需定位并核实 |

**预处理口径**：区分"原始 µV 振幅裁剪"和"模型输入规范"。本项目数据口径为 NoClip。REVE 若需要归一化或位置处理，先核对本地官方实现，并在 baseline 与所有候选之间一致冻结。旧 REVE wrapper 的 z-score / ±15 SD 不能未经说明直接继承。

## 领域模型清单（待开题调研补全）

LaBraM、EEGPT、BIOT、CBraMod、REVE 等模型的预训练数据、输入格式、已报告结果，**本文件尚未整理**。开题调研（PROGRAM.md §2）中查到的内容写进各任务的 RESEARCH_BRIEF；经核实、跨任务有用的事实再整理到这里，并附来源。
