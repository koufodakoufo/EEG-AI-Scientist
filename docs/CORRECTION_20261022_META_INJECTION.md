# 更正记录：旧情绪研究的 Meta 规则没有进入模型输入

日期：2026-10-22（组会当日）
状态：仅追加说明；原始回答、`messages.json`、`scientist_input.md`、账本、旧评审和事件日志均未改写。

## 结论

2026-10-21 的情绪 state-vs-trait 研究（`archive/experiments/emotion_20261021/`）中，Meta 规则包被生成并保存到了每次运行的 `rules/` 目录，但**没有进入实际发送给模型的 system 或 user 消息**，也没有出现在 `scientist_input.md` 中。因此，baseline 与 meta_rule 两组的模型上下文实质相同，不能把两组差异归因于 Meta 规则。

需要撤回的表述：

- “Meta 主要改变引用表述”
- “规则有效性未见改善”
- 任何把两组输出差异当作规则干预效果的因果比较

应改为：

> Meta 完成了一次候选规则生成；规则注入失败；该规则的效果尚未被有效检验。

## 本轮复核（对当前归档原件）

复核对象：`archive/experiments/emotion_20261021/runs/flash_emotion_20261021/runs/` 下 10 次尝试（baseline ×4、meta_rule ×4，以及 retry 变体，共 10 个 run 目录）。

逐项检查结果（2026-10-22，离线，读取归档原件）：

| 检查 | 结果 |
|---|---|
| 是否存在规则快照文件 | 10/10 存在（baseline 为 `emotion_baseline_v1.md`，meta 为 `emotion_baseline_v1+meta_*.md`） |
| 规则快照正文是否出现在第一条 system 消息 | 0/10 |
| 规则快照正文是否出现在第一条 user 消息 | 0/10 |
| 规则快照正文是否出现在 `scientist_input.md` | 0/10 |
| 归一化 System 正文（去掉当前时间字段）SHA-256 | `76706dcbdded6dd5...`（10 次相同） |
| 归一化 User 正文（去掉当前时间字段）SHA-256 | `59e7bf720a323d1d...`（10 次相同） |

最后两行说明：这 10 次尝试真正发送的上下文（除明确记录的时间字段外）是同一份输入，`run_manifest.json` 或目录名中的 rule_version 不同并不等于模型看到了不同规则。

复现命令（不调用模型）：

```powershell
.\.venv\Scripts\python.exe audit_20261022\verify_historical_rule_absence.py
```

该脚本只读归档原件，输出逐 run 的检查结果。

## 原因

旧版 `ResearchRunner._initialize()` 调用 `_snapshot_rule()` 保存规则文件，但构造 system/user 消息时没有把规则正文拼接进去；`scientist_input.md` 也只拼接了 system 和 user。旧版 `study_runtime.run_study()` 同样没有把 `task.md` 正文送入运行，只使用了 `question`。

## 对后续工作的约束

- 不向旧 `messages.json`、`scientist_input.md` 或 `final_answer.md` 补写规则；历史保持原样。
- 需要检验规则效果时，必须新建 study/run，并使用本轮的冻结输入快照与 preflight。
- 旧实验只能作为“规则生成已发生、注入未发生”的记录，不能作为规则有效的证据。

## 新运行中的修复（2026-10-22）

- 规则正文进入 system 消息，并写入 `input_snapshot.json` 与 `scientist_input.md`。
- `task.md` 成为实际任务正文，`question` 仅作元数据。
- 配置了规则但文件缺失/为空时显式失败。
- `study preflight` 显示各 arm 的模型、任务/材料/规则哈希及提示差异；两个不同规则文件的正文相同时拒绝以规则对照启动。

详见 [`docs/VERIFICATION_20261022.md`](VERIFICATION_20261022.md) 和 [`HANDOFF.md`](../HANDOFF.md)。
