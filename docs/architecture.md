# 代码结构

项目是一套研究执行与评估工具，不是一个已经验证的 RSI 系统。

| 位置 | 职责 |
|---|---|
| `src/eegfm/agent/` | 内环运行状态、尝试、作业、模型会话和研究控制器 |
| `src/eegfm/evaluation/` | 可信计算、候选与结果验证、证据、主张和重放；legacy 保留早期评分 |
| `src/eegfm/eeg/` | EEG 数据、属性计算、参考分析、公共导出及当前具体任务 |
| `src/eegfm/improvement/` | 方法经验、允许的轨迹和记忆；尚无已验收的自动 RSI 优化器 |
| `tasks/` | 任务定义和候选模板，不保存实际大规模运行产物 |
| `skills/` | 已有方法提示与来源；可见性由实验条件控制 |
| `knowledge/` | 领域索引与历史经验，不能整体默认注入受测研究者 |
| `tests/` | 行为、隔离、数值与迁移后接口回归 |
| `scripts/` | 环境与同步等运维入口，科学算法优先作为包模块复用 |

`eeg/episode.py`显式登记EEGMAT、EEGMMIDB属性依赖分析和新的EEGMMIDB缓存读出任务，分别绑定题面、scope、评分器和完成条件。未知任务名拒绝执行，不能只换名称复用旧评分规则。

| 具体接口 | 当前职责与边界 |
| --- | --- |
| `eeg/aggregation.py` | 属性读出、表示干预与残余探针的可信聚合；机械完成不代表三个科学分项均完成 |
| `eeg/readout_data.py`、`eeg/readout_study.py` | Builder私有缓存准备、固定读出拟合及统计；参考方法和答案不进入Actor |
| `eeg/readout_aggregation.py`、`tasks/readout_bottleneck/` | 新读出任务的声明、绑定输入、逐行预测及可信统计；合法拟合与科学判别仍需源码和重放审计 |
| `evaluation/ssh_worker.py` | 可信控制器将冻结候选提交至已登记云端执行器，核验返回身份；认证留在控制层 |
| `agent/provider.py`、`provider_trace.py`、`provider_export.py` | 编码研究者的任务、文件及请求通道；本地核验原生会话，向可信服务器传送限定的执行记录与背景哈希。合成及真实 EEG 任务均已完成流程与数值复算；会话执行、调度等待与回执交付使用分别登记的时间边界 |
| `evaluation/public_workbench.py` | 在容器内拟合公开训练数据，核验有限数值参数后交回研究者；与保留标签的科学评价分开，检查共享截止时间 |
| `evaluation/worker.py`、`evaluation/docker_worker.py` | 受限科学候选执行，支持bwrap或Docker；当前火山云实际使用Docker |
| `evaluation/paper.py`、`evaluation/assessment.py` | 论文问题、私有参考与公共题包分开；逐项比较报告主张，未知实验条件保留待评；保存真实模型请求与可重放响应 |
| `evaluation/report_package.py`、`registered_assessment.py` | 新的可选报告入口：保留原文和来源位置，将运行登记与作者主张分开，按明确编号分批比较；旧评价协议不变 |
| `eeg/evidence_policy.py` | 新 v2 任务的验证证据缺口提示；只读取当前验证结果，完成数量不等于科学有效性 |
| `eeg/erasure.py` | 独立实现的线性概念移除；训练样本上的协方差约束不等于新样本中所有信息消失 |
| `eeg/motor_imagery.py` | 明确时间窗、通道和标签的运动想象准备；旧开发入口保持训练/验证边界，可信新研究须显式登记准入记录 |
| `improvement/decision.py`、`selection.py` | 有限实验请求、不可变结果账本和事前选择规则；允许更新器返回不修改，不强制产生新方法 |

当前实际完成的研究链是本地独立上下文 → 固定网关 → NCC 控制器 → 火山云 Docker 拟合与推理 → 宿主可信评分。研究者自己编写源码、提交实验并写报告。合成任务与历史 EEG 读出任务都已完成计划、候选、冻结、测试、报告及数值复核。NCC 旧原生模型通道的授权仍失效，与本轮通道分开记录。

控制器按页交付大结果并核对完整性；本地自动交付已核验的会话回执，避免依赖人工及时转发。可选的原生计时策略从已核验的实际会话开始计时，调度等待和回执交付另有上限，总截止时间保持固定。失败运行保留原结果，修复只用于后续版本。模型上下文接受访问审计，仍不等于模型进程的操作系统隔离。Builder 原生 CPU 分析使用单独资源限额；冻结的输入、源码、模型、评分依赖和预算不能由当前 checkout 替换。

内环：问题 → 假设及预测 → 实验 → 证据 → 结论。

外环：允许的开发反馈 → 策略更新 → 冻结版本 → 新问题上的对照评价。

可信评价器不能被正在改进的策略修改。隔离落实到题包、文件可见性和会话输入，不能靠目录命名实现。

第一项研究的六次目标Actor均完成有效Q1 `24/24`，Q2/Q3未执行，没有方法组覆盖增益；见[方法迁移结果](research/method-transfer-results.md)。[Builder读出分析](research/readout-bottleneck-results.md)也已完成并经缓存、拟合和统计审计，但不是受测Actor成果。[第二组读出对照](research/readout-method-transfer-results.md)的六份候选均通过独立拟合、全1008行预测及统计复核；四份最终报告完成，两份因总结阶段后端不可用而缺失。实验有效性与报告完成分开记录，同起点updater比较及ignition未准入。

论文问题与当前任务的对应见[BrainPEC主张索引](research/brainpec-claim-map.md)：本地残余探针Q3不等于论文closure，改编参考也不等于原论文复现。旧`framework/`、`research_bench/`和`integration/`的演变留在Git历史及[历史索引](history/README.md)，当前源码入口统一为安装包与各机器的`code`目录。
