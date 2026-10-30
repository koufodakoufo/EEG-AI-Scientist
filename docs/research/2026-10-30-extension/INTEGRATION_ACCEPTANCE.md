# E05/E06 真实生命周期集成验收

2026-10-30 上午结题时只读验收。**E05、E06 均有真实原生模型会话和真实 EEG worker 证据，生命周期接受；科学范围均为部分完成（Q1 完整覆盖，Q2/Q3 未完成）。** 本文没有运行新模型、测试或重放，没有把脚本演示、Builder 参考分析计入 Actor 成绩。

## 权威位置与实现

`WORK=/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029`；`CODE=/data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration`。对下表 episode `E05` 或 `E06`，定义 `EP=WORK/episodes/<episode>`，`RUN=EP/controller/runs/real-<episode>`。这些均为服务器上现有路径。

实现位于 `CODE/framework/eegfm/research_bench/`：`real_episode.py::run_episode` 组装真实执行，`NativeEpisodeLaunch` 执行原生会话，`review_brief` 作委托协议 review；`driver_bridge.py::BridgeController.handle/_dispatch/review` 管理状态与请求；`real_worker.py::SandboxedWorkerEvaluator` 运行隔离 worker；`real_aggregate.py` 与 `real_science.py` 在候选沙箱外计算受信结果。`driver_bridge.py` 的 report 分支设置 `status=done`；没有独立的 `done` 事件，因此以最终 STATE/result 验证完成状态。

逐字节冻结身份核验见 [E06 与配对审计](E06_AND_PAIR_AUDIT.zh-CN.md)；私有机器快照在 `.local/research/2026-10-30-extension/closeout/E06/AUDIT.json`，含 events、精简 sessions、状态、源路径和哈希。未复制认证或 Actor controls。

## 实际状态链

下表时间全部为 **2026-10-30 +08:00**，取 `RUN/events.jsonl`。`RUN/audit.jsonl` 另作事件身份交叉核对。每 episode 各 11 个事件，不人为补造事件。

| 阶段 / 实际 event | E05 时间及身份 | E06 时间及身份 | 权威产物 |
| --- | --- | --- | --- |
| brief | 01:12:57；`E05-s01-brief-v1` | 01:26:55；`E06-s01-brief-v1` | `RUN/RESEARCH_BRIEF.md`；相应 `RUN/requests/<request>/request.json`、`response.json` |
| brief_review | 01:12:57；approved | 01:26:55；approved | `RUN/review.json`，reviewer `frozen-scope-reviewer`，mode `delegated_protocol_review` |
| contract | 01:14:44；`E05-s02-contract-v1` | 01:28:50；`E06-s02-contract-v1` | `RUN/freeze.json`，冻结科学协议 |
| baseline | 01:14:45；`real-E05-A1-validation` | 01:28:50；`real-E06-A1-validation` | `RUN/attempts/A1/attempt.json`，`RUN/jobs/<job>.json` |
| job_result（baseline） | 01:15:09；succeeded | 01:28:56；succeeded | `EP/worker-evidence/<job>/receipt.json`、`released_metrics.json` |
| attempt | 01:18:21；`E05-s03-attempt-v1` | 01:43:54；`E06-s03-science-v1` | `RUN/attempts/A2/attempt.json`；job `real-<episode>-A2-validation` |
| job_result（science validation） | 01:18:29；succeeded | 01:48:21；succeeded | `EP/worker-evidence/real-<episode>-A2-validation/` |
| lock | 01:19:34；A2 digest `9e5ccc…cc0e7` | 01:49:31；A2 digest `520080…dd925` | `RUN/lock.json`，`RUN/candidates/<digest>.json` 与 `<digest>/` |
| test | 01:19:34；`E05-s04-test-v1` | 01:49:31；`E06-s04-test-v1` | `RUN/jobs/real-<episode>-A2-test.json`，同一锁定 digest |
| job_result（one final test） | 01:19:42；succeeded | 01:53:35；succeeded | `RUN/sealed/final_test.json`，`EP/worker-evidence/real-<episode>-A2-test/` |
| report | 01:22:07；`E05-s05-report-v1` | 01:56:26；`E06-s05-report-v1` | `RUN/FINAL_REPORT.md`，对应 request/response |
| 最终状态（不是独立 event） | done，version 11 | done，version 11 | `RUN/STATE.json`、`EP/EPISODE_RESULT.json` |

