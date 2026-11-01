# PROGRAM.md：EEG 基础模型研究程序

适用于所有 EEG FM 研究任务（后训练方法、适配、下游迁移、预处理、评估协议……）。具体任务的目标、数据、可改文件和预算写在 `tasks/<task>/TASK.md` 与 `task.yaml`。本文件写"怎么做研究"；不要为某个任务改它。

命令都通过 `bin/eegfm` 执行，`<run>` 是运行 ID（也在环境变量 `EEGFM_RUN` 里）。`bin/eegfm <group> --help` 可查看参数。

---

## 1. 每次唤醒的流程（必须按顺序）

1. 读 `AGENTS.md`、本文件、`tasks/<task>/TASK.md`。
2. 读 `knowledge/INDEX.md`，按需要打开其中的文档（第一次进入任务时，读完与任务相关的全部条目）。
3. 读 `memory/INDEX.md`（共享记忆）与 `tasks/<task>/memory/INDEX.md`（任务记忆）。
4. 读 `runs/<run>/STATE.json`、`runs/<run>/NOTES.md`（若存在）、`runs/<run>/RESEARCH_BRIEF.md`（若存在）。
5. 读 `runs/<run>/attempts/INDEX.md` 的**全部**行；对正在决策的分支，打开每个相关 attempt 的 `proposal.md`、`eval/score.json` 与 `eval/error.txt`。**相信实测结果，不相信提案对自己的描述。**
6. 根据 `STATE.json` 的 `status` 进入对应阶段：

| status | 你要做的 |
|---|---|
| `brief` | 第 2 节：写或修改研究 brief（若被驳回，`note` 里有审阅意见） |
| `working` | 若 `note` 说作业已结束：先 `bin/eegfm eval collect <run> <A#>`。然后按阶段继续：未冻结→第 3 节；无 baseline→第 4 节；否则第 5 节；预算或轮数已满→第 9 节 |
| `waiting_job` / `awaiting_review` / `done` / `blocked` | 正常情况下不会被唤醒；若被唤醒，只检查状态、补 NOTES，然后结束 |

7. 会话结束前：在 `NOTES.md` 末尾追加本次会话记录（第 11 节），并用 `bin/eegfm state set` 写明状态。

一次会话可以完成多个步骤（例如：收集结果 → 判定 → 提出并提交下一个 attempt）。**作业运行超过几分钟就不要在会话里等**：提交后 `state set --status waiting_job --job <id> ...`，结束会话，续接器会在作业结束后叫醒你。

---

## 2. 研究 brief（任务开始时，人工审阅一次）

目的：在花 GPU 之前，把科学问题想清楚，并把领域已有知识落到纸面上。

1. 读完知识库中与任务相关的全部文档、两层记忆、以及 TASK.md 列出的历史材料。
2. 用你自带的网页检索做**有限的**文献调研（Codex：web search；Claude Code：WebSearch/WebFetch）。优先：原始论文、官方代码仓库、作者报告。每条外部论断记下来源（arXiv ID / DOI / URL）与访问日期。
3. 按 `templates/RESEARCH_BRIEF.md` 写 `runs/<run>/RESEARCH_BRIEF.md`：
   - 问题定义与成功标准（与 TASK.md 一致，不擅自放宽）；
   - **我们自己的实测事实**与**论文中的说法**分两节写，不混用；
   - 3～6 个候选假设（每个：理由、预期效果、可证伪的反向结果、风险、所需成本），**作为选项而不是指令**；
   - 已知未知、可能的混杂因素、对评估协议的风险。
4. `bin/eegfm brief submit <run>`，结束会话。人会用 `bin/eegfm brief approve` 或 `reject --note` 回应；被驳回时按意见修改后再次提交。
5. 若 `tasks/<task>/RESEARCH_BRIEF.md` 已有批准过的 brief，运行会直接从 `working` 开始；先读它，再决定是否需要补充（补充写进 NOTES，不改已批准版本）。

