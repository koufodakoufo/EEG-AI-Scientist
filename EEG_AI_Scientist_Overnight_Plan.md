# EEG AI Scientist Overnight Implementation Plan

> **交给 DSH 的执行计划｜2026-10-18｜版本 1.0**  
> **For agentic workers:** 若当前环境已安装 Superpowers，可用 `executing-plans` 逐项执行；独立开发任务可用 `subagent-driven-development`。未安装时直接遵循本文，不把安装技能当作前置任务。用户已指定 DSH 为执行者，并授权在项目内自主完成开发、运行、检查和修复；常规实施选择无需逐项请示。  
> **Goal:** 在一夜内搭建并运行一个可追溯的 EEG 风格假设诊断闭环，留下真实模型调用、事前预测、实际实验结果、证据更新，以及小规模 S0/S1 方法规则对照。  
> **Architecture:** Python 控制器管理数据、固定实验工具、模型输入、预算与日志。Scientist 仅通过结构化请求选择实验；开发 DSH 可以编写代码，参加评价的 Scientist 看不到生成机制、答案或其他测试案例。  
> **Tech Stack:** Python 3.12 优先；NumPy、scikit-learn、Pydantic、pytest；直接 API 路线按需使用官方 SDK。CPU 优先，无须 GPU。  
> **Spec:** 本文第 1—8 节是实验与工程规格，第 9 节是实施任务，第 10—14 节是操作、验收和恢复指南。

## 0. Danius 先看这一页

今晚的任务是让 DSH **把项目做出来并跑出可审查的研究轨迹**。你暂时不手敲代码；明早挑核心文件学习和审核。

请把本文件保存为：

`X:\projects\eeg-ai-scients\EEG_AI_Scientist_Overnight_Plan.md`

这里沿用你提供的 `eeg-ai-scients` 拼写，不自行改成 `scientist`。本文没有访问你的 Windows 电脑，也没有确认目录内现有文件；DSH 必须先检查实际项目。

**最快操作顺序：**

1. 在 DSH Desktop 中选择这个项目，确认工作目录和你已经设置的权限。
2. 使用第 10 节的 `/plan` 提示词，让她完成一次环境检查与实施计划核对。
3. 睡前批准这份计划，确保已经退出 Plan 模式。
4. 创建第 10 节的 `/goal`，再发送完整执行提示词。
5. 看见一次真实模型调用和一次实际实验完成，并确认没有待处理的审批弹窗，再离开电脑。

**今晚默认时长为“启动后 8 小时”**，按你的电脑实际本地时间计算；这是工作上限，不是必须耗满的时长。目标提前完成就结束。你也可以在启动提示词里改为 6 小时或指定本地截止时间。不要照抄文档日期作为运行截止日期。

明早优先看：`reports/MORNING_REPORT.md`、`reports/RESULTS_TABLE.md`、`reports/CORE_CODE_WALKTHROUGH.md`、`reports/FAILURE_CASES.md`。带给 ChatGPT 审查的材料由 DSH 打包成 `artifacts/review_bundle.zip`。

**四条不能误解的边界：**

- `/plan` 是工作模式，不是另一个基础模型；它的正常流程包含计划审批。
- `/goal` 管理持续目标；自动续跑还依赖当前部署的续跑组件、有效权限、进程、网络和额度。
- DSH Desktop 能聊天，不等于新建 Python 程序已经能调用模型 API。
- 模拟案例跑通，只能说明受控诊断流程可运行；不能据此宣布发现了真实 EEG 规律，更不能宣布完成 RSI。

## 1. 已确定的研究目标与取舍

### 1.1 我们要回答的问题

> 面对 EEG 风格数据中的预测表现，AI 能否提出不同解释，选择能区分解释的实验，先写出预测，再根据实际结果修正判断？从开发案例提炼出的研究规则，能否改善它处理未见案例的行为？

一个典型现象是：随机切分窗口时分数高，换成按试次或被试隔离后分数下降。这个现象可能涉及试次特异信息、采集条件、被试间分布变化、任务信息的个体差异，也可能涉及多个因素。**分数下降本身不能唯一确定机制。**

### 1.2 与四份原始材料的连接

| 材料 | 今晚保留的内容 | 今晚如何落地 |
|---|---|---|
| `selections_deep_chat_about_the_boundry_of_large_language_models_and_math_theories_related.md` | 模型参数与整体系统能力需要区分 | 固定模型，改变研究规则；记录系统版本，避免把上下文变化说成模型权重进化 |
| `selections_measures_and_representations_to_EEG-FM_info_structure.md` | 解码性能不自动等于稳定神经表征；测量、统计结构和语义须区分 | 检查什么信息支持了预测，结论限定到实际测量和实验范围 |
| `general_discussion_about_neuroscience_workmode_gpt.md` | “我们如何知道”；竞争解释、预测、干预和证据链 | 必须保存实验前预测和实验后修正，允许证据不足 |
| `EEG_AI_Scientist_RSI_Idea.md` | Inner loop 产生领域结论，Outer loop 改进研究方法；两类记忆分开 | 保存 `scientific_knowledge` 与 `research_methods`，只做一次冻结的规则更新对照 |

原方案提出的多条 EEG-FM 实验轴、专家评价和 20–50 个完整研究回合，留作后续路线。今晚不训练 EEG Foundation Model，不复现庞大的 AI Scientist 平台，不比较多家大模型，不做自动改权重、JEPA 或递归改进器。

原始聊天中的理论性描述只作为动机和背景，不能直接转写为已验证事实。今晚所有项目结论必须来自本次实验记录。

### 1.3 今晚的成功分层

| 等级 | 必须有的证据 | 可以怎样汇报 |
|---|---|---|
| E0：工程保底 | 数据生成、固定工具、校验、日志、恢复与脚本测试可运行；模型接入可能受阻 | “实验基础设施完成，AI 研究决策尚未完成” |
| E1：最小研究闭环 | 至少一个真实 LLM 决策回合，包含预测封存、实验执行、结果解释 | “完成受控案例上的一次 AI 假设诊断” |
| E2：今晚主目标 | 开发案例 + 冻结 S1 + 至少 4 个未见案例上的 S0/S1 成对运行 | “获得方法规则更新的小规模探索性对照” |
| E3：预算内扩展 | 第二个数据种子，或一个小型真实 EEG 案例 | 分别报告合成案例扩展和真实数据探索 |

E0、E1 是有价值的降级产物，但**不能标记 E2 已完成**。S1 没有更好甚至更差，也完全可以完成 E2；我们要求有效比较，不要求漂亮结论。

## 2. Global Constraints：全局执行约束

