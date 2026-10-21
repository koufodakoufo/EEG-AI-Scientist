# EEG-AI-Scientist 整理与评审接口——实施方案（评审稿）

状态：方案与预算草案。**未启动实施，未调用付费模型，未扫描私有数据，未移动旧运行。**
依据：`EEG_HARNESS_REFACTOR_AND_REVIEW_BRIEF.md`、当前仓库源码与 `docs/FILE_INVENTORY.md`、旧 `review_bundle_emotion_20261021`。

## 1. 目标与边界

让用户不依赖 dsh 也能完成：`配置研究 → 启动/恢复 → 查看结果 → 导出评审包 → 导入反馈 → 选择反馈供 Meta`。同一新问题、同一材料、同一规则下，后续比较 Flash、一个 Claude、一个 Gemini，各两次。

不做：全面重写、通用多代理平台、自动无限 Meta、PDF/OCR 平台、真实 EEG 大训练。旧 `runs/`、`reports/`、旧 review 包**不搬迁、不改写**。

## 2. 复用与修改

### 直接复用

| 模块 | 复用方式 |
|---|---|
| `research.py::ResearchRunner` | 继续作为唯一的模型工具调用/恢复/`finish_study` 核心；只改接 StudySpec 和中性模型类型。 |
| `evidence.py` | 同一材料包、来源快照、字符区间和注入记录。 |
| `ledger.py` / `storage.py` | 预算预留、usage 结算、UNKNOWN、哈希链事件、原子写。 |
| `run_manifest.py` | 运行来源；新增 proposal/review 绑定，不重写。 |
| `meta.py` + `schema.py::ResearchRule` | 复用 Trigger/Action/Boundary/Evidence 结构和结构校验。 |
| `backends.py` / `deepseek_api.py` | 已有模型/工具分离和 Flash 客户端；工具端仍用 DeepSeek Search/Fetch。 |
| `emotion_experiment.py` | 作为旧情绪研究的兼容入口保留；不把旧逻辑复制成新平台。 |

### 最小新增/修改

| 文件 | 改动 | 规模 |
|---|---|---|
| `src/eeg_scientist/study_spec.py` | 新增 `StudySpec`/`ProposalRecord`/`ReviewRecord`/`RuleCandidate` 的 Pydantic 模型；严格字段，不用 `object/Any` 做核心边界。 | 中 |
| `src/eeg_scientist/study_runtime.py` | 薄编排层：读 StudySpec、arms、材料、规则、预算；调用现有 `ResearchRunner`；写 proposal ID。 | 中 |
| `src/eeg_scientist/study_cli.py` | 只实现 `study init/validate/run/status/report` 与 `review export/import`、`meta propose`；旧 CLI 保留。 | 中 |
| `src/eeg_scientist/review_io.py` | review packet 导出、Markdown 导入、原文/结构化双存、proposal hash 绑定、feedback-set。 | 中 |
| `src/eeg_scientist/anthropic_api.py` | Anthropic Messages 适配器：tools、tool_result、thinking、raw/usage。 | 中 |
| `src/eeg_scientist/gemini_api.py` | Gemini `generateContent` 适配器：functionDeclarations/functionResponse、usage、raw。 | 中 |
| `backends.py` | 后端工厂按 provider 选适配器；`verified` 只在真实连通性调用后由人设置。 | 小 |
| `research.py` | 接受中性 `ModelChatClient`，不再假定 `DeepSeekChatResult` 的厂商名。 | 小 |
| `run_manifest.py` | 记录 `proposal_id`、正文 SHA、review packet/feedback set 版本。 | 小 |
| `cli.py` | 增加顶层 `study`/`review` 组；旧 `emotion-study`/`overnight-flash` 保持。 | 小 |
| `README.md` / `docs/architecture.md` | 一个当前入口图、三条常用命令、旧研究索引。 | 小 |

不改：`runner.py`、`study.py`、`provider.py`、旧 `prompts/`、旧 `reports/`、旧 `runs/`、旧 `review_bundle`。

## 3. 新研究布局（只约束未来）

```text
studies/<study_id>/
  study.json          # 唯一入口：问题、任务类型、材料版本、arms、规则、预算、选择策略
  task.md             # 问题与交付要求
  materials/          # 本材料包（引用 configs/materials 的冻结版本）
  runs/<run_id>/      # 复用现有 ResearchRunner 的运行目录
  reviews/            # packet、raw feedback、structured records、feedback-set
  meta/               # 候选规则/决策
  snapshots/          # 同 study 共享的不可变代码/配置快照
  report.md           # 唯一当前阅读入口
```

旧 `runs/`、`reports/` 不移动；新增 `docs/history/STUDY_INDEX.md` 记录旧研究路径、冻结哈希、布局版本，以及“无 code_snapshot”的旧 manifest。旧 `proposal_01` 等只是批次展示号，不作为永久 ID。

