# EEG 基础模型研究：Agent 入口

本仓库是一个**由 markdown 驱动**的 EEG 基础模型（EEG FM）研究程序。你（Codex、Claude Code 或其他 agent）就是研究者；`bin/eegfm` 只负责记录、评估和保证规则，不替你做研究。

## 先读什么

1. `PROGRAM.md`：怎么做研究（通用，所有任务都适用）。**这是主规则，按第 1 节的唤醒流程开始。**
2. `tasks/<task>/TASK.md`：这次研究什么。
3. `knowledge/INDEX.md`、`memory/INDEX.md`、`tasks/<task>/memory/INDEX.md`：领域知识与记忆。
4. `runs/<run>/`：本次运行的全部状态（`STATE.json`、`NOTES.md`、`attempts/INDEX.md`）。

## 不可违反的规则（详见 PROGRAM.md）

- **评估器冻结后不得修改**；只能改 `task.yaml` 里 `source.editable` 列出的文件。
- **test 隔离**：所有决定只看 validation；不得读取 `runs/<run>/sealed/`，不得自行计算 test 指标；test 只能通过 `bin/eegfm eval submit --phase test` 对已锁定候选执行一次。
- **不在运行中途向人提问**。唯一的人工节点是研究 brief 的审阅（`bin/eegfm brief submit`）。其他不确定性写进 `runs/<run>/NOTES.md`，在授权范围内自己决定。
- **每次会话结束前更新状态**：`bin/eegfm state set <run> --status ...`。
- **存储**：大文件不放 `/tmp`、`/dev/shm`；临时文件放 `/omni-eeg-00/home/wzf/scratch/eeg-fm-research/<run>/`；新的持久数据集放对象存储（`/mnt/omni-eeg-01/...`）。遵守 `/mnt/cfs-omni/wzf/AGENTS.md`。
- **不清理、不覆盖**其他用户、其他项目或正在运行的实验的文件。
- 不修改 `bin/`、`eegfm/`、`PROGRAM.md`、`AGENTS.md`、`tasks/<task>/task.yaml`；它们是研究的规则，不是研究对象。