1. 工作根目录为 `X:\projects\eeg-ai-scients\`。先读当前目录及适用上级的 `AGENTS.md` 和已有项目说明，记录既有文件与未提交修改；不要覆盖用户工作。
2. 默认只在该项目及其项目专用环境、缓存中写入。不得为此修改用户其他科研项目或原始 EEG 文件，不从其他目录搬走、清理或重命名资料。
3. 用户已授权项目内自主开发、依赖安装、实验运行、测试、文档和本地检查点。若本地 Git 配置可用，可提交本次改动；不推送、不发布、不改全局 Git 身份、不使用破坏性重置。既有未提交修改不得夹带进提交。
4. 不修改 DSH 自身代码、全局记忆、权限策略、账号配置来规避阻塞；不绕过审批或服务限制。外部阻塞采用第 12 节降级路径。
5. Python 的函数参数、返回值、类字段和关键局部变量均写明确类型提示；数组使用 `numpy.typing.NDArray`。外部 JSON 在边界验证为具体模型，核心代码不靠 `Any` 和静默类型忽略拼接。
6. 用户只需看中文报告；代码、变量名和结构化字段使用清楚的英文。报告解释缩写：LLM = Large Language Model，EEG = Electroencephalography，RSI = Recursive Self-Improvement。
7. 采用固定、轻量分类器和特征空间。禁止为了取得某个预期结论临时更换测试种子、隐藏运行或放宽评价规则。
8. Scientist 不能改工具实现、评价脚本、案例生成器或预算。DSH 开发时可修复实现；冻结后修改需版本化并标记受影响运行。
9. API 密钥从显式配置的环境变量或项目本地秘密文件获取；不把密钥写入模型上下文、报告、Git 或审查包，不导出 Desktop 登录令牌。
10. 所有结果区分 `real_llm`、`scripted`、`mock`，以及 `synthetic_features`、`synthetic_eeg`、`real_eeg`。空表和待运行项目不能写成完成结果。

### Review Focus：最容易出错的五处

| 风险 | 必须出现的行为 | 所属任务 |
|---|---|---|
| Desktop 已登录，但 Python 无 API 访问 | 明确区分调用链；失败有降级说明，不能伪造 AI 输出 | T4 |
| trial ID 在不同被试中重复 | 使用全局 trial UID；分组切分真正无交集 | T1、T2 |
| 在拿到结果后才补写预测 | 控制器拒绝没有封存预测的实验；事件序号可审计 | T3 |
| 中断后重跑已完成模型调用或实验 | 从持久状态恢复；不改原日志；不确定调用单独标记 | T3、T5 |
| S1 接触测试结果，或 S0/S1 条件不同 | 冻结规则、输入摘要和实验配置；成对比较；污染运行不当作留出结果 | T5、T6 |

## 3. 系统分工与模型接入

### 3.1 三个角色，不必有三个框架

| 角色 | 做什么 | 能看到什么 |
|---|---|---|
| 开发 DSH | 编写、调试、运行项目，整理报告 | 项目代码、案例生成器、评价真值与开发日志 |
| 被评价的 Scientist | 提解释、选实验、预测、更新结论 | 当前案例的公开观察、工具规格、允许的历史事实和当前研究规则 |
| 确定性控制器与评估器 | 检查请求、执行固定实验、封存记录、核对结果 | 数据与私有清单；只向 Scientist 返回批准的公开结果 |

Scientist 不需要自由终端或完整仓库访问。它提交 JSON 请求，控制器把请求映射到允许的 Python 函数。开发 DSH 知道案例机制是正常的，但**不能将这些知识带入被评价 Scientist 的输入**。

### 3.2 首选：Python 直接调用模型 API

使用用户已经配置并授权的模型服务。先检测变量是否存在，只报告布尔值；随后进行一次极小的结构化输出调用，验证连接、模型名和输出格式。不要凭记忆写死模型名称。

建议配置项：

```yaml
provider: openai_compatible
base_url_env: SCIENTIST_BASE_URL
api_key_env: SCIENTIST_API_KEY
model_env: SCIENTIST_MODEL
temperature: 0
max_output_tokens: 4096
request_timeout_seconds: 120
```

若使用 DeepSeek 官方 API，可按当前官方文档配置相应 `base_url`；已有 `DEEPSEEK_API_KEY` 可在明确配置下使用。温度、JSON 输出和 reasoning 参数是否支持以实际模型为准，任何回退要记录，S0/S1 必须一致。温度 0 不等于绝对可重复；保存原始请求和最终回答是必要的。

不要求记录隐藏思维链。保存可见的结构化理由、预测和结论即可；若服务返回推理 token 用量，纳入成本记录。

### 3.3 备用：DSH 文件交换式 Scientist

当独立 API 不可用时，DSH 可生成 `request.json`，通过当前版本正式支持的独立会话或子 agent 收到 `response.json`，再交给同一控制器执行。这条路线必须先证明：

- 新会话没有继承开发者上下文、真值、生成器源码和测试日志。
- 输入只含当前允许的公开文件；可读工具范围能限制到这些文件。
- 每次响应有独立请求标识、完整消息记录和可辨认的模型信息。
- 无需用户逐个复制请求；DSH 有受支持的编排方式。

**仅在提示词中写“请不要看答案”不构成隔离。** 如果这些条件无法验证，只把该路线作为 `engineering_demo`；可以演示流程，但不提供有效的 Scientist 泛化或 S0/S1 优劣证据。

睡前没有 API 密钥时，你可以让 DSH 指引你在本地安全配置；不要把密钥发给 ChatGPT 或粘贴进普通对话。夜里仍不可用时，先完成 E0 和所有非模型工作，留下待恢复命令。不要整晚研究 Desktop 私有接口或提取登录凭据。

### 3.4 适量使用开发子 agent

若 DSH 当前版本支持且允许，可以把“测试与审查”和“文档与结果整理”分给开发子 agent，最多同时 2 个工作者；主 agent 负责接口和合并。不要让多个 agent 同时改核心文件。**开发子 agent 的结论不计为被评价 Scientist 的独立能力。** 没有子 agent 能力就顺序完成，不安装新平台。

## 4. 案例：先把可检验性做好

### 4.1 默认从 EEG 风格的分层特征数据开始

第一夜不必下载真实 EEG。最小数据是具有“被试—session—trial—window”结构的数值特征，标签在 trial 内一致。它模拟 EEG 研究中常见的依赖关系，**本身不是实测脑电，也不是生物物理 EEG 仿真**。

默认候选规模：16 个被试 × 每人 2 个 session × 每 session 16 个 trial × 每 trial 8 个 window，共 4096 行，每行 32 个特征。每 session 两类 trial 各 8 个。先用更小规模做 smoke test，再在开发阶段校准规模和强度；冻结后不得因留出结果不理想而调整。

每行至少含：

`sample_id, subject_id, session_uid, trial_uid, window_index, label, feature_row_index`

`session_uid` 和 `trial_uid` 必须包含上级身份，不能只拿每个 session 里重复出现的 `trial_01` 分组。

元数据不进入普通分类器的特征矩阵。模拟机制、参数和真值保存在私有 evaluator 清单；公开案例编号使用中性名称如 `case_004`，不能叫 `trial_leakage_case`。

### 4.2 四个案例家族

下面是**给开发者的构造规格**，不直接提供给被评价的 Scientist。

| 家族 | 构造原则 | 预期用于检验的行为 | 不允许的捷径结论 |
|---|---|---|---|
| T：试次签名 | 每个 trial 有独立稳定向量，窗口围绕它波动；trial 标签随机平衡；没有共享任务方向 | 发现共享 trial 的窗口可以帮助预测任意 trial 标签；按 trial 隔离后表现应回落 | “所有 EEG 高分都来自泄漏” |
| G：可迁移任务信息 | 所有被试共享标签相关方向，窗口噪声独立；不加入独立 trial 签名 | 在正确隔离后仍保留任务预测；随机 trial 标签不应稳定可迁移 | “可预测就证明神经语义” |
| D：被试相关的任务映射 | 每个被试有不同任务方向/符号及与标签独立的被试特征；每人类别严格平衡；无独立 trial 签名 | 同被试新 trial 预测可行，未见被试更难；区分域变化与身份—标签捷径 | “能识别被试，所以标签肯定靠身份预测” |
| N：证据不足/纯噪声 | 特征与标签独立，不加入 trial 签名；样本有限 | 允许没有可靠现象，承认当前工具未检出可泛化信息 | “一次接近机会水平就证明数据没有信息” |

一种可读的生成表达式是：

\[
x_{srtw}=a\,y_{srt}v_s+b\,u_s+c\,q_{srt}+\epsilon_{srtw}.
\]

其中标签编码为 −1/+1；`v_s` 为共享或被试相关的任务方向，`u_s` 是与标签独立的被试特征，`q_srt` 是试次签名，`epsilon` 为独立噪声。各家族通过开关这些分量来构造；不同分量最好先放在明确分开的特征子空间，便于开发检查，但这些分区名称不向 Scientist 泄露。

注意：逐列标准化会改变不同分量的相对权重，所以不能只凭公式断言某个分类器一定达到某个分数。**在开发数据上检验固定工具确实能暴露这些差异，再冻结生成器和评价条件。** 若某家族不稳定，保留失败说明；不要到留出阶段才挑好看的结果。

### 4.3 开发与留出安排

- 开发案例 2 个：T 和 D，各 1 个数据种子；用于调试、校准和生成 S1。
- 最小留出案例 4 个：T、G、D、N 各 1 个新数据种子；S0 与 S1 都运行。
- 完整留出案例 8 个：四个家族各 2 个新数据种子；预算充足再做第二批。
- 所有种子由主种子确定性派生；使用独立命名的 `data_seed`、`split_seed`、`label_seed`、`model_seed`，不要混用。
- 新种子测试的是同一构造家族的新实例；不能称为对全新 EEG 科学领域的泛化。

在开发阶段结束时冻结：生成器版本、家族参数、所有留出 ID 与种子、工具、模型、评分规则、S0 和 S1 文本。开发者可以知道生成机制，但不能根据留出成绩修改它。

初始观察必须从该案例的数据真实计算。公开被试数、各类计数、三种切分的基线分数和交集审计，但不公开真值。没有出现高分差异也照实呈现，不把所有案例包装成同一种异常。

### 4.4 真实 EEG 只作后续扩展

优先使用项目内已经授权且有明确标签/分组说明的小型特征表。没有就跳过；不要自行扫描或修改 `daily-emo-eeg` 等其他项目。

若用户另行给出可用数据路径，再接只读适配器，确认 sample/trial/subject 映射、预处理来源、标签和切分。下载公开数据不是今晚主线；如实施，应有明确许可、来源和体积上限，并且总探索不超过 30 分钟。

真实案例通常没有唯一真值，只能报告诊断证据。EEGNet 回归的 `r` 与本计划二分类 balanced accuracy 是不同任务和指标，不能把此前情绪预测结果直接当作本次分类实验结果。

## 5. 固定工具与科研判断规则

### 5.1 工具目录

Scientist 每个 episode 最多执行 3 个诊断动作。初始观察已经包含基线结果，重复请求不返回新证据，记录为重复动作。

| 工具 ID | 具体操作 | 回答的问题 |
|---|---|---|
| `split_audit` | 列出 window/trial/subject 切分的身份交集、计数、标签比例和每组表现 | 原先的评价究竟测哪种泛化；组数是否足够 |
| `trial_random_labels` | 在 trial 层重新分配平衡随机标签，同 trial 所有窗口共享；分别做 window 和 trial 切分 | 流程是否能利用 trial 特异信息预测任意标签 |
| `trial_shuffle_within_subject` | 在每个被试内按 trial 置换原始标签，保留该被试类别数；分别做 window 和 trial 切分 | 打乱 trial—任务关系但保留被试标签分布后，表现如何 |
| `window_random_labels` | 每个窗口独立分配平衡随机标签，重新训练 | 基础负对照；不能替代分组层级对照 |
| `metadata_only` | 只用预先允许的 subject/session 类别元数据预测标签，按 trial 隔离 | 已知身份/采集分组是否具有标签预测价值 |

`trial_random_labels` 与 `trial_shuffle_within_subject` 使用预注册的 10 个随机标签种子，输出分布与全部种子结果。它们是诊断随机化对照，今晚默认不包装成通用显著性检验。

**不要直接套用某个库的 `groups` 参数就声称完成了 trial 级置换。** 某些函数的 groups 表示限制标签只能在组内交换；若组内标签原本相同，操作甚至没有改变标签。应显式在 trial 表上生成映射，再传播到窗口，并检验映射确实发生变化。[R5]

固定工具不得接收任意代码、任意文件路径、自由命令、模型超参数搜索范围或生成机制开关。

### 5.2 切分与分类器

默认普通特征基线：`StandardScaler` + `KNeighborsClassifier(n_neighbors=1)`。T 家族的 trial 签名适合用最近邻检查可利用通道；这不是在模仿 EEGNet 的能力。备选线性基线为 `StandardScaler` + 固定参数 `LogisticRegression(C=1.0, max_iter=1000)`，只有在开发阶段决定加入后才在所有相应实验一致使用。第一夜不调参。

主切分按下表生成固定索引，并保存样本列表：

| 切分 | 默认 4096 行设置 | 允许重合 | 必须隔离 |
|---|---|---|---|
| window | 每 trial 的 8 个窗口取 6 训练、2 测试 | subject、session、trial | sample |
| trial | 每 session 16 个 trial 按标签各取 6 训练、2 测试，即 12/4 | subject、session | trial、sample |
| subject | 16 个被试取 12 训练、4 测试 | 无 subject 重合 | subject、session、trial、sample |

这里 trial 切分按真实任务标签平衡划分，索引随后固定；随机标签实验不能每次依据随机标签重选“好切分”。对照中如出现训练/测试单类，返回明确 invalid 标记并保留记录，不自动找替代种子。

三个切分的训练量均为 75%，有助减少一个混杂因素，但测试样本和目标分布仍不同。它们的分数差异**仍不能单独视为机制因果效应**。后续做严格切分效应研究应补充共同测试样本或匹配设计。

所有 `fit`、标准化、缺失值处理和特征选择只在训练数据上完成；再 `transform` 测试数据。Pipeline 应随每次重训重新创建。[R4]

元数据工具使用训练集拟合的 one-hot 编码和固定分类器；未见类别按明确规则处理，不能把数字 subject ID 当成连续测量值。元数据高分说明某些相关结构可被利用，不自动证明普通特征模型实际使用了它。

### 5.3 指标、对照与结论边界

主指标使用 balanced accuracy，附普通 accuracy、混淆矩阵、样本数和每组结果。二分类 balanced accuracy 的机会基准为 0.5；报告百分比时统一标为百分点，避免把 0.05 和 5% 相对增幅混淆。

原始标签必须在 trial 内一致。预测可附 trial 聚合结果：对一个 trial 的窗口概率取平均后分类；每个 trial 等权，同时保留窗口级数值。报告受试者宏平均，避免大组主导。

不要把同一 trial 的大量窗口当成独立受试者计算漂亮的置信区间。第一夜以原始逐组结果和跨数据种子变化为主；测试被试仅 4 个时，明确不支持精确总体推断。若额外 bootstrap，必须按与推断目标一致的组重抽样，写清重采样单位和有限组数的局限。

随机标签实验如出现异常高分，需要看切分与随机标签分布、模型、负对照和稳定性。没有高分不能证明原始任务绝无泄漏；可能工具或样本不足。阳性结果也只说明存在可利用通道，不能直接推算原始分数中有多少“来自泄漏”。

**“泄漏”应绑定预期泛化目标。** 如果目标本来就是同一试次内的新窗口预测，共享 trial 是目标设计的一部分；如果宣称预测未见 trial 或被试，就必须使用对应隔离评价。报告必须写清 estimand /ˈestɪmænd/（希望估计的目标量），不将所有重合一律定罪。

### 5.4 实验前预测的结构

每次动作前 Scientist 提交：

- 当前 2–3 个竞争解释及其依据；允许解释共存，不强迫唯一赢家。
- 当前动作，以及它要区分的解释对。
- 对不同解释的预期结果；例如同一 `score_gap` 在 H1 下应为正、H2 下应接近零。
- 一个主要、无条件的可评分预测，以及出现相反结果时会怎样更新。
- 不能区分解释的结果区域和已知局限。

为避免“高”“差不多”无法核对，方向型预测可采用预注册阈值：差值 > 0.05 为 `positive`，< −0.05 为 `negative`，其余为 `near_zero`。**0.05 只是此次方向分类阈值，不是显著性或科学重要性的阈值。** 数值区间预测额外记录覆盖率与区间宽度，不能让 `[0,1]` 这种无信息区间获得高质量评价。

条件预测和主要预测分开：一个假设被削弱时，其条件预测不符合结果不应机械地算作 Scientist 失败；需要看它有没有据此正确更新判断。

## 6. S0/S1 对照：今晚只更新一次

### 6.1 为什么先做这么小

S0 与 S1 的模型权重相同。改变的是一段有来源的研究方法规则。我们要观察规则是否改变决策，并查找反作用；这个实验不训练模型，也不能证明递归自我改进。

### 6.2 固定流程

1. 以 S0 完成两个开发案例，保存全部有效、无效和失败请求。
2. 控制器形成同一份开发事实摘要：实验结果、验证失败及可公开的结果，不把生成器真值当成领域发现。
3. 单独一次 Meta 调用读取开发轨迹和已有检查结果，提出最多 3 条方法规则，总长不超过 600 个中文字符；每条含触发情境、具体动作、适用边界及支持的开发事件 ID。
4. 仅验证规则格式、事实来源和禁止内容；不根据留出成绩筛选规则。若修订语义，记录是谁改的；DSH 改写也是开发者辅助。
5. 冻结 `S0.md`、`S1.md`、`shared_development_facts.json` 及其 SHA-256 哈希。规则不得含留出答案、家族编号与硬编码选择。
6. 对每个未见案例，各开独立 Scientist 会话运行 S0 和 S1，执行顺序用预定种子交替或随机化；不把另一组轨迹放入上下文。
7. 双方都得到相同开发事实摘要、当前观察、工具说明、模型和上限。S0 保留原规则，S1 增加新规则；每组后续选择不同导致的实验结果差异是研究对象的一部分。
8. 全部完成后做逐例对照。不要在看到任何留出结果后继续改 S1、重试到赢，或者把测试轨迹补回开发记忆。

如果 S0 没出现明确失败，可以让 Meta 基于可见的低效之处提出规则，或者得到 `no_update`。不要制造错误来证明系统需要改进；`S1 == S0` 是合法结果。

### 6.3 公平性具体检查

| 项目 | 要求 |
|---|---|
| 基础模型 | 同一 provider、模型 ID、可用参数；记录服务返回版本信息，若服务漂移则注明 |
| 初始事实 | 同一份公开案例和开发事实哈希 |
| 工具 | 同一版本、同一实验种子映射和数据 |
| 预算 | 每组最多 3 个动作；相同请求/输出上限与格式修复规则 |
| 记忆 | 测试案例间不在线学习；S0、S1 不能互读轨迹 |
| 随机性 | 数据/切分/随机标签固定；LLM 的随机种子仅在服务支持时设置，并记录实际支持情况 |
| 成本 | 各组实际调用次数、token、实验耗时单独报告；Meta 成本额外列出 |

相同 token 上限不等于相同实际成本。S1 增加文本本身也可能产生提示长度/注意力效应；本夜不声称已经排除该机制。只有预算充足、事先写入设计时才增加等长中性文本对照，不能临时为了解释结果追加后再称预注册。

### 6.4 评价表，不做主观总分

自动统计：格式有效率、请求违规率、预测先于结果的比例、主要方向预测命中率及分母、动作数、重复动作、停止原因、实际成本。预测数少时直接显示 `3/5`，不只写 `60%`。

逐条证据审查：竞争解释是否真有区别、实验是否具有区分力、结论是否越界、是否忽视反例。用固定 checklist 生成待人工复核的表；DSH 可给初步判断，但标记为 `developer_review`。另一 LLM 的评分只能作为附加意见，不能替代真实实验和人工核查。

对每个留出案例报告配对差值和具体轨迹，不在 4–8 个案例上宣称统计确证。两组自行选择了不同问题时，方向命中率的差别也可能来自题目难度，不能当作唯一优劣标准。

失败案例允许是：格式失败、无信息动作、过度断言、过度怀疑泄漏、S1 退步、工具揭示能力不足。若没有发现实质失败，如实写“本轮未观察到”，不要编造。

## 7. 状态、类型接口与目录

### 7.1 建议目录职责

以下是拟建结构；若已有代码，DSH 应复用合适模块并在实施计划里记录映射，不强行重构。

| 路径 | 职责 |
|---|---|
| `pyproject.toml` | 项目依赖、CLI、测试与类型检查配置 |
| `configs/overnight.json` | 时间、预算、模型引用和案例清单 |
| `src/eeg_scientist/schema.py` | 数据结构、枚举与边界校验 |
| `src/eeg_scientist/cases.py` | 模拟数据与公开视图；私有机制不被序列化给模型 |
| `src/eeg_scientist/splits.py` | 分组切分和身份交集审计 |
| `src/eeg_scientist/experiments.py` | 固定分类器、随机标签与元数据工具 |
| `src/eeg_scientist/provider.py` | 模型 API；可选文件交换适配器；明确区分 mock |
| `src/eeg_scientist/scientist.py` | 公开输入、请求解析、一次研究决策 |
| `src/eeg_scientist/storage.py` | 原子写入、事件日志、哈希与恢复 |
| `src/eeg_scientist/runner.py` | episode 状态机、动作上限和超时 |
| `src/eeg_scientist/study.py` | 开发→规则冻结→留出成对运行 |
| `src/eeg_scientist/reporting.py` | 从保存记录生成报告、表与审查包 |
| `src/eeg_scientist/cli.py` | 可执行入口 |
| `tests/` | 科学约束、边界与恢复测试 |
| `prompts/S0.md`, `prompts/S1.md` | 冻结的研究规则 |
| `memory/scientific_knowledge/`, `memory/research_methods/` | 两类记忆，来源可追溯 |
| `data/private/` | 生成机制、种子清单与真值；只给 evaluator |
| `runs/<study_id>/` | 每个 episode 的输入、预测、结果、事件和配置快照 |
| `reports/`, `artifacts/` | 用户阅读与移交产物 |

避免微服务、数据库服务、网页 UI、向量数据库、消息队列或通用插件系统。一夜内的扩展性来自清楚的输入输出，而不是框架数量。

### 7.2 最少数据结构

在 `schema.py` 定义以下类型，字段可有实现性补充，但不得减少溯源信息：

| 类型 | 核心字段 |
|---|---|
| `FeatureDataset` | `x`, `y`, `sample_ids`, `subject_ids`, `session_uids`, `trial_uids`，shape 与长度一致 |
| `CaseSpec` | evaluator-only 的 `case_id`, `family`, `data_seed`, `generator_version`, 参数；不能直接进入 prompt |
| `SplitIndices` | `train_indices`, `test_indices`, `split_level`, `split_seed` |
| `SplitAudit` | 各层交集、标签计数、组数、invalid 原因 |
| `PublicCase` | 中性 `case_id`, 数据来源类型、结构摘要、基线结果、允许工具 |
| `Hypothesis` | `id`, `claim`, `mechanism`, `supporting_evidence_ids`, `limitations` |
| `Prediction` | `metric_key`, 主要方向/区间、阈值、分假设预测、反向结果更新规则 |
| `ExperimentRequest` | `request_id`, `tool_id`, 允许参数、区分的假设 ID、`Prediction` |
| `Decision` | `hypotheses`, `action` 或 `stop`, 更新说明与证据 ID；两者互斥 |
| `ExperimentResult` | 指标、随机化分布、审计、配置/数据哈希、计时、有效状态 |
| `EpisodeState` | `episode_id`, 版本、case、阶段、已用预算、最后已提交事件号、停止原因 |
| `StudyState` | 冻结清单哈希、待跑/完成配对、当前 episode、总预算与截止时刻 |
| `ResearchRule` | 触发情境、动作、边界、来源事件、作者/辅助信息 |

可变长 JSON 只在 I/O 边界存在。Scientist 输出用 Pydantic 等显式模型验证；未知工具、重复 ID、非法参数、超预算、非有限数值均拒绝执行。

### 7.3 相邻模块接口

下列签名是拟议接口，不是已经存在或已经测试的代码。具体类在前表所属模块定义；CLI 的结果类型也在 schema 中声明。

```python
from pathlib import Path
from typing import Protocol

