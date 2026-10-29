# 科研主张与证据协议 v3（开发校准版）

2026-10-29，Builder R05。实现为 `framework/eegfm/research_bench/claims_v3.py` 和 `evidence_v3.py`；旧 v1/v2 模块、旧分数和旧产物未改。**本版本已提供确定性契约与合成单元校准；真实报告的语义抽取/judge 校准尚未完成，不是已验收的正式科学评分器。**根执行者应在首个正式 Actor 前冻结本文件、代码、prompt、fixture、运行契约及其哈希；正式语义评分若仍未校准，应标“待审”，不得阻塞已具备协议的真实研究，更不得补造一个已验收总分。

## 1. 输出维度及允许解释

| 维度 | 输出 | 不能替代什么 |
| --- | --- | --- |
| 参考发现覆盖 | 定向支持/覆盖边，P/R/F1 和已覆盖参考 ID | 科研质量总分或参考外主张真伪 |
| 数值/证据有效性 | valid/invalid/pending 主张 ID；绑定与独立重算结果 | 因果机制验证、实验设计正确性 |
| 参考外但有证据的发现 | 所有给定参考均判 not_covered，且可信证据有效的独立列表 | 扩充私有 gold，或事后把新发现写回参考 |
| 矛盾 | 同条件参考矛盾与 evidence-invalid 分列 | 把参考未提到解释为错误 |
| 缺证据 | 无参考支持、无有效证据的列表 | 将未知事实宣布为错误 |
| 过程质量 | 命名检查项及证据，例如隔离、预注册、被试划分、对照、重放、预算 | 任意权重拼成“taste/科学能力”总分 |

未完成、冲突或缺失的语义判定令参考指标为 `null`，同时保留已确认边。真正完成的空报告对有效参考给出 0；外部服务失败导致空输出给出 `null`，不能当能力零分。空参考不能给分。不同 kind/split/条件的 supported 或 contradicted 边被拒绝。

## 2. 原子单元与抽取审计

一条原子主张包含：`claim_id, kind, scope, subject, predicate, direction, qualifiers, payload, source_spans, evidence_ids`。scope 强制包含 dataset/model/split/conditions，conditions 是 JSON 对象。payload 只允许一种类型：

```json
{"kind":"point","payload":{"metric":"accuracy","estimate":0.5,"unit":"fraction"}}
{"kind":"interval","payload":{"metric":"accuracy","low":0.4,"high":0.6,"level":0.95,"method":"cluster percentile","unit":"fraction"}}
{"kind":"mechanism","payload":{"relation":"明确的一项机制解释"}}
{"kind":"qualitative","payload":{"statement":"明确的一项定性断言"}}
```

点估计、置信区间和额外机制解释即使同处一句话，也分别抽取；不同 context、层、对照、模型或目标也不能装进同一数值 payload。保留“本数据/规定干预/未发现证据”等限定。结构验证不能证明自由文本真正原子化，仍需独立语义校准。

`build_extraction_plan(report, source_id, segment_chars=4000)` 生成连续、不丢字符的主片段及前后各最多 1000 字上下文。只允许抽取源 span 位于当前主片段的主张；邻接上下文只用来补足条件。每片段声明 complete/truncated/service_failure，附 notes；`assemble_extractions` 要求每片段恰有一个响应、原始全报告 hash 相同、全局 Unicode offset 与 quote 精确一致。完整响应的 canonical claims、每段响应 hash、原始条数、别名和所有源位置均保留。

公开容量：报告最多 2,000,000 字符、最多 512 片段、每片段最多 64 条、总计最多 4096 条。默认 4000 字分段；超限显式报错或 truncated，并保留原始响应供外部审计。不得把 65 条重新捆成 64 条；不得把溢出当完整输出。不存在旧 30 条全报告上限。

去重只合并 kind、scope、subject、predicate、direction、qualifiers、typed payload 完全相同的结构化语义；保留不同源位置及 evidence ID。不会自动把改写后的机制/定性文字视为等价；这需要经校准的外部规范化。拆句/合句不改变 typed payload 的测试已覆盖，但这不等于任意自然语言语义不变性已获证明。

## 3. Prompt、judge 与校准冻结

- 抽取模板：`atomic_segment_extract_v3.0`，常量 `EXTRACTION_PROMPT`。
- 定向判定模板：`directional_scoped_match_v3.0`，常量 `JUDGE_PROMPT`。
- 协议：`research_scoring_v3`；数字公式：`registered_metrics_v3.0`。
- 抽取接口不调用模型；允许外部响应适配器注入。任何修复、重试和失败必须由外部调度另存原始字节及原因，禁止静默更换配置。
- 外部 judge 配置必须冻结 provider/model/revision（如可得）、reasoning、temperature/seed（如支持）、prompt hash、schema、重试策略和独立上下文身份。当前没有填一个未实际执行的模型配置，`semantic_model_calibration=not_run`。
- fixture 位于 `framework/tests/research_bench/fixtures/scoring_v3_calibration.json`，完全虚构，覆盖点/区间、拆合句、重复、空提交、新发现、不同 split、外部失败、截断、机制越界、被试 bootstrap。执行性测试在 `test_protocol_v3.py`。fixture 的人工 oracle 是 Builder 开发标准，不是假装独立盲审。

在语义抽取器/判定器用该 fixture（及必要扩充的非本任务开发集）达到预先写明的一致性要求之前，不发布正式文本评分。不得读当前真实 holdout 后再调整模板、规则或 skill，并把重算当确认性证据。R05 没有调用模型 judge、没有读取本轮真实 EEG 科学输出。

