# EEG RSI Scientist

让 AI 从真实 EEG 实验和反馈中学习可迁移的科研方法，并检验它是否更擅长改进下一代研究者。

内环提出假设、设计实验、形成证据；外环修改研究策略，在新问题上比较改进前后。EEG 表征分析是目前的实验场。一次任务完成、一次较好分数或一份新 skill 都不等于 RSI。

## 从哪里开始

- [下一轮 ignition 研究设计](docs/research/ignition-study.md)：研究什么、怎样比较、什么结果算证据。
- [代码结构](docs/architecture.md)：各部分负责什么，哪些能力已经实现。
- [机器与同步](docs/workspaces.md)：本地、火山云、ncc 和 GitHub 的关系。
- [历史成果](docs/history/README.md)：已有结果和原始证据入口。

## 日常使用

已配置环境中，从仓库根安装当前项目：

```bash
python -m pip install --no-deps -e .
python -m eegfm --help
python -m pytest -q
```

新环境先按[机器说明](docs/workspaces.md)安装 CPU 科学依赖；`dev` 包含测试与科学依赖，`plots` 和 `reve` 按需添加。Linux 负责受限 Agent、进程和沙箱执行。Windows 可编辑代码、阅读结果并运行可移植检查。

代码在 src/eegfm/，测试在 tests/，任务定义在 tasks/。运行产物、数据、权重和私有参考不进 Git。唯一正式本地工程为 X:/projects/EEG-AI-Scientist。

## 当前事实

已完成真实 EEG 参考分析，以及一次无/有固定方法提示的独立 AI 对照。两次 AI 运行只完成属性恢复分析；尚未证明稳定技能收益、真实任务经验迁移或递归自我改进。当前外环已有轨迹、记忆和 skill 材料管理，自动优化器和 ignition 对照仍待实现与运行。

主线为 main。开发使用短期主题分支，验证后合回主线；旧阶段保存在 archive/* 标签。新运行按研究主题、协议版本、代际、条件与重复次数命名，日期只记录在元数据中。
