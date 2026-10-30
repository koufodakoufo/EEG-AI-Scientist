# 从这里看当前项目

本轮按用户2026-10-30上午“先收尾并报告”的要求停止研究。**真实EEG流程已接通；科研能力提升与真实任务间技能迁移尚未证实。**

1. 先读[一页简报](MORNING_SUMMARY.md)。
2. 理解结果与限制，读[详细报告](docs/research/2026-10-30-extension/DETAILED_REPORT.zh-CN.md)。
3. 看Agent实际做了什么，读[案例](docs/research/2026-10-30-extension/AGENT_CASE_STUDY.zh-CN.md)和[连接验收](docs/research/2026-10-30-extension/INTEGRATION_ACCEPTANCE.md)。
4. 继续前读[恢复说明](docs/research/2026-10-30-extension/RESUME.md)；不直接重置旧账本或自动启动尚未运行的实验。

本机VS Code打开 **X:\projects\EEG-AI-Scientist**。Remote-SSH连接nccserver0后，用“文件→打开文件夹”打开/data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration；仅在终端cd不会改变文件树。

当前代码并非wzf原件原封不动：保留driver生命周期，增加隔离评测和真实数据适配，修复有限状态/恢复逻辑。见[改动](docs/research/2026-10-30-extension/CHANGES.zh-CN.md)。原fb6c37e来源副本和发行归档仍保留。

eegfm-stage-a-20261028是历史部署名，不是研究结论。为保持冻结绝对路径有效，本轮没有搬迁服务器工程。X盘为唯一正式本地工作区，GitHub发布代码，nccserver0执行隔离研究，火山云准备模型计算。[路径表](docs/research/2026-10-30-extension/PATH_MAP.md)

旧PROGRESS、环境JSON及夜报均为历史快照。原一页早报已按原字节保存为[旧早报](docs/overnight/2026-10-29/MORNING_SUMMARY.original.md)，以当前报告核验时间为准。
