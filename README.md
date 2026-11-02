# EEG RSI Scientist

让 AI 从真实 EEG 实验和反馈中学习可迁移的科研方法，并检验它是否更擅长改进下一代研究者。

内环提出假设、设计实验、形成证据；外环修改研究策略，在新问题上比较改进前后。EEG 表征分析是目前的实验场。一次任务完成、一次较好分数或一份新 skill 都不等于 RSI。

## 从哪里开始

- [方法迁移试点结果](docs/research/method-transfer-results.md)：六次目标 Actor 均完成 Q1，未观察到有效证据覆盖增益。
- [旧分类头瓶颈分析](docs/research/readout-bottleneck-results.md)：已完成并审计的 Builder 结果，不能计作 Actor 成果。
- [读出任务的研究者对照](docs/research/readout-method-transfer-results.md)：同一份冻结方法在新问题上的六次比较；六份候选复验通过，四份完整报告、两次总结中断。
- [主计划与 ignition 准入](docs/research/ignition-study.md)：当前进度、原时间窗口和仍未满足的准入条件。
- [BrainPEC 主张索引](docs/research/brainpec-claim-map.md)：原论文问题、作者结论与改编条件的比较边界。
- [代码结构](docs/architecture.md)：各部分负责什么，哪些能力已经实现。
- [机器与同步](docs/workspaces.md)：本地、火山云、ncc 和 GitHub 的关系。
- [历史成果](docs/history/README.md)：已有结果和原始证据入口。

## 日常使用

日常只需辨认三个部分：`src/`是实现，`tasks/`是要研究的问题与接口，`docs/`是设计和证据说明。`tests/`用于检查实现，`config/`和`scripts/`用于环境与同步；`knowledge/`、`skills/`、`registry/`分别放领域材料、方法提示和资源登记。它们是否提供给受测AI由实验条件决定。

本地用于开发与阅读；NCC运行模型会话和可信控制器，通过SSH把冻结候选交给火山云Docker科学执行端。火山云也执行受限额管理的原生Builder分析；这与Actor沙箱分开。GitHub保存共同的main，旧源码与过程记录保留在Git历史、归档标签和原冻结证据目录。

已配置环境中，从仓库根安装当前项目：

```bash
python -m pip install --no-deps -e .
python -m eegfm --help
python -m pytest -q
```

新环境先按[机器说明](docs/workspaces.md)安装 CPU 科学依赖；`dev` 包含测试与科学依赖，`plots` 和 `reve` 按需添加。Linux 负责受限 Agent、进程和沙箱执行。Windows 可编辑代码、阅读结果并运行可移植检查。

代码在 src/eegfm/，测试在 tests/，任务定义在 tasks/。运行产物、数据、权重和私有参考不进 Git。唯一正式本地工程为 X:/projects/EEG-AI-Scientist。

## 当前事实

第一项方法迁移研究已完成真实源任务、一次方法更新和三条件各两次目标Actor运行。六次有效覆盖均为Q1 `24/24`、Q2 `0/2`、Q3 `0/2`；后两项未执行，方法组没有覆盖增益。

Builder读出分析及缓存、数值审计已完成：42名新测试被试上，新表示读出减旧头的BA差为−1.39个百分点，95%区间[−4.56, +1.88]，未支持有用增益。数值审计的同作者实现与审查边界见结果报告。第二组六次Actor读出实验均通过独立拟合、全1008行预测及统计复核；其中四次完成最终报告，两次在总结会话遇到后端不可用而中断，未补跑替换。当前没有可靠的方法增益证据，ignition未准入。

收尾维护代码`0206182`的完整套件：Windows 380通过/83跳过，NCC 445通过/18跳过，火山云443通过/20跳过。本轮科研仍绑定原冻结代码`5f2beb8`；之后的跨平台清单排序修复不改写运行身份。隔离资格与研究准入另行核验，详见[机器与验证记录](docs/workspaces.md)。

主线为 main。开发使用短期主题分支，验证后合回主线；旧阶段保存在 archive/* 标签。新运行按研究主题、协议版本、代际、条件与重复次数命名，日期只记录在元数据中。
