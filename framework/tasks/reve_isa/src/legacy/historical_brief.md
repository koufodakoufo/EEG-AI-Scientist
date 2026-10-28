# REVE × ISA：两轮证据驱动 RSI 科研任务书

日期：2026-10-08（北京时间）。任务标识建议：`reve_isa_seedfix_rsi2`。

本任务书依据 [RSI_TASK_START_GUIDE.md](RSI_TASK_START_GUIDE.md) 编写，供启动 Agent 生成具体协议、执行适配器和机器配置。它是完整的科研需求入口，不是已可执行的 YAML，也不代表实验或 Supervisor 已启动。

## 1. 用户目标与任务对象

用户已确认：将历史 CBraMod ISA 成功实验的方法迁移到 REVE，让 RSI Agent 自主完成两轮由真实实验反馈驱动的科研迭代，检验能否复现六个数据集 FT 都提升的现象。

RSI 改进对象为 REVE 上的 ISA 科研方法及实验代码。运行中的 Harness、控制器、认证、预算和可信评价器不属于候选改写对象。

核心问题：在相同六数据集、LODO、被试划分和下游评估口径下，同刺激跨被试 ISA 能否改善 REVE 的下游性能？若直接迁移效果不足，Agent 能否根据训练与验证证据诊断原因，并在保留 ISA 核心机制的范围内改进？

主要比较是“官方预训练 REVE 直接下游”与“由同一官方权重初始化、经过 ISA 后训练的 REVE”。不要求 REVE 达到 CBraMod 的绝对分数或相同增幅。主要目标为六集 FT test bAcc 均提升；同时完整报告 LP、macro-F1、逐集差值、宏平均和不确定性。

性能成功和流程成功分别判断。两轮有效迭代完成但收益不足，仍需如实交付有证据的负结果；不能宣布性能目标达成。

## 2. 唯一主参照及已查证事实

主参照是 **2026-08-16，10s Lance、60ch、all-source、SEED session-fix** 的 dense CBraMod ISA 实验。不要替换成旧 Zarr/bridge 版、raw-metadata 版、source train-only 版或 MoE 版。

工程根：`/mnt/cfs-omni/wzf/cross paradigm/60ch_again`。

| 材料 | 相对该工程根的路径 |
|---|---|
| 截图对应报告 | `ISA_10S_LANCE_LODO_ALLSOURCE_SEEDFIX_NOCLIP_SEEDS42_47.md` |
| 协议、代码和复现命令索引 | `ISA_10S_LANCE_LODO_ALLSOURCE_SEEDFIX_CODE_AND_RESULTS.md` |
| ISA 原始结果根 | `results/tencent_lodo_allsource_seedfix/20260816160135` |
| 官方 CBraMod baseline 结果根 | `results/tencent_cbramod_official_baseline/20260816123039` |
| 数据定义 | `isa_10s_repro/manifest.py`、`isa_10s_repro/lance_io.py` |
| 后训练协议与执行 | `isa_10s_repro/protocol.py`、`isa_10s_repro/run_lodo.py` |
| 下游参照 | `isa_10s_repro/run_official_baseline.py`、`isa_10s_repro/run_checkpoint_baseline.py` |

每个结果根下使用 `<TARGET>/downstream/lp.json` 和 `ft.json`。ISA 另有 `<TARGET>/run_config.json`、`posttrain/A_leaveout-<TARGET>/train_log.json`。

已经读取两组共 24 个下游 JSON，重新计算六折 bAcc 均值，与用户截图一致：

| Target | CBraMod baseline FT bAcc (%) | ISA FT bAcc (%) | 历史报告差值 (pp) |
|---|---:|---:|---:|
| SEED | 47.86 | 54.48 | +6.62 |
| SEEDIV | 32.85 | 38.51 | +5.66 |
| SEED_V | 25.06 | 31.03 | +5.97 |
| SEED_VII | 20.97 | 24.02 | +3.04 |
| FACED | 35.15 | 51.59 | +16.44 |
| DEAP | 51.36 | 55.51 | +4.15 |
| 宏平均 | 35.54 | 42.52 | +6.98 |

