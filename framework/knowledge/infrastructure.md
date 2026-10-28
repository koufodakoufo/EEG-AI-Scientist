# 基础设施

核实日期：2026-10-21。

## 计算：腾讯 TiONE

- 用户明确要求 REVE 相关任务使用 TiONE，**不使用当前 notebook 的本地 GPU**。
- 提交使用可信 helper：`/mnt/cfs-omni/wzf/iclr2027/experiments/3stage/scripts/tione/submit_full_npd_70gpu.py`（STS 凭据来自 notebook，镜像、资源组、VPC、CFS/COS 挂载均在其中定义）。本项目通过 `bin/eegfm eval submit` 使用它，不要另写提交脚本。
- 资源形状：每 GPU 4 CPU、112 GB 内存；单节点。CFS 挂载到作业内的 `/mnt/cfs-omni`，路径与 notebook 相同。
- 每个新 TiONE 任务都要用 `/mnt/cfs-omni/wzf/.volcengine/record_job.py` 登记（工具已自动完成）。
- 作业失败时可能晚一些才出现 guard/日志；确认失败后再做修复。

## 时长估算（REVE × ISA）

- 一次完整 development 评估（6 个目标并行，每个 6 GPU，后训练 40 epoch + LP/FT 6 折）：后训练约 2–3.6 小时/目标；按 2026-10-19 的吞吐预测，含 1.5 倍余量约 8 小时。
- 完整流程（baseline + 1 轮 development + final test）在 2026-10-19 估算为约 16.1 小时；12 小时的期限放不下。
- posttrain 占 development 时间的约 82%；单步耗时 p90 约 0.93 s，中位数约 0.71 s。
- 来源：`logs/handoff_fix_20261020/actual-replay.json`；`logs/reve_isa_hparam_recovery_20261019_broker/remote/...FACED.preflight.log`。

## 存储

- 临时文件：`/omni-eeg-00/home/wzf/scratch/<project>/<run>`；启动进程前设置 `TMPDIR/TMP/TEMP`，并验证可写。
- 缓存：`/omni-eeg-00/home/wzf/cache/<project>`。
- 新的持久数据集、预处理产物：对象存储，例如 `/mnt/omni-eeg-01/...`。不要放在 `/mnt/cfs-omni`、`/tmp` 或 `/dev/shm`。
- `/omni-eeg-00` 显示的 8.0E 容量是虚拟值，不代表无限配额。
- 不清理其他用户、项目或正在运行的实验的文件。

## 网络

- 服务器不能直连外网；Codex / Claude / 网页检索都经由本机代理 `HTTP(S)_PROXY=http://127.0.0.1:17897`。2026-10-21 观察到该代理不可用时，所有 LLM 调用失败（推测与 SSH 会话有关，尚未确认）。

## Agent 后端

- 2026-10-21 下午至晚间，Codex `gpt-6.1-sol` 多次返回 `serverOverloaded`；长的多工具回合更容易中途失败。续接器会退避重试，状态在文件中，不会丢进度。
- Codex 与 Claude Code 都可以作为研究 agent（续接器 `--agent codex|claude`）；切换 agent 由用户决定。
