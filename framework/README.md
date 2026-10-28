# eeg-fm-research：markdown 驱动的 EEG 基础模型自动研究程序

让一个编码 agent（Claude Code 或 Codex）**自主完成一整轮 EEG 基础模型（EEG FM）研究**：写研究 brief → 人审阅一次 → 搭建并冻结评估器 → 跑 baseline → 多轮"改代码/参数 → 评估 → 保留或丢弃" → 锁定候选并做一次 test → 写最终报告 → 整理经验记忆。

研究本身由 agent 完成。本仓库提供三样东西：

1. **规则文档**（`AGENTS.md`、`PROGRAM.md`、`tasks/<task>/TASK.md`）：告诉 agent 怎么做研究；
2. **工具 `bin/eegfm`**：记录状态和尝试，提交与收集评估，冻结评估器，封存 test，管理记忆；
3. **续接器 `eegfm/driver.py`**：agent 会话结束、断线或需要等待作业时，在合适的时间把 agent 重新拉起。

---

## 1. 为什么这样设计

之前的方案是一个约 16k 行的多角色控制器（Scientist / Engineer / Reviewer / Executor / BugFix 之间轮流交接，约 30 个审批出口）。它在 10 天里的 4 次真实运行都没有跑完闭环，每次都停在不同的出口上等人。

业内能稳定无人值守运行的系统（Karpathy autoresearch、Meta AIRA-dojo、AlphaEvolve、Sakana AI Scientist-v2）结构都很相似：

- 一个 agent 连续工作；
- 评估器固定，agent 改不了；
- 失败也作为一条结果记录下来，而不是停下；
- 状态都存在文件里。

本仓库就是按这个结构做的，同时保留了旧方案中有价值的部分：test 隔离、冻结评估、TiONE 计算账本、两层记忆。

| 机制 | 来源 |
|---|---|
| keep/discard 迭代，评估代码不可改 | Karpathy autoresearch |
| draft / improve / debug，按 validation 选择，警惕验证集过拟合 | AIDE / Meta AIRA-dojo |
| 每次唤醒完整读历史尝试；记忆只记事实，不写"该往哪走" | Dream-RSI（arXiv 2609.14858）§5.1 的结论；其策略回放功能暂未启用 |
| 追加写的事件日志，按文件状态续跑 | DeepSeek Harness 的 session log 思路 |

---

## 2. 目录

```
AGENTS.md            agent 入口（不可违反的规则）；CLAUDE.md 只有一行 @AGENTS.md，两种 agent 读同一份
PROGRAM.md           通用研究流程（所有任务共用）：唤醒流程、brief、setup/冻结、baseline、迭代、探索策略、
                     test 隔离、记忆、收尾、失败处理、NOTES、计算与存储
README.md            本文件
bin/eegfm            命令行入口（agent 与人共用）
eegfm/               工具实现
  state.py           运行状态 STATE.json 与状态转移规则
  attempts.py        run 初始化、attempt 记录（发现树）、attempts/INDEX.md
  evaluation.py      冻结、分片评估提交/收集、候选锁定、test 封存与解封、审计
  jobs.py            计算后端：local（后台进程）与 tione（腾讯 TiONE）
  memory.py          两层记忆：写入校验、晋升筛选、争议标记、索引
  driver.py          续接器与 agent 适配器（claude / codex / script）
  cli.py             命令解析
templates/           RESEARCH_BRIEF.md、proposal.md、FINAL_REPORT.md、memory_item.md
knowledge/           有出处的领域知识（数据集、协议、模型、历史结果、基础设施、方法论）
memory/              跨任务共享记忆（items/*.md + INDEX.md）
registry/            datasets.yaml、models.yaml、protocols.yaml
tasks/
  synthetic_demo/    本地合成任务（几秒一次评估），用于验证流程
  reve_isa/          第一个正式任务：REVE × stimulus ISA，6 个情绪数据集，LODO
examples/
  demo_claude_001/   一次真实 Claude Code 运行的完整产物（synthetic_demo）
tests/               离线测试（脚本化 agent，不调用 LLM，不提交 GPU）
runs/                运行目录（不进 git）
```

