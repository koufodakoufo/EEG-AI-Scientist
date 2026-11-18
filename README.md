# EEG RSI Scientist

我们研究两个问题。第一，脑电模型保留了哪些信号，作判断时是否用到了它们？第二，AI 能否从一次实验学到研究方法，在下一道新题上做得更好？

**先读[研究速览](docs/研究速览.md)**，两分钟了解做成了什么。要看从王知非的原型到最近一次脑电实验、论文对照和复算的全过程，读[研究全记录](docs/研究全记录.md)。

| 想做什么 | 从哪里开始 |
| --- | --- |
| 核查最近一次实验的数字、原报告和证据位置 | [本阶段实验与论文对照](docs/research/phase-completion.md) |
| 找研究者、实验工具、论文比较的代码 | [代码结构](docs/architecture.md) |
| 找本地工程、服务器、模型权重或备份 | [机器与同步](docs/workspaces.md) |
| 找早期实验原文或恢复旧版本 | [历史索引](docs/history/README.md) |

正式本地工程是 `X:/projects/EEG-AI-Scientist`。源码在 `src/eegfm/`，实验题面在 `tasks/`。装好依赖后，可以在工程根目录用以下命令检查入口。

```sh
python -m pip install --no-deps -e .
python -m eegfm --help
```