class ScientistProvider(Protocol):
    def decide(self, request: ModelRequest) -> ProviderResponse: ...

def generate_case(spec: CaseSpec) -> FeatureDataset: ...
def build_split(dataset: FeatureDataset, level: SplitLevel, seed: int) -> SplitIndices: ...
def audit_split(dataset: FeatureDataset, indices: SplitIndices) -> SplitAudit: ...
def build_public_case(dataset: FeatureDataset, baseline: BaselineBundle) -> PublicCase: ...
def execute_experiment(dataset: FeatureDataset, request: ExperimentRequest,
                       context: ExperimentContext) -> ExperimentResult: ...
def run_sealed_experiment(dataset: FeatureDataset, sealed: SealedRequest,
                          context: ExperimentContext) -> ExperimentResult: ...
def seal_prediction(run_dir: Path, request: ExperimentRequest) -> SealedRequest: ...
def append_event(run_dir: Path, event: RunEvent) -> int: ...
def run_episode(config: EpisodeConfig, provider: ScientistProvider) -> EpisodeSummary: ...
def resume_episode(run_dir: Path, provider: ScientistProvider) -> EpisodeSummary: ...
def run_study(config: StudyConfig, provider: ScientistProvider) -> StudySummary: ...
def render_reports(study_dir: Path, output_dir: Path) -> ReportPaths: ...
```

`ModelRequest`, `ProviderResponse`, `SplitLevel`, `BaselineBundle`, `ExperimentContext`, `SealedRequest`, `RunEvent`, `EpisodeConfig`, `EpisodeSummary`, `StudyConfig`, `StudySummary`, `ReportPaths` 均为 `schema.py` 的显式类型。不要把拼写不同的重复概念分散定义。

补充字段约定：`ModelRequest` 包含完整允许消息、规则哈希、模型配置及请求 ID；`ProviderResponse` 包含可见响应、返回模型标识、用量、延迟及状态；`ExperimentContext` 包含固定切分、标签种子清单、工具版本和超时；`SealedRequest` 包含原始请求、规范化内容哈希、已持久化事件号和运行路径。`EpisodeConfig` 指向一个公开案例、规则版本、模型与动作上限；`StudyConfig` 包含开发/留出清单、总预算、截止时刻与报告预留时间。其余 Summary/Paths 类型是对应结果和产物路径的汇总。T1 先定义跨模块共享结构，后续仅增补明确需要的字段。

### 7.4 状态机和事件顺序

正常 episode 的顺序：公开观察→Scientist 决策→校验→封存预测→执行→持久化结果→Scientist 更新；最多 3 个动作后强制请求结论。模型可更早停止并说明为什么。

封存需要：规范化 JSON、SHA-256、UTC 时间和单调事件序号。研究运行只能从 `run_sealed_experiment` 进入，它核对控制器签发的 `SealedRequest` 和已落盘事件，再调用底层纯实验函数 `execute_experiment`；底层函数可在开发测试中单独使用，但不能成为 Scientist 的入口。不能靠模型声称“已封存”。这是审计记录，不是不可篡改的外部公证；开发者仍有文件权限，不能夸大保证。

每个 episode 至少保存：

`public_input.json`、`config_snapshot.json`、`events.jsonl`、`state.json`、逐次 `request_*.json`、`prediction_*.json`、`result_*.json`、`final.json`、`summary.md`。

JSONL = JSON Lines，每行一个完整 JSON 事件。状态文件采用临时文件加原子替换；活动日志只追加。重启时仅可忽略并隔离最后一行未完成的写入，不能吞掉中间损坏。

请求缓存按“模型配置＋完整公开输入＋规则版本＋动作阶段”确定键；S0/S1 的不同提示不能复用模型回答。确定性实验可以共享缓存，但请求者在封存预测前看不到结果，缓存键包含数据、工具版本、切分、标签种子及全部相关参数。

对 API 超时但可能已计费的请求标记 `unknown_completion`，最多按既定规则重试；不声称 exactly-once。恢复只保证不重复使用已有完整记录，不保证服务端没有处理过超时请求。

## 8. 时间、预算和降级

### 8.1 默认上限

| 项目 | 默认值 |
|---|---:|
| 总工作窗口 | 启动后 8 小时 |
| 预留报告与打包时间 | 45 分钟 |
| Scientist 动作上限 | 每 episode 3 个 |
| 正常 Scientist 调用 | 最多 4 次/episode：3 个动作决策＋最终结论 |
| Scientist/Meta/格式修复/API 重试总尝试数 | 96 次 |
| 项目模型累计计费 token 上限 | 1,000,000，输入、输出、可用推理用量均计入 |
| 单次模型输出上限 | 4096 token；按服务实际语义记录 |
| 单次 API 超时 | 120 秒 |
| 429/临时 5xx/网络故障 | 每请求最多额外重试 2 次；指数退避，总等待不超过 5 分钟 |
| 格式修复 | 每次决策最多 1 次额外调用，计入总尝试与 token |
| 单个确定性诊断动作 | 最多 5 分钟，超时停止项目启动的该子进程 |
| 训练/数值线程 | 最多 4，避免拖死电脑 |
| 同时实验作业 | 1；先保证简单与恢复性 |
| 新增数据/输出软上限 | 2 GB；内存目标不超过 4 GB |
| 同一工程错误修复尝试 | 最多 3 轮或 30 分钟，之后降级 |
| 开发 DSH goal rounds 建议上限 | 80，若当前版本支持授权设置 |

这些是上限而非消费目标。主对照完整 8 个留出案例 × 2 版本，加 2 个开发案例，共 18 个 episode；每个最多 4 次正常调用，再加一次 Meta，约 73 次正常调用，余量用于少量修复。最小 4 个留出案例则约 41 次正常调用。

**DSH 开发会话的 token 与 Python Scientist 的 token 是两个账本。** Python 预算不能限制 DSH 自身消耗，80 个 goal rounds 也不等于 80 次模型请求或确定金额。若你有金额上限，在 DSH/服务商账单设置中明确限制；预检核实价格后才估算，不能凭本文推算固定费用。

若服务不给完整 token 用量，使用保守估计并标为 `estimated`，不要标为零。发起调用前预留本次最大输出和已知输入预算；实际花费仍以供应商账单为准。

### 8.2 时间分配建议

| 相对启动时间 | 重点 | 验收 |
|---|---|---|
| 0–20 分钟 | 环境、模型、目录、期限检查 | `PREFLIGHT.md`；模型通路结论 |
| 20–90 分钟 | 数据、分组和固定工具 | T1/T2 的关键测试；真实数值输出 |
| 90–180 分钟 | 状态机、日志与模型接入 | 首个 E1 回合；一次中断恢复验证 |
| 180–270 分钟 | 开发案例、S1 与冻结 | `FREEZE_MANIFEST.json` |
| 270–420 分钟 | 留出配对运行 | 优先完成 4 对，再扩至 8 对 |
| 最后 45 分钟 | 报告、核心代码讲解、打包 | 审查包与明确状态 |

这不是运行时承诺；DSH 根据机器与已有项目调整。达到停止新任务时刻后，不启动无法在截止前完成的 episode。应先完成一个案例的 S0/S1 配对再开始下一个；如果只完成一半，保留并标记 `unpaired`，不要丢弃。

### 8.3 降级顺序

时间不够：先取消真实 EEG，再取消第二个数据种子，仍不够则保留已经完成的配对和 E1 记录，最后完成报告。不能通过取消分组检查、预测封存或真假调用标注来“赶进度”。

API 不可用：优先完成 E0；可验证隔离的 DSH 文件交换可支持 E1/E2，否则仅工程演示。真实 EEG 不可用：继续模拟主线。Git 不可用：保存文件哈希和状态，不因为提交失败停掉整个任务。

## 9. 逐项实施任务

下列命令是**要求 DSH 实现后提供的接口和验收方式**，目前尚不存在。Windows 路径以项目根目录为起点；若复用已有环境，替换解释器路径并在报告里写出实际命令。

命令中的 `-m` 表示 module（以模块运行），`-q` 表示 quiet（简洁输出），安装时 `-e` 表示 editable（可编辑安装），`--config` 表示 configuration（配置）。`pytest` 中出现的测试名就是本任务要求的行为；DSH 可补实现性测试，但不能用只验证自己实现细节的测试代替这些约束。

### T0：预检与可恢复的项目初始化

**文件：** `reports/PREFLIGHT.md`、`PROGRESS.md`、`NEXT_ACTION.md`、`configs/overnight.json`、`pyproject.toml`、`.gitignore`。已有文件先读取和保留，不自动替换。

**输入：** 本计划、项目实际状态和已有指令。  
**输出：** `StudyConfig` 的具体配置和运行路径；模型接入的可用/不可用结论。

- [ ] 检查工作目录、现有文件、Git 状态、Python 版本、磁盘空间、CPU/内存以及可用依赖。只读确认适用的项目指令，不遍历个人目录找密钥或数据。
- [ ] 记录启动时刻、电脑时区、截止时刻、停止新任务时刻；启动后 8 小时是默认值。
- [ ] 优先使用项目现有隔离环境；没有则创建 `.venv`。不更改 Anaconda base 环境，不强行升级系统 Python。
- [ ] 安装必要依赖并记录实际版本；Python 3.11+ 已可用时可以采用并说明，不为追逐版本浪费一夜。安装失败先尝试已有缓存和已装依赖。
- [ ] 确定 API 路线，或记录备用路线的隔离限制；密钥检查只输出存在与否。
- [ ] 写出待办、当前阶段、下一条可执行命令，建立项目级进度文件；若已有 `AGENTS.md`，先保存增量说明，不粗暴覆盖。
- [ ] 按下一任务需要创建最小目录，不预先做庞大的框架。

**验收：** `PREFLIGHT.md` 明确模型通路、环境、时间、预算及阻塞。依赖环境可导入；无未授权外部目录写入。

### T1：数据结构与可信的分组切分

**创建/修改：** `schema.py`、`cases.py`、`splits.py`。  
**测试：** `tests/test_cases.py`、`tests/test_splits.py`。  
**接口：** 产出 `FeatureDataset`、`SplitIndices`、`SplitAudit`，实现第 7.3 节 `generate_case`、`build_split`、`audit_split`。

- [ ] 先写 `test_trial_uid_is_globally_unique`：两个被试都存在 `trial_01` 时，完整 UID 不能相等，trial 切分不能错误合并它们。
- [ ] 写 `test_subject_split_disjoint`：train/test 的 subject、session、trial、sample 集合全部无交集；window 切分只有 sample 必须无交集，trial 重合必须被报告。
- [ ] 写 `test_label_constant_within_trial`、`test_array_lengths_match`、`test_same_seed_reproduces_data`：不一致数据报错，相同配置产生同一数据哈希。
- [ ] 写 `test_public_case_has_no_private_fields`：公开序列化不得出现 family、注入参数、答案、生成器路径或私有内容哨兵字符串。
- [ ] 运行测试确认缺少实现的具体失败，然后实现最小数据模型、四家族生成器和切分逻辑。
- [ ] 验证默认规模的三种切分各 3072 行训练、1024 行测试；不能靠手写假计数通过。
- [ ] 保存开发案例的配置、数据哈希和实际审计结果；仅在开发阶段调整构造参数。

**验证命令：**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cases.py tests/test_splits.py -q
```