---

## 3. 工作方式

```
              ┌──────────────── driver.py（续接器，常驻后台） ────────────────┐
              │ 读 runs/<run>/STATE.json，决定：                               │
              │   brief / working   → 启动一次 agent 会话（固定提示词）        │
              │   waiting_job       → 自己轮询作业，不占用 agent；结束后转 working│
              │   awaiting_review   → 等人审阅 brief（写 ATTENTION.md）        │
              │   blocked / done    → 停止（blocked 写明原因）                 │
              └───────────────────────────────┬───────────────────────────────┘
                                              │ claude -p … / codex exec …
                                              ▼
   agent：读 AGENTS.md → PROGRAM.md → TASK.md → 知识库与记忆 → 本 run 的状态与全部尝试
          → 做一步或多步研究（只通过 bin/eegfm 提交评估、记录结果）
          → 更新 STATE（waiting_job / awaiting_review / done / blocked），结束会话
```

**一个 run 的生命周期**

1. `brief`：agent 读知识库和记忆，必要时做网页检索，写 `RESEARCH_BRIEF.md`（事实和文献分开写，假设作为选项），然后提交审阅。
2. `awaiting_review`：**唯一的人工节点**。人批准或驳回（驳回时附意见）。
3. setup：核实数据和权重，实现或核对评估入口，跑 smoke，然后 `eegfm freeze`。冻结后评估器文件被哈希锁定。
4. baseline：用 `--kind baseline` 跑一次。
5. 迭代：每个 attempt 写提案（假设、改动、预期、反向结果的含义）→ 改可编辑文件 → `eval submit` → 状态设为 `waiting_job` 并结束会话 → 被叫醒后 `eval collect` → 判定 keep/discard → 写记忆和 NOTES。
6. 收尾：按 validation 选出最终候选 → 锁定（baseline + 最终候选）→ 每个候选跑一次 test → `report final` 解封 → 写最终报告 → 晋升记忆 → `done`。

**故障时续接器怎么处理**

| 情况 | 处理 |
|---|---|
| agent 后端过载、限流、网络错误、会话超时 | 退避重试（60 s 起，封顶 900 s），超过 6 小时窗口则标记 blocked |
| 认证失败 | 立即 blocked，写明原因 |
| 其他失败，或会话结束后什么都没改变 | 计为"无进展"，连续 `--stall-limit` 次后 blocked |
| 续接器进程被杀 | 重新 `start` 即可，从文件状态继续，不会重复提交 |
| agent 发现只有人能解决的问题（例如工具 bug、凭据） | agent 自己设为 blocked 并写明原因与建议（真实运行中发生过，见 §8） |

---

## 4. 环境要求

本仓库目前在腾讯云 notebook（`/mnt/cfs-omni/wzf/auto research/eeg-fm-research`）上开发和运行，以下路径都是这台机器上的路径：

- Python 3.10+，依赖：`PyYAML`（测试另需 `pytest`）；TiONE 后端需要 notebook 环境中的 `tikit`。
- Agent CLI：`claude`（Claude Code 2.x）和/或 `codex`（codex-cli 0.15x），已登录。
- 网络：这台机器不能直连外网，agent 与网页检索要走代理 `HTTP(S)_PROXY=http://127.0.0.1:17897`。
- TiONE（仅 `compute.backend: tione` 的任务需要）：复用 `/mnt/cfs-omni/wzf/iclr2027/experiments/3stage/scripts/tione/submit_full_npd_70gpu.py` 的配置与 STS 凭据；每个新任务会自动用 `/mnt/cfs-omni/wzf/.volcengine/record_job.py` 登记。
- 存储约定（见 `/mnt/cfs-omni/wzf/AGENTS.md`）：
  - 临时文件放 `/omni-eeg-00/home/wzf/scratch/eeg-fm-research/<run>/`；
  - 缓存放 `/omni-eeg-00/home/wzf/cache/eeg-fm-research/`；
  - 新的持久数据放对象存储 `/mnt/omni-eeg-01/...`；
  - 不要往 `/tmp`、`/dev/shm` 写大文件。