**重新调研**：同一假设族连续 `task.yaml: research.resurvey_after_stalled` 次 attempt 的 validation 没有超过当前最优时，可以做一次有限检索，把新发现追加到 `RESEARCH_BRIEF.md` 末尾的"补充调研"一节（注明日期与触发原因），不改动已批准内容。

---

## 3. Setup：数据、模型、评估器（冻结前）

目的：建立一个**可信、可重复、之后不再改动**的评估入口。setup 阶段的 attempt 用 `--kind setup`，不计入科研轮次。

1. 核实数据：路径、版本、样本数、通道、采样率、标签含义、划分清单。与 `registry/` 和 TASK.md 对照；不一致时以实际文件为准，写进 NOTES，并考虑写成记忆（第 8 节）。
2. 核实模型权重能真实加载（禁止权重缺失时静默随机初始化）。
3. 按 TASK.md 的"评估契约"实现或核对评估入口（`task.yaml: evaluation.val_command / test_command`）：
   - 每个分片（`evaluation.shards`，通常一个数据集一个）写 `{out}/metrics.json`，其中必须包含主指标 `evaluation.metric`（数值）；
   - **validation 输出里不得出现任何 test 数值或以 test 命名的键**；
   - test 命令只在锁定候选后使用（第 7 节）；
   - 记录随机种子、划分种子、选 epoch 的规则（只按 validation）。
4. 用一个小规模 smoke（少量 epoch / 少量数据）验证整条链能产出 `metrics.json`。setup attempt 可以通过 `eval submit` 提交，也可以本地直接跑。
5. 确认无误后：`bin/eegfm freeze <run> --note "<冻结了什么、为什么可信>"`。冻结后 `source.frozen` 的文件被哈希锁定，之后只能改 `source.editable`。**评估器有错只能开新 run**，不能就地修。

---

## 4. Baseline

1. `bin/eegfm attempt new <run> --kind baseline --title "..."`，在 `proposal.md` 写明 baseline 的确切配置。
2. 不改动任何可编辑文件（或按 TASK.md 的 baseline 定义设置），`bin/eegfm eval submit <run> <A#> --phase val`。
3. 作业结束后 `eval collect`；baseline 失败不算研究结果，修好 setup 后重来（冻结前发现问题→仍可修；冻结后发现评估器问题→开新 run）。
4. 若 TASK.md 指出已有可复用的 baseline 产物，只有在数据、划分、权重、评估代码完全一致并有哈希证据时才能复用；否则重跑。

---

## 5. 迭代：一个 attempt 的完整协议

1. **选父节点**（第 6 节的探索策略）。需要从某个旧 attempt 的代码出发时：`bin/eegfm workspace checkout <run> <父A#>`。
2. `bin/eegfm attempt new <run> --kind iteration --parent <父A#> --title "..." --hypothesis "..."`。
3. 在 `attempts/<A#>/proposal.md` 写：假设、具体改动、保留不变的部分、预期结果、**反向结果意味着什么**、成本估计、依据（引用 brief 的假设编号、记忆条目 ID、attempt ID）。
4. 修改 `runs/<run>/workspace/` 中允许的文件。能本地快速检查的先检查（语法、形状、一个 batch 的 loss/梯度）。
5. `bin/eegfm eval submit <run> <A#> --phase val`，然后 `bin/eegfm state set <run> --status waiting_job --job <id> ...`（列出全部分片 job），结束会话。
6. 被叫醒后：`bin/eegfm eval collect <run> <A#>`。
   - `evaluated`：逐分片看 `eval/score.json` 与相对 baseline / 父节点的变化；看训练诊断（loss、梯度、收敛、耗时）。
   - `failed`：读 `eval/error.txt` 与作业日志，判断是代码问题（→ 新的 debug attempt，父节点为它）还是基础设施问题（→ 同一代码新 attempt 重新提交，写明原因）。
7. `bin/eegfm attempt verdict <run> <A#> --keep|--discard --reason "..."`：
   - **keep**：主指标优于当前最优，且没有明显的有效性问题（例如某个分片崩溃、训练未收敛）；
   - **discard**：不优于当前最优、或结论不可信。
