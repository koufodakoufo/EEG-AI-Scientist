# EEG RSI Scientist

研究两件事：**EEG 模型保留了什么信息，以及 AI 能否从真实实验中学到更好的科研方法。**

研究者提出问题、写代码、做实验和报告；更新器尝试改进研究方法，再交给新的研究者检验。完成实验、写出一份方法提示，都不自动等于自我提升。

## 现在到哪了

独立 AI 已在火山云完成 EEG 实验。对六名测试参与者，线性擦除以后，高斯核读出没有比线性读出找回更多有用的 delta 功率信息。另一套复算从源码得到相同的参数、预测和统计结果。

本阶段已归档。两份报告均已与原论文逐项对照。BrainPEC 得到了局部“哪些特征可以读出”的证据，后面的分类决策和性能解释问题仍待实验。LEACE 只检验了两种具体读出。当前证据尚不能判断 AI 的科研能力是否因方法更新而提高。[本阶段结果与边界](docs/research/phase-completion.md)

## 从这里看

- [当前阶段：实验结果与论文对照](docs/research/phase-completion.md)
- [此前研究做了什么](docs/research/evidence-guided-results.md)
- [代码怎样组成一个研究流程](docs/architecture.md)
- [本地、火山云、NCC 和 GitHub 怎么使用](docs/workspaces.md)
- [以前的实验与版本](docs/history/README.md)

## 代码与运行

`src/eegfm/` 是系统实现，`tasks/` 是研究题目和实验接口，`tests/` 检查实现，`docs/` 解释设计和证据。数据、权重和私有实验产物不进 Git。

正式本地工程为 `X:/projects/EEG-AI-Scientist`。新计算优先在火山云；各次实验绑定自己的代码、输入和预算。Git 的共同主线是 `main`，开发分支完成后合回主线，旧阶段用归档标签保留。

已有依赖的环境中：

```bash
python -m pip install --no-deps -e .
python -m eegfm --help
```

新环境的依赖、机器入口和同步命令见上面的机器说明。
