# CODE READING GUIDE — Flash 研究回路

目标：从运行入口一路读到“模型实际收到什么、工具实际做了什么、证据如何被保存”。按顺序读，约 60–90 分钟。

## 1. 入口：一次研究运行如何开始

`src/eeg_scientist/cli.py`

- `command_flash_research`：加载 `configs/studies/overnight_flash_20261020.json` 与 `configs/models/deepseek_flash.json`，显式读取 `credentials/deepseek.env`，构造 `BudgetLedger` 与 `DeepSeekClient`，再构造 `ResearchRunner`。
- 研究目录：`runs/<run_id>/research/<name>/`；报告目录：`reports/<run_id>/`。
- 关键点：没有 `provider_from_config` 的自动 fallback；DeepSeek 是显式路径。

自测：如果删掉 `credentials/deepseek.env`，程序应在哪一层报错？会不会自动改调 Ollama？（答案：`load_deepseek_key` 抛 `CredentialError`；不会。）

## 2. 模型边界：`src/eeg_scientist/deepseek_api.py`

- `DeepSeekClient.chat`：把内部 `messages` 规范成 Chat Completions wire shape；assistant 消息保留 `reasoning_content` 与 `tool_calls`；tool 消息保留 `tool_call_id`。
- 请求体：`model=deepseek-flash`、`thinking={"type":"enabled"}`、`reasoning_effort="high"`、`stream=false`、可选 `tools`。
- 返回：`DeepSeekChatResult`（content、reasoning_content、tool_calls、finish_reason、usage、returned_model、raw）。
- `search` / `fetch`：官方 `/v1/tools/search`、`/v1/tools/fetch`；错误按 4xx/5xx/超时分类，调用账本。
- `DeepSeekDecisionProvider`：把同一个 client 适配成旧 `decide(ModelRequest)` 接口，仅用于 Task C 的合成案例诊断。

自测：为什么带 tools 的后续请求必须回传 `reasoning_content`？如果不回传，服务端会怎样？（答案：见官方 thinking 文档；会 400。）

## 3. 钱与次数：`src/eeg_scientist/ledger.py`

- 每次付费请求前 `reserve_model` / `reserve_tool`，按峰值价格和 UTF-8 字节上界预留。
- 成功后 `settle_model` 按 usage 结算；超时或结果不明 `mark_unknown`，预留不释放；连接失败才 `release`。
- 账本在 `runs/<run_id>/budget.json`，原子替换；恢复时沿用，不清零。
- `model_attempts` 在预留时加一，所以重试也计数。

自测：一次请求超时但服务器可能已计费，账本应显示 `spent` 还是 `unknown`？为什么不能直接释放？（答案：`unknown`；避免把不确定成本当成零。）

## 4. 证据：`src/eeg_scientist/evidence.py`

- `EvidenceStore.add_text`：按正文 SHA-256 生成 `ev_<12hex>`；保存 URL、标题、抓取时间、字符数、全文。
- `read`：只接受已登记 ID 和显式字符范围；每次读取追加 `injections.jsonl`，记录范围与切片哈希。
- `estimate_injection_fraction`：报告“读过多少字符”，但不等于“读懂了全文”。

自测：为什么不能允许 `read_evidence` 接受任意文件路径？（答案：模型可以读取私有文件或凭证；证据边界会失效。）

## 5. 研究回路：`src/eeg_scientist/research.py`

- `SYSTEM_PROMPT` / `_user_prompt`：Scientist 实际看到的全部初始材料。检查它是否包含本任务书、参考答案、生成器机制或旧研究答案；不应包含。
- `_tool_specs`：五个工具的 JSON Schema；`allowed_experiments` 控制实验注册表。
- `_execute_tool`：参数校验 → 执行 → `ToolEnvelope`；错误也作为 tool 消息返回，不丢失 `tool_call_id`。
- `_call_model`：写入 `pending_attempt` → 调模型 → 清除；恢复时把未结算预留标为 UNKNOWN。
- `_save_exchange`：请求（调用前 messages）与响应（content/reasoning/tool_calls/usage/raw）分别落盘。
- `run`：模型请求工具 → 本地执行 → 结果回传 → 继续；`finish_study` 校验 evidence ID 确实被 `read_evidence` 读过。
- `_repair_incomplete_tool_calls`：中断后给缺失的 tool_call 补一条明确的 error，不猜测结果。

自测：如果进程在“模型返回 tool_calls”与“工具结果写回”之间崩溃，恢复后会发生什么？（答案：补 error 结果，不重复执行，不伪造成功。）

## 6. 诊断与报告：`src/eeg_scientist/diagnostic.py`、`flash_report.py`

- 回归检查：原始 99%/50% 表格直接给模型，不预设答案；规则检查只看数值与句子，不是科学评分。
- 两个中性案例：`case_c41a` / `case_a72e` 是别名；私有映射在 `runs/.../PRIVATE_MAPPING.json` 与 `review_only/DIAGNOSTIC_MAP.json`，不进入 prompt。
- `flash_report.py`：只从落盘状态生成索引与结果表，不编造科学结论。

自测：`case_c41a` 的真实 family 是什么？它出现在模型请求里吗？（答案：映射在私有文件；模型只看到 neutral ID。）

## 7. 建议的动手检查

1. 打开 `runs/flash_20261020_0058/research/literature_v1/scientist_input.md`，确认初始输入只有 system + user，没有任务书。
2. 打开 `messages.json`，找一条 assistant tool_calls 和下一条 tool 消息，核对 `id` 与 `tool_call_id` 一致。
3. 打开 `evidence/injections.jsonl`，与 `final.json` 的 `evidence_ids` 对照。
4. 打开 `budget.json`，把 `spent_cny` 与 `history` 中每次 settle 相加核对。
5. 运行 `pytest tests/test_flash_stack.py -q`，看离线失败模式是否仍被覆盖。
