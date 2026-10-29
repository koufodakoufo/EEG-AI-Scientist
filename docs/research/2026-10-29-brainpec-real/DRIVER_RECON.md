# R02：driver 与真实隔离研究的最小连接方案

日期：2026-10-29。角色：Builder / R02，静态源码核查；不是受测 Actor。

## 结论

**保留 `eegfm.driver.Driver.loop` 作为内层生命周期所有者，给它增加调用现有隔离 launcher 的执行适配器，以及一个小型、可信、类型化的请求分发边界。** 不能只替换 Codex 命令行，也不能把旧 CLI 放入沙箱后，让可信父进程代执行其任意 Shell。

现有实现已有 attempt、freeze、job ledger、等待恢复、错误分类、会话预算、report 等可复用基础；但默认 adapter 的联网权限、可修改的 run 文件、未重新校验的锁定代码、宽权限计算作业、`done` 的声明式成功，都不满足本轮正式 Actor 的边界。最低实现需要同时改 launch、authority、test 三条路径。

本报告只检查源码、模板、任务书和规则，没有读取 gold、真实科学输出、认证内容、`framework/tasks/reve_isa/src/split_manifest.json`；没有启动模型、作业或服务器操作，没有修改源代码或提交。代码位置以本次现场文件为准，未对已有 canary 的现场有效性作重新认证。只写本文件。

## 已有实现与具体缺口

下表行号用于定位本次核查版本，不是历史实验完成的证据。