## 4. 每项指标的精确绑定

`audit_metric_binding(binding, artifact_root, trusted_split_manifest, expected_run_id=..., trusted_receipt=...)` 是离线数值审计。controller 提供可信 manifest 和执行 receipt；Actor 提交同名 JSON 不能让它获得可信身份。

```json
{
  "schema_version":"split_manifest_v3", "run_id":"fixture",
  "samples":{"b":{"subject_id":"S1","split":"validation"},"c":{"subject_id":"S2","split":"validation"}}
}
```

```json
{
  "binding_id":"e1", "run_id":"fixture", "split":"validation",
  "artifact_path":"predictions.csv", "artifact_sha256":"<64 hex>",
  "split_manifest_sha256":"<canonical JSON SHA256>",
  "row_selection":{"indices":[0,1],"sample_ids":["b","c"]},
  "row_conditions":{"layer":"4","feature":"declared_feature"},
  "calculation":{"name":"accuracy","columns":{"prediction":"pred","target":"label"},"parameters":{}},
  "reported_value":0.5
}
```

receipt 形如 `{"run_id":"fixture","status":"completed","exit_code":0,"artifacts":{"predictions.csv":"<hash>"}}`。数字 0 与布尔 false 区分。CSV 强制唯一表头及 sample_id/subject_id/split；指标列另显式指名。索引从 0 开始，不含表头；sample IDs 与索引同序且不得重复。artifact hash 在解析前后核对，文件链接/硬链接和路径逃逸被拒绝；上限 64 MiB / 200,000 行。

无论文件是否混合 split，必须明确选择行。每个被选样本/被试/split 与可信 manifest 一致；同被试在可信 manifest 跨 split 会整体拒绝。`expected_sample_ids` 可由 evaluator 进一步固定全部分析队列，防止只挑部分样本。split 授权在读文件前检查，test 默认禁止；最终可信评估可显式加 test。返回不包含行内容或测试样本名单。

公式名单为 mean、accuracy、balanced_accuracy（至少两个已观察类别）、mse、r2（常量目标无定义并拒绝）、paired_mean_difference（after-before）、cluster_bootstrap_mean_ci。最后一项公开参数 seed/iterations/level，使用 Python `random.Random` 按排序被试 ID 有放回抽取同数目完整被试组；每次保留各组全部行，再求行加权均值，区间为线性插值分位数，iterations 2–10,000。这是明确的一种 bootstrap 估计量，不自动等同于任意报告的 bootstrap。

数值比较默认可信 `atol=1e-8, rtol=1e-6`；不是 Actor 自选 tolerance。新公式必须先实现/校准/冻结，再用于正式结果。当前只支持 CSV 数值指标；任意 NPZ/JSON、自由表达式、复杂机制判断不被伪装成自动验证。

**信任边界：**重新计算文件中 target 列不能证明它就是原始真标签。可信 worker 仍需从冻结数据接口生成/校验标签与特征目标，绑定数据/模型/预处理/代码哈希。当前模块提供完整性、行身份和公式重算，不替代可信数据加载器、隔离或实验有效性审查。机制主张即使关联一个有效点估计，也不能据此成为“证据已验证”；传入 evidence_verdict 的判定器必须保留 claim-kind 与测量范围。

## 5. 运行前公开的重放契约

`validate_replay_contract` 只验证契约结构与 DAG，不执行任何命令。版本 `replay_contract_v3`，必填 run_id、limits、seeded_inputs、commands。limits 声明 max_commands/timeout_seconds/storage_bytes/threads，校验器公开上限 256 commands、4 threads。每条 command 声明 command_id、完整 argv（包含任何 `-B` 或选项）、相对 cwd、完整 env、所有 RNG seeds、depends_on、inputs、writable_paths、outputs。执行者不能事后增加隐藏命令数、特殊必需文件名或选项。

seeded_inputs 是路径→SHA256，必须包括源程序、依赖配置、事前计划等需要预置的文件。每个 generated input 必须来自显式依赖或其祖先输出；缺件、环、未声明依赖、重复输出所有者和覆盖 seeded input 都拒绝。解析器不把路径安全等同于 argv 授权：实际解释器路径、依赖版本、shell/网络限制、环境解析和隔离规则还需 controller 在冻结契约中公开并执行。

科学产物声明 `role=scientific`，比较策略是 exact sha256，或 json_numeric 与事前冻结 atol/rtol；不允许 record_only。诊断产物如时长、时间戳、资源采样、动态文件清单声明 diagnostic/record_only，保留差异，但不能只因为诊断 hash 不同就否定所有科学结果。不得把不匹配的关键科学结果事后改标诊断。

根执行者仍须完成：干净目录预置输入及 hash 核对、按 DAG 运行、限时/限资源、科学 JSON 比较与诊断分离、可信 receipt、篡改/缺依赖失败演示。R05 没有声称完成这条真实 worker 重放；返回状态明确为 `structurally_valid_not_executed`。

## 6. 交付与当前验收状态

本模块的结构/数值合同测试通过；旧分数例子在 `OLD_SCORE_CASE_STUDY.md`。实际根流程是否接入 v3、契约何时冻结、是否通过 Linux 回归、是否完成真实独立重放，由根执行者据现场证据另记。未接入/未校准时，中文报告应写“v3 确定性审计可用，语义评分待审”，而非“科研评分已修好”。