**通过标准：** 所有上述断言通过；公开案例不泄露机制；按层级切分实际可追踪。

### T2：固定实验与随机化对照

**创建/修改：** `experiments.py`。  
**测试：** `tests/test_experiments.py`、`tests/test_randomization.py`。  
**接口：** 消费 T1 的数据与切分；产出 `BaselineBundle`、`ExperimentResult`；实现 `execute_experiment`。控制器后续要求封存对象后才能调用底层执行。

- [ ] 写 `test_scaler_fit_uses_training_rows_only`：人为使测试特征均值远离训练，拟合参数仍等于训练均值，不能等于全体均值。
- [ ] 写 `test_trial_random_labels_shared_across_windows`：新标签在 trial 内一致，同一 trial 的训练和测试窗口看到同一随机标签映射。
- [ ] 写 `test_within_subject_permutation_preserves_counts`：每被试每类 trial 数不变；构造的非退化标签映射实际改变；只有一类时明确报告无法置换。
- [ ] 写 `test_window_randomization_is_distinct_from_trial_randomization`：固定测试数据和种子下，窗口独立打乱不被误实现成 trial 共享标签。
- [ ] 写 `test_ids_never_enter_feature_classifier`、`test_invalid_class_support_is_reported`、`test_duplicate_samples_are_rejected`。
- [ ] 实现固定 Pipeline、工具参数验证、计时、标签映射和完整结果输出。主工具不接受自由代码。
- [ ] 在开发种子上生成校准表。对 T 家族，最近邻 window 分数应明显高于 trial 分数，随机 trial 标签仍体现共享签名；对 G，隔离后应保留共享任务信息。若不满足，先解释生成器与工具相互作用再修复；不得提前打开留出结果调参。
- [ ] 冻结工具列表和超参数；禁止运行期间无日志切换模型。