| 文件 / 函数 | 现场事实 | 本轮含义 |
| --- | --- | --- |
| `framework/eegfm/driver.py:57` `Adapter.argv` | Codex 分支启用 `network_access=true`、`web_search=live`、`inherit=all`，以 `ROOT` 为目录；Claude 分支开放 Web 工具；允许额外参数和外部可写目录 | 正式 tested 模式必须拒绝这条路径及 `--agent-arg` 权限覆盖，不能降级后仍算正式运行 |
| `driver.py:176` `Driver.session` | 直接 `Popen`，继承宿主环境，向 PATH 注入全部 framework CLI；写 session log；超时杀 process group | 保留会话记录结构，增加 adapter 的执行方法，tested adapter 调 `launch_actor`，不走这段宽权限 Popen；复用 owned descendant cleanup |
| `driver.py:213` `Driver.loop` | 已负责 brief、等待 job、恢复、最大会话数、瞬态错误退避、blocked；见 `done` 就返回成功 | 可以继续作为唯一 resumer；增加 delegated review、请求接收和完成验证；错误会话改变文件不能自动抵销失败 |
| `framework/eegfm/research_bench/actor.py:107` `prepare_control` | 新 control home 必须不存在；只复制授权认证文件，另建 runtime；明确不复制用户配置、记忆或历史 | 每次真实唤醒用新 home、新 call ID；同一 episode 的允许历史通过经过筛选的文件快照传递，不 resume 全局会话 |
| `actor.py:24/159/191` `build_profile` / `launch_actor` / `validate_isolation_gate` | case 可写、public 只读，工具禁网，环境不继承，禁止自动规则/skill/memory；实际 launch 校验 public/profile，并对 actor/distiller 要求 live report | 直接复用；新增真实计算依赖、桥接路径或数据视图会改变边界，需在实际新路径做 canary。不能拿旧模板的通过替新 profile 背书 |
| `actor.py:159` 与 `budget.py:131` | `launch_actor` 返回 bounded process 状态；`run_bounded` 的 completed 由 exit=0 决定 | 还必须结合 `Adapter.classify` 的完整 Codex 事件流检查；容量错误/`turn.failed`/无 `turn.completed` 不算 Actor 成功 |
| `framework/eegfm/cli.py:95` brief 分支 | approve/reject 固定记 `actor="human"`；approve 把 brief 写回任务级 standing brief | 需要可信 reviewer 身份；tested 模式不写跨 episode standing brief；Actor 不得自调用 approve |
| `framework/eegfm/attempts.py:28` `init_run` | 任务已有 standing brief 会直接进入 working；整个 run 包含 sealed/jobs/attempts | tested run 强制 episode 内 brief；不能把整个可信 run 挂给 Actor |
| `attempts.py:82` `new_attempt` | 已加文件锁和 iteration 上限；注释明确不是针对同用户恶意改写的隔离 | 可复用到可信 run；Actor 只读投影，不能编辑 allocation、attempt、freeze 权威文件 |
| `attempts.py:126/145` `set_verdict` / `write_index` | Python 不自动按准确率 discard，但只允许 keep/discard，表格围绕 primary 与 baseline delta | 分析任务需要有效性/证据分类；真正的 accuracy-frontier 规则主要在 `PROGRAM.md:83–98`，也要换掉 Actor 所见协议 |
| `framework/eegfm/evaluation.py:44/66` `freeze` / `snapshot` | freeze 保存哈希；val snapshot 检查 editable/frozen，再从工作区复制文件；会调用该工作区的 git | tested 路径须从已停止 Actor 的普通文件接收快照，不信任 Actor 的 `.git`、hooks、外链；trusted snapshot 才是权威 |
| `evaluation.py:94` `submit` | test 只检查 locks/audit 文件；使用 `attempts/<id>/code`，没有重算锁定代码哈希；默认最多 2 candidates；job 启动后才写 test audit | 不能满足 episode 一次最终测试。需要可信原子 reservation、完整 candidate digest、启动前及 worker 输入校验、幂等恢复 |
| `evaluation.py:204` `lock` | 记录 attempt commit 和 val primary，没有不可变内容快照、协议参数/依赖/资源哈希 | Git commit 字符串不足以证明即将执行的目录字节。参数、拟合产物、预处理、权重及统计判定规则同样要锁 |
| `evaluation.py:218` `final_report` | 只要求 job 进入 terminal；失败 job 有 metrics 仍可能聚合；不核对 expected shard 集是否完整 | failed/stopped、缺 shard、非有限数不能成为成功最终测试。结果可保留为失败证据，但不记 done |
| `framework/eegfm/jobs.py:30/141` `LocalBackend.submit` / `submit` | 接收任意 cwd 和 command，以宿主 `bash -c` 执行；继承环境；状态靠 exit 文件 | 不是隔离计算接口。当前 CLI 没有通用 `job submit` 子命令，但 Python API 和任务中的可执行 candidate 足以构成宽权限入口 |
| `jobs.py:159` `refresh` | `submitting` 原样返回；本地中断 submit 没有真正的自动 adoption；本地 PID 身份只检查 PID | 定义 reservation/启动/恢复规则，不声称本地天然 exactly-once；同 digest 的技术重试与未知提交状态应明确记录 |
| `framework/eegfm/state.py:24` `set_state` | `done` 不验证报告、锁、测试、成功执行；`actor` 是普通参数 | Actor 只能请求状态变更；可信 controller 决定 reviewer 身份和终态 |
| `framework/eegfm/research_bench/replay.py:50/72` | 已有停止后冻结、symlink/hardlink 拒绝、沙箱重放；重放只接受 output 下 Python 入口；现为 60 秒、标准 Python、统一 validation ledger | 复用冻结与沙箱思路；真实依赖、逐行 split、最终测试输出和科学结果比较需扩展。现有 replay 不等于受保护的 test executor |
| `framework/eegfm/research_bench/evidence.py:83` `audit_evidence` | 校验 command/run/status/exit/path/hash/split；支持 artifact-level split label | 尚不能仅靠 split 字符串证明混合文件某行归属。真实输出增加 row/sample binding 和可信 split manifest hash |
| `scripts/overnight/actor_job.py` / `collect_episode.py` | 旧单次 isolated episode 与停止后收集，硬编码 M ID、旧预算/路径；没有 driver 生命周期连接 | 保留历史脚本；新增本轮薄入口，调用复用库与 Driver，不把旧 M 脚本改造成第二个 orchestrator |

## 最小架构与所有权

建议增加一个小模块 `framework/eegfm/research_bench/driver_bridge.py`，其中包含 tested adapter、会话投影、请求验证与分发；科学数据执行器独立于此模块。已有 Driver 仍决定何时唤醒、等待作业、审核、停止。

