# 从这里看项目：先理解，再翻代码

更新：2026-11-01。当前研究已停止；本页是中文阅读入口，不是启动任务指令。

**我们搭了一套“让独立 AI 做 EEG 分析，再检查它做得怎样”的实验系统。真实任务上完成过一对无／有技能的比较，两者只完成属性恢复，没有证明技能有效。**

## 现在只需要三个入口

1. [Agent 实际收到的问题](framework/benchmarks/brainpec_real/TASK.md)：读前三段即可。Q1 读出属性；Q2 干预后看预测；Q3 看属性信息是否还残留。
2. [真实 EEG 参考结果](docs/research/2026-10-29-brainpec-real/SCIENCE_RESULT.zh-CN.md)：先看结果图；这是构建者参考，不是 Agent 成绩。历史五页演示的 HTML 入口目前缺失，仅两张图片和汇总 JSON 仍在原目录。
3. 想看真正写出的程序：VS Code 连 nccserver0，打开 `/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/episodes/E05/worker-evidence/real-E05-A2-test/candidate`。先读 `main.py`，它是无 skill 回合最终测试的候选入口，不是构建者参考程序。

不需要先读审计报告、哈希、JSON、旧计划。它们用于查证，不是入门教材。

## 文件夹不是一个“人”，也不是权限边界

| 位置 | 实际是什么 | 谁使用 |
|---|---|---|
| `framework/eegfm/` | Python 软件包；含原有调度、作业、状态与记忆管理代码 | 系统开发者；运行中的可信调度器 |
| `framework/eegfm/research_bench/` | 我们新增的评测代码；同时混有科学参考实现和数据适配，当前分层并不理想 | 构建者和可信执行层；不是整个暴露给 Actor |
| `framework/benchmarks/brainpec_real/` | 可重复使用的真实任务题面和接口模板 | 选中的文件会导出给 Actor |
| `framework/benchmarks/brainpec_pilot/` | 早期合成任务说明、评分政策与冻结 skill | 不同文件供不同角色；不能整体给 Actor |
| `framework/memory/` | wzf 来源中的共享经验条目 | 原框架的共享记忆机制；不是本轮自动学到的经验 |
| `.local/` | 未进入 Git 的本地材料：资源、私有参考、运行证据与备份等 | 按用途受限使用；不是无关文件，也不全是 Builder 私有答案 |
| `docs/` | 设计、历史报告、验收和恢复记录 | 开发与追溯 |
| `reports/` | 给人讲解的展示材料 | 你与合作者 |
| `archive/` | 原件、旧工程与恢复资料 | 需要追溯时才看 |

真正的 Actor 工作区在 nccserver0：`/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/cases/E05`（另一回合是 E06）。启动器只把允许的材料放入或挂载到沙箱中，并提供指定可写区域。目录叫 public/private 或被 Git 忽略，本身不会产生隔离。

## 当时是谁拆题，怎样选题？

M01 是构建侧的独立模型工作任务，负责阅读来源、组织问题树；不是受测 Actor。记录依据：旧预算账本的 M01 role=builder_research、kind=collaboration_subagent，以及树的 authoring 字段。当前对话属于构建侧协调角色，不等于全部文件都是此对话单独生成。

当时得到粗粒度树：12 节点、7 叶节点、3 候选（编码、预测依赖、表现恢复）。随后因资源条件，选择编码与依赖方向，并以 EEGMAT 做新配置。没有穷举所有问题，也没有独立专家确认这棵树。

- [原树](.local/overnight-20261029/private/reference/research_tree.json)：Builder 参考，包含来源信息，不给受测 Actor。
- [候选](.local/overnight-20261029/private/reference/candidate_slices.json)：`parent_node_id` 是给出较宽问题的父节点，`target_leaf_node_id` 是对应具体证据的叶节点，`public_question` 是拟给 Actor 的问题；`proposed_scope` 是拟定范围，`missing` 是缺少资源，`difference_from_paper` 是偏离原论文之处。候选不等于已运行。
- [真实资源改选记录](docs/research/2026-10-29-brainpec-real/TASK_SELECTION.md)。

## 术语与数字

- `binary y`：二分类标签数组，用 0/1 表示两类；这里是背景与心算。不是特殊算法。
- 只看第 6/12 层：预先限制的中间／末层分析范围；不等于遍历全部层，也不能声称找到全模型峰值层。lexicon 是属性目录，不是层数目录。
- 12 属性组、62 列：前 10 项逐通道计算后，各用跨通道的均值、标准差、中位数、25%分位数、75%分位数、最大值概括，得到 10×6=60 列；另两项通道相关性汇总各 1 列，共 62。代码见 `framework/eegfm/research_bench/real_data.py` 的 `compute_feature_panel`。
- M01/M15：旧夜间模型工作任务的预算编号，不是论文问题或网络层号。一个任务可能包含多次底层模型往返，不等于一个 HTTP 请求。M15 负责技能蒸馏。
- E01：旧协议真实 Agent 回合，未锁定、未最终测试，失败保留。
- E02–E04：旧协议预先安排，未启动。
- E05/E06：新协议真正运行的无 skill／固定 skill 对照；均只完成 Q1。
- E07/E08：预定第二对，未运行。

## Skill 与 memory 不相同

M15 skill 是从一个合成开发回合提炼出的实验方法提醒：先弄清要证明什么；用合适对照；不把读得出、预测会变、生理因果混为一谈；报告不确定性并保留证据。它没有修改模型权重，也没有被全局安装。只有指定处理组收到固定正文。

wzf 的 memory 则保存具体事实和踩坑记录，分任务记忆和共享记忆。当前共享索引与来源归档完全相同，含 REVE/ISA、数据集和旧环境经验。旧机器网络等条目不代表我们当前环境有效。它们不应自动提供给受测 Actor，也不需要你现在通读。

## 代码阅读不要混淆作者

- Builder 的岭回归示范：`framework/eegfm/research_bench/real_science.py` → `fit_probe`。
- Builder 的参考流程：同目录 `real_reference.py`。
- 可信统计汇总：同目录 `real_aggregate.py`。
- 调度接线：同目录 `driver_bridge.py`。
- Actor 实际候选：上文服务器 E05/E06 的 `candidate/`，不能用 Builder 代码冒充。

## 目录整理的真实状态

本次简化的是阅读入口，没有搬移旧证据或重构代码。不是所有散落报告都必须永久保持现在的呈现方式。当前确实存在通用评测、BrainPEC 专用适配、参考算法混在一个包的问题；`real_*` 名称也过泛。

后续代码整理应区分“通用评测基础设施、具体任务适配、Builder参考方法、运行产物”，但迁移需要兼顾 Python 导入、冻结代码身份和已有绝对路径。不能只改文件夹名就宣称分层完成。原始历史可以归档保留，人类入口无需列出所有审计文件。

## 需要核查时再打开

- [运行完成范围](docs/research/2026-10-30-extension/COMPLETION_AUDIT.zh-CN.md)
- [Skill 来源](framework/benchmarks/brainpec_pilot/skills/distinguish-recovery-response-and-causation/PROVENANCE.json)
- [机器与目录详细映射](docs/research/2026-10-30-extension/PATH_MAP.md)
- [完整结果审计](docs/research/2026-10-30-extension/E06_AND_PAIR_AUDIT.zh-CN.md)
- [恢复说明](docs/research/2026-10-30-extension/RESUME.md)