历史 LP 宏平均为 35.74 → 38.01%，+2.27 pp；LP 不是全部提升。差值来自未四舍五入数据，可能与表中两位小数直接相减不同。

已确认对应代码和结果 JSON 存在。六个历史后训练 `emotion_cbramod.pth` 在报告指定位置均未找到；报告记录了历史哈希，不能用记录代替文件存在证明。REVE 迁移从官方 REVE 权重开始，不依赖找回 CBraMod 后训练权重；若需重新执行 CBraMod 校准，另计资源，不能默认增加完整复跑。

外部实现参考：

- `/mnt/cfs-omni/wzf/tasks/ISA-only/isa_data_new_scripts/isa_data_new_patch/posttrain_dense_exp1.py`：stimulus 配对及 InfoNCE。
- `/mnt/cfs-omni/wzf/tasks/ISA-only/isa_posttrain_trainlance_v1_repro_20260815`：Lance 接入依赖。
- `/mnt/omni-eeg-01/cx/AAAI_NeuroAffect/decop`：现已定位的下游依赖工程；正式冻结前核对实际版本与调用链。

历史 REVE 工程 `/mnt/cfs-omni/wzf/tasks/REVE-ISA` 仅供权重加载、适配和故障参考。其 `scripts/reve_posttrain_isa_checked.py` 实际采用 attention pooling、batch 中心化、projector 和按情绪标签 SupCon，与本任务的 stimulus-paired flatten InfoNCE 不同。旧报告的 FT 5/6 提升、FACED 下降不能作为本任务 baseline 或直接迁移结果。旧 `tasks/ISA_posttrain_spec.md` 也存在将 stimulus ISA 写为标签 SupCon 的描述冲突，以本次主参照代码和运行配置为准。

## 3. 数据与隔离协议

数据根为 `/mnt/omni-eeg-01/downstream_preprocess/wzf_dataset`。以下是历史 manifest 的明确入口；启动 Agent 必须实际打开、核验版本与元数据，不能只检查目录名。

| Target | 相对数据根的 release | 历史样本数 | 被试数 | 类别数 | 每折 train/val 被试数 |
|---|---|---:|---:|---:|---:|
| SEED | `SEED/derived/lance_mdjpt60_badch` | 14895 | 15 | 3 | 4/4 |
| SEEDIV | `SEED-IV_10s_v1/derived/lance_mdjpt60_badch` | 14655 | 15 | 4 | 4/4 |
| SEED_V | `SEED-V_10s_v1/derived/lance_mdjpt60_badch` | 11424 | 16 | 5 | 4/4 |
| SEED_VII | `SEED-VII/derived/lance_mdjpt60_badch` | 27340 | 20 | 7 | 5/5 |
| FACED | `FACED/derived/lance_mdjpt60_badch` | 10332 | 123 | 9 | 31/31 |
| DEAP | `DEAP/derived/lance_mdjpt60_badch` | 7680 | 32 | 2 | 8/8 |

固定输入为 200 Hz、10 秒、60 个 mdJPT 通道，历史 shape `(N,60,2000)`。保留坏导处理后的 release，不覆盖原始数据。通道顺序、单位、标签值及语义必须从 release 和 loader 查证并记录，尤其 DEAP 二分类维度与阈值不得凭经验猜测。

每个 target 独立从官方 REVE 权重开始，其他五个 source 的全部样本用于后训练：显式 `posttrain_split=all`，不能沿用函数默认的 `train`。目标数据集不参与该模型的后训练；六个 target 之间不继承候选权重。

SEED 按每个 subject 的日期 session 排序映射为 `1/2/3`，核对每人恰好三个 session；其它五集不改写 session。只修正元数据解释，不改信号、标签或行顺序。检查 stimulus key、trial 对应关系、不同 subject 正对以及每个 source 的有效配对数量；禁止静默回退为随机正对或标签 SupCon。