```text
外层 episode 配置（case/condition/task seal/budget/工具身份）
  -> Driver.loop（可信，唯一生命周期与 session budget 所有者）
       -> IsolatedAdapter.execute -> prepare_control + launch_actor
          Actor：公共任务 + 本 episode 允许历史 + train/val 接口 + 自有 output
       <- 会话结束、所有后代停止后的类型化请求 / 提交文件
       -> trusted dispatcher -> 原 attempts/state/evaluation/jobs 的受限模式
       -> 固定计算入口 -> 隔离 candidate worker（无控制层权限）
       <- schema 校验的结果、可信 job receipt、分割绑定
       -> 更新可信 run -> 只读反馈投影 -> 下一次全新 Actor 会话
  -> 冻结报告/证据 -> 独立 replay / scorer
```

目录边界建议：

| 区域 | 所有者与可见性 |
| --- | --- |
| `trusted/runs/<run>/` | 原 wzf `STATE.json`、run、attempt、freeze、locks、jobs、audit、sealed、session 状态；Actor 无挂载 |
| `trusted/episodes/<episode>/requests/<id>/` | 原始已接受请求、request hash、接受身份/序号、响应；只追加且不可覆盖；Actor 无挂载 |
| `trusted/controls/<call>/` | 新 CODEX_HOME；认证与原生会话；Actor 工具不可读；仅脱敏可见 trace 进入审计 |
| `cases/<episode>/<session>/public/` | 本轮固定公开包 + 本 episode 允许反馈的只读投影；不要放可信绝对路径、gold、Builder 文档 |
| `cases/<episode>/<session>/output/` | Actor 自有代码、分析计划、brief、请求、报告草稿；停止后接收普通文件快照 |
| `trusted/candidates/<digest>/` | 内容寻址的不可变代码、训练拟合产物、分析参数/规则、依赖清单；Actor 后续写入无影响 |
| `worker/<job>/` | 只含当前固定任务允许输入与独立输出；不能继承 controller home、env、源码根、数据根或其他作业目录 |

可以复用同一个 episode case，但每次 fresh control home 是必要条件；采用每 session 新 case + 明确快照更容易防止隐蔽文件/缓存跨会话扩散。无论选择哪种，跨 episode 都是新的空白 home、memory、tmp/cache 和 workspace。public 下动态反馈生成后重新冻结 manifest；永久任务包 hash 与 session 反馈 hash 分开记录。

`case_id -> episode_id -> run_id -> attempt_id -> job_id`；condition 属于 episode，模型唤醒另有 `call_id/session_id`。一个 episode 恰好一个 wzf run。日志/请求/响应/产物同时携带这些关联键；不能借 run 名、路径或 Actor 提交的 condition 获得其他 episode 的内容。

## 类型化桥接：不能变成代执行 Shell

建议 Actor 可请求的有限操作：`brief.submit`、`freeze.request`、`attempt.propose`、`eval.validation`、`attempt.record_result`、`candidate.lock_and_test`、`report.submit`、`state.blocked`。状态/作业查询使用只读投影；独立 `eval.test` 只能使用已保存的唯一 lock token。`brief.approve/reject`、自选 cwd/command/env、memory.promote、任意路径读取不进入 Actor capability。

请求最小 envelope：

```json
{
  "schema_version": "driver_request_v1",
  "request_id": "opaque-episode-local-id",
  "episode_id": "E...",
  "run_id": "run...",
  "expected_state_version": 3,
  "operation": "candidate.lock_and_test",
  "payload": {
    "attempt_id": "A3",
    "candidate_manifest": "candidate/manifest.json",
    "reason": "selection based on allowed validation evidence"
  }
}
```

字段是设计建议，不是已经实现的 API。controller 不信任请求中的身份：运行上下文绑定 episode/run，检查所有 ID 与现有 trusted state；拒绝多余字段、外部 run、绝对路径、`..`、链接、设备文件、大文件/深 JSON 和版本不符。manifest 路径只在停止后的 output snapshot 内解析。路径验证后仍应以安全打开/复制方式消除链接替换与 TOCTOU。

最小实现可在 session 退出后处理请求，不需要网络服务，也不开放监听端口。允许一批顺序明确的操作（例如锁定并提交同一方案），依赖前一步的操作使用 controller 分配的引用。每个实际 operation 仍留下原 driver/attempt/job/audit 事件。不要让 Actor 靠伪造本地 STATE 改动触发可信工作。

