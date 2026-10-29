# E05 源码与隔离重放审计

**审计接受：源码/保存参数检查通过；验证与测试干净重放的逐数组、逐指标结果均与原始证据完全一致。** 完成时间为 2026-10-30 01:43:47 +08。

审计对象为已完成的 E05（`no_skill`），不是 Builder 参考分析。原始结果为五次真实原生会话、生命周期 `done`，科学覆盖范围仅 Q1；Q2/Q3 均未完成。审计只读取其冻结候选、公开资源、报告和受信作业证据，不读取认证或 Actor controls，不向 Actor 回传重放结果，不触发新的模型调用、拟合、候选选择或原始一次性测试账本。

## 身份与范围

- 服务器代码 HEAD：`23f9df73dcbdf2318f7a0c794d7d7ccff2674358`。
- 原工作根：`/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029`（以下称 WORK）。
- 原配置：`WORK/controller/comparison-v2/E05.json`。
- 锁定候选：`WORK/episodes/E05/worker-evidence/real-E05-A2-test/candidate`。
- 候选 digest：`9e5ccc8dcc20bd1e85aa3bcdbd1a90329193e3f979f1b820cf9ca8af202cc0e7`。
- 原报告 SHA256：`dc1c2412b4813623c0453092cad425fc9f5d3f8ee674efc5d72b21dec99b0fa1`。
- 新证据目录：`WORK/replays/E05`。原 E05 目录不作为重放输出目录。
- 执行器：`scripts/research/replay_real_episode.py`，显式调用原 `SandboxedWorkerEvaluator` 与 `ScientificAggregator`，不调用 `run_episode`、Actor 或其控制器。

重放属于**相同锁定代码、相同输入和运行环境的独立干净执行**，不是算法的独立实现，不是新的未见测试，也不构成新的科学样本。其目的为核验执行可重现性及报告一致性。

## 源码与已保存参数检查

直接审阅实际 `candidate/main.py`、`output/fit_probes.py`、公开 `eeg_api.py` 与冻结协议。独立检查保存在 `PREEXECUTION_AUDIT.json`。

| 检查 | 证据与结论 |
| --- | --- |
| 训练范围 | 训练脚本只取公开训练集的 features、subject_ids、sample_ids、x 和两层表示；没有读取任务标签 y。576 行、24 名训练参与者；144 行、6 名验证参与者，参与者和样本集合不相交。 |
| 标准化 | 保存的 x_mean、x_scale、y_mean、y_scale、active_columns 五项与训练数组直接重算完全相等；所有 62 个目标列活跃。验证集不用于估计这些变换。 |
| 拟合系数 | 对保存的四个系数矩阵计算对应岭回归正规方程残差，最大相对残差 `5.365169394369652e-16`。仅代入检查，不求解或重新拟合。 |
| 验证选择 | 两层正模型 alpha 均为 1000，负对照均为 10000。保存的选择与记录网格中的验证评分/大 alpha 平局规则一致；保存系数的验证评分与所选记录一致。未重新拟合整个网格，故此项不声称独立重建每个被舍弃模型。 |
| 负对照 | 保存的 permutation 与 default_rng(20261030) 的完整重建完全相同；参与者块偏移 18、块内非零偏移、双射、参与者无自映射、块内位置无自映射以及所有活跃目标列改变均通过。负模型的正规方程右端确实使用置换后的训练目标。一个随机化仅是诊断对照，不是显著性置换检验。 |
| 推理路径 | main.py 只从 evaluation 输入读取原始 x 与 sample_ids；保存的训练变换和系数用于预测。它接受但不读取 train 参数，也不重新拟合或调参。实际测试输入由受信 worker 限制为 x、sample_ids、subject_ids 三个数组。 |
| 冻结模型 | EEGModel 从公开 resources 严格校验固定 CBraMod 文件/权重，strict load_state_dict 后 CPU/eval/requires_grad_(False)，通过 inference_mode 获取第 6、12 层表示。原任务 logits 由第 12 层继续执行最终归一化、池化及公开冻结头得到；无骨干或任务头更新。 |
| 标签边界 | 候选的测试挂载不含标签/特征金标；私有 truth 仅供沙箱外受信聚合器读取。公开验证特征用于协议允许的验证选择；这不是未见数据估计。静态源码和当前执行支持未使用任务标签的结论，不声称对未审阅历史行为作全面取证。 |

## 报告与科学结论核对

原报告的 CSV 含全部 48 行（两划分 × 两层 × 12 组）；576 个数值单元与受信 `released_metrics.json` 在 `rtol=1e-6, atol=1e-8` 下均一致。报告 Markdown 的 432 个 Q1 数值及 27 个任务数值在其各自三位/六位小数舍入精度下均一致，11 个候选/公开文件哈希均吻合；另存 `REPORT_NUMERIC_AUDIT.json`。