下游冻结历史六次被试划分（split seeds 42–47），直接从原始 JSON 提取实际 ID，保存 split manifest。每折内部 train/val/test 被试互斥；六次划分是重复随机划分，不是 test 互斥的传统 K-fold。检查样本、trial 及可识别跨数据集同源关系，记录 SEED 家族隔离的已知边界，不能宣称 LODO 已证明跨家族无重叠。

## 4. REVE 迁移与基线验收

### 4.1 忠实迁移起点

- 官方 REVE-base 初始化；定位实际模型、配置、通道位置资源、代码版本及 SHA256，验证加载成功，禁止缺权重后随机初始化。
- ISA 正对来自同一 source 内同刺激、不同被试；不同 source 不直接组成正对。
- 首个忠实实现使用 REVE 相应 token 输出 flatten 后 L2 normalize，配对 InfoNCE，temperature 0.1。明确 token 轴、是否含特殊 token、位置编码和有效 token mask。
- 不假设 REVE token 与 CBraMod 的 `(C,10,200)` 相同；不硬套 CBraMod 的 patch 数与特征维数。
- 目标初始为 `L_total = L_ISA`，无 NPD、CDA、Recon、MoE 或标签 SupCon。
- 历史后训练参照：full encoder、seed 42、batch 64、40 epochs、Adam、LR 2e-4、warmup 3、cosine、weight decay 1e-4、梯度 norm clip 1。优化器细节须与真实执行源码/日志核对。
- 学习率不要求机械照搬 CBraMod；Agent 可依据数值和吞吐预检在第 6 节范围内选 REVE 起点，记录理由。工程 smoke 不计科研轮次。

预处理需要明确区分“原始 µV 振幅裁剪”和“REVE 输入规范”。保留历史 NoClip 数据口径，不引入 ±100 µV 裁剪；REVE 若需要归一化或位置处理，先核对本地官方实现，然后在 baseline 与所有候选间一致冻结。旧 REVE wrapper 的 z-score/±15 SD 不能无说明自动继承。

### 4.2 先完成 R0：原始 REVE baseline

baseline 必须使用上述数据和 split，不能直接挪用旧 REVE 表。先核验数值、梯度、权重加载和下游 head，再完成六集 LP/FT 对照；baseline 建立和校准不计入两轮科研迭代。

历史下游起点：LP 冻结 encoder、新线性头、flatten、最多 100 epochs、LR 1e-3；FT 更新 encoder、新 MLP 头、flatten、最多 60 epochs、LR 1e-5；batch 128、weight decay 1e-4、early-stop patience 10、min_delta 0.01。核验特征标准化拟合范围、优化器、调度、分类头尺寸和随机状态的真实实现。

如这些设置对 REVE 明显数值无效，可以在 R0 校准阶段只依据 validation 做一次明确、有限的共同协议修正。随后冻结同一评价规则，baseline 与候选都使用；不能给候选更多调参机会或训练预算。记录训练 seed、split seed、初始化和单/多进程 RNG 行为，不能把 split seeds 自动当作 FT 的全部训练 seeds。

baseline 验收以加载真实性、split 一致性、数值有效、训练记录和完整输出为准，不以达到某个 CBraMod 分数为门槛。基线失败不能算作候选收益。

## 5. 开发反馈、测试隔离与科学指标

两轮科研决策使用后训练诊断及 target 下游 validation 指标。每轮下游在 validation 上选 epoch；不得按 test 选择 epoch、LR、方法或是否继续训练。

baseline 和每轮候选可按冻结协议产生最终 test 输出，但将其保存在独立审计路径，最终方案冻结前不得进入 Scientist/Engineer 的上下文、累计开发报告或决策工具。若当前 adapter 无法保证隔离，则推迟 test 执行，保存 val-best 权重和划分，在两轮决策及最终候选锁定后统一评测。Reviewer 也不得将封存测试差值反馈为研究建议。

