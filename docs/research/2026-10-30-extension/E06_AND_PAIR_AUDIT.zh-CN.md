# E06 与 E05/E06 配对结题审计

**接受现有 E06 的候选身份、报告数值和 Q1 点估计一致性；两回合均仅完成 Q1，不能宣称 Q2/Q3 完成或技能有效。** 本审计在 2026-10-30 上午用户要求停止新研究后完成；只读现有证据并作确定性哈希与算术核对，没有调用模型、重新拟合、运行候选、启动重放或增加测试机会。

## 审计位置与范围

服务器 `nccserver0` 的根路径定义如下，后文缩写均严格展开到这些位置：

- `WORK=/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029`。
- `CODE=/data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration`。
- `E=WORK/episodes/E06`，`R=E/controller/runs/real-E06`。
- E06 锁定候选为 `E/worker-evidence/real-E06-A2-test/candidate`；报告为 `R/FINAL_REPORT.md`。
- 本地私有复核脚本与机器结果为 `.local/research/2026-10-30-extension/closeout/E06/audit_existing.py`、`AUDIT.json`。仅保存摘要、源路径和哈希，无凭据、原始 EEG、个体预测或金标。

E05 的既有独立干净重放另见 [E05 源码与重放审计](E05_SOURCE_REPLAY_AUDIT.zh-CN.md)。**E06 本次没有执行独立干净重放**；E06 自己报告的 prelock local replay 属于 Actor 自查，不能替代 Builder 独立重放。两者的验证强度不应混写。

## 身份、输入与处理条件

| 对象 | 当前实测 SHA256 / digest |
| --- | --- |
| E05 锁定候选 | `9e5ccc8dcc20bd1e85aa3bcdbd1a90329193e3f979f1b820cf9ca8af202cc0e7` |
| E06 锁定候选 | `520080f35e31d116a41f399a80ca20ed142a3eb4ddd0108c1a27215bae4dd925` |
| E06 报告 | `0a0260accfa50802a16b884a67c304256d5ced29a7dc56d5a13318e9c29a47c7` |
| E06 enrollment | `9a6b3ed1c40179208d1fae0f1a6c42fd3536647dbb113ec02c0baa445d76d891` |
| E06 冻结 contract | `6175a7862d6b362fab9be6d99d5b1fe1961de583b2557857007aeab303d686dc` |
| E05 comparison-v2 配置 | `d8b0191448ce75605ff946a600fd6f7b5da524b9f4c1d6f9f2150b0b2866ec79` |
| E06 comparison-v2 配置 | `dcf5ae5f09f8e8a124865f21f429b4b39d3a2211cfaaa669c8954f7923df7cfc` |
| 实际注入的 M15 skill | `54d5ce036ebb184bc653060196bed701807bb516b63dfc40d892d9938079191d` |
| E06 A1 validation 发布指标 | `248c79149d2c74c3e0d4a9e2d126dd7b65690d3dbda3259dac23303404af8d3f` |
| E06 A2 validation 发布指标 | `78a0421cd10ffa5de6c10799c95169ac6d007f264209f330f333535cf2826dbb` |
| E06 A2 test 发布指标 | `369a5f85c25208e49c73eca14d5b51618f42767ee0bf4caa94723945df79d191` |

逐项实测 `WORK/controller/comparison-v2/EXPERIMENT_FREEZE.json` 的 63 项绑定全部吻合；包括冻结比较协议、配置、科学代码、公开资源和数据绑定。E05/E06 配置的不同键只有 `call_ids`、`case_root`、`condition`、`episode_id`、`run_id`、`skill`、`trusted_root`。前后两回合使用相同任务、模型 `gpt-6.1-sol`、medium effort、每会话 900 秒、最多六会话、每 episode 5400 秒、科学 worker 900 秒、4 CPU 线程、12 GiB 内存和零 GPU 配额；实际用量可以不同。

技能源为 `CODE/framework/benchmarks/brainpec_pilot/skills/distinguish-recovery-response-and-causation/SKILL.md`；源文件、E06 public-staging 和实际 case public 三处字节哈希一致。E06 五个 own-session receipts 都记录同一注入哈希，E05 五次均为 null；原生状态与模型完成记录相符。`PROVENANCE.json` 明确为 **M15 从一个 synthetic development 轨迹蒸馏**，不是本轮真实任务 dev 蒸馏，不是实时更新的技能，也没有此前已证实的技能收益。

E06 候选的四文件共 833244 字节；controller snapshot、validation worker、test worker 和 case output 四处逐文件吻合。按冻结的规范化 manifest 算法重算 digest 也吻合。

| 文件 | SHA256 |
| --- | --- |
| `README.md` | `58ffd7033e45c64e05fac8fd3608d9e03d679922bdc6f4a06a32a4582cee3a41` |
| `fit.npz` | `1080641abeab92ef81cb8e8d9217056ef24280c3b5961fb3db67f0e5aeeb338c` |
| `main.py` | `34cb0a00c0298ccc69163bc75d4b77ead31de20ce419825e2427af184cc1ece8` |
| `science.py` | `845b3ae0f73e84ab0030377e983a30171ce9f200f3e2d5f3755b340604b92ae5` |

