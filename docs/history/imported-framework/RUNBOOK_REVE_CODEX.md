# 操作手册：用 Codex 跑 REVE × ISA

面向：在这台 TiONE notebook 上用 Codex 启动并看护 `reve_isa` 任务的人。原理见 `README.md`，任务定义见 `tasks/reve_isa/TASK.md`。

## 0. 会发生什么

| 阶段 | 谁在做 | 预计耗时 | GPU | 需要人做什么 |
|---|---|---|---|---|
| brief | Codex 读知识库、记忆、历史结果，做网页检索，写研究 brief | 10–30 分钟 | 否 | **审阅 brief 并批准或驳回** |
| setup | Codex 实现 `src/run_eval.py`，切断旧耦合（TASK.md §5.2），提交 smoke 作业，通过后冻结评估器 | 数小时（含多次 smoke） | 是（每次 smoke 6 个作业 × 6 GPU，单次估计 20–40 分钟） | 无；被 blocked 时处理 |
| baseline（R0） | 官方 REVE 直接下游，6 个目标并行 | 约 1–2 小时 | 是（36 GPU） | 无 |
| 迭代（至少 2 轮） | 每轮 ISA 后训练 + 下游，6 个目标并行 | 每轮约 4–8 小时 | 是（36 GPU） | 无 |
| 收尾 | 锁定 R0 与最终候选，各跑一次 test，写报告，整理记忆 | 约 1–2 小时 | 是 | 读最终报告 |

总计约 1–2 天墙钟。agent 调用费用另计，取决于模型与推理强度。

## 1. 前置条件（缺一不可）

1. **在 TiONE notebook 网页里打开的终端中操作**。TiONE 提交依赖容器注入的环境变量 `QCLOUD_CONTAINER_INSTANCE_CREDENTIALS_URL`（notebook 的 STS 凭据入口）。SSH 或 VS Code 远程会话里通常**没有**这个变量，在那里启动会导致所有 GPU 作业提交失败。可以这样确认（只看是否存在，不要打印值）：
   ```bash
   test -n "$QCLOUD_CONTAINER_INSTANCE_CREDENTIALS_URL" && echo present || echo MISSING
   ```
2. 代理：
   ```bash
   export HTTP_PROXY=http://127.0.0.1:17897 HTTPS_PROXY=http://127.0.0.1:17897
   ```
3. Codex 已登录：`codex login status` 显示 `Logged in`。使用的是这台机器上当前登录的账户。
4. 临时目录（按工作区规则，不要用 `/tmp`）：
   ```bash
   export TMPDIR=/omni-eeg-00/home/wzf/scratch/eeg-fm-research/<run>; mkdir -p "$TMPDIR"
   ```

## 2. 开跑前自检

```bash
cd "/mnt/cfs-omni/wzf/auto research/eeg-fm-research"
bin/eegfm preflight --agent codex --task reve_isa          # 本地与只读检查，不花钱
bin/eegfm preflight --agent codex --task reve_isa --live   # 再加一次极小的真实 Codex 会话
```

全部 `[ok]` 才继续。`--live` 验证 Codex 在沙箱内能运行 `bin/eegfm`、能写 run 目录和 scratch、能联网，会话日志在输出最后一行给出的路径中。

常见失败：

| 失败项 | 处理 |
|---|---|
| `notebook STS env` / `TiONE read-only lookup` | 换到 notebook 网页终端（见 §1.1） |
| `internet via proxy` | 代理不可用，检查 17897 端口的代理是否在运行 |
| `codex login status` | `codex login` |
| live 会话写不了 scratch | 续接器启动时用 `--writable <目录>` 加上该目录 |

## 3. 启动

```bash
RUN=reve_isa_$(date +%Y%m%d)
export TMPDIR=/omni-eeg-00/home/wzf/scratch/eeg-fm-research/$RUN; mkdir -p "$TMPDIR"
bin/eegfm run init --task reve_isa --run-id $RUN
python3 -B -m eegfm.driver start --run $RUN --agent codex \
    --poll 120 --session-timeout 14400 --stall-limit 3
```