六次历史划分存在交叉复用被试，本次还会使用各 target 的 validation 指导方法；即使逐折隔离正确，也属于开发性迁移研究，不能声称是全新独立人群的确认性结果。若发生 test 信息进入决策，显式标记污染与结论降级，不能继续称“未见测试”；另建独立确认集需新协议及资源。

主要指标：每个数据集六次划分的 test balanced accuracy 均值、标准差，以及 candidate − 同协议 REVE baseline 的配对差值；六集等权宏平均和正增益数据集数。辅助指标为 macro-F1、LP、逐折表现、收敛与计算代价。历史主表采用逐折样本预测计算 bAcc，不要擅自改为先逐被试算指标再平均；后者可另列诊断。

最终性能目标是锁定的共同候选在六个 FT 数据集上均有正的平均 bAcc 差值，同时报告幅度及 paired bootstrap CI（5000 次、seed 20260713）。六次划分有依赖，CI 主要描述划分稳定性，不等同于六次独立实验的显著性。不能用“部分集显著、其余集忽略”宣布六集提升，也不能从两轮中按各集 test 挑最优拼表。

## 6. Agent 自主范围

固定：六集及其 release、60ch/10s、SEED session policy、LODO/all-source、split manifest、官方 REVE 初始化、下游评价协议、测试隔离、完整报告。原始工程、历史结果、数据及官方权重只读。

允许 Agent 在独立候选快照中修改 REVE adapter、ISA batch builder、loss/representation 和后训练优化代码，并补 loader、诊断、结果汇总与数值测试。可信评价器、split、job 模板、验证器不放入候选可编辑清单；发现错误时单独修复并重新审查相关 baseline/候选有效性。

以下为任务设计的建议研究边界，启动时冻结为具体数值参数及可编辑文件清单，不是要求穷举：

| 可研究项 | 范围与约束 |
|---|---|
| 后训练 LR | 1e-6 至 2e-4 |
| temperature | 0.03 至 0.3 |
| weight decay | 0 至 1e-2 |
| warmup | 0 至 8 个整数 epoch，总 epochs 固定 40 |
| 梯度 norm clip | 0.5 至 5 |
| REVE 表征/投影 | 先建立 flatten 忠实迁移；第二轮可有依据调整 token 聚合或投影，仍保持 stimulus 对比目标，明确其已是变体 |
| source 采样与配对 | 可改平衡和有效配对效率，不删掉某个 source、不引入 target，不改 stimulus 身份 |
| 工程性能 | AMP、分块、梯度检查点、loader/cache 可优化，验证数值语义和对比负样本集合 |

有效对比 batch 初始 64；梯度累积不自动等价于同一 InfoNCE 大 batch，必须单独记录每步真实负样本数。OOM 修复不能悄悄改变比较条件。

两轮默认均从官方 REVE 权重重新后训练，不把第 2 轮变成第一轮续训 40 epochs。将续训、多后训练 seeds、额外消融、MoE/NPD/重建、多阶段 S1/S2、标签 SupCon 或新数据集纳入主实验均超出本任务默认范围，需要明确扩展协议。

## 7. 两轮有效迭代契约

流程：准备及 R0 基线 → R1 忠实迁移实验 → 根据 R1 的训练/validation 证据确定 R2 → R2 完成 → 冻结最终候选 → 测试汇总与有限结束审议。

R1 回答“正确迁移 stimulus ISA 后 REVE 的表征与下游验证表现如何变化”；R2 必须针对 R1 的证据提出有区分力的改动或必要的稳定性验证，不提前写死为某个 LR。R1 已提升也不能跳过 R2；不得强行将负结果改写成正结果。稳定性验证若是重复，应解释它回答的不确定性，不能仅重复执行凑数。

**最低有效轮数为 2**，本次用户的明确要求优先于通用文档的三至四轮示例。每轮必须覆盖六个 LODO target，并完成六集 LP/FT 六次划分的训练与验证；测试按第 5 节封存或延迟。封存未完成时不得称最终性能验收完成。

