# 晨报 — Flash 过夜运行（2026-10-20）

**一句话：** 工程链路真实打通（DeepSeek Flash、项目工具、Search/Fetch、可恢复轨迹）；Scientist 基于 7 篇可核对文献完成一轮探索，给出 3 张假设卡和 1 个优先实验；**没有真实 EEG 数据，因此没有真实 EEG 结果**。

**研究什么：** EEG 表示中哪些可预测信息在换试次/会话/被试后仍成立，现有证据能解释到什么程度。优先“任务 vs 被试/会话/采集条件”，延伸选“跨被试掉分是信息缺失还是读出受限”。

**模型看到了什么：** Scientist 自己发起 8 次 Search、14 次 Fetch 尝试，保留 10 篇正文，最终引用 7 篇（MOABB、Yin 跨被试划分、Liu EEG-FM 基准、LaBraM、Banville SSL、Fallahi 身份、Hebart & Baker）。只读分段字符范围，覆盖率 5–21%，无一篇全文；3 篇抓错未引用，EEGManyPipelines 抓取 504。未收到任务书、参考答案、生成器或私有映射。

**提出的解释：** ① 同会话高分可能混有被试/会话/采集签名（文献未直接分解）；② 身份/环境可能是主轴（身份 EER 1 天 6.7%→1 年 14.3%；SSL 簇跟通道数/记录日期走）；③ 优先：同一冻结编码器上线性探针 vs 微调的差距（BENDR 32.18→51.11，chance 25%），但缺“无标签对齐+线性读出”的中间条件。

**实际做了什么：** 真实 capability 五项全 PASS；99.3/49.6→99.2/50.8 回归解释 6/6 规则检查通过；两个中性合成案例各完成 2–3 次真实工具执行（预测 3/3、2/2）；文献回合 16 次模型请求/42 次工具调用，以 `finish_study` 收尾并校验引用。真实 EEG 未执行；按 E2 写了数据要求与人工夹具入口。

**判断变化：** 不能把同会话高分直接当泛化；MOABB 自称 within-session 是上界，cross-session/subject 不在其范围；2K EEGNet 在 EEG-FM 基准总排名第二，削弱“更大模型=更好迁移”。但这**不等于**“EEG 解码主要是泄漏”——没有直接分解，不能证明没有任务信息。下一步从“再训大模型”转为“读出阶梯 + 身份/元数据混淆基线”。

**还缺：** 真实 EEG 的试次/会话/被试三级不相交分解；无标签对齐能否追回微调收益；跨会话任务解码；EEGManyPipelines 分析灵活性；7 篇低于 8–12 目标，两篇 2026 为预印本。Fallahi 的“345 人/6007 会话”和“嵌入按会话/设备聚簇”在源文为真，但**不在实际读取范围**；顶层“低维频谱/节律结构”是推断而非测量。

**资源：** 00:58–01:30；项目 API 峰值价保守计 **CNY 1.65 / 20**；30 次模型尝试、10 Search、18 Fetch；输入 560,786 / 输出 52,938 tokens；无未知费用；不含 dsh 开发费。

**位置与命令：** 报告 `reports/flash_20261020_0058/`；轨迹 `runs/flash_20261020_0058/`。启动/恢复均为 `python -m eeg_scientist.cli overnight-flash research --name literature_v1`（先 `status` 看状态；重跑复用状态、不再付费；完整命令见 `RUN_INDEX.md`）。

**最值得看：** ① `runs/flash_20261020_0058/research/literature_v1/final_answer.md`（Scientist 原文） ② `reports/flash_20261020_0058/EVIDENCE_AUDIT.md`（逐条核对） ③ `reports/flash_20261020_0058/EXPERIMENT_PROTOCOL.md`（缩减版下一步）。