## 独立检查的方法与结果

直接审阅锁定 `main.py`、`science.py` 和 case output 的 `fit_science.py`、`finalize_q1.py`。推理入口只读取 evaluation 的 `x`、`sample_ids`，调用冻结模型并加载保存的系数；不读取 evaluation feature targets，不使用任务标签拟合，不在 worker 中重训。训练脚本以公开 train features 为探针目标，训练变换只取 train，验证用于预先声明的 family/alpha 选择。`science.py` 内虽保留干预辅助函数，最终入口没有调用，最终 fit 只保留 Q1/负对照及 permutation，未提交干预或残差产物。

这是一项有界源码审查，不是对全部历史操作的取证；本次没有独立重新估计 E06 的训练标准化和正规方程，也未重新拟合被舍弃的选择网格。报告中这些 Actor 自查结果不因此升级为本次独立核验。

| 核对 | 本次结果 |
| --- | --- |
| 受信数值副本 | 每作业的 released_metrics、receipt、aggregation-private 与 trusted_analysis 四处 metrics 完全一致；A2 sealed final test 与锁定候选身份一致。 |
| E06 报告表格 | 96 个 Q1 点估计、168 个区间/差值数值、14 个任务指标/区间值，均在报告六位小数舍入精度内吻合；48 个 family/alpha 字段吻合。未声称自动核验全文每个数字。 |
| 选择记录 | 保存的 24 个组/层选择均满足已有 240 个 family/alpha 组评分与平局规则；保存的 family 与记录一致，所选 validation score 与受信指标一致。只核对记录，不重新拟合网格。 |
| 科学 manifest | `WORK/cases/E06/output/scientific-manifest.json` 的 25 个文件绑定全部吻合。 |
| 独立点估计 | 从既有 worker predictions 与沙箱外私有 truth，以直接 NumPy 公式核对每划分 75 项：accuracy、balanced accuracy、成对排序 AUROC、24 组正/负 R² 和差值。validation 最大绝对差为 0，test 为 `1.1102230246251565e-16`。没有运行模型或重算 bootstrap。 |
| 原始预测跨条件比较 | E05/E06 的 validation 和 test 原始 logits 分别逐数组精确相等。 |
| 失败检查 | 机器核对 failures 为空。保留局部原型退出 130，不将它改记为成功。 |

私有 truth 只在服务器端作上述算术核对，没有进入 Actor 或候选沙箱，没有复制到本地。报告和候选身份已核对不意味着科学设计无偏，也不排除共同实现误差。

## 配对结果

| 量 | E05：无 skill | E06：固定 M15 skill |
| --- | --- | --- |
| 实际原生会话 / 生命周期 | 5 / done | 5 / done |
| 科学验证 / 最终测试 | 1 / 1 | 1 / 1 |
| Q1 覆盖（每划分） | 24 组/层 | 24 组/层 |
| Q2 / Q3 / numeric_scope_complete | 0 / 0 / 0 | 0 / 0 / 0 |
| validation balanced accuracy | 0.673611 | 0.673611 |
| test balanced accuracy | 0.569444 [0.402778, 0.736111] | 完全相同 |
| test AUROC | 0.643904 [0.398852, 0.877701] | 完全相同 |
| 正向描述性规则：validation / test | 4 / 1 | 8 / 5 |
| 五次原生进程 elapsed_seconds 总和 | 612.528 秒 | 1360.898 秒 |
| 原始 A2 validation / test worker 耗时 | 4.077 / 3.670 秒 | 257.651 / 233.919 秒 |

这里的正向描述性规则是同时要求 Q1 family-adjusted R² 下界 >0、正模型减负对照 R² 的 marginal CI 下界 >0；它不是新做的显著性检验，也不是通用研究能力评分。E05 test 只有 `(6,04)`；E06 test 为 `(6,02)`、`(6,03)`、`(6,04)`、`(6,10)`、`(12,04)`。后者分别为 delta log power、theta log power、供给版 wavelet entropy、绝对相关均值，以及第 12 层 wavelet entropy。

E06 validation 通过的八组合是 `(6,01)`、`(6,02)`、`(6,03)`、`(6,06)`、`(6,07)`、`(6,10)`、`(12,03)`、`(12,05)`，其中三个 `(6,02)`、`(6,03)`、`(6,10)` 在 test 也通过；E05 四个 validation 组合均未在 test 通过同规则。区间只是从原受信发布产物读取；2000 次 participant bootstrap、六名测试参与者和极端分位数的不稳定性依然成立。

下表保留全部 test Q1 组均值，差值只是两个已完成方法的点估计相减，未建立差值采样区间。组定义沿用公开 panel，未重新定义 EEG 特征。

