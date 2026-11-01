# 本轮需求完成度审计

审计日期：2026-10-30，北京时间；现场证据核对截至 09:59。依据为 [原任务书](../2026-10-29-brainpec-real/TASKBOOK.md)、[延长阶段计划](PLAN.zh-CN.md)及用户上午“本轮先收尾并报告”的决定。此次只读核对现有文件、运行状态、源码和已保存结果，没有启动 Actor、Distiller、科学实验或重放，也没有新增研究预约。之后生成的总入口、备份和最终同步以收尾收据补验，不凭准备状态宣布完成。

**本轮取得了真实 EEG 参考研究，以及真实隔离 Actor 经维护版 wzf Driver 完成 Q1 的可核验轨迹；没有完成全部科研与技能学习目标。** 两个真实 Actor 都只覆盖 Q1。完整 Q1–Q3 是 Builder 的参考研究成果，不能记到 Actor 名下。已有一对生命周期完成的 skill/no-skill 运行，不能宣称技能有效、通用科研能力提高或 RSI。

状态含义：“完成”只针对本行限定交付；“部分完成”已有实物但仍缺验收内容；“未做”尚未启动；“未核验”现有证据不足以确认。下文不把计划、配置文件、`done` 字段或测试数量单独当作科学成功。

## 逐项需求矩阵

