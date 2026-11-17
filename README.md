# EEG RSI Scientist

研究两件事：**EEG 模型保留了什么信息，以及 AI 能否从真实实验中学到更好的科研方法。**

研究者提出问题、写代码、做实验和报告；更新器尝试改进研究方法，再交给新的研究者检验。完成实验、写出一份方法提示，都不自动等于自我提升。

## 现在到哪了

已完成真实 EEG 分析，以及独立研究者的写代码、拟合、选择、测试和报告验证；结果与局限集中在下方研究报告。

正在继续完成论文工作流试验的原定目标。上次尝试只完成一次基线拟合，完整科研链和 BrainPEC 报告评价均未完成；失败记录保留。此次先修复任务交付、分段提交和长报告比较，再推进实验、独立复算及完整报告对照，详见[阶段进度](docs/research/phase-completion.md)。

目前尚无可靠的科研能力提升或 RSI 证据。BrainPEC 只完成了缩减的 Q1 试点，整篇论文没有复现完成。

## 从这里看

- [本阶段做了什么、结果如何](docs/research/evidence-guided-results.md)
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