每轮必须具备：问题和假设、冻结执行计划、工程/协议检查、实际实验、核验报告及下一步决策。失败、smoke、修复、R0、历史结果引用和单个 LODO target 不计科研轮数。Supervisor 计数必须与此对应，不能把 baseline campaign 或六个 worker 误计有效轮次。

每轮记录：已知证据、改变与保留项、预期与反向结果解释、实际源码/数据/权重身份、loss/梯度/训练有效性、validation 比较、成本、继续/换方向依据。R2 必须可追溯地引用 R1 报告。

完成两轮后进入结束审议；不默认增加第三轮，不默认追加消融或多 seed。流程符合契约时可自主交付，无需逐轮或最终重复批准。预算耗尽或前提无效时保存部分结果和真实阻塞，不把终止写成两轮成功。

## 8. 资源、预算和启动状态

当前用户授权本次撰写任务书，准备交给 RSI 启动；本次不调用付费模型、不提交 GPU 作业、不部署服务。实际启动时沿用会话或 run 已有明确授权，不重复索要；本文件不凭空新增云资源或账户授权。

建议预算起点：`min_valid_rounds=2`、最多 4 次科研实验尝试、48 次 Agent 调用、每实验最多 2 次工程修复；有限结束审议最多 2 轮、600 秒。上述数字是本任务建议，需启动 Agent 根据 adapter 粒度和吞吐估时落实，不能把“4 次科研尝试”机械套成包含 R0 的总 campaign 上限。

| 启动项 | 已知状态与落实责任 |
|---|---|
| 后端/模型 | 当前 Harness 文档为 `codex_python`、`gpt-6.1-sol / xhigh`；启动 Agent 核对任务采用的真实配置，禁止静默切换 |
| account profile | 本任务尚未绑定具体 profile；先查已有明确授权和配置引用，无法确定时只询问缺失选择，不读取或写入凭据正文 |
| GPU 平台/卡型/卡数 | 历史在腾讯 TiONE，不代表本次自动沿用；核实可用且已授权资源，冻结每 campaign 最大卡数和 worker 数 |
| 并发 | 建议一个活动 campaign；六个 target 可在已授权卡数内并行，每个 target 默认一个训练进程 |
| GPU 时间/截止时间 | 用户尚未指定；先进行已授权的吞吐 smoke，给出 R0、R1、R2 与最终评测的估时，落实运行上限，不能填写无限 |
| 提交数 | 按真实 adapter 定义计数，并另列 worker 提交上限，包含 R0、两轮、失败重试和可能延迟的测试任务；不得用一个 campaign 掩盖多作业开销 |
| 调用与服务权限 | 在本次 run 专属配置中显式记录；禁止直接复制单次 SDK smoke 的一次调用/零实验预算 |

GPU-hours 或总截止时间若为硬上限，需由 adapter/运行管理层真正执行；不要向 Harness YAML 填不支持字段并宣称已生效。资源不足时保留实验完整性，不能擅自删数据集或划分来凑两轮。

新任务 scratch：`/omni-eeg-00/home/wzf/scratch/reve_isa_rsi/<run_id>/<job_id>`；可复用 cache：`/omni-eeg-00/home/wzf/cache/reve_isa_rsi`。启动进程前验证可写并设置 `TMPDIR/TMP/TEMP`。持久产物保留独立项目的 `results/` 和 `logs/`。不在 `/tmp`、`/dev/shm` 放大文件，不因存储规则改动已有运行；只清理本 run 自有且已成功完成的临时目录。HPVS 的 `8.0E` 不是无限配额。

## 9. Harness 接入和启动 Agent 的交付责任

建议任务目录：`/mnt/cfs-omni/wzf/auto research/tasks/reve_isa_rsi`；新实验代码和结果使用独立项目目录，不在历史 `60ch_again` 上就地研究。

启动 Agent 应自行补齐：