**验证命令：**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_experiments.py tests/test_randomization.py -q
```

**通过标准：** 标签操作和切分断言通过；实际拟合产生结果；已有校准表解释工具能检测什么、不能检测什么。这里的高分只是工程校准，不能当作 Scientist 的成功。

### T3：预测封存、日志和恢复

**创建/修改：** `storage.py`、`runner.py` 的非模型部分。  
**测试：** `tests/test_storage.py`、`tests/test_resume.py`。  
**接口：** 产出 `SealedRequest`、`RunEvent`、`EpisodeState`；实现 `seal_prediction`、`append_event` 和 `runner.py` 的 `run_sealed_experiment`，为 episode runner 提供持久状态与受控实验入口。

- [ ] 写 `test_execution_requires_sealed_prediction`：缺少预测、预测非法或哈希不匹配时，不允许执行实验。
- [ ] 写 `test_prediction_event_precedes_result_event`：模型请求、封存、执行开始、结果的序号严格递增；对一个正常工具回合做真实检查。
- [ ] 写 `test_resume_after_result_does_not_rerun_experiment`：结果落盘后模拟进程中断，恢复时实验调用计数不增加。
- [ ] 写 `test_partial_last_log_line_recoverable` 和 `test_corrupt_middle_log_fails_loudly`：两类损坏不得混为“自动修复”。
- [ ] 写 `test_unknown_api_completion_recorded`：超时后状态可区分已知失败与未知是否完成；计入已尝试预算。
- [ ] 实现原子状态文件、只追加事件、缓存键和恢复流程；Windows 文件替换与路径均需实际验证。
- [ ] 用明确标注 `scripted` 的确定性策略跑一轮；这是状态机测试，不计入 E1 或研究比较。

**验证命令：**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_storage.py tests/test_resume.py -q
```