额外以独立 NumPy 公式和只读私有 truth 核对点估计：A1 验证 3 项、A2 验证 147 项、A2 测试 147 项全部通过，最大绝对差分别为 0、0、`1.1102230246251565e-16`。内容包括 accuracy、balanced accuracy、按正负样本对计分的 AUROC、逐组正/负 R² 及差值、活跃/有定义/常数列数量。金标始终位于候选沙箱之外；没有输出个体标识或标签。该补充核验没有独立重写 bootstrap 区间，记录为 `POINT_ESTIMATE_AUDIT.json`。

| 核心量 | 原始受信结果 |
| --- | --- |
| A1 验证 balanced accuracy | 0.673611 |
| A2 验证 balanced accuracy | 0.673611 |
| A2 测试 balanced accuracy | 0.569444 |
| A2 每划分 Q1 覆盖 | 24 个层/特征组组合 |
| Q2 / Q3 / numeric_scope_complete | 0 / 0 / 0 |
| 预先规定正向规则通过的验证组合 | (6,02)、(6,03)、(6,05)、(12,03) |
| 同规则通过的测试组合 | 仅 (6,04)，即第 6 层的供给版 wavelet entropy |

测试 activity 的 R² 在第 6/12 层分别为 −5.046798、−3.696017，负向结果未删除。四个验证阳性组合均未在测试通过同一规则。总体仅支持有限的线性可恢复性结论；不能推出任务依赖、因果作用、临床有效性或 Q2/Q3 完成。小参与者数、单个诊断置换、固定模型/头、均值池化、线性探针和粗粒度 bootstrap 尾部分位数仍是限制。

## 干净执行与逐数组对照

重放在原报告完成后启动。原始 worker enrollment 与新执行器逐字段完全一致，包括 FileBinding 路径/哈希、运行时二进制、冻结依赖清单、worker/aggregator 源码、聚合策略和预算。输入/公开资源只读引用，不复制数据集；仅 worker 复制候选自身的三个小文件到新的证据目录。沙箱为 bwrap `--unshare-all`，无网络、无 GPU，4 线程、12 GiB 上限；父进程及子 worker 使用 4–7 核，和 Actor 的 0–3 核分离。

冻结运行时清单的 3 个绑定文件、10 个已安装包版本及 Python 链接均另行核实相符，见 `RUNTIME_AUDIT.json`。这验证了已登记运行时身份，不等同于对完整依赖/操作系统文件树逐字节封存。

最终 `REPLAY_AUDIT.json` 状态为 `accepted`。两划分各自的 `results.npz` / `analysis.npz` 均具有相同成员、形状、dtype、行标识及数组值；浮点数组的最大绝对差也为 **0**，强于预定 `rtol=1e-6, atol=1e-8` 标准。样本标识 dtype 为 `<U34`，logits 和正/负预测为 float64，训练 permutation 为 int64。两划分每份 305 项发布指标和 `trusted_analysis.json` 都完全相同。原 A1/A2 验证 logits 亦完全相同。

| 重放 | 退出码 | worker 耗时 | 峰值子孙进程 RSS | 数组 / 指标 |
| --- | --- | --- | --- | --- |
| A2 validation | 0 | 168.331 秒 | 293,093,376 字节 | 全部精确一致 / 305 项精确一致 |
| A2 test | 0 | 264.700 秒 | 292,360,192 字节 | 全部精确一致 / 305 项精确一致 |

两次 worker 均确认无存活自有子进程；全过程无重试。诊断时间戳/路径及执行耗时不作为科学数值一致性的条件；时间差没有用于改写原始性能记录。比较器的五项合成自检还确认：同值与容差内数值通过，行标识变化、dtype 变化及超容差数值均被拒绝，见 `VALIDATOR_SELFCHECK.json`。

执行命令与参数可在脚本和新目录下 request/execution/status 记录中核对。重新调用脚本必须另给全新目录；它拒绝覆盖现有重放。原源码、候选拟合文件、受信原作业产物、原 worker 数据库和报告共 56 个保护文件的运行前后 SHA256 快照完全相同，变化路径为空；快照文件为 `SOURCE_HASHES_BEFORE.json` / `SOURCE_HASHES_AFTER.json`。本次执行脚本 SHA256 为 `1aa9a553fc14d22896c91739f3cd8a095c44ed7d55231db29f494618c880afd4`。

## 验收边界

源码及保存参数、报告数值、独立点估计核对、干净重放均接受。没有发现足以否定当前 Q1 结果的软件/报告不一致。结论仍是 **E05 的部分 Q1 分析获得可重现性支持，Q2/Q3 未做**。源码审查和恒等代码重放不能排除共同实现误差、原始科学设计局限或未审阅历史行为；完整模型/数据管线的独立方法复现、bootstrap 方法的独立实现均不在此次验收之内。

本审计不修改 E05–E08 封存核心/公开文档，不对原 Actor 成绩追加新的测试机会，不推送或提交 Git，不将审计自身的实现核验计作新的科学发现。
