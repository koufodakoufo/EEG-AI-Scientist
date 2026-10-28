# 2026-10-22 A 部分核验记录

范围：`DSH_NEXT_TASK.md` 的 A1–A4。未启动新科研，未扫描 `daily-emo-eeg`，未 push，未调用任何付费模型，未执行 B 的目录迁移。原始实验回答、`messages.json`、`scientist_input.md`、账本、旧评审、事件日志保持原字节（见 §6）。

## 0. 执行身份与起点

- 仓库：`X:\projects\EEG-AI-Scientist`，分支 `overnight/flash-20261020-0058`。
- 未发现仓库级 `AGENTS.md`（根目录无此文件）；本轮遵循 `DSH_NEXT_TASK.md`、`CODE_AUDIT.md` 和根目录 `HANDOFF.md`。
- 起始工作区只有用户既有的 `.gitignore` 暂存/未暂存修改、未跟踪的会议包 zip 与解压目录；本轮未改动它们。
- 起始测试基线：`77 passed in 20.74s`。
- 起始复现：用 `meeting_20261022/audit/probe_current_code.py` 对当前源码运行，输出与包内 `probe_findings.json` 一致（规则未进入消息、缺失 `unresolved` 仍 accepted、arm 解析为 `repeat_01`、导出表单无法导入、相同正文误绑、Claude 签名丢失/截断未识别、Gemini 签名丢失/用量 14≠20、completion 4≠10）。

这些是“修复前”证据；本轮所有修改都在这之后进行。

## 1. A1：任务与规则进入实际请求

修复内容：

- `task.md` 成为实际任务正文；`question` 仅作元数据/旧运行回退。
- 规则正文以带版本标签的段落嵌入 system 消息；单独保存规则快照。
- 新增 `input_snapshot.json`：精确 system/task/rule 文本、材料 manifest、完整工具定义、首轮两条消息的 SHA-256。
- 配置了规则但文件缺失、不可读或为空时显式失败。
- 运行冻结后修改 task/rule，恢复运行时拒绝，不补写旧消息。
- 新增离线 `study preflight`：显示各 arm 模型、任务/材料/规则哈希、system/user/prompt 哈希和实际提示 diff；不同规则文件但有效正文相同时，preflight 与 `study run` 都拒绝。

发送边界证据（`tests/test_input_provenance.py`）：

- 用模拟客户端捕获完整两次请求；第一请求 system 含 `RULE_SENTINEL_ALPHA`、user 含 `TASK_SENTINEL_ALPHA`。
- 换成 B 标记后，只出现 B 标记；去掉时间字段和路径字段后，两次 user 正文一致，system 只差规则标记。
- 规则快照文件 SHA、`run_manifest.rule.sha256`、`input_snapshot.rule.snapshot_sha256` 三者相等。
- `input_snapshot.request.system_sha256`/`user_sha256` 与捕获到的首轮请求相等。
- `scientist_input.md` 同时包含规则和任务原文。
- `requests/request_001.json` 保存完整 `tool_specs`，而不只是工具名。

独立探针（`audit_20261022/probe_fixed_code.py` → `probe_findings_after.json`）：

```text
task_in_user: true
rule_in_system: true
manifest_rule_sha256 == snapshot_rule_sha256 == rules/probe_rule.md SHA-256
input_snapshot.request.system_sha256 == actual system SHA-256
scientist_input_has_rule: true
rule_injected_into: "system"
```

preflight 证据（`tests/test_study_controls.py`）：

- baseline 无规则 vs meta 规则：`ok=true`，两个规则哈希不同，diff 含 `Applied research rules`。
- 两个不同规则文件正文相同：`rule_contrast.requested=true`、`valid=false`；`run_study` 抛 `preflight rejected`，且没有创建 `runs/`。
- 两个 arm 共用同一规则文件：不当作规则对照，提示一致。

## 2. A2：可直接填写并导入的评审表

修复内容：

- 每个 proposal 导出一份自包含 `forms/Bxx.md`：正文在 `<!-- BEGIN REVIEW -->` 之前，之后是身份、固定绑定字段、三个问题和 unreviewed 区。
- packet 另有 `review_packet.md` 概览；评审字段不出现 arm/model/repeat。
- 绑定使用 packet_id + display_id + run_id + 完整 body SHA-256；导入额外核对 body 文件哈希与运行 `state.json`。
- 不同 run 相同正文时，按 display 选择对应 key，不再按 proposal_id 取第一个。
- arm/repeat/run_id 优先读 `state.json`/`run_index.json`；旧记录缺少字段时回退到 `runs/<arm>/repeat_XX` 路径并记录 `binding_source=path`。
- 跨 study 的 packet、被改正文、display 与 proposal 冲突、state run_id 冲突都拒绝。
- 原始 Markdown 与结构化 record 分存；重复导入相同内容返回 `unchanged`。
- feedback_set 版本不可被不同内容覆盖；相同内容重复选择只读返回；新选择用新版本。
- 未知单次运行费用保存为 `null`，概览显示 `unknown`，不写 0。