**通过标准：** 中断后的恢复不重做已有完整工作；预测确实先于结果；原记录不会被悄悄覆盖。

### T4：接入真正的 Scientist，跑出 E1

**创建/修改：** `provider.py`、`scientist.py`、`runner.py`、`prompts/S0.md`。  
**测试：** `tests/test_provider.py`、`tests/test_scientist.py`。  
**接口：** 实现 `ScientistProvider.decide`、`run_episode`、`resume_episode`。`ProviderResponse` 至少记录可见文本、模型标识、用量、请求 ID 与异常状态。

- [ ] 写 `test_unavailable_api_is_not_mock_success`、`test_unknown_tool_rejected`、`test_action_budget_enforced`、`test_nan_metric_rejected`。
- [ ] 写 `test_secret_redacted_from_logs`：使用假密钥哨兵，检查原始请求保存、错误文本和审查包都不出现它。
- [ ] 写 `test_format_repair_cannot_see_experiment_result`：格式修复输入只有原模型输出和校验错误，未包含未执行实验的结果。
- [ ] 编写 S0：要求竞争解释、事前预测、证据引用、有限动作、合理停止；不要把家族答案或“每次先做哪个工具”写进去。
- [ ] 先做一次最小实际 API 调用，验证响应与用量；这个调用不伪装成完整研究 episode。
- [ ] 在开发案例上完成一条真实研究轨迹。模型输出在获得结果后明确更新至少一次判断，或者有理由维持判断。
- [ ] 若 API 阻塞，按第 3 节判断备用路线；不能通过模板拼出“AI 结论”满足验收。

无结果可预测的纯审计动作使用明确的 `not_applicable` 评分状态；仍需事前写出要核查的事实与不同结果的意义，但不把它强塞进数值方向命中率的分母。`window_random_labels` 的目标不再在 trial 内恒定，因此只报告窗口级指标；不能聚合成一个不存在的 trial 真标签。原始标签和 trial 层随机标签实验才报告 trial 聚合指标。

**验证命令：**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_provider.py tests/test_scientist.py -q
.\.venv\Scripts\python.exe -m eeg_scientist.cli episode --config configs/dev_episode.json
```

`configs/dev_episode.json` 由 T4 创建，引用 T1/T2 的首个开发案例。`episode` 表示单次研究回合；第一行测试可使用 mock，第二行研究运行必须标明真实 backend。

**通过标准：** 至少一条可读完整轨迹具有真实 LLM 调用记录和实际实验文件。无法达到时清楚标记 E0，不伪报 E1。

### T5：冻结 S1，运行留出配对

**创建/修改：** `study.py`、`prompts/S1.md`、`memory/`、`FREEZE_MANIFEST.json`。  
**测试：** `tests/test_study.py`。  
**接口：** 消费 episode runner；实现 `run_study`，持久化 `StudyState` 和每个案例的两组状态。

- [ ] 写 `test_s0_s1_share_same_facts_and_tools`：初始事实、工具、数据和相应种子哈希一致，只有允许的规则文本不同。
- [ ] 写 `test_holdout_not_used_in_rule_update`：Meta 输入只含开发 IDs；使用哨兵内容证明留出真值和轨迹没有进入请求。
- [ ] 写 `test_rule_edit_after_freeze_is_rejected`：运行前核对冻结哈希，变化则拒绝继续原 study；另建版本并说明污染边界。
- [ ] 写 `test_no_cross_arm_or_case_memory`、`test_deadline_preserves_partial_pair`、`test_study_resume_skips_completed_pairs`。
- [ ] 完成两个开发案例，执行最多一次有效 Meta 更新，保存规则来源及辅助情况；格式修复不算新的规则搜索，但仍计费与记录。
- [ ] 冻结全部清单；冻结后不再根据留出结果修改实验或规则。
- [ ] 先完成第一数据种子的 4 对，再做第二数据种子的 4 对。单组失败保持失败记录，可继续下一对，不悄悄更换案例。
- [ ] 输出自动指标和待人工审核表。不使用真实标签/真值之外的信息替模型补写结论。

**验证命令：**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_study.py -q
.\.venv\Scripts\python.exe -m eeg_scientist.cli overnight --config configs/overnight.json
```

**通过标准：** 至少 4 对留出 episode 有完整状态，或明确记录为何未达到；共享输入可核对，S1 在留出之前冻结。S1 不优于 S0 不影响工程验收。

### T6：生成明早能审查的产物

**创建/修改：** `reporting.py`、`cli.py`、`reports/`、`artifacts/review_bundle.zip`。  
**测试：** `tests/test_reporting.py`。  
**接口：** 实现 `render_reports`；CLI 至少支持 `preflight`、`episode`、`overnight`、`resume`、`report`。

- [ ] 写 `test_report_numbers_match_saved_results`：报告的样本数、完成数、预测命中分子分母、成本都来自保存记录。
- [ ] 写 `test_mock_and_partial_runs_cannot_be_reported_as_real_success`。
- [ ] 写 `test_review_bundle_excludes_secrets_and_raw_private_data`；原始 API headers、秘密文件、虚拟环境和大数据不得打包。
- [ ] 编写中文晨报、结果表、失败案例和核心代码讲解；未测项目明确标记未测。
- [ ] 运行完整科学约束测试、一次报告重建和压缩包清单检查。不要为了形式覆盖率追加一堆低价值测试。
- [ ] 更新 `PROGRESS.md`、`NEXT_ACTION.md`、最终停止原因、模型/依赖版本、Git 提交或文件哈希。