- REVE 任务所需的数据与权重：`/mnt/omni-eeg-01/downstream_preprocess/wzf_dataset`、`/mnt/omni-eeg-01/cx/EEG_FM/baseline/REVE/weights`（见 `registry/`）。

换机器使用时，需要改 `registry/*.yaml`、`knowledge/*`、`tasks/reve_isa/task.yaml` 中的路径，以及 `eegfm/jobs.py` 顶部的 TiONE helper 和 `record_job.py` 路径。

---

## 5. 快速开始

### 5.1 离线自检（不调 LLM，不用 GPU，约 1 分钟）

```bash
cd "/mnt/cfs-omni/wzf/auto research/eeg-fm-research"
TMPDIR=/omni-eeg-00/home/wzf/scratch/eeg-fm-research/tests python3 -m pytest -q tests/
```

### 5.2 用真实 agent 跑合成任务（约 20 分钟，几美元）

```bash
cd "/mnt/cfs-omni/wzf/auto research/eeg-fm-research"
export HTTP_PROXY=http://127.0.0.1:17897 HTTPS_PROXY=http://127.0.0.1:17897
RUN=demo_$(date +%m%d_%H%M); export TMPDIR=/omni-eeg-00/home/wzf/scratch/eeg-fm-research/$RUN; mkdir -p "$TMPDIR"

bin/eegfm run init --task synthetic_demo --run-id $RUN
python3 -B -m eegfm.driver start --run $RUN --agent claude --poll 15 --session-timeout 1800
# 或：--agent codex [--model <模型>]

# 几分钟后会停在 brief 审阅：
cat runs/$RUN/ATTENTION.md
cat runs/$RUN/RESEARCH_BRIEF.md
bin/eegfm brief approve $RUN --note "ok"
```

> 续接器在等待审阅时会持续轮询，批准后自动继续；如果它已经退出（例如用了 `--once`），重新执行上面的 `start` 即可。

### 5.3 开跑前自检

```bash
bin/eegfm preflight --agent codex --task reve_isa          # CLI 与登录、代理、可写目录、数据与权重、TiONE（只读）
bin/eegfm preflight --agent codex --task reve_isa --live   # 再加一次极小的真实 agent 会话（沙箱、联网、写权限）
```

### 5.4 正式任务（REVE × ISA）

**用 Codex 跑 REVE 请按 `RUNBOOK_REVE_CODEX.md` 操作。**

```bash
bin/eegfm run init --task reve_isa --run-id reve_isa_001
python3 -B -m eegfm.driver start --run reve_isa_001 --agent claude --poll 60
```

brief 阶段不使用 GPU。setup 阶段 agent 需要实现 `src/run_eval.py`（契约见 `tasks/reve_isa/TASK.md` §5），并在 TiONE 上跑 smoke，**从这一步开始产生 GPU 费用**。一次完整评估约 8 小时（6 个目标并行，每个 6 GPU）。

---

## 6. 人需要做的事

| 时机 | 命令 |
|---|---|
| 审阅 brief | `bin/eegfm brief approve <run> --note "…"`（批准后同时保存为该任务的标准 brief）/ `bin/eegfm brief reject <run> --note "修改意见"` |
| run 被 blocked | 读 `runs/<run>/ATTENTION.md` 和 `STATE.json` 的 note，处理后执行 `bin/eegfm state set <run> --status working --note "已处理：…"`，再 `driver start` |
| 停止 | `kill <runs/<run>/driver.json 中的 pid>`；已提交的作业不受影响 |
| 切换 agent | 停止后用另一个 `--agent` 重新 `start` |

**查看进度**

```bash
bin/eegfm status <run>           # 状态、尝试统计、是否已冻结、锁定的候选、最近事件
bin/eegfm attempt list <run>     # 全部尝试的表（只含 validation）
cat runs/<run>/NOTES.md          # agent 每次会话的交接记录
bin/eegfm job list <run>
tail runs/<run>/sessions.jsonl   # 每次会话：耗时、是否有进展、错误类型、费用
```