证据（`tests/test_review_roundtrip.py`、`tests/test_study_review.py`）：

- 直接对 exporter 生成的表单只填身份和三个答案即可导入；record 的 packet/display/proposal/run/body SHA 全部与 packet/key 对应。
- 两个 run 正文完全相同：两个 proposal_id 相同，但 B01→`review_test__baseline__01`、B02→`review_test__meta_rule__01`。
- 交换 display 被拒绝；换到另一 study 的 packet 被拒绝；正文被改被拒绝；state run_id 被改被拒绝。
- 同一表单重复导入：第二次 `unchanged`，只有一个 raw 和一个 record。
- `v1` 已选 review A，再以 `v1` 选 B 被拒绝；`v2` 可以创建；重复 `v1` 相同内容返回 `unchanged`。
- 未知费用：packet/key 中 `cost_cny=null`，概览含 `unknown`。

独立探针：3 份表单全部填好导入，绑定分别为 baseline/meta_rule/third_arm；前两份正文相同仍正确分开；把 B01 表单 display 改为 B03 被拒绝。

## 3. A3：Claude/Gemini 完整工具往返

修复内容：

- `DeepSeekChatResult` 新增 `native_blocks`，`messages.json` 的 assistant 消息保存并回传原始块/part。
- Claude：保留 thinking 与 redacted_thinking 原块及 signature；多个并行 tool_result 合并为一个 user turn；重复 tool_use id 视为协议错误。
- Gemini：保留 functionCall 所在 part 与 thoughtSignature；thought 文本进入 `reasoning_content`，不混入可见正文；工具 ID 按全对话递增生成（`gcall_001`…），跨轮不重复。
- 两个适配器都把 `max_tokens` / `MAX_TOKENS` 映射为 `truncated`；截断的工具参数不执行，重试前检查调用次数/截止时间，预算仍由 ledger  Reservation 控制。
- Gemini `thoughtsTokenCount` 计入计费输出，同时单独记录为 `reasoning_tokens`；Anthropic `cache_read_input_tokens`/`cache_creation_input_tokens` 计入 prompt 总量并保留字段。
- 未知/无效用量仍进入 UNKNOWN，不变成零费用。
- `verified` 未改；所有 Claude/Gemini 后端仍为 `unverified`。

证据（`tests/test_adapter_roundtrip.py`，全部使用 `httpx.MockTransport`）：

- Claude 两次请求：第一次返回 thinking + redacted_thinking + tool_use；执行工具后，第二次请求的 assistant content 原样包含 signature 和 redacted data，随后是配对的 `tool_result`；最终 `finish_study` 成功，`call_count==2`。
- Claude 并行两个 `tool_use`：第二次请求只有一个含两个 `tool_result` 的 user turn，ID 分别为 `toolu_a`/`toolu_b`。
- Claude `max_tokens`：第一次截断 → 第二次请求 `max_tokens=24000` 且不含未完成 tool 结果；第二次仍截断 → failed，未执行部分参数。
- Claude 用量：`input_tokens=10 + cache_read=100 + cache_creation=50` → prompt=160；record 保留 cache 字段。
- Gemini 两次请求：第一次两个 functionCall 各带 thoughtSignature；第二次请求的 model turn 原样保留两个 signature，user turn 合并两个 functionResponse；最终 `finish_study` 成功。
- Gemini 跨三轮：ID 为 `gcall_001`、`gcall_002`、`gcall_003`，无重复。
- Gemini 用量示例：prompt 10、candidates 4、thoughts 6、total 20 → 计费 completion=10、total=20、reasoning=6。
- Gemini `MAX_TOKENS`：`truncated=true`，原生 part 与 signature 保留。

独立探针：Claude signature/redacted 均回传、`truncated=true`；Gemini signature 回传、`truncated=true`、ID `gcall_001`、total 20 / completion 10 / reasoning 6，thought 文本不在 visible content。

## 4. A4：边界收紧

- `finish_study`：`answer` 必须是非空字符串；`evidence_ids` 必须是字符串列表；`unresolved` 必须存在且为字符串列表，允许显式 `[]`；类型错误/缺失/空项都拒绝。
- accepted 语义仍是“程序协议检查通过”，`report.md` 明确写出这一点，并在运行表同时显示 phase、accepted、acceptance、stop reason。
- 项目根解析新增 `paths.project_root()`：支持 `EEG_SCIENTIST_ROOT`、从当前目录向上查找、从包位置回退；`study`/`review` 在 `group-meeting/` 子目录启动也定位同一仓库。
- 通用 `study init` 不再引用任何 emotion/archive 路径或日期；旧材料只能通过显式 `--template emotion_20261021` 选择。
- 未引入 PDF、向量检索、skill 系统、自动 Reviewer 或新 Meta 平台。

证据（`tests/test_finish_contract.py`、`tests/test_study_controls.py`）：

