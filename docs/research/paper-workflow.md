# 从论文制题到比较完整报告

从已安装项目的环境运行下面的命令，也可以用 `python -m eegfm` 代替 `eegfm`。这三步只处理本地文件。把工作目录、论文、参考和调用记录放在 Git 之外；研究者只接收审阅过的公开题包和既有 runner 允许的资源。

```sh
eegfm paper prepare --paper paper.txt --resources resources.json --policy policy.json --out WORK
eegfm paper freeze --work WORK --review review.json
eegfm paper compare --work WORK --report report.md --out COMPARE
```

**1. 准备。** `paper.txt` 是严格 UTF-8 的论文全文，保留原始换行。`resources.json` 描述实际可执行条件；下面是格式示例，请替换为自己的资源：

```json
{
  "schema_version": "paper_resources_v1",
  "task_id": "residual-probe",
  "revision": "r01",
  "paper": {"title": "Paper title", "version": "v1", "uri": "https://example.org/paper-v1"},
  "scope": {
    "dataset": "available dataset", "model": "available model", "split": "held out",
    "conditions": {"cohort": null, "checkpoint": null, "head": "linear", "preprocessing": null,
                   "representation": null, "metric": "balanced accuracy", "inference_unit": "participant"}
  },
  "resources": ["Existing runner and its documented inputs"],
  "constraints": ["Keep the runner's fixed split"],
  "budget": {"max_runs": 4},
  "resource_text": "Describe what the researcher can actually run."
}
```

七项条件都要提供；未知条件写 `null`。最小政策为 `{"schema_version":"paper_workflow_policy_v1","provider_id":"your-bridge-id"}`，可加非敏感的 `provider_metadata`。默认 `timeout_seconds=900`、`segment_chars=4000`，准备/比较请求上限 `max_prepare_requests=8` / `max_compare_requests=80`，判定上限 `max_judge_calls=64` / `max_judge_pairs=256`，论文/参考/报告字符上限 `max_paper_chars=128000` / `max_reference_chars=16000` / `max_report_chars=32000`。超限不自动放宽。论文、资源、政策文件须位于 `WORK` 之外。首个请求前，`inputs/IDENTITY.json` 绑定论文和资源的原始字节及解析后的完整政策。准备阶段从论文选一个连续的逐字参考段，按与报告相同的契约抽取主张；参考保留论文自己的条件。换题、换源或换政策时，在新目录用 `--parent WORK`，沿用 `task_id`、改 `revision`，并在新政策中写 `revision_reason`。

**交付请求（准备和比较共用）。** 命令返回 exit 3 时，读取输出目录 `pending.json`（或 stdout 的 `pending` 列表）。每项给出相对该目录的 `request_path`、`response_path` 和 `request_sha256`。外部 bridge 从 `requests/<sha>.json` 读取完整请求，按其中的 `instructions`、`data` 和 `response_contract` 运行，向 `responses/<sha>.json` 交付现有 call record，字段如下：

| 字段 | 值 |
| --- | --- |
| `request`, `request_sha256` | 原请求对象及其原有哈希 |
| `raw_response`, `response_sha256` | 原始响应字符串及该字符串 UTF-8 字节的 SHA-256；无原文的终端服务失败两项均为 `null` |
| `status`, `failure` | `complete` / `truncated` / `service_failure` / `invalid_output`；通常 `failure` 为 `null`，无原文的服务失败和带原文的无效输出填写 `{"type":"…","message":"…"}` |

原样保留响应，包括换行和空白；只有 `pending.json` 是可更新的视图。消费响应时，`requests/<sha>.response-sha256` 绑定响应文件的完整字节，重入会校验。一次只由一个调用者推进该目录，bridge 在原子交付后再重跑同一命令；可能陆续出现新的待交付项。未交付不算失败，终端失败不会自动重试。真实模型调用、独立上下文、超时、权限与实际用量记录由外部 bridge 负责；这里的请求上限按唯一请求哈希计数。

**2. 审阅并冻结。** `prepared` 后，独立审阅者检查 `PREPARED.json` 的拟公开题包、原文锚点、资源适配和参考抽取。外部 `review.json` 提供 `schema_version: "paper_workflow_review_v1"`、`prepared_sha256`（`PREPARED.json` 原始字节）、`paper_sha256`（论文原始字节）、`reviewer_id`、`reviewer_kind`（`ai` 或 `human`）和字符串 `notes`。以下四项须经审阅确认为 `true`：`question_source_supported`、`adaptation_and_resources_correct`、`public_no_answer_leakage`、`reference_faithful_unknowns_preserved`。在首次释放题目前，把 `FREEZE.json`、`public-task.json` 和既有 runner 的公开接口绑定到运行记录；只向研究者交付公开内容。冻结文件本身不能证明释放顺序。

**3. 比较。** 用既有 runner 做研究后交付完整、未改写的 UTF-8 最终报告。报告、可选 `--evidence evidence.json` 及其中的文件都须在 `COMPARE` 之外；两个工作目录不得嵌套。可信调用者可在证据 JSON 中提供 `evidence_verdicts`（含 `claim_id` 和 `status` 的对象列表，状态为 `valid`、`invalid` 或 `pending`）、`process_checks`（对象）和 `artifacts`（含 `path`、`sha256` 的对象列表，相对路径以证据清单为准）。报告自述不能授予数值或流程信用。先读 `COMPARISON.md` 的具体条件差异与锚点，再查 `assessment.json` 的原始结果和有序调用、`report.txt` 的完整原文及 `COMPARISON.json` 的终端校验记录。已知条件不相容记为未覆盖，未知条件保留待核查。

| 退出码 | 如何解释 |
| --- | --- |
| `3` | `awaiting_responses`：还有待交付项，`assessment_status=not_run`。 |
| `2` | `input_error` 表示输入或已有文件校验失败，`prepare_failed` 表示准备已终止；命令语法错误由参数解析器报告。 |
| `0` | 本地阶段为 `prepared`、`frozen` 或 `compared`。比较保留评估器原有的 `assessment_status`，可为待评或未完成。 |

运行结果的 stdout 是含 `pipeline_status`、`assessment_status`、`pending` 的 JSON。另看 `scientific_assessment_complete`：须有实际双向判定、已处理的数值证据，以及可信 `process_checks.assessment_status == "complete"`；原始评估状态和流程检查不改写。负结果也可完整评估；若全部不可比、全部待核查或没有可抽取的报告主张，该标记仍为 `false`。这套记录可用于检查一次实际使用，不能单凭本地流程完成宣称已复现论文或已验证评估器。