8. 把能复用的事实/坑写进记忆（第 8 节），在 NOTES 记下决定与理由。

**有效科研轮次**：冻结之后、`kind=iteration`、validation 评估成功的 attempt 才算。失败、smoke、setup、baseline、重复提交都不算。

---

## 6. 探索策略（当前为固定策略）

- **前沿**：当前最优的 keep 节点；默认从它出发做 improve。
- **debug**：失败的 attempt 最多连续 debug `task.yaml: search.max_debug_depth` 次（默认 2），超过就放弃这条路径并记录原因。
- **换方向**：同一假设族连续 `search.patience`（默认 3）次没有超过前沿，就换 brief 里的另一个假设族，或触发重新调研（第 2 节）。
- **多样性**：不要只做同一方向的小步调参；有依据时可以从较早的节点或 baseline 开新分支。
- **预算**：每次提交前看 `task.yaml: search.max_attempts` 与 GPU 小时上限，剩余预算不足以完成一次完整评估时进入第 9 节。

> Dream-RSI 式的"用历史回放离线改进探索策略"目前**关闭**（`task.yaml: search.exploration_policy: static`）。现阶段只需把每次选择父节点、换方向、停止的理由写进 NOTES，作为以后开启该功能的历史数据。

---

## 7. 评估与 test 隔离

**test** 是每个数据集划分中的测试部分（例如每个目标数据集各折的 test 被试）。规则：

1. 选方法、调超参、选 epoch、keep/discard、写记忆——全部只用 validation。
2. 不读 `runs/<run>/sealed/`，不自己写代码计算 test 指标，不在 NOTES、brief、记忆里写本次运行的 test 数字。
3. 收尾时：`bin/eegfm lock <run> <A#> --reason "..."` 锁定候选（通常是 baseline 和最终选中的 attempt），再 `bin/eegfm eval submit <run> <A#> --phase test`。每个候选只能跑一次 test，总数受 `evaluation.test.max_candidates` 限制。
4. 全部 test 作业结束后，`bin/eegfm report final <run>` 才会解封结果。解封后**不能再改候选选择**。
5. 开发阶段想要更稳健的估计：只在 **train+val 内部**轮换验证划分的种子（若 TASK.md 允许），并在同一种子上与 baseline 做配对比较；**test 划分保持固定**。最终若想报告多划分的稳健性，在锁定之后再做，不参与选择。
6. 数据层面的泄漏同样禁止：LODO 中目标数据集不得进入后训练；跨被试设定中 test 被试不得进入训练；归一化统计、通道选择等不得在 test 上拟合。
7. 若发现 test 信息已经进入决策，立刻在 NOTES 和最终报告中标注"test 污染"，结论降级为开发性结果。

工具层面：`eval submit --phase test` 要求先锁定；所有评估请求写入 `audit.jsonl`；冻结文件每次评估前都校验哈希。由于 agent 与工具以同一系统用户运行，这是**流程与审计层面**的隔离；需要硬隔离的任务应让 test 标签只存在于计算作业内部（在 TASK.md 中说明）。

---

## 8. 记忆：两层，带筛选

| 层 | 位置 | 写什么 |
|---|---|---|
| 任务记忆 | `tasks/<task>/memory/` | 与本科学问题相关的发现与坑（方法在哪些数据集上有效/失效、敏感超参、失败模式） |
| 共享记忆 | `memory/` | 跨任务成立的事实：数据集性质、模型加载与输入格式、协议陷阱、基础设施经验 |

写入：`bin/eegfm memory add --task <task> --run <run> --kind fact|pitfall|observation --applies <scope> --evidence <ref> --claim "..."`

- `--applies` 必须是 `dataset:<名>`、`model:<名>`、`protocol:<名>`、`infra:<名>`、`domain:<主题>` 或 `method:<名>`；可重复。
- `--evidence` 必须指向证据：`run:<run>/attempt:<A#>`、`doc:<路径>`、`url:<链接>`；可重复。
- **只写事实、坑和观察，不写"下一步应该尝试什么"**——方向性建议会把后续搜索限制住（Dream-RSI §5.1 的实验结论）。方向写在 brief 的假设里。
- 运行未结束时，不得写入本次运行的 test 结果。
- 新证据与已有条目矛盾时：`bin/eegfm memory dispute --task <task> <ID> --evidence <ref> --note "..."`，不要删除或覆盖。