- 8 种缺失/类型错误参数全部拒绝且不写 `final.json`；显式 `unresolved: []` 可 accepted。
- 截断两次的 run 为 failed，没有 tool 消息、没有 `final.json`；调用上限为 1 时只发 1 次请求，不做超预算重试。
- 从 `group-meeting/` 导入 `study_cli` 得到 `ROOT=X:\projects\EEG-AI-Scientist`；临时嵌套目录也能解析到含 `pyproject.toml`+`src/eeg_scientist` 的根。
- 通用 init 的 spec 路径不含 `emotion`/`archive`，`question=""`，材料 manifest 为空，validate 报“没有材料”而不是暗中使用旧材料。

## 5. 测试与探针命令

```powershell
cd X:\projects\EEG-AI-Scientist
$py = ".\.venv\Scripts\python.exe"

# full offline suite
& $py -m pytest
# 114 passed

# post-fix probe (temp dir only, no model call)
& $py audit_20261022\probe_fixed_code.py --source-root src

# historical rule-injection audit (read-only)
& $py audit_20261022\verify_historical_rule_absence.py

# historical byte-identity check
& $py audit_20261022\verify_payload_hashes.py
```

结果文件：

- `audit_20261022/probe_findings_after.json`
- `audit_20261022/historical_rule_absence.json`
- `audit_20261022/hash_comparison.json`
- `audit_20261022/pytest_after.log`

## 6. 旧实验未被改写

- 修复前基线：`audit_20261022/before_hashes.json`，覆盖 `archive/` 830 个文件 + `meeting_20261022/originals/` 8 个文件，聚合 SHA-256 `8e107e59de6e2f00142184afc8d0e141a6080b51b6362ba8edad585ee6f2aa23`。
- 修复后核对：838/838 个原文件字节相同，无 changed、无 missing。
- 唯一新增：`archive/experiments/emotion_20261021/CORRECTION_20261022.md`（追加更正说明，不是原始回答/消息/账本/评审/事件）。
- 2026-10-21 会议包 zip 与解压目录未修改。

## 7. 旧 Meta 干预结论（更正）

见 `docs/CORRECTION_20261022_META_INJECTION.md`。要点：10 次归档尝试的规则快照都存在，但规则正文 0/10 进入 system、0/10 进入 user、0/10 出现在 `scientist_input.md`；10 次的归一化 system/user 哈希各只有一组。因此不能把 baseline/meta 的输出差异归因于规则，相关因果表述撤回。旧文件未补写。

## 8. 剩余限制

1. **没有真实 Claude/Gemini 调用。** 模型 ID、凭据、价格、thinking 参数和真实网络连通性均未验证；后端仍为 `unverified`。离线协议通过只说明“离线协议验证通过”。
2. **原生块回传仍是离线契约。** Claude thinking signature、Gemini thoughtSignature 的保存/回传路径已测，但具体模型是否接受完整 thought part、特定模型的 thinking 配置仍需真实调用核对。
3. **评审只覆盖新 study。** 归档研究的评审导出/导入属于 B；本轮没有为旧档案复制运行或伪造 key。
4. **单次运行费用仍可能未知。** 现有账本按 arm 累计，不按 repeat 拆分；仅在 `final.json`/`state.json` 显式含 `cost_cny` 时显示数值，否则为 null/unknown。
5. **没有真实 EEG 内环，也没有有效规则对照。** 本轮未宣称 self-improvement/RSI 已验证。
6. **B 未做。** 目录迁移、归档评审绑定、旧材料路径统一 resolver 等在组会后单独处理。
7. **旧运行不能“修复后重放”。** 冻结输入检查会拒绝没有快照的旧运行被补写规则；需要新 study/run 才能检验规则效果。

## 9. 本轮改动文件

源码：`src/eeg_scientist/{research,study_runtime,study_spec,review_io,anthropic_api,gemini_api,deepseek_api,run_manifest,backends,study_cli,paths}.py`

测试：`tests/test_input_provenance.py`、`test_review_roundtrip.py`、`test_adapter_roundtrip.py`、`test_finish_contract.py`、`test_study_controls.py`（并保留、原样通过原有测试）

文档：`README.md`、`HANDOFF.md`、`docs/architecture.md`、`docs/COMMAND_REFERENCE.md`、`studies/README.md`、`docs/CORRECTION_20261022_META_INJECTION.md`

审计：`audit_20261022/`、`archive/experiments/emotion_20261021/CORRECTION_20261022.md`

## 10. 审核包

- 文件：`EEG_AI_Scientist_Review_20261022.zip`
- 内容：源码、测试、脱敏配置、`pyproject.toml`/`uv.lock`/`.python-version`、文档、审计证据；另含一个合成 prompt 夹具和两份旧 study 配置/锁记录（`emotion_20261021`），用于让一个既有 provenance 测试在包内独立通过。
- 排除：`credentials/`、实验回答/消息/账本/评审/事件、`meeting_20261022/` 输入包与旧 zip、`group-meeting/`、`.venv`、缓存和 git 元数据。
- 包内独立运行：解压后 `python -m pytest` → **114 passed**（2026-10-22）。
- 包 SHA-256 由最终交付消息给出（文档更新会改变包哈希，故不在包内自引用）。
