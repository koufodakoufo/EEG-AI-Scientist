# 本轮代码与行为变化

比较起点为上一轮`58b8d71`，维护分支`research/brainpec-real-20261029`。原来源快照`fb6c37e`与原发行归档未修改；当前是wzf的维护修改版，不是已核实的团队最新上游。

| 改动 | 为什么需要 | 证据/边界 |
| --- | --- | --- |
| driver分析模式与受信bridge | 让研究候选是分析程序；保留正负发现，不按分类分数下降就丢弃解释实验 | 实际EpisodeDriver→BridgeDriver→Driver.loop；原优化任务语义保留。见INTEGRATION_ACCEPTANCE。 |
| 真实episode编排 | brief、契约、baseline、attempt、lock、一次test和报告与真实会话关联 | E05/E06全生命周期；done不等于Q1–Q3全做。 |
| 真EEG公共视图与可信worker/aggregator | 公开训练/验证与隐藏测试truth分离；结果绑定模型、数据、split与候选 | 原生隔离canary26项；E05干净重放；原始共享数据不写入。 |
| 科学参考与新任务导出 | 固定特征、跨参与者划分、探针、匹配扰动、残余可读性与不确定性 | EEGMAT/EEGMMIDB各自封存；新任务controller适配仍未完成。 |
| validation-recovery-v1 | 允许有界开发纠错，失败仍消耗预算；未知可信层错误不能误判为可纠正 | 旧strict默认保留，E01不重写；R56独立审查及Linux240项测试记录。 |
| 实际skill正文注入 | 不能以存在skill文件冒充模型已读到技能 | E06每次实际prompt与注入SHA；原M15字节不改。 |
| 原子主张与证据评分v3 | 拆点估计、区间、机制和scope，区分错误与参考外结论 | 旧分数保留，12案例/16判断合成开发校准通过；无通用能力分数。 |
| 重放与诊断脚本 | 核验同一锁定代码、保存参数、报告数值、统计稳定性 | E05完整干净重放；E06只做已有证据核对；不混为独立方法复现。 |
| 火山云个人CPU环境 | 用可追溯依赖与自己的代码验证共享权重接口 | 共享权重原位只读，无GPU、无共享数据复制；读取隔离尚未验收。 |

工程主位置是`framework/eegfm/research_bench/`、`framework/eegfm/driver.py`及`scripts/research/`。晚间关键提交包括6263df8（恢复/注入）、23f9df7（基线/统计/云环境）、25049ce（新EEG题包与校准准备）、30cac6f（E05重放）。收尾只增加审计和文档，不修改已冻结科学实现或现有受测条件。

有些旧报告写“未提交/未push”是子工作完成当时状态，现由主工作统一出版；实际最终Git节点以同步收据为准。Windows读取/生成中文文档时曾遇stdin默认编码错误，已改用ASCII转义传输后按UTF-8写入，最终文档另做UTF-8与链接校验；没有改科学产物。