1. 将本任务书全文作为原始 `research_prompt`，固定约束进入非空版本化 `research.protocol`；保存本文件哈希，避免 SDK 角色只看到泛化摘要。
2. 生成 `brief.md` 引用、`protocol.md`、`research.yaml`、真实 `job_spec.json` 模板、run 配置、数据/split/源码/基础权重索引和哈希；大数据/权重只建索引，不塞进上下文。
3. 明确 `source_root/source_files`、逐个 `editable_files`、有限数值 `parameter_bounds`、同键 `allowed_variations` 和真实参数绑定。类别参数、整数及组合约束由可信 adapter 验证。
4. 实现真实 `scheduler` adapter 的准备、审查、提交、等待、分析与重连；禁止使用 `fake` 结果充当科研。R0、两轮和最终评估阶段需具体编排，文字任务书不会自动拆分 campaign。
5. 候选代码改进需先通过实际执行认证。当前通用 scheduler 的 `candidate_execution_adapter_not_certified` 限制必须在本任务接入时解决，核实远端加载的是冻结候选源码及其依赖；只设 `allow_code_changes=true` 不够。未接通时明确阻塞，不能将固定脚本顺序运行宣传为完整代码自进化。
6. 可信验证入口至少检查：跨被试 stimulus 正对、SEED session policy、LODO target 排除、数据行/标签一致、官方权重非随机初始化、InfoNCE 数值/梯度、REVE token/位置对齐、baseline/candidate split 与评价协议一致、测试信息隔离。
7. analyzer 在 `{analysis_output_dir}/report.json` 输出真实来源、协议/源码哈希、执行有效性、预期评估次数和任务 schema。明确一轮有 6×2×6=72 个目标/模式/划分评价单元；若测试延后，区分 validation 与 test 阶段计数，不虚报 72 次 test 已完成。`expected_test_evaluations` 依据控制器实际语义绑定。
8. 生成跨轮累计开发报告，排除封存 test；分别检查 Scientist/Engineer/Reviewer 的 context packet 包含本任务、允许范围、最新验证证据与 R1→R2 决策链。
9. 运行适当的适配器检查、数值 smoke、吞吐估时、`inspect` 与 `doctor`；这些检查不替代科学协议验收。
10. 使用 `runtime.cli research start` 注册、`research requirements` 核对任务解释，通过独立 Supervisor 持续执行。返回真实 run ID、namespace、配置/账户引用、heartbeat、当前阶段、有效轮数/尝试数/预算和管理命令。注册成功不等于服务运行。

## 10. 结果报告与最终验收

每轮保存实际命令、源码快照与执行哈希、release/split 身份、初始化与选中 checkpoint、请求/实际 epoch 和 update、停止原因、loss/学习率/梯度诊断、LP/FT 逐折 validation 指标、wall time/step time/吞吐/显存与利用率采样，以及异常和修复记录。

最终交付：

- R0、R1、R2 和锁定候选的身份及完整配置；逐集逐折 LP/FT bAcc、macro-F1 和汇总表。
- baseline 对照、每轮变化和最终候选选择依据；测试封存/解封记录，不按 test 重选方案。
- 两轮有效性与 R1→R2 证据驱动关系；测试性能成功、研究流程成功分别给出判断。
- 迁移与历史 CBraMod 的一致项/差异项，已知数据家族重叠和重复划分限制；不将旧 REVE SupCon 结果混为同方法证据。
- 所有负结果、缺失项、预算与计算代价、仍未解决的问题；保留可复现代码、必要权重及产物索引。
- run ID、Supervisor 实际状态、结果路径、暂停/恢复/状态查询命令；不因本会话结束而失去后续执行。

给启动 Agent 的指令：以本文件为科研任务契约来源，先补齐真实 REVE 接入与启动材料，核实已有资源授权并落实剩余运行配置，再通过持久 Supervisor 执行。无需用户手写 loader、loss、YAML 或长串哈希；可以查证和实现的问题自行处理，只有资料无法消除的研究范围或资源授权缺口才向用户提问。


---

## 11. 本次实际启动补充：后续会话授权优先

