# EEG RSI Scientist

我们研究两个问题。第一，脑电模型保留了哪些信号，作判断时是否用到了它们？第二，AI 能否从一次实验学到研究方法，在下一道新题上做得更好？

**先读[研究速览](docs/研究速览.md)**，两分钟了解做成了什么。要看从王知非的原型到最近一次脑电实验、论文对照和复算的全过程，读[研究全记录](docs/研究全记录.md)。

| 想做什么 | 从哪里开始 |
| --- | --- |
| 让独立研究者选一项真实 EEG 实验，查看结果或接续研究 | [启动科研会话](#启动科研会话) |
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

### 启动科研会话

在有科学计算依赖、已登录原生 Codex CLI 和 EEGMAT/CBraMod 缓存的项目根目录运行。首次准备缓存见下方小试。下面依次是查看本轮、让下一位研究者继承材料并停在方案阶段、审阅 `plan.json` 后继续。

```sh
python -m eegfm.eeg.scientist status objective-choice-eegmat-r02
python -m eegfm.eeg.scientist run objective-choice-eegmat-r03 --parent objective-choice-eegmat-r02 --through design
python -m eegfm.eeg.scientist run objective-choice-eegmat-r03
```

在新克隆中用 `python -m eegfm.eeg.scientist run my-first-study` 开始。每个轮次的材料保存在本机 `.local/research-episodes/<轮次名>/`。想亲自审阅研究者的选择，可以加 `--through design`，阅读 `plan.json` 后再用同名 `run` 继续。也可用 `--through experiment` 在实验结果落盘后退出。同名运行会核对已登记的记录，再从下一阶段接续。已结束的轮次可反复查看。[会话控制器](src/eegfm/eeg/scientist.py) · [CPU 训练与评价](src/eegfm/eeg/objective_pilot.py)

**第一轮由研究者决定的实验**（`objective-choice-eegmat-r01`）。研究者读到下方开发小试的结果表、两篇论文的简要摘记和可执行范围。它选择了一对等带宽对照。两组都重建被遮挡波形的 1–4、4–8、8–13 Hz 对数能量；第四个目标，A 用 30–47 Hz，B 用 13–30 Hz。主指标是冻结编码器后从中央电极表示预测 β 功率的 R²。从同一公开权重出发，在 24 名训练者上用完全相同的批次和遮挡配对继续训练，每组每个种子 24 步，学习率均为 0.00001。四次训练合计用时约 27 秒，使用 CPU。下面的 6 名验证者在开发阶段已使用过。

| 训练种子 | 初始 R² | A | B | B 减 A［被试重采样 95% 区间］ |
| --- | ---: | ---: | ---: | --- |
| 42 | 0.396 | 0.364 | 0.407 | +0.042［+0.004，+0.135］ |
| 43 | 0.396 | 0.315 | 0.295 | −0.020［−0.125，+0.022］ |

研究者事先要求两个种子各自提高至少 0.02，且区间下限都高于零。接续研究者据此判为不确定。它选择下一步只在训练人群中检查各频带能量的方差、各目标产生的梯度大小和方向；本轮到判读为止。区间固定了已拟合模型，两个种子共用同一批人。独立重拟合复现了 864 个窗口级预测，最大绝对差小于 8.1×10⁻¹⁵。

两次设计回复因字段格式被拒收。开发者修正接口提示并允许再提交一次，研究者保留了原对照、指标和门槛。方案落盘后由受限的 CPU 执行器训练和评价；控制进程退出并重启后，一个新的原生线程取得此前声明的材料、冻结方案和计算结果。在本机查看 `trajectory.jsonl`、`decision.json` 及各会话的 `receipt.json` 可追溯这些步骤。这个例子验证了一轮跨会话研究接续；科研方法是否随经验改善，还需要独立评价。

**第二轮训练诊断**（`objective-choice-eegmat-r02`）。独立研究者选择重放第一轮四条 CPU 训练轨迹，仅打开训练分区。它预先选择第 1、8、16、24 步，以第四频带梯度在前三带合计梯度方向上的投影来衡量抵消。每个种子要有至少三步满足同向判据；每一步既要求两臂抵消比例相差至少 0.20，也要求相应一臂确实发生抵消。

八个配对观测全部判为不确定。两个种子的第 1、8 步中，两臂的第四频带都顺着前三带的合计方向。八次比较里，30–47 Hz 臂的第四带目标值方差都更小，预测误差和未裁剪的编码器梯度都更大。以首步为例，两种子的第四带原始梯度范数分别约为 β 臂的 4.4 和 5.4 倍；全模型的合计梯度经裁剪后范数约为 1，四条轨迹的 AdamW 实际编码器位移范数都约为 0.021。该观察无法确立梯度尺度对 β 读出的因果作用。

逐步损失及裁剪前全模型梯度范数与第一轮一致，四个终点的编码器、输出头、优化器和随机状态也逐一相同。Windows 原生数值进程曾三次异常退出，分臂核验及接续保留了已完成的工作。计入失败尝试，执行器保守计时约 249 秒，上限 600 秒，最多四个 CPU 线程，GPU 用量为零。接续研究者选择下一步保留等权对照，另用训练批次校准第四带权重后比较。此干预需要扩展训练损失，本轮停在决定处。[诊断实现](src/eegfm/eeg/objective_pilot.py) · [运行及恢复](src/eegfm/eeg/scientist.py)

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
