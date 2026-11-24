# EEG RSI Scientist

我们研究两个问题。第一，脑电模型保留了哪些信号，作判断时是否用到了它们？第二，AI 能否从一次实验学到研究方法，在下一道新题上做得更好？

**先读[研究速览](docs/研究速览.md)**，两分钟了解做成了什么。要看从王知非的原型到最近一次脑电实验、论文对照和复算的全过程，读[研究全记录](docs/研究全记录.md)。

| 想做什么 | 从哪里开始 |
| --- | --- |
| 查看波形与频带目标的真实 EEG 继续训练结果、亲手复算或启动小试 | [CBraMod 小试](#cbramod-小试) |
| 核查最近一次实验的数字、原报告和证据位置 | [本阶段实验与论文对照](docs/research/phase-completion.md) |
| 找研究者、实验工具、论文比较的代码 | [代码结构](docs/architecture.md) |
| 找本地工程、服务器、模型权重或备份 | [机器与同步](docs/workspaces.md) |
| 找早期实验原文或恢复旧版本 | [历史索引](docs/history/README.md) |

正式本地工程是 `X:/projects/EEG-AI-Scientist`。源码在 `src/eegfm/`，实验题面在 `tasks/`。装好依赖后，可以在工程根目录用以下命令检查入口。

```sh
python -m pip install --no-deps -e .
python -m eegfm --help
```

### CBraMod 小试

在公开 EEGMAT 心算数据上，从同一 CBraMod 权重出发，以相同小批次和遮挡分别继续训练 24 步。波形组预测原始波形，频带组对同一预测波形的 1–4、4–8、8–13 Hz 对数能量计算损失。按参与者划分为 24 人训练、6 人验证、6 人评估。两个训练种子共用同一评估人群，结果属于探索性证据。[计算与训练入口](src/eegfm/eeg/objective_pilot.py) · [公开运行协议](tasks/masked_objective_eegmat/protocol.json)

| 六名评估参与者，48 个窗口 | 初始 | 波形，种子 42 / 43 | 频带，种子 42 / 43 |
| --- | ---: | ---: | ---: |
| 枕部 α 功率 R²，事前主指标 | 0.715 | 0.801 / 0.821 | 0.765 / 0.792 |
| 中央 β 功率 R²，次指标 | 0.148 | 0.159 / 0.215 | 0.382 / 0.346 |
| 心算前后平衡准确率 | 58.3% | 62.5% / 64.6% | 58.3% / 56.3% |

频带减波形的主指标差为 −0.036 和 −0.029，按人重采样的 95% 区间分别为 [−0.079, +0.016] 和 [−0.073, +0.007]，未达到预定的 +0.02 晋级门槛。β 的区间较宽。频带组的 48 个更新步全部触发梯度裁剪，波形组 7 步触发。实际参数更新幅度值得在新研究中控制。四次训练使用 CPU；这个试点由一次普通科研会话组织。

公开版由工程已有的固定版本加载器读取官方 CBraMod 源码和权重。首次运行使用有科学计算依赖的 Python 环境，在仓库根目录准备个人缓存；本地已有相同结构的已校验缓存时可设置 `EEGFM_EEGMAT_RESOURCES` 指向它，略过下载步骤。数据、权重和运行回执留在个人工作区。[EEGMAT 数据与引用](https://physionet.org/content/eegmat/1.0.0/) · [CBraMod 上游与许可](https://github.com/wjq-learning/CBraMod) · [官方权重](https://huggingface.co/weighting666/CBraMod)

```sh
python -m pip install -e ".[science]"
python -c "from pathlib import Path; from eegfm.eeg.data import acquire_resources; root=Path('.local'); root.mkdir(exist_ok=True); acquire_resources(root/'eegmat-resources', allowed_parent=root)"
python -m eegfm.eeg.objective_pilot prepare
python -m eegfm.eeg.objective_pilot train
python -m eegfm.eeg.objective_pilot evaluate
```

要独立核分或从保存的表示重新拟合，运行 `python -m eegfm.eeg.verify_objective_pilot --help` 和 `python -m eegfm.eeg.recheck_objective_readout --help`。每个新运行使用独立目录。