晋升（收尾时做一次，第 9 节）：`bin/eegfm memory promote --task <task> <ID> [--confirmed-by <另一个任务>]`。工具只允许以下条目进入共享记忆：适用范围是数据集/模型/协议/基础设施/领域（不是某个方法），并且要么是有文档或链接来源的客观事实，要么已被至少两个任务确认。

---

## 9. 收尾

触发条件（满足任一）：达到 `search.min_valid_rounds` 且没有更有希望的分支；`search.max_attempts` 或 GPU 预算用完；TASK.md 的结束条件满足。

1. 选定最终候选：按 validation 主指标与有效性，**不看 test**。在 NOTES 写明选择理由。
2. `bin/eegfm lock` baseline 与最终候选 → `eval submit --phase test` → `state set --status waiting_job --job ...` → 结束会话。
3. 被叫醒后：`bin/eegfm eval collect` 各候选 → `bin/eegfm report final <run>`。
4. 按 `templates/FINAL_REPORT.md` 写 `runs/<run>/FINAL_REPORT.md`：问题、方法、每个有效轮次、最终候选、validation 与 test 结果（逐分片、均值、变化）、流程是否符合协议、性能是否达成目标（两者分开判断）、负结果如实写、局限与证据边界。
5. 记忆整理：检查本次写入的任务记忆，按第 8 节晋升符合条件的条目；此时可以把最终 test 结论写入任务记忆（注明"已解封"）。
6. `bin/eegfm state set <run> --status done --note "<一句话结论>"`。

---

## 10. 失败处理（不要停下来问人）

| 情况 | 处理 |
|---|---|
| 评估作业失败 | 看 `eval/error.txt` 和作业日志 → 代码错误：新 debug attempt；资源/网络/抢占：同代码新 attempt 重新提交，NOTES 记原因 |
| 作业长时间无进展 | `bin/eegfm job status` 查看；确认卡死后 `bin/eegfm job stop`，按上一行处理 |
| 工具报错（例如改了冻结文件、越界修改） | 按报错恢复文件，不要绕过工具 |
| 数据或权重与预期不符 | 冻结前：修 setup 并记录；冻结后：在 NOTES 标注影响范围，必要时以 blocked 说明需要新 run |
| 需要凭据、额度、授权等只有人能解决的事 | `bin/eegfm state set <run> --status blocked --note "<确切原因与需要的操作>"` |

---

## 11. NOTES.md：会话日志

`runs/<run>/NOTES.md` 是给下一次会话（可能是另一个 agent）的交接。每次会话结束前在末尾追加：

```
## <UTC 时间> <agent 名称>
- 做了什么：…
- 决定与理由：…（父节点选择、keep/discard、换方向、停止）
- 未决问题与不确定性：…
- 下一步：…
```

只追加，不改写历史条目。

---

## 12. 计算与存储

- 计算后端由 `task.yaml: compute.backend` 决定（`tione` 或 `local`），通过 `bin/eegfm eval submit` 使用；TiONE 任务提交后由工具自动登记到 `/mnt/cfs-omni/wzf/.volcengine/`。
- 不要自行绕过工具直接提交 GPU 作业；需要额外的诊断作业时，在 NOTES 说明并作为 setup/iteration attempt 的一部分提交。
- 临时文件：`/omni-eeg-00/home/wzf/scratch/eeg-fm-research/<run>/`，进程启动前设置 `TMPDIR/TMP/TEMP`；可复用缓存：`/omni-eeg-00/home/wzf/cache/eeg-fm-research/`；新的持久数据集与预处理产物：对象存储。
- 大的检查点与产物放在作业输出目录（`{out}` 之下或 TASK.md 指定的结果目录），不要放进 `workspace/`。