- 不加 `--model` 时，使用这台机器上 Codex 的默认配置（`$CODEX_HOME/config.toml`，2026-10-21 为 `gpt-6-astra`、推理强度 medium），与平时在终端里用 `codex` 完全一致。
- 需要指定时：`--model <模型> --agent-arg=-c --agent-arg='model_reasoning_effort="high"'`。注意：旧 harness 用过的 `gpt-6.1-sol` 在当前 CLI（0.155.1）+ ChatGPT 账户下会被服务端拒绝（`model is not supported when using Codex with a ChatGPT account`）；换模型前先用 `bin/eegfm preflight --agent codex --live --model <模型>` 验证。
- `--session-timeout 14400`：单次会话最长 4 小时，setup 阶段写代码可能比较久。
- 续接器在后台运行，日志在 `runs/$RUN/driver.log`。

## 4. 人工节点：审阅 brief

续接器会停下来，并生成 `runs/$RUN/ATTENTION.md`。

1. 阅读 `runs/$RUN/RESEARCH_BRIEF.md`，重点看：
   - 问题和成功标准是否与 TASK.md 一致；
   - "我们的实测事实"和"文献"是否分开写了；
   - 候选假设是否在 TASK.md §4 允许的范围内；
   - 有没有提议改动 §3 里固定的部分。
2. 批准：`bin/eegfm brief approve $RUN --note "…"`；或驳回：`bin/eegfm brief reject $RUN --note "具体修改意见"`。

续接器会自动继续；如果它已经退出，重新执行 §3 的 `driver start` 即可。

## 5. 运行中怎么看

```bash
bin/eegfm status $RUN                    # 当前状态、尝试统计、是否已冻结、最近事件
bin/eegfm attempt list $RUN              # 每个 attempt 的 validation 主指标与判定
tail -40 runs/$RUN/NOTES.md              # Codex 每次会话的交接记录：做了什么、为什么、下一步
bin/eegfm job list $RUN                  # TiONE 作业状态
tail -3 runs/$RUN/sessions.jsonl         # 每次会话：耗时、有无进展、错误类型
cat runs/$RUN/driver.json                # 续接器心跳与当前阶段
```

TiONE 作业也会登记在 `/mnt/cfs-omni/wzf/.volcengine/jobs/`，可以用 `python3 /mnt/cfs-omni/wzf/.volcengine/record_job.py show --task-id <id>` 查看。

**不要做的事**：
- 不要读 `runs/$RUN/sealed/` 再把内容告诉 agent（会破坏 test 隔离）；
- 不要手动改 `workspace/` 里的冻结文件；
- 不要绕过 `bin/eegfm` 直接提交 GPU 作业。

## 6. 出问题时

| 现象 | 原因与处理 |
|---|---|
| `STATE.json` 为 `blocked`，`ATTENTION.md` 写明原因 | agent 或续接器判断只有人能解决。按原因处理后执行 `bin/eegfm state set $RUN --status working --note "已处理：…"`，再 `driver start` |
| 心跳停在 `backing_off` | Codex 过载或网络中断，正在退避重试（最长 15 分钟一次，6 小时后转为 blocked），一般无需处理 |
| 作业一直 `running` | `bin/eegfm job status $RUN <job>` 查看；确认卡死后 `bin/eegfm job stop $RUN <job>`，agent 下次会话会按失败处理 |
| 作业失败 | agent 会读 `attempts/<A#>/eval/error.txt` 和作业日志，自己 debug；连续失败会在 NOTES 里写明 |
| 续接器进程不见了 | 重新 `driver start`，从文件状态继续，不会重复提交 |
| 想换成 Claude Code | 停掉续接器（`kill $(python3 -c "import json;print(json.load(open('runs/$RUN/driver.json'))['pid'])")`），用 `--agent claude` 重新 start |
| 想暂停 | 停掉续接器即可；已提交的 TiONE 作业会继续跑完，下次 start 时会被收集 |

## 7. 预算

`tasks/reve_isa/task.yaml: search` 规定了：至少 2 个有效轮次、最多 6 个 iteration、`gpu_hours_budget: 900`。

**GPU 小时预算目前由 agent 按 PROGRAM.md 自行遵守，工具不会强制拦截。** 请在 `bin/eegfm attempt list` 的 GPU-h 一列留意累计用量，超出预期时停掉续接器。

## 8. 结束后

- `runs/$RUN/FINAL_REPORT.md`：最终报告。性能结论和流程结论分开写；报告中应注明这套划分的 test 在 2026-10-18 已被看过，结论属于开发性比较。
- `runs/$RUN/final_test.json`：解封后的 test 结果。
- `tasks/reve_isa/memory/`、`memory/`：本次新增或晋升的记忆（用 `git diff` 查看）。
- 把 `tasks/` 与 `memory/` 的变更提交到 git；`runs/` 不进 git，按需归档到项目的 `results/` 或 `logs/`。