| 需求 | 状态 | 实际证据与剩余边界 |
|---|---|---|
| A：唯一正式工作区、原来源与活动代码清晰 | 完成，当前入口已补验 | 当前本地为 `X:/projects/EEG-AI-Scientist`；活动源码在 `framework/`，服务器继续使用既有 integration。根 `AGENTS.md` 与 `docs/source-import.md` 明确保留来源、原始快照和私有排除项。新START_HERE、MORNING_SUMMARY、PATH_MAP、RESUME已落盘并核对；当前资源状态另见CURRENT_RESOURCE_STATUS.json，原冻结清单不改写。 |
| B1：解释旧争议评分，保留失败 | 完成限定诊断 | [OLD_SCORE_CASE_STUDY.md](../2026-10-29-brainpec-real/OLD_SCORE_CASE_STUDY.md)区分原句、原子主张、数值与参考覆盖；原合成结果和 E01 失败保留。该诊断不构成新确认性 skill 改善。 |
| B2：评分拆分、开发校准 | 部分完成 | v3 协议与离线边界测试存在；服务器 R85/R86 实际完成两个独立原生调用，已保存输出的 `CALIBRATION_RESULT.json` 为 `passed_synthetic_development_calibration`，13/13 原子匹配、16/16 定向判定正确，critical/native evidence errors 为空。它只验收这份小型合成开发集，尚不等于真实科研评分器的普遍有效性，也未给本轮 Actor 发布已验收的综合能力分数。 |
| B3：重放、数值与分割绑定 | E05 完成；其他结果按范围部分完成 | 直接核对服务器 E05 `REPLAY_AUDIT.json`：`accepted`；validation/test 各 305 项指标精确相同，逐数组最大误差 0，56 个原文件未变。[E06 收尾审计](E06_AND_PAIR_AUDIT.zh-CN.md)接受候选身份、报告和 Q1 点估计；没有干净重放。Builder 两个数据集有点估计/锁文件核验；它们不是完整模型管线的独立实现。 |
| C：真实数据、已识别权重、训练/验证/测试、冻结参考 | 完成适配路线 | EEGMAT 的官方预训练 CBraMod + 新训练线性头、24/6/6 人、12 组/62 列、第 6/12 层已实跑 Q1–Q3。已核对实际结果文件及报告哈希一致。不是 Mumtaz/Stress 匹配下游模型，也不是严格 BrainPEC 论文复现。 |
| C：资源说明与原协议差异 | 部分完成 | [TASK_SELECTION.md](../2026-10-29-brainpec-real/TASK_SELECTION.md)、[科学报告](../2026-10-29-brainpec-real/SCIENCE_RESULT.zh-CN.md)、私有锁与来源记录给出适配身份。`RESOURCE_MANIFEST.json` 仍保留早期 `actual server strict load pending` 状态，不能把该字段当当前运行结论；后续加载/运行证据应与旧清单一起读。骨干预训练参与者重叠仍未知。 |
| D：真实原生 Actor、隔离工具与 wzf Driver 生命周期 | E05/E06 完成，科学范围 Q1 | `EpisodeDriver → BridgeDriver → Driver.loop` 的实际调用路径存在；两者各五次真实会话、委托协议审核、baseline、A2、lock、一次 test、报告与 `done` 均有原始记录。[集成验收](INTEGRATION_ACCEPTANCE.md)逐节点列出事件、时间和产物；E05 另完成干净重放。未把 Builder 脚本伪装为 Actor。 |
| D：真实路径隔离与关键工程回归 | 完成限定验收 | 直接核对 R15 `ISOLATION_REPORT.json`：passed、实际工具表已核验、模型控制成功；公共读取/自有写入通过，答案、其他 case、测试特征、祖先规则、受保护配置、外网工具等探针拒绝。`full-linux-tests-04/output.log` 实有 240 passed，退出码 0。此为所用二进制/配置的经验边界，内存为采样限制，不是内核安全性证明。 |
| D：真实 Actor 完成 Q2/Q3 | 未完成 | E01 尝试干预但验证失败，未锁定、未测试；E06 的局部干预原型中断，未证明完整运行时间可行。E05/E06 最终均仅提交 Q1，`q2_interventions=0`、`q3_residual_groups=0`、`numeric_scope_complete=0`。没有合格 Actor 预测依赖/残余信息结果，不能将未估计当作零效应。 |
| E：冻结条件、公平预算、真实注入 skill | 完成一对执行，比较验收部分完成 | v2 预定 E05 无 skill/E06 有 skill、统一模型/6 次会话上限/4 CPU/12 GiB/0 GPU；两者实际各用 5 次。权威账本 E05 的注入哈希为空，E06 五次均为同一冻结 M15 哈希 `54d5ce03…79191d`。核心冻结与失败不被事后改写。服务端精确模型 revision 不可见，不能声称已锁定不可变服务权重。 |
| E：争取两对完整运行 | 部分完成 | E05/E06 生命周期和本轮逐维案例比较完成；E06 的有界源码/现有数值审查与 E05 的干净重放层级分别报告。第二对 E07/E08 没有 episode 目录，权威账本没有相应实际调用。配置中列出的 R72–R83 是预定顺序，不是已经执行。 |
| 延长目标：真实 dev 轨迹 → 新 skill → 新真实 holdout | 未做 | 使用的是未改字节的合成 dev M15 skill。尚无真实 dev-only Distiller 产物、独立冻结的新 skill 或 EEGMMIDB Actor 对照。因此没有实际完成真实任务间自改进闭环。 |
| 延长目标：新真实任务 EEGMMIDB | 参考与导出完成，Actor 未做 | 36 人睁眼/闭眼基线任务的 Builder Q1–Q3、匿名导出和核验存在；实际结果哈希与报告一致。`POST_RESULT_AUDIT.json` 核对 30 个锁文件、24 个 Q1 点估计、8 个干预变体、864 行及 36 名互斥匿名参与者。最初 OpenMP 中断及续跑保留。尚未完成新任务的 controller/episode 接线和成对 Actor 实验。 |
| 延长目标：预训练/随机/透明特征比较 | 完成探索性分析 | [基线报告](REPRESENTATION_BASELINES.zh-CN.md)及实际 `VERIFICATION.json` 存在且 passed：5 个分类头、96 个 Q1 点估计核对。预训练与随机 200 维，透明特征 62 维，属于相同学习规则的实用比较，不是等容量比较。已见测试队列上的追加结果始终是探索性。 |
| 延长目标：统计稳健性 | 完成限定敏感性分析 | [精确 bootstrap 报告](EXACT_BOOTSTRAP_SENSITIVITY.zh-CN.md)及 `final/VERIFICATION.json` 为 passed：46,656 个有序重采样、462 个计数向量、53 项统计量、106 项区间核验；零的跨越判定改变 0/53。只减少 Monte Carlo 噪声，不能增加六名测试参与者的信息量。 |
| 延长目标：REVE 新真实 EEG 研究 | 未做 | 权威账本 R92 为 cancelled，理由为仅预约、没有启动 helper/实验，用户要求收尾。云端 REVE 严格加载与合成前向不算真实 EEG 科研。 |
| 延长目标：火山云自有环境 | 完成 CPU 基础设施 | 已现场只读核对自有目录、`repository/.git` 与 `evidence/acceptance.json`：passed，明确 `synthetic_cpu_infrastructure_acceptance`、`actor_result=false`、`real_eeg_data_read=false`、`gpu_use=false`。共享权重原位只读。未验收 Actor 读取隔离、真实 EEG 完整任务、GPU 分配或个人持久配额。 |
| 延长目标：既有 GitHub 仓库同步 | 完成至35c7631检查点，最终收据提交另验 | 实读远端 research 分支已经存在，09:51 核验为 `23f9df7`；本地/实验室代码为 `30cac6f`，火山云 repository 为 `23f9df7`。这证明先前推送与云仓库建立完成，不能证明收尾新增文件已同步。最终 HEAD/增量出版审计应以本轮同步收据为准。 |
| 中文简报、详细报告、可恢复证据、进程收尾 | 本轮收尾交付完成，研究缺口保留 | 独立科学报告、[Agent 案例](AGENT_CASE_STUDY.zh-CN.md)、集成验收、E05/E06 审计、协议与预算已经存在并核读；新入口、当前总报告、路径/恢复/变化说明与备份核验由本轮收尾统一交付。不能用旧 10/28 HANDOFF 或旧 10/29 早报代替当前事实；所有仍存活进程与取消入口需在恢复说明中明确。 |