| 层 | 组 | E05 R² | E06 R² | E06−E05 |
| --- | --- | ---: | ---: | ---: |
| 6 | 00 | -5.046798 | -5.046798 | 0.000000 |
| 6 | 01 | 0.299810 | 0.361563 | 0.061754 |
| 6 | 02 | 0.468840 | 0.633241 | 0.164401 |
| 6 | 03 | 0.355496 | 0.549342 | 0.193846 |
| 6 | 04 | 0.666675 | 0.679113 | 0.012439 |
| 6 | 05 | 0.615794 | 0.654881 | 0.039087 |
| 6 | 06 | 0.538088 | 0.633407 | 0.095319 |
| 6 | 07 | 0.553134 | 0.629656 | 0.076522 |
| 6 | 08 | 0.224203 | 0.224203 | 0.000000 |
| 6 | 09 | 0.024597 | 0.024597 | 0.000000 |
| 6 | 10 | 0.656351 | 0.781376 | 0.125026 |
| 6 | 11 | 0.348501 | 0.273609 | -0.074892 |
| 12 | 00 | -3.696017 | -3.696017 | 0.000000 |
| 12 | 01 | 0.268792 | 0.298891 | 0.030099 |
| 12 | 02 | 0.298390 | 0.359820 | 0.061430 |
| 12 | 03 | 0.241578 | 0.345178 | 0.103600 |
| 12 | 04 | 0.505796 | 0.614055 | 0.108259 |
| 12 | 05 | 0.504252 | 0.582651 | 0.078400 |
| 12 | 06 | 0.484848 | 0.546554 | 0.061706 |
| 12 | 07 | 0.498788 | 0.465724 | -0.033064 |
| 12 | 08 | 0.088489 | 0.088489 | 0.000000 |
| 12 | 09 | 0.004763 | 0.004763 | 0.000000 |
| 12 | 10 | 0.562636 | 0.611208 | 0.048572 |
| 12 | 11 | 0.240553 | 0.240553 | 0.000000 |

E05 使用按层整体选择的线性探针，最终正模型 alpha=1000、负对照 alpha=10000；E06 每组/层分别选择线性或坐标平方扩展与 `{0.1,1,10,100,1000}`，23 组选择线性、仅 `(12,07)` 选择平方扩展。E06 负对照沿用该组正模型 family/alpha 重新拟合，使用 seed 1701 的参与者块错配；E05 使用另一预定随机化 seed 20261030。负对照的变坏也会放大正减负差值，因此不能把差值改善单独解读为更强表征恢复。

上述方法差异是 Actor 在共同任务约束下的实际选择，必须与 skill 条件一起完整报告。一个按顺序执行的 Agent 配对、一个任务、无独立条件重复，不能识别技能的平均或因果收益；也不能用 24 个相关组当作 24 个独立 Agent 重复。原生进程耗时含推理、工具和等待，worker 耗时受环境负载等影响，不是纯模型推理成本；实际美元成本未知。E05 独立重放也曾耗时 168.331/264.700 秒，故不能以原始单次 worker 耗时差直接量化算法加速或技能成本效应。

## Q2/Q3 失败保留与生命周期解释

E06 预先声明 Q2/Q3 须同时满足数值与完整 worker 运行时间可行性。已有 `fit-evidence.json` 记录数值门通过；`aborted-prototype-runtime.json` 记录干预延续阶段 Ctrl-C、退出 130，原始/Q1 部分约 174 秒，尚有八次六层延续未完成，且声明未查看干预 outcomes。这个局部声明的历史完整性未由本次全面取证验证，但最终缺少干预/残差产物、受信 Q2/Q3 均为零是直接验证的事实。中断不证明完整 worker 必定超过 900 秒；它证明完整可行性尚未建立，不能把未估计效应写成零效应。

R68 原生会话自身与该原型不同：`E/launches/session-03-R68/status.json` 是 `completed`、退出码 0、895.377 秒，小于 900 秒；`E/launch-receipts/session-03.json` 与权威 BUDGET 的 R68 完成状态、prompt SHA 相符，所有受跟踪子进程已回收。`WORK/cases/E06/output/local-science/session3-status.json` 仍写着 fitting in progress，是保留的中间状态，已由受信结束回执取代，不据此误报 episode 仍在运行。

两回合均真实经过 brief、委托 scope review、contract、baseline、scientific attempt、lock、一次 test、report，最后 `STATE.json` 和 `EPISODE_RESULT.json` 为 done。scope review 是协议机械准入，并非科学结论背书；done 是生命周期结束，并非三个问题全部成功。更多逐节点证据见 [集成验收](INTEGRATION_ACCEPTANCE.md)。

仍须保留：两条件 activity 泛化失败、PAC 恢复较弱、E06 某些组低于 E05、Q2/Q3 空缺、单次诊断随机化、validation 选择不确定性未进入 bootstrap、小参与者样本、固定模型/头及均值池化局限。没有证据支持任务依赖、唯一生理因果机制、临床效果、一般能力提升或 RSI。E01 的冻结失败另存；E07/E08 只有预注册配置，未启动，不能填补第二对实验。