## 4. 统一入口与命令

```text
eeg-scientist study init     --id <study_id>
eeg-scientist study validate --study <study_id>
eeg-scientist study run      --study <study_id>        # 付费；需显式 --confirm-cost
eeg-scientist study status   --study <study_id>
eeg-scientist study report   --study <study_id>
eeg-scientist review export  --study <study_id> [--run <run_id>]
eeg-scientist review import  --study <study_id> --file <feedback.md>
eeg-scientist meta propose   --study <study_id> --feedback-set <version>
```

`init/validate/status/report/review export/import` **不调用模型**。`run/meta propose` 需 `--confirm-cost`，并在启动前打印预算和模型状态。旧命令保留：

```powershell
.\.venv\Scripts\python.exe -m eeg_scientist.cli emotion-study status --config configs/studies/flash_emotion_20261021.json
```

## 5. 固定提案版本与评审

### Proposal

```text
proposal_id = "p_" + sha256(canonical proposal body)[:16]
```

记录：`proposal_id`、`study_id`、`run_id`、arm、正文路径/正文 SHA、创建时间、批次内盲号（如 B01）。盲号只属于该 packet；packet manifest 绑定 `proposal_id` + 正文 SHA。**旧 proposal_01..04 不改名、不重绑**；新导出使用内容哈希。

### Review packet

`review_packet.md` + `packet.json` + `proposals/B01.md...` + 协调者侧 `key.json`（不进评审包）：

- 问题、资源约束、匿名提案正文、约 300 字辅助摘要、至多 5 条关键主张与已读原文片段/来源位置、评审表；
- 隐藏模型名、arm、成本、已有评分；文风可泄露时记录“非严格盲法”；
- `packet.json` 含每个 `proposal_id`、正文 SHA、packet 版本。

### Review record

人工可直接写 Markdown，不要求 JSON。评审标准固定为：证据支持、推理有效、实验区分力、可执行性、研究价值；可读性单列，不用漂亮文字替代科学质量。导入时保存：

- 原始文字（不可覆盖）+ `review_record.json`（reviewer_id/role、时间、是否盲评、是否参与开发、proposal_id/正文 SHA、三问回答、verdict、未审查项、转换者）；
- 可选 accept/revise/reject/uncertain；人类、ChatGPT 手动评审、模型 Reviewer 分别标 `source_type`；
- 冲突意见并列保存，不做多数投票/平均分；
- `feedback_set_v<version>.json` 只列被显式选中、允许 Meta 使用的 review ID。未选中的反馈不进入 Meta。

规则状态至少区分 `candidate` / `structurally_valid` / `evaluated` / `adopted`。结构校验通过不等于效果已验证；`adopted` 必须有人类决定和证据记录。

Meta 只接收 `feedback_set` 和绑定的旧开发轨迹；正式评测题的答案/评审/分数不进入。

## 6. Claude / Gemini 真实适配

统一 `ModelChatClient` 协议，内部结果至少含：content、reasoning/thinking（若返回）、tool_calls、finish_reason、usage、request_id、raw、latency；工具返回保留 tool_call_id。两家的 API 形状不同，适配器负责映射，不改 `ResearchRunner` 的工具语义。

| 后端 | API | 必须保留 |
|---|---|---|
| DeepSeek Flash | Chat Completions | 现有行为 |
| Claude | `/v1/messages` | thinking/text blocks、tool_use/tool_result、stop_reason、usage、raw |
| Gemini | `generateContent` | functionCall/functionResponse、usageMetadata、finishReason、raw |

- 凭据仍从 `credentials/claude.env`、`credentials/gemini.txt` 显式读取；只记录变量名/文件存在性，不打印。
- 配置中的 Claude/Gemini `model_name` 目前为 null：必须先填实际可用 model ID；`study validate` 对未验证后端报错，不允许静默 fallback。
- 本轮**不**做真实连通性调用；适配器先做离线契约测试（mock transport/录制响应）。只有一次真实、计费的连通性测试成功后，才可人工把状态改为 `verified`。
- Search/Fetch 仍由 DeepSeek 工具端执行；即使 Scientist 换成 Claude/Gemini，工具接口不变。
- Gemini 模型必须填实际可用的 model ID；免费层/付费层的数据条款分开记录。若发生限流，按既定重试策略等待或标记阻塞，不换模型。
- 正式主比较固定 6 次（3 模型 ×2）；若另测规则作用，另加 2 次 Flash 原规则，共 8 次，但必须作为独立比较、且在查看正式结果前决定。
- 本方案不把 Claude/Gemini 与 Flash 的 token 数、reasoning 参数当作“同等算力”；只报告实际用量和费用。

## 7. 冻结、恢复与旧研究可读