## 真实 episode 的不可混淆状态

下表来自服务器实际 `EPISODE_RESULT.json`、`FINAL_PUBLIC_PROJECTION.json` 和目录/账本核对，不是复述计划。

| episode | 执行状态 | 原生会话 | 科学范围与验收 |
|---|---|---:|---|
| E01 | `blocked`，exit 3 | 6 | baseline 成功、A2 验证失败；lock=null，无最终测试。失败保留，后续 v2 不能冒充其原始成功。 |
| E05 | `done`，exit 0 | 5 | validation/test 各 24 个 Q1 组合；Q2/Q3=0。源码、保存参数、报告、独立点估计与干净重放接受。 |
| E06 | `done`，exit 0 | 5 | validation/test 各 24 个 Q1 组合；Q2/Q3=0。独立收尾审查接受候选身份、报告和点估计；没有 E06 干净重放，不能套用 E05 的重放 accepted。 |
| E02–E04 | 未准入执行 | 0 | v1 首条失败后没有以配置代替执行。 |
| E07/E08 | 未启动 | 0 | 第二对保留为未做；不在上午收尾补跑。 |

E05/E06 的原始冻结分类头测试 BA 均为 0.569444。这是同一个固定模型/数据任务的基线指标，不是两名 Actor 科研质量相等或 skill 无效的统计证明。已有逐维比较显示预定正向描述性规则通过的测试组合为 1 与 5，但两者的探针选择和诊断随机化也不同，且仅一对、一个任务；不能由组合计数推断 skill 的因果收益。具体方法、全量组结果与成本边界见 [配对审计](E06_AND_PAIR_AUDIT.zh-CN.md)。

## wzf 复用的准确范围

当前是基于原导入源码的**维护修改版**：复用 `eegfm.driver.Driver.loop` 调度器及 run/state/attempt/jobs 的生命周期思想，在 `research_bench/driver_bridge.py` 中增加受信控制器、分析模式、一次性测试、委托审核与隔离 adapter。源码中 `BridgeDriver.loop()` 持有 episode 锁后明确调用 `super().loop()`；`real_episode.py` 实际构造 `EpisodeDriver` 并调用 `driver.loop()`。这不是绕开 driver 的独立 notebook，也不是原 wzf 不加改动就具备所有评测能力。

原导入 281 文件的来源说明、分发材料和 `fb6c37e` 来源快照保留；当前可发布 Git 是经过排除历史运行产物与参与者清单的源码集。团队上游仓库及其最新 revision 仍未核实，不能称为“已同步团队最新 wzf”。自己的 GitHub research 分支同步与团队上游同步是不同事项。[来源说明](../../source-import.md)