**验证命令：**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m eeg_scientist.cli report --study runs/<实际study_id>
```

`--study` 指定研究运行目录；`<实际study_id>` 是需替换的说明文字，不应原样输入。最终报告必须提供替换完成、可直接执行的命令。

**通过标准：** 从保存数据重新生成报告而不重新调用模型；所有成败状态可追溯；审查包可解压，清单没有秘密和原始私人数据。

### T7：只有主线完成才做的扩展

若 E2 完成且剩余至少 60 分钟，可以在“补第二数据种子”与“一个真实 EEG 只读适配”中按第 8 节优先级执行。不得启动新框架、追加基础模型训练、扩充无限工具或不断改 S1。扩展失败不能损坏 E2 已有记录。

## 10. DSH Desktop：今晚具体怎样操作

### 10.1 先准备文件和运行条件

1. 把本 Markdown 放到项目根目录，确认 DSH 正在该项目会话内。
2. 四份背景文件若本地已有，可放在 `docs/context/`；没有也不阻塞，本计划已包含执行所需规格。不要把大量不相关聊天灌进 Scientist。
3. 你已经设置完全权限，不需要为了这份任务再次修改全局权限。仍应确认当前会话的实际目录与政策；权限标签并不保证所有服务或插件都不会要求操作确认。
4. Windows 接上电源，在设置中检查接电状态下的自动睡眠；允许屏幕熄灭，但不要让电脑休眠。不要在运行中退出 Desktop 或停止它的后台进程。系统锁屏是否保留当前任务，应以睡前短运行观察为准。
5. 若要走 Python API，提前准备本地已授权的 API 配置。无需把密钥发给我。

### 10.2 一次 Plan 检查：复制这段

在 DSH 对话框发送；斜杠命令以你当前安装版本的补全和帮助为准。官方当前文档支持 `/plan` 与 `/plan off`。[R1]

```text
/plan 读取当前项目根目录的 EEG_AI_Scientist_Overnight_Plan.md，以及当前项目适用的 AGENTS.md 和已有说明。我们已经确定要做“小型、可检验的 EEG 假设诊断闭环”，由你开发与运行，我明早审核核心代码。请做一次不超过约 15 分钟的环境与实施计划核对，不重新发散研究方向。

确认工作目录确实是 X:\projects\eeg-ai-scients。保留现有文件和未提交修改。核对 Python、依赖、目录、时间和模型调用路线。特别区分 Desktop 登录与 Python API；只报告密钥是否存在，不显示值。若有可用授权 API，可用一次最小请求检查连通性。

按文档 T0—T6 给出实际文件映射、执行顺序、预算、冻结与恢复方案，标明不确定项并给出默认处理。默认运行窗口是我批准执行后 8 小时，最后 45 分钟用于报告。无需因为常规实现细节反复问我。请只把必须由我在睡前完成的外部设置列出来，例如 API 尚未配置。

提交一次可审批的实施计划。计划通过后转入执行；今晚不需要另装复杂框架、技能或插件。不要把“给出计划”当作任务完成。
```

审查时你只需抓住：目录对、没有越界改你的真实数据、模型通路清楚、预算明确、保留 S0/S1 隔离、明早产物齐。然后选择界面中的批准/Approve。若当前版本无法显示审批界面，你可以在看完计划后手动 `/plan off`，再发送执行指令；不要把手动退出误当成已经自动批准了所有外部操作。[R1]

**不要把 DSH 留在 Plan 审批弹窗里就去睡觉。** 当前文档描述的是先审查再执行的流程，它不靠“请不要停”自动批准计划。

### 10.3 建立持续目标

完成 Plan 审批后发送：

```text
/goal 按 EEG_AI_Scientist_Overnight_Plan.md 在当前项目自主完成 T0—T6：实现可恢复的 EEG 风格假设诊断闭环，优先完成真实 LLM 回合和至少 4 对冻结的 S0/S1 留出运行，生成晨报、结果表、失败案例、核心代码讲解和 review_bundle.zip；按已设置的时间与预算上限结束，未完成项如实记录，不把计划或 mock 演示当成研究完成。
```

再发送下一节完整执行指令。当前 `/goal` 命令用于创建/查看/暂停/恢复目标；裸 `/goal` 可检查状态。自动继续取决于 goal driver，目标状态存在并不等于它正在续跑。[R2][R3]

需要特别区分两种故障：**我们写的 Python 程序可以实现有限 API 重试；DSH 自身的模型调用如果异常终止，其 goal driver 当前并不保证自动重试。** 官方文档明确列出这类故障可能需要后续人工授权恢复。因此本计划降低停顿概率并提供恢复点，不能承诺整夜零中断。[R3]

### 10.4 完整执行指令：复制这段

```text
我已批准这次项目内的开发与运行。现在开始执行 EEG_AI_Scientist_Overnight_Plan.md，不停在规划或脚手架阶段。你是开发与运行的负责人；被评价的 Scientist 必须是独立且输入受控的模型调用，不能把你已知的生成机制带给它。

默认截止时间为本次执行启动后 8 小时，使用本机时区，立刻记录具体时刻；最后 45 分钟用于报告与打包。目标提前完成可以提前结束。按文档的调用次数、token、实验和修复预算执行；不要通过等待或重复运行凑够时长。

项目内可逆开发、必要依赖、测试、实际运行、报告和本地检查点已授权。普通实施选择自主决定并记在 decisions 日志里，不每完成一项就询问是否继续。已有文件、未提交工作和外部目录须保护；任何现行权限或审批限制仍应遵守，不通过改设置绕过。

按 T0—T6 推进：先可靠数据/工具，再状态机和真实 LLM 回合，再开发案例与一次规则更新，冻结后做未见案例的 S0/S1 成对比较。每个阶段完成后先检查证据再继续。S1 变差、没有规则更新、没有观测到明显失败，都可以如实交付。

模型 API 不可用时，先完成所有不依赖 API 的工作。只在能验证新会话上下文与文件权限隔离时采用 DSH 文件交换备用路线；否则只做明确标为 engineering_demo 的演示，不冒充有效 AI 对照。不得提取 Desktop 登录令牌，不得制造实验数值或 AI 回答。

每个阶段更新 PROGRESS.md、NEXT_ACTION.md 和运行状态。长命令要有可查看的日志、开始/结束时间和超时；不启动无人跟踪的后台实验。上下文压缩或会话恢复后先读状态再继续，不重复完成的实验。

如果当前 DSH 的 goal 工具支持，我授权把本目标 max_goal_rounds 设为 80，并检查自动续跑处于 armed/可继续状态；不要凭空使用不存在的斜杠参数，不修改全局部署绕过限制。若不支持，记录实际限制，使用当前可用机制执行。

发生常规错误可自主修复，每个问题最多 3 轮或 30 分钟；达到上限就按计划降级并继续可做的部分。真实外部阻塞、配额耗尽或现行审批要求无法解决时，保存检查点和准确原因，不无限重试。