---

## 7. 关键机制

### 7.1 冻结评估器与可编辑范围

`task.yaml` 中：
- `source.frozen`：`eegfm freeze` 时计算哈希，之后每次评估前都会校验；
- `source.editable`：冻结之后只允许改这些文件。

工具会拒绝以下情况：评估器被改动；冻结后改动了可编辑范围以外的文件；`task.yaml` 在 run 开始后被修改。评估器有错时只能开新 run。

### 7.2 分片评估

`evaluation.shards`（例如一个数据集一个分片）：一次 `eval submit` 为每个分片提交一个作业，命令中的 `{shard}`、`{out}`、`{val_out}`、`{code}` 等占位符会被替换并加引号。每个分片写 `{out}/metrics.json`，必须包含主指标 `evaluation.metric`；attempt 的主分数是各分片的均值。

### 7.3 test 隔离

test 指的是每个数据集划分里的测试部分。规则如下：
- 所有决策只看 validation；
- validation 输出里出现任何以 test 命名的键，该 attempt 直接判为失败；
- test 只能对锁定的候选（`eegfm lock`）跑**一次**，总数受 `evaluation.test.max_candidates` 限制；
- test 结果写到 `runs/<run>/sealed/`，`eegfm report final` 之后才汇总出来；
- 锁定、提交、解封都写入 `audit.jsonl`。

**限制**：agent 和工具以同一个系统用户运行，所以这是工具和审计层面的隔离，而不是操作系统层面的隔离。需要硬隔离的任务，应让 test 标签只存在于计算作业内部。

### 7.4 两层记忆

- 任务记忆：`tasks/<task>/memory/`；共享记忆：`memory/`。每条是一个带 YAML 头的 markdown 文件。
- 写入时工具会检查：
  - 必须有证据（`run:<run>/attempt:<A#>`、`doc:<路径>` 或 `url:<链接>`）；
  - 适用范围必须带前缀（`dataset:` / `model:` / `protocol:` / `infra:` / `domain:` / `method:`）；
  - 不能写"下一步应该尝试…"这类方向性建议；
  - run 结束前不能写入本次运行的 test 数字。
- 晋升为共享记忆需要同时满足：适用范围不是某个具体方法；并且要么是有文档或链接出处的事实或坑，要么已被至少两个任务确认。
- 新证据与旧条目矛盾时用 `memory dispute` 标记，不删除。

### 7.5 知识库

`knowledge/INDEX.md` 列出全部文档，每篇都写明来源和核实日期。agent 在任务开始时阅读；运行中学到的东西写进记忆，不写进知识库。`knowledge/SOURCES.md` 里有待补充的清单。

---

## 8. 验证记录（2026-10-21）

- **离线测试 10 个全部通过**（数据路径故意含空格）：
  - 完整闭环；
  - 续接器被杀后续跑，没有重复的 attempt；
  - 后端过载时退避重试；
  - 会话没有进展、agent 崩溃时都会被标记 blocked；
  - 冻结与可编辑范围的检查；
  - test 必须先锁定、每个候选只能跑一次；
  - validation 输出含 test 键时判为失败；
  - 评估崩溃记为失败的 attempt；
  - 记忆规则与晋升筛选。
- **真实 Claude Code 运行**（`examples/demo_claude_001`，synthetic_demo）：共 3 次会话，约 7.2 美元。
  1. 写 brief 并提交审阅（2 分钟）；
  2. setup 时发现工具的 bug：项目路径 `auto research` 含空格，评估命令的路径没有加引号。agent 没有越权修改工具，而是把 run 设为 blocked，指出了具体代码位置和三种修复方案；
  3. 修复后续跑：冻结 → baseline → 4 个有效迭代（3 次保留、1 次丢弃）→ 锁定 2 个候选 → test → 解封 → 最终报告 → 记忆。
  - 审计日志显示顺序正确：先锁定再跑 test，解封在最后。最终候选只按 validation 选出（validation 47.37 vs baseline 44.44；test 47.03 vs 44.61），报告中如实写出了 dsB 在 test 上下降 9.85。