## 证据定位与审计范围

- 正式本地根：`X:/projects/EEG-AI-Scientist`；本地私有证据根分别为 `.local/research/2026-10-29-brainpec-real/` 与 `.local/research/2026-10-30-extension/`。公开报告不复制 EEG、参与者预测、模型权重、私有 gold 或原生对话。
- 服务器 WORK：`/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029`。核验了 `controller/BUDGET.json` 的现有记录、`episodes/E01|E05|E06/EPISODE_RESULT.json`、对应 `FINAL_PUBLIC_PROJECTION.json`、`replays/E05/REPLAY_AUDIT.json`、`evidence/ISOLATION_REPORT.json`、`evidence/full-linux-tests-04/`、`builders/semantic-calibration-v1/CALIBRATION_RESULT.json`。
- E01/E05/E06 实际结果文件 SHA-256 依次为 `7556c4ff51e08ed665c98f356e36ac3fd8764c38eb0d824189781dd4b0063815`、`1fd50406d3cd29d7b489d0434556a09a18a3d4b04f1cfd62c5e7eb9e707f4943`、`90a8344fa6d40c2c6987cd88055cb5f0eb079feb38bd5d12aaca614dd74ef14c`。
- 直接重算并核对 EEGMAT 与 EEGMMIDB `REFERENCE_TEST_RESULT.json` 的文件哈希，分别为 `57921432aa9ddbfc4252f0a97148bb957b786e88ac2bf6d767550ee32819fd18` 和 `0b7e87a2af5d776c2a1d94333bb37a84b243f96564d7985d471a417f5370e51d`，与各自公开报告一致。这里只核对保存文件，没有重跑模型或计算实验。
- 火山云自有根：`/home/duandh/projects/EEG-AI-Scientist-20261030`；源码 Git 在 `repository/`，先前接口验收源码在 `source/`，两者身份不混同。

这是需求与已有证据的一致性审计，不是全历史取证或对所有共享数据/系统文件的扫描。未访问认证与控制文件、未修改数据或共享文件、未复跑测试/实验。已保存测试、探针与核验记录只支持其明确覆盖的边界。

## 留到下一轮的工作

1. 先完成 E06 尚缺的干净重放及双方逐维证据比较；一对结果仍仅作单任务案例，不追认一般能力收益。
2. 将真实开发任务与未用于技能调整的新任务提前分开，再让隔离 Distiller 仅接收允许的 real-dev 轨迹；冻结新 skill 后再启动新任务的成对 Actor。EEGMMIDB 当前只有 Builder 参考与导出准备。
3. 若继续科学主线，优先让 Actor 实际完成 Q2/Q3 并检验残余恢复与匹配随机控制；后续独立任务验证优于在已见测试集上追加确认性措辞。
4. 需要 REVE 或云端科研时另定新协议、资源身份和 Actor 隔离；现有 CPU 合成验收不能替代这些准入条件。

上述均为剩余工作说明，本轮不启动。

## 主工作收尾补验

2026-10-30上午：当前中文入口、一页简报、详细报告、路径/恢复/改动/进程说明已经落盘；427文件私有归档在源端前后及本地逐成员校验通过，认证未打包。10:04:50的权威账本快照中C01/C02均终态且无reserved/running调用，两个本人工作区无匹配研究进程，记录的临时隧道已安全停止。随后另登记C03作最终文档审查，不是新科研；其终态单独记录。原始科研未完成项保持上表结论。最终代码同步另见SYNC_RECEIPT.json；收据生成前不提前称所有节点最新。

最终主工作补验：10:33已核对Windows、GitHub、nccserver0与火山云的35c7631内容提交一致，两服务器工作树干净；SYNC_RECEIPT.json记录各自现场时点与传输SHA。C03已完成、权威账本所有调用均终态；其四处措辞/舍入修正纳入随后的收尾提交。此前“最终同步另验”表格中的早期SHA仅为09:51快照，不再代表最新节点。原科研未完成项不因文档收尾而升级为完成。