用户现在已要求启动，并明确“用腾讯的 tione，很多 GPU”。第8节“本次仅撰写，不启动”是历史状态，本次依据后续授权运行，无需再次询问模型调用、持久Supervisor及TiONE提交。科学协议保持原文不变，目标仍为两轮REVE ISA，不是S1/S2。

### 已落实部署

- Run ID: reve_isa_tione_20261008。账户user_current；codex_python，gpt-6.1-sol/xhigh；48次Agent action、4次campaign尝试、2次修复、2次结束审议/600秒。配置由启动端设置，Engineer不可修改。
- 训练仅在腾讯TiONE现有预付费资源池rsg-b227f5pp，GPU-HCCPNV6；最多48卡同时运行，每worker最多8卡，总云任务上限32（部署probe已占1），每worker最长86400秒；总截止1792057831.603617。不购买资源，不停止别人的任务；不足则等待。
- 48卡是上限，不必占满。按六target组织worker，在分配GPU内并行独立downstream folds。posttrain batch64必须是真实InfoNCE negatives；不可把每卡64变成全局512，梯度累积不等于扩大negatives。先测吞吐再调并行；LP特征可按权重/样本身份缓存。
- Supervisor在当前机器调度；隔离任务通过broker请求TiONE，不能在本机训练，不能直接读取凭据/调用云SDK。接口文档：`/mnt/cfs-omni/wzf/auto research/docs/research/TIONE_BROKER.md`。请实现task内请求生成、remote worker和等待/分析，不再向用户索要工程接入或YAML。
- 源码以批准snapshot为准；broker会复制到自己的只读snapshot。不要依赖旧工程cwd。使用scheduler占位符`{research_artifacts_dir}`；云worker写broker定义的output与共享artifacts。准备和数值验收不计科研轮次。
- prepare/review做本地CPU元数据/契约检查；真实REVE CUDA/梯度/吞吐smoke在云worker完成，通过后开始R0与R1。bootstrap validation不占GPU、不提交网络请求；覆盖数据映射、正对、InfoNCE小输入、scheduler/broker构造。
- scratch在`/omni-eeg-00/home/wzf/scratch/reve_isa_rsi/reve_isa_tione_20261008/<job_id>`；持久checkpoint/metrics写本run artifacts，缓存须按版本/权重身份复用。截止由broker和worker共同落实；不能删数据集或划分来凑轮数。

### 已有证据与实现提醒

- 优先读取审计：`/mnt/cfs-omni/wzf/auto research/docs/research/REVE_ISA_RSI_READINESS_AUDIT.md`。按实际文件核验其中事实，勿重复猜参数。
- 官方权重与代码目录：`/mnt/omni-eeg-01/cx/EEG_FM/baseline/REVE/weights/reve-base`、`/mnt/omni-eeg-01/cx/EEG_FM/baseline/REVE/weights/reve-positions`。参考适配器：`/mnt/omni-eeg-01/cx/Neuro_KE/neuro_ke_organized/src/neuro_ke_fusion/backbones/reve_adapter.py`。请求读取所需源码，复制必要模型实现进task包并固定版本；禁止执行旧SupCon方法。
- 本地`/usr/bin/python3`已发现torch/lance/pyarrow/numpy/transformers/scipy/sklearn。启动端正在进行真实TiONE环境与sandbox probe；这不代表CUDA已通过。云worker再次自检；缺依赖查实际错误，不假定安装状态。
- R0可在首个campaign内先执行并持久化，再做R1；R2须等R1训练/validation分析后决策，不能预先硬编码。R0不计有效迭代。
- 延迟test到方法锁定后。如果最后完整评估R0/R1/R2三个条件，则expected_test_evaluations为{"1":0,"2":216}（6targets×2modes×6splits×3conditions），必须由真实调用统计，不可按test重选方法。216也不是同一候选的独立统计样本。保持原文最终交付与测试隔离要求。
- 缺实现自行补全。账户、平台、部署预算已明确，只有证据无法消除的科学歧义才形成用户问题。