---

## 9. 接入一个新任务

1. 新建 `tasks/<task>/`：
   - `src/`：实验代码，会被复制进每个 run 的 `workspace/`，并在其中用 git 管理；
   - `task.yaml`：字段见下表，可参考 `tasks/reve_isa/task.yaml`；
   - `TASK.md`：科学问题、成功标准、固定不变的部分、可研究的范围与参数边界、评估契约、baseline 定义、轮次与预算；
   - `memory/items/`：空目录，之后执行 `bin/eegfm memory index --task <task>`。
2. 需要时补充 `registry/` 和 `knowledge/`（写明出处）。
3. 先用 `--agent script` 或 synthetic_demo 熟悉流程，再启动真实 agent。

`task.yaml` 字段：

| 字段 | 含义 |
|---|---|
| `source.root / include / exclude` | 代码来源与复制范围 |
| `source.editable` | 冻结后 agent 可以改的文件（glob） |
| `source.frozen` | 冻结时计算哈希的评估器文件（glob） |
| `evaluation.val_command / test_command` | 评估命令；占位符 `{shard} {out} {val_out} {code} {attempt} {phase} {run}` |
| `evaluation.shards` | 分片列表（可省略，表示只有一个作业） |
| `evaluation.metric / direction` | 主指标键名；maximize 或 minimize |
| `evaluation.test.max_candidates` | 最多几个候选可以跑 test |
| `compute.backend` | `local` 或 `tione`；tione 还需要 `gpus_per_job`、`gpu_type`、`extra_cosfs_mounts` 等 |
| `search.min_valid_rounds / max_attempts / max_debug_depth / patience / gpu_hours_budget` | 轮次、预算与探索策略参数（PROGRAM.md §6） |
| `search.exploration_policy` | 目前只有 `static`（Dream-RSI 回放关闭） |
| `research.web_search / resurvey_after_stalled` | 是否做网页调研；连续几次没有提升后重新调研 |
| `review.brief_requires_approval` | brief 是否需要人工审阅 |

---

## 10. 当前状态与待办

- [x] 通用程序、工具、续接器、两层记忆、知识库、合成任务；离线测试与真实 Claude Code 闭环。
- [x] **Codex** 适配器真实自检通过（`preflight --live`，默认模型 `gpt-6-astra`）：沙箱内可运行 `bin/eegfm`、写 run 与 scratch 目录、联网。尚未用 Codex 跑过完整任务。
- [ ] **TiONE 凭据**：提交依赖 notebook 容器注入的 `QCLOUD_CONTAINER_INSTANCE_CREDENTIALS_URL`，SSH / VS Code 远程会话里没有这个变量，需要从 notebook 网页终端启动（见 RUNBOOK §1）。
- [ ] **REVE × ISA**：任务定义、核心代码、知识与记忆都已就绪；`src/run_eval.py` 需要 agent 在 setup 阶段实现；**TiONE 后端尚未真实提交过作业**，需要在第一次 setup smoke 时验证。
- [ ] 知识库待补：论文清单与笔记、数据下载和预处理流程说明、`Emoposttrain` 项目摘要、其他 EEG FM 模型卡片（见 `knowledge/SOURCES.md`）。
- [ ] 探索策略回放（Dream-RSI）：等积累了多个任务的尝试历史之后再开启。
- 已知限制：
  - test 隔离是工具和审计层面的，不是操作系统层面的；
  - 单机运行，依赖本机代理；
  - 续接器没有自动保活，进程退出后需要手动 `start`（会从文件状态继续）。

## 11. 相关历史文档

- 旧方案复盘：`../docs/HARNESS_REVIEW_20261021.md`
- REVE 任务原始任务书：`../docs/research/REVE_ISA_RSI_TASK_BRIEF.md`
- REVE R1 结果：`../docs/research/REVE_ISA_R1_RESULTS_20261018.md`