接受请求后先保存原始字节、canonical hash、调用身份、sequence，再处理副作用；同 request ID + 同 hash 返回已记录响应，同 ID + 不同 hash 拒绝。响应含 request hash、结果状态、允许显示的 metrics/artifact hash、state version。规范响应保存在 trusted 区，只读拷贝才进入下一 session；Actor 自写 response/exit/metrics 文件均不具可信身份。

复用现有 CLI 语义但不要让桥接入口调用 `cli.main(argv)` 接受任意 argv。公开的 `bin/eegfm` 若保留，应是只产生 typed request 的小 facade；真正的 `E/J/A/S` 调用只在 trusted dispatcher 内发生。Actor 可自主写任意分析代码，但只能在规定权限的 candidate worker 中运行。

## 最终测试必须有两层隔离

第一层是交互 Actor：只提供明确 train/validation 的视图或 loader 能力。**不能挂载混合 train/val/test 的 LMDB，不能仅过滤标签，不能仅隐藏目录名。** 公共视图不能包含 test EEG、feature targets、表征缓存、索引/键列表、可定位 test 样本的元数据。原数据只由可信 loader 读取，不修改、搬移或复制既有数据库；允许的数据视图/派生缓存写入本轮自有目录，并记录来源、分割和哈希。

第二层是计算 worker：最终测试获准后，可信 loader 才读取冻结 split，按固定入口把规定张量交给**独立沙箱进程**。不要在可访问源数据库、标签、gold、认证或宿主文件的 controller 进程里 `import`/`exec` Actor 的 Python。固定 `python trusted_eval.py --candidate ...` 本身不足以构成隔离；如果它在同一进程导入 candidate，就仍有权限继承漏洞。

Q1 可让 candidate 只输出从规定表征得到的预测，可信侧计算隐藏目标/指标。Q2/Q3 的接口必须按已冻结的通用模型操作能力定义；需要中间激活与继续前向时，由可信模型 runner 提供受限张量运算边界，不能假装均值池化缓存等于完整模型。接口不能偷偷附送论文专用方法。若最小安全接口只能支持 Q1，冻结为 Q1 子任务，并明确 Q2/Q3 未完成。

最终测试 sequence：

1. 确认对应 validation job 全部 succeeded，brief 与 evaluator 合约获批，candidate 是已知 attempt。
2. 停止 candidate 写入；复制、检查并哈希代码、训练拟合产物、参数、特征/层选择、对照、统计族/规则、依赖与模型/预处理/split 身份。`commit` 仅作溯源，不作内容真实性替代。
3. 在 Actor 不可写的 episode lock 中保存唯一 `candidate_digest`、规则 hash、split hash、allowlisted worker entrypoint/version、预算；episode 只能选择一个方案。未干预 baseline 和所有预定对照可包含在这个锁定方案的一次 test 中，不分别挑多个候选。
4. 原子写入 test reservation 和 job identity 后才启动。并发重复请求不多启动；crash 状态不自动重发。明确可证明未启动、仍在跑、已完成、未知四类恢复；允许的纯技术重试只能重跑完全相同 digest，所有失败保留，不能自选新的候选。
5. worker 从可信不可变 snapshot 运行；启动前与完成后核验输入清单。拒绝 candidate 里路径/网络/loader 绕过；运行超时和后代清理沿用 bounded launcher。
6. 可信 evaluator 只接受规定 schema、完整 shard、finite metric、成功 worker receipt。日志/错误先脱敏，不向 Actor 回传测试样本、标签、绝对路径、任意文件内容或未限制的 stdout。
7. 将 canonical response 固定，重复读取返回同一结果；最后 Actor 只补充报告解释，不能再改层/特征/规则或以 test 反馈重新开发。同冻结产物的独立重放走审计通道，不反馈新适应性测试信息。

候选代码即使没有网络，也可通过输出编码输入；因此不能原样解封 worker 的任意输出/日志。测试数据保持在 worker 内，交互 Actor 仅得到提前规定的结果表与诊断。这是本轮威胁模型的一部分，不是 `chmod 0700` 能代替的检查。

## analysis 模式与审核 / 完成语义

在 task 合约加局部 `research_mode: analysis`（默认仍是现有 optimization），通过 `common.load_task` 校验。对分析模式：