最终交付 reports/MORNING_REPORT.md、reports/RESULTS_TABLE.md、reports/FAILURE_CASES.md、reports/CORE_CODE_WALKTHROUGH.md、FREEZE_MANIFEST.json、可重放的运行记录、artifacts/review_bundle.zip，并给出本机实际可复制的恢复命令。说明达到 E0/E1/E2/E3 哪一级，不能只写“完成”。现在开始。
```

### 10.5 睡前最后一次看什么

- [ ] DSH 当前没有等待审批的对话框，且 Plan 已退出。
- [ ] `/goal` 显示目标有效；如版本暴露该信息，检查 `active`、`armed` 及剩余 rounds。
- [ ] DSH 已实际执行一条项目命令，有文件与日志生成。
- [ ] Python API 至少一次成功；若不可用，你知道夜间将降级到哪一级，而不是以为它会自行拿到密钥。
- [ ] 至少一个确定性实验已经产生真实结果，输出不是只有目录结构和文档。
- [ ] 截止时间、模型调用上限与下一步写在本地进度文件。
- [ ] 电脑不会因接电自动睡眠而中断，Desktop/后台进程保留运行。

若你还有 10 分钟，最好看见第一个真实 LLM 回合。完整 E1 可能需要更久，但这比只确认“她说会跑”更有价值。

### 10.6 如果 `/goal` 没有出现

先用当前界面的命令补全/帮助确认是否支持；不要把未知命令当普通聊天后误以为启用了目标模式。可以正常发送完整执行指令，要求 DSH 使用当前已支持的长任务方式并持久化进度。若它一轮结束后不会自动继续，就无法保证无人值守完成多轮开发；睡前应明确这个限制。

不要为了目标模式临时升级或改写 DSH 的内部组件。已构建的 Python `overnight` 命令可以在一个被 DSH 跟踪的长进程中自行执行实验；但它不能替代尚未完成的代码开发。没有可靠自动续跑机制时，应先让她完成可运行的主程序，再启动实验。

## 11. 明早的交付规范

### 11.1 `MORNING_REPORT.md`

首页就回答以下问题：

1. 本次达到哪个等级？`complete`、`partial` 或 `blocked` 的理由是什么？
2. 实际完成多少真实 LLM episode、多少 scripted/mock、多少 S0/S1 配对？
3. 使用什么模型、数据类型、代码版本？何时冻结？
4. 最值得看的一条证据是什么？它支持什么、不支持什么？
5. S1 在哪些案例改善、无变化、退步？或者为什么不能比较？
6. 耗时、调用、token、可确定的费用及不确定项是多少？开发 DSH 成本是否另计？
7. 当前阻塞、剩余风险和下次唯一最优先动作是什么？

正文附：真实测试命令与退出码、失败项、实际运行命令、文件入口及未完成清单。不得只写“所有测试通过”而无输出或日志位置。

### 11.2 `RESULTS_TABLE.md`

至少包含列：`case_id`、数据来源类型、数据种子、S0/S1、backend 标记、有效状态、动作序列、主要预测命中分子/分母、结论证据 ID、调用次数、token、实验秒数、停止原因、人工/开发者辅助。

另有基线/随机化表，显示每个工具的真实指标、组数和标签分布。表格分清：

- EEG 风格分类器做得怎样；
- Scientist 的研究决策做得怎样。

不要用分类器 accuracy 上升代表 Scientist 学会科研。

### 11.3 `FAILURE_CASES.md`

每个案例记录：观察→原解释→预先预测→实际结果→更新→评审意见。指出错误属于实现、工具能力、研究决策还是评价不足。至少详写一个确实观察到的失败/局限；若无实质失败，详写最重要的未解决判断边界，并明确这不是失败证据。

### 11.4 `CORE_CODE_WALKTHROUGH.md`

供 Danius 之后学习，按下面次序解释，每个文件给“输入、输出、核心逻辑、为何如此设计、如何检查错没错”：

1. `schema.py`：一条科学主张怎样成为结构化对象；哪些限制由类型表达，哪些需要运行校验。
2. `splits.py`：为什么 shuffle 不会消除身份；训练与测试的单位究竟是什么。
3. `experiments.py`：trial 随机标签与窗口随机标签差在哪里；为什么每次要重新 fit。
4. `runner.py`：预测为何先落盘；预算与中断如何控制。
5. `scientist.py` / `provider.py`：模型实际收到哪些消息，输出如何变成一次实验。
6. `study.py`：S0/S1 共享什么、只改变什么；哪里可能发生测试污染。

每部分附 2 个自测问题和对应答案位置。不要让用户从环境搭建脚本开始读起，也不需要逐行复述所有代码。

### 11.5 审查包

`artifacts/review_bundle.zip` 包含：上述四份报告、实际配置的脱敏副本、冻结清单、规则版本、共享开发事实、结构化结果、关键轨迹、测试摘要、核心代码与依赖清单、复现说明。模拟数据优先用生成种子复现，不塞虚拟环境。

不包含：密钥、认证 headers、Desktop 会话令牌、秘密文件、原始私有 EEG、大体积缓存或整个电脑日志。私有 evaluator 配置可为本地审查保留并明确标记，但禁止混入 Scientist 的公开请求。包名不代表数据可公开发布。

## 12. 停住之后怎样恢复

| 情形 | 正确处理 |
|---|---|
| 停在计划审批 | 你读完计划后批准；确认退出 Plan 再执行 |
| goal 因会话恢复而未续跑 | 先读当前状态；当前官方机制下可能需要 `/goal resume` 重新激活 [R2][R3] |
| 403/401、密钥缺失 | 记录并停该模型路线；不重复撞接口，完成非 API 工作 |
| 429/临时服务故障 | 按有限重试执行；耗尽则检查点与降级 |
| 她认为“代码写完”就结束 | 检查 goal 验收项，要求继续真实运行和报告，不能把未执行测试当成功 |
| 科学结果与预期不同 | 保留；先检查实现证据，不改真值或挑种子 |
| 磁盘/内存不足 | 停新任务，保留状态；减并发与规模需新版本，不能混入冻结比较 |
| 需要现行政策规定的人工审批 | 不绕过；写出被阻止的具体动作，完成其他允许工作 |
| 宕机或意外退出 | 恢复原会话/项目，读取持久状态，执行报告给出的实际 resume 命令 |

可以复制的恢复提示词：

```text
继续当前项目的过夜任务。先读取 EEG_AI_Scientist_Overnight_Plan.md、PROGRESS.md、NEXT_ACTION.md、最新 MORNING_REPORT.md（如果存在）、StudyState 和 FREEZE_MANIFEST.json，再检查实际文件和当前进程。不要从头重建或重跑已完成结果。

告诉我上次停在哪个精确阶段、为什么停、现有结果是否成对且仍符合冻结条件。普通可恢复问题自行处理。优先完成剩余可用的配对和报告，不根据测试结果修改 S1。若需要续跑 goal，使用当前版本正式支持的方式；若需改预算或截止时间，明确报告旧值并采用我这次给出的新上限。
```

如果你只是想停止，可以用当前支持的 `/goal pause` 暂停续跑，再要求 DSH 优雅停止正在执行的项目作业并落盘。暂停 goal 不应被假定会自动终止所有已经启动的外部进程。[R2]

## 13. 明早我们一起怎么审

先发 `MORNING_REPORT.md` 和 `RESULTS_TABLE.md`，或者直接上传审查包。无需先把整段 DSH 对话复制过来。

我们先检查一条完整轨迹，然后只审四个高价值问题：

1. **模型到底看到了什么？** 有没有答案、生成器机制或其他测试案例泄露。
2. **实验改变了什么？** 分组、随机标签与拟合范围是否正确。
3. **结果支持到哪？** 是否把可利用通道、相关性或有限负结果夸大为唯一机制。
4. **S1 为什么变好或变差？** 是否改变了实验选择，还是只是回答更长、重复规则或获得了更多信息。

之后按 `splits.py → experiments.py → runner.py → scientist.py` 的顺序读核心逻辑。你不必逐行理解所有依赖，也不需要重新手敲一遍；先能回答“输入是什么、输出是什么、依赖什么假设、这一步错了会怎样影响结论”。

如果明早只有 E0/E1，我们根据真实阻塞决定补哪一步；如果有 E2，也先检查对照是否成立，再决定增加真实 EEG、更多案例或更自由的假设空间。不要因为第一夜某个分数好看就马上扩成完整 RSI。

## 14. 来源与证据范围

本计划的案例数量、预算、目录与默认参数属于此次任务的工程/实验设计建议，不是论文已经验证的最佳配置。本文件是实施计划，**尚未在你的 Windows 环境中执行或验证**。

### DSH 与工程文档（核对日期：2026-10-18）

- **[R1]** DeepSeek AI (n.d.) *DeepSeek Harness: Plan mode*. Available at: https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/plan/plan-mode/README.md (Accessed: 18 October 2026). 支持本文关于 `/plan`、审批和 `/plan off` 的说明；当前安装版行为仍需本机确认。
- **[R2]** DeepSeek AI (n.d.) *DeepSeek Harness: command-goal*. Available at: https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/goal/command-goal/README.md (Accessed: 18 October 2026). 支持目标命令及状态查询；当前命令没有通用的 inline round-cap 参数，因此本文采用自然语言授权工具设置，不编造 `/goal --...`。
- **[R3]** DeepSeek AI (n.d.) *DeepSeek Harness: goal*. Available at: https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/goal/goal/README.md (Accessed: 18 October 2026). 目标保存与自动续跑分离；恢复后激活状态需要单独处理。相关 driver 文档：https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/goal/goal-round-driver/README.md 。
- **[R4]** scikit-learn developers (n.d.) *Common pitfalls and recommended practices*. Available at: https://scikit-learn.org/stable/common_pitfalls.html (Accessed: 18 October 2026). 支持训练/测试预处理隔离与 Pipeline 使用原则。
- **[R5]** scikit-learn developers (n.d.) *permutation_test_score*. Available at: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.permutation_test_score.html (Accessed: 18 October 2026). 应检查 groups 的具体语义，不能把限制组内置换等同于在 trial 间重分配标签。
- **[R6]** DeepSeek (n.d.) *Your First API Call*. Available at: https://api-docs.deepseek.com/ (Accessed: 18 October 2026). 官方 API 使用独立 API 配置；本文不假定 Desktop 登录自动提供 Python 调用能力。

### 科学参考

- **[R7]** Brookshire, G., Kasper, J., Blauch, N.M., Wu, Y.C., Glatt, R., Merrill, D.A., Gerrol, S., Yoder, K.J., Quirk, C. and Lucero, C. (2024) ‘Data leakage in deep learning studies of translational EEG’, *Frontiers in Neuroscience*, 18, 1373515. https://doi.org/10.3389/fnins.2024.1373515. 这项研究为按片段与按被试评价的差异提供背景；不能替代对本项目数据与模型的实测诊断。
- **[R8]** Majumder, B.P., Surana, H., Agarwal, D., Mishra, B.D., Meena, A., Prakhar, A., Vora, T., Khot, T., Sabharwal, A. and Clark, P. (2024) ‘DiscoveryBench: Towards Data-Driven Discovery with Large Language Models’, *arXiv*, 2407.01725. https://doi.org/10.48550/arXiv.2407.01725. 借鉴其用受控任务评价研究过程的思路；本计划不是 DiscoveryBench 的复现，也不沿用其成绩。

原始四份材料是研究背景和用户需求来源。它们中的开放设想、聊天推测与本次实测证据必须在报告中分开。

---

**给执行 DSH 的最后一条要求：** 在截止前交付能检查的真实进度。能做的部分继续做；做不到的部分说清楚；不能为了“整晚不停”无限尝试，也不能为了“明早好看”把未知写成已完成。