所有同名事件的非时间字段在 events/audit 两份日志一致；两处顺序写日志的时间相差一秒：E05 test 的 events 为 01:19:34、audit 为 01:19:35；E06 baseline job_result 的 events 为 01:28:56、audit 为 01:28:57。E06 `lock.json` 的 locked_at 为 01:49:30，lock 事件写入为 01:49:31。没有据这些写入时刻差制造额外作业或改写历史。

## 原生执行与边界

E05 实际调用为 R60–R64，E06 为 R66–R70。每回合五次，会话 6 没有启动；预留调用号不是已用调用。`EP/own-session-receipts.json`、五份 `EP/launch-receipts/session-0N.json`、`EP/launches/session-0N-Rxx/status.json` 与 `RUN/sessions.jsonl` 相互支持：实际原生 invocation、verified model turn、完成 turn、退出码 0。它们不是以预写请求冒充模型运行的脚本轨迹。

E06 五次实际注入同一 skill SHA256 `54d5ce036ebb184bc653060196bed701807bb516b63dfc40d892d9938079191d`；E05 均为 null。冻结 source、public-staging、实际 public 的 skill 字节相符。源为 synthetic-dev M15，不能写成 real-dev 自我改进。

R68 原生状态特别复核：01:28:58.303309 至 01:43:53.679953，elapsed 895.377 秒，timeout 900 秒，completed、退出码 0。权威 `WORK/controller/BUDGET.json` 同一 R68 记录 completed，prompt hash 与原生 status 一致。该会话内部的局部干预原型退出 130，记录于 `WORK/cases/E06/output/local-science/aborted-prototype-runtime.json`；原型失败和会话成功同时保留，不能互相替换。

各受信 worker 的 request enrollment 与 episode 的 worker enrollment 完全一致；隔离命令记录 CPU 4 线程、无 GPU、bwrap `--unshare-all`、只读候选/输入/公开资源，标签/特征金标留在聚合器一侧。这里只复核已有配置和执行证据，没有重新攻击隔离边界或重复安全测试。原生与 worker 回执均没有存活的已跟踪自有子进程；这不等价于全面扫描服务器上所有进程。

## 验收判定

| 验收项 | 判定及边界 |
| --- | --- |
| 真实生命周期 | E05/E06 均通过上述节点；每个条件 5 个真实原生会话、1 次基线验证、1 次科学验证、1 次锁定测试、1 份最终报告。 |
| 真实科学输入 | EEGMAT 真实 EEG、公开官方 CBraMod 预训练骨干和该任务新增冻结二分类头；是 mental arithmetic/background 新适配，非论文结果复现。 |
| Q1 数值范围 | 两回合每划分 24 个组/层；E06 报告、身份和独立点估计核对通过。 |
| Q2/Q3 | 两回合均未完成；`q2_interventions=0`、`q3_residual_groups=0`、`numeric_scope_complete=0`。生命周期 done 不改变这些科学事实。 |
| 重现强度 | E05 既有 Builder 干净重放精确一致；E06 本轮只有现有证据/源码/点估计核对，无 Builder 独立干净重放。 |
| review 的含义 | scope review 仅协议准入；不能当作独立科学发现审稿或 semantic composite 评分验收。 |
| 对照推断 | 一个真实任务、一个完整 Agent pair；不能证明 skill 效益或 RSI。24 组不能当作独立 Actor 重复。 |
| 保留未完成与失败 | E01 冻结失败保留；E02–E04 未按原准入规则启动；E07/E08 未启动，没有第二对结果。 |

本次只补充可追溯的结题解释，不修改冻结 comparison-v2、原候选、原发布指标或状态机历史，不给 Actor 追加测试机会。