- 原分类模型/输出头冻结，不能为提高解释结论的可见效果而微调。baseline 指未干预模型/初始分析方法；condition baseline 指不注入 skill 的 Actor，日志分别命名。
- `collect` 保留各指标原值、控制有效性、残余信息、强度/秩、subject uncertainty 和证据链接；不以 accuracy 大小决定 keep。
- 可增加 `retained_valid` / `invalid_protocol` / `execution_failed` 等明确字段，保留原有 keep/discard 兼容映射；分析模式的 keep=有效证据被保留，discard=不能支持推断而非数值变差。所有文件和负结果仍归档。
- `write_index` 展示假设、协议有效性、结果方向、证据和成本；不把最高 primary 节点叫作前沿。停止由预算、预定问题覆盖、必要对照和判定规则决定。
- Actor 公开协议和模板必须明确覆盖 `PROGRAM.md` 的准确率 frontier、Web 调研、全局 memory 和 task standing brief 行为。不能直接把当前 PROGRAM.md 连同这些指令送进去再只加一句“analysis”。用受审查的任务专用公开流程文档；原 optimization 行为继续兼容。

brief 采用冻结规则 reviewer：记录 `approval_mode=delegated_protocol_review`、`reviewer_id`、policy hash、brief hash、decision/reason、时间。只审资源、范围、预算、数据保护和协议完整性，不提供目标方法/预期结果。reviewer 身份由 trusted controller 设置，不能来自 Actor 自填字符串。该 episode 每次单独审阅，不写任务级 standing brief。

`done` 的必要条件：有效 Actor 会话完成；brief/review/freeze/baseline/至少一次科学分析或对照有真实记录；必需 jobs succeeded；唯一锁定 test 已完成；报告及必需证据 schema/路径/hash 完整；提交冻结成功。正结果和更高准确率不是完成条件。`report final` 若 test job 失败可产生失败说明，但不能产出“研究完成”的终态；外部容量错误与科学负结果分开。

session 预算内的最小正常路径可为：brief+setup 请求 → 审核/冻结 → baseline 请求/等待 → baseline 反馈+分析请求/等待 → 分析反馈+锁定最终测试/等待 → 最终反馈+报告。具体可合并合法操作，但不得伪造未真实触发的节点，也不为凑多轮制造失败。

## 实施文件与顺序

1. `research_bench/driver_bridge.py`（新增薄层）：`IsolatedAdapter.execute`、`build_episode_view`、`ingest_request`、`dispatch_request`、`validate_completion`；所有新增 Python 保持类型注解。先冻结请求 schema、只读投影和权限映射。
2. `driver.py`：抽出 adapter 执行接口；tested 分支调用 bridge，保留 legacy 分支；loop 处理 trusted request/review/job 的状态并验证 done；tested 模式拒绝宽 adapter 与权限追加参数。session/attempt/job 全部加入 episode/condition/call 关联。
3. `cli.py` / `state.py` / `attempts.py` / `common.py`：受信 caller 的 review 元数据、episode-only brief、analysis 合约、有效性 retention、完成门槛；Actor facade 仅序列化允许请求。
4. `evaluation.py`：trusted candidate freeze/lock manifest、原子 test reservation、幂等 final response、完整 successful shard 校验；analysis 聚合不丢原值。
5. `jobs.py`：增加受限本地 backend（固定 argv 的 trusted wrapper + 单 job 沙箱），不把 Actor 的命令串交给 LocalBackend；绑定 job/candidate/run，恢复需 PID+start identity/receipt，终止所有本次拥有的后代。
6. 本轮科学模块的固定 worker（名字随资源方案确定）：typed split loader、已冻结模型操作接口、受限 candidate 子进程、结果 schema、test output 过滤。此接口未验收前不运行正式 Actor。
7. `research_bench/actor.py`：若依赖 runtime/反馈路径有新增，最小扩展 profile 且拒绝宽 mount；launch 前重新校验真实二进制/host/bwrap 与模板身份，不能只比较旧 metadata 中缓存的 hash。扩大真实数据只读体积时，把输入与新增写入 storage quota 分开；现 launcher 的 64 MiB case scope 不适合直接塞入真实 EEG 大视图。
8. `research_bench/replay.py` / `evidence.py`：以冻结的运行约定支持真实依赖与多阶段产物；逐指标绑定 artifact hash、row selection/sample IDs、split manifest hash、calculation；科学结果与时间戳等诊断分别比较，不能把整个文件字节相等当科学复现的唯一判定。
9. 本轮公开 task/protocol/template 及薄启动脚本：不改旧 M 脚本/旧预算；薄脚本只准备 episode/config 并调用 driver。保留旧 optimization 测试。