- `study init` 只生成未冻结模板；`study validate` 检查配置/材料/规则/凭据引用。
- `study run` 生成 `study_manifest`：代码快照、依赖锁、prompt/规则/材料哈希、模型返回 ID、预算、proposal ID；恢复时逐项校验，不一致则拒绝或要求新版本。
- 旧 run 没有 code_snapshot：在 `docs/history/STUDY_INDEX.md` 标 `legacy_no_code_snapshot`，不回填、不改写、不重编号。
- 旧 review packet 保持原样；新 exporter 只对旧包做显式 `--legacy` 读取，新包才用 `proposal_id`。
- 旧 `emotion_experiment.py`/`overnight-flash` 仍可运行；新 `study` 入口是新增层，不替换旧逻辑。
- 每批研究只有一个 `report.md`；不再新增多个语义相同的 FINAL/NEXT/HANDOFF。旧文件归档只写索引，不物理搬迁。

## 8. 验收步骤

1. 无 dsh、无网络：`--help`、`study init`、`study validate`、`study status`、`review export`、`review import` 全部可跑；不产生模型请求。
2. 用一个旧 proposal 与一份示例 Markdown 反馈，完成 export→import→feedback-set；重生成 report 后 `proposal_id`/正文 SHA 不变。
3. 已完成 run 恢复：0 新请求、0 新费用；修改代码/材料/规则后恢复必须报版本不一致。
4. Claude/Gemini：无凭据/未验证时 `study validate` 失败；mock 契约测试通过不代表 verified；只有一次真实连通性调用成功后才标记。
5. 旧 `runs/`、`reports/`、旧 answer/hash、失败尝试、旧预算和用户 `.gitignore`/未跟踪文件保持不变。
6. 审核包只含配置/prompt/规则/依赖锁/报告/评审记录；不含密钥、`.venv`、缓存、私有映射、未授权数据。

## 9. 用户最后可自己运行的命令（实施后）

```powershell
cd X:\projects\EEG-AI-Scientist
$py = ".\.venv\Scripts\python.exe"

& $py -m eeg_scientist.cli --help
& $py -m eeg_scientist.cli study validate --study emotion_compare_2026xx
& $py -m eeg_scientist.cli study status  --study emotion_compare_2026xx
& $py -m eeg_scientist.cli review export --study emotion_compare_2026xx
& $py -m eeg_scientist.cli review import --study emotion_compare_2026xx --file .\feedback\reviewer_A.md
& $py -m eeg_scientist.cli study report  --study emotion_compare_2026xx

# 以下命令会调用付费模型；实施后由你确认预算再运行
& $py -m eeg_scientist.cli study run --study emotion_compare_2026xx --confirm-cost
& $py -m eeg_scientist.cli meta propose --study emotion_compare_2026xx --feedback-set v1
```

## 10. 预算草案（不含本轮）

假设：同一冻结材料/规则；每 run 6–8 次模型调用；每次约 12–20k input、2–3k output；正式 3 模型 ×2 次；不做全排列。主配置优先 Claude Opus；Sonnet 只作为你明确选择的降级，不静默替换。

| 项目 | 估算 | 说明 |
|---|---:|---|
| 实施/离线测试/评审导入导出 | ¥0 API | 不调用付费模型 |
| 连通性检查（Flash+Claude+Gemini 各一次小请求） | ¥3–5 | 计费、记录实际 model ID/usage |
| Flash 2 次正式 | ¥1–2 | 按峰值价 ¥2/¥8 每 M，实际可能更低 |
| Claude Opus 2 次正式（主配置） | ¥25–45 | 需按官方当日价与 model ID 复核；6–8 calls/run |
| Claude Sonnet 2 次（明确降级方案） | ¥6–12 | 不静默替换 Opus；需你确认 |
| Gemini 2 次 | ¥2–6 | 免费层/实际配额依账户；不假定旗舰免费 |
| 可选：另加 2 次 Flash 原规则方法对照 | ¥1–2 | 独立比较，不能由模型差异推出 Meta 有效；须在看正式结果前决定 |
| 预留 20% | 上述合计的 20% | 限流/重试/未知 usage |

建议：
- **Opus 方案总 cap ¥75**（含连通性、可选 Flash 对照和 20% 预留；按上限估算，实际通常更低）；若实际报价使单 run 预计超过 ¥25，先停下重新预算。
- **Sonnet 方案总 cap ¥35**；只在明确接受“不是 Opus 对照”时使用。
- 任何情况下不自动提高 cap，不把免费层当已验证；预算不足时保存已有结果并记录阻塞。
- 第一步“专家反馈→提案修订”的开发调用另计，最多 1 次 Flash，≤¥2；不与正式六次混表。

## 11. 本轮状态

- 本文件是方案，不是已实现命令；未修改源码，未启动付费研究，未读取私有数据，未改动旧运行或用户未提交内容。
- 下一步由你选择：先实施离线层（入口/评审/版本/适配器 mock），还是同时准备正式对照。
