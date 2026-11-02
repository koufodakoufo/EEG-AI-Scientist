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
| `evaluation/worker.py`、`evaluation/docker_worker.py` | 受限科学候选执行，支持bwrap或Docker；当前火山云实际使用Docker |

实际研究链是NCC模型会话与控制器 → SSH传输 → 火山云Docker候选执行 → 宿主可信评分。Builder原生CPU分析使用单独的资源限额，不与Actor沙箱混称。冻结的输入、源码、模型、评分依赖和预算按运行登记；不能用当前checkout替换旧证据绑定。

内环：问题 → 假设及预测 → 实验 → 证据 → 结论。

外环：允许的开发反馈 → 策略更新 → 冻结版本 → 新问题上的对照评价。

可信评价器不能被正在改进的策略修改。隔离落实到题包、文件可见性和会话输入，不能靠目录命名实现。

第一项研究的六次目标Actor均完成有效Q1 `24/24`，Q2/Q3未执行，没有方法组覆盖增益；见[方法迁移结果](research/method-transfer-results.md)。[Builder读出分析](research/readout-bottleneck-results.md)也已完成并经缓存、拟合和统计审计，但不是受测Actor成果。[第二组读出对照](research/readout-method-transfer-results.md)的六份候选均通过独立拟合、全1008行预测及统计复核；四份最终报告完成，两份因总结阶段后端不可用而缺失。实验有效性与报告完成分开记录，同起点updater比较及ignition未准入。

论文问题与当前任务的对应见[BrainPEC主张索引](research/brainpec-claim-map.md)：本地残余探针Q3不等于论文closure，改编参考也不等于原论文复现。旧`framework/`、`research_bench/`和`integration/`的演变留在Git历史及[历史索引](history/README.md)，当前源码入口统一为安装包与各机器的`code`目录。