## 主要绕过点与定向回归

这些是必须针对真实连接路径做的检查，不是要求重复跑完整旧测试集或用测试数作为科研进度。合成 fixture 可用于权限 canary，科学验收仍需真实数据 + 真实 Actor。

| 测试 | 必须观察到的行为 |
| --- | --- |
| adapter routing | tested driver 确实进入 `launch_actor`；legacy 网络/env/`--agent-arg` 不生效；binary/profile 变化拒绝旧 canary |
| actual tool surface | 当前真实启动记录的 tools 不含 Web、网络、其他模型/插件/skill；OpenAI control 请求仍可工作；空配置不是证明 |
| input isolation | train/val 正常可用；绝对路径、父目录、symlink、hardlink、`/proc`、混合 LMDB、test EEG/特征/缓存/metadata、其他 episode、Builder docs、ancestor AGENTS、认证均拒绝 |
| request authority | 自写 STATE/locks/audit/responses/exit 无效；跨 run ID、重复 ID 异 hash、stale state version、路径穿越、额外 cwd/command/env 字段拒绝 |
| privileged execution | candidate 尝试 Python `open`、subprocess、import hooks、pickle side effects、网络/代理、任意宿主路径，不能触及 trusted loader/control；固定 worker 不在父进程导入 candidate |
| brief identity | 自动 review 记 delegated reviewer/policy hash，不记 human；Actor 自 approve 拒绝；下一 episode 仍需自己的 brief |
| lock integrity | 未 lock 拒绝 test；lock 后改代码/参数/拟合缓存/权重/规则被拒；相同 snapshot 不受 Actor 新文件影响；每 episode 只有一个方案 |
| one final test | 并发和重复请求只一个 reservation；在 intent/启动/receipt 写入之间注入 crash，不产生静默双跑；纯技术重试仅同 digest 且不增加适应性反馈 |
| report success | failed/stopped job 即使留 metrics 也不能成功；缺 shard、NaN/Inf、空报告、缺产物均不能 done；容量 error exit=0 仍失败；完整负结果允许 done |
| driver continuity | 等待 job 后重启 driver 可恢复且不重复提交；iteration/session 上限生效；超时 fork/setsid 后无存活 owned descendants |
| analysis retention | 相同冻结模型下有效干预使准确率下降，attempt/指标/证据仍保留；analysis 不按 accuracy 淘汰；旧 optimization 行为不变 |
| sealed feedback | worker stdout/异常含私有样本值或路径不原样返给 Actor；正式结果只在 lock 后、从固定响应解封；test 后不能重选方案 |
| split/replay | 混合 train/val 产物按行绑定；同名不同 split、换 row、改 metric 明确失败；纯时间戳变化不否定相同科学数值；重放不能再给 Actor 测试反馈 |

现有可扩展测试位置：`framework/tests/test_program.py`（正常生命周期、恢复、freeze/test gate、iteration budget）、`framework/tests/research_bench/test_actor_config.py`、`test_legacy_adapter.py`、`test_replay.py`、`test_evidence.py`、`test_bundle_budget.py`。新增 `test_driver_bridge.py` 覆盖跨信任边界，避免把真实安全断言全塞进 legacy 单元测试。真正内核/工具隔离断言仍需 Linux live canary，本次 Windows 源码阅读不能替代。

## 验收与当前状态

本次可行动的设计已完成；实现、真实资源适配、Linux canary 和真实 Actor 验收均未由 R02 执行。没有证据表明当前源码已经满足正式双流程连接。最先实现的阻断项应为：可信 run 所有权与 typed dispatch → isolated Driver adapter → 固定 sandbox eval worker/封存测试 → analysis/review/done → 真实 canary 与第一条完整轨迹。

若最终只使用旧 `actor_job.py` 做真实 EEG 单次研究，应记“真实分析完成、连接未完成”；若只能保护并运行 Q1，可记“真实编码子任务”，不要据此宣称预测依赖问题已解决。
