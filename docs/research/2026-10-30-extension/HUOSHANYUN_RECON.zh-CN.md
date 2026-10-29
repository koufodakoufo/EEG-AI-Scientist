# 火山云有限只读勘察（2026-10-30）

采集时间：2026-10-30 00:03–00:11（Asia/Shanghai）。Builder R50 的首轮勘察；不属于 tested Actor 结果。正式本地项目为 `X:/projects/EEG-AI-Scientist`。

已确认 SSH、本人账户和多组共享代码/权重/EEG 数据候选；已创建本人空工作目录。**尚不能直接运行实验**：没有确认 GPU 配额，默认 Python 缺少科学计算依赖，REVE 代码要求的 Python 版本更高，EEGMAT 存在两套不等价预处理版本。BrainPEC 的确切代码入口和协作者真实身份映射尚未证实。

## 1. 范围与写入记录

- 使用现有 SSH 别名 `huoshanyun`，固定 `BatchMode=yes`、`StrictHostKeyChecking=yes`、`ConnectTimeout=8`、`ServerAliveInterval=10`、`ServerAliveCountMax=2`；未读取或输出认证文件。
- 远端检查为账户公开字段、有限目录清单、容量/设备元数据、少量相关 README/config/license、指定权重 SHA-256。没有全盘递归扫描，没有进入其他账户的 `/home/<user>` 内容。
- 共享挂载内的 `home/wzf`、`home/cx`、`home/wangzf_rebuttal` 只从已观察到的目录逐级定位相关研究代码；未读取迁移日志、敏感清单、代理配置、认证、个人笔记或运行日志。
- 唯一远端写入：在验证 `/home/duandh` 为 UID 1027 所有、非符号链接后，创建 `/home/duandh/projects` 与 `/home/duandh/projects/EEG-AI-Scientist-20261030`，均以 0700 创建。最终工作目录 UID 1027、0700、空目录。
- 未创建 Git 仓库，未安装、克隆、复制数据或权重，未启动 CPU/GPU 实验；未修改/删除/移动/改权限任何共享、公共或他人文件。组权限与目录可写位不构成写入或算力使用授权。
- 原始输出只保存在 Git 已忽略的 `.local/research/2026-10-30-extension/volcano/`；本报告未包含服务地址、个人邮箱或认证内容。

## 2. 身份与协作者候选

| 项目 | 实测 | 解释 |
|---|---|---|
| 当前登录 | `duandh`，UID 1027，GID 0，HOME `/home/duandh`，shell `/bin/bash` | 当前本人命名空间明确 |
| 组 | root、wheel、docker-access | 本轮没有提权，也不据此扩大授权 |
| 精确账户名 | `wzf`、`cx`、`wangzhifei`、`chenxiang` 均未命中 | 不代表对应协作者没有账户 |
| 姓名缩写候选 | `wangzf` UID 1014；`chenx` UID 1017 | 仅拼写线索，未证实真实身份 |
| wzf 共享树 | `/vePFS-0x0d/home/wzf` UID 1009 | 与当前 wangzf UID 不同，不能用目录名直接认人 |
| wangzf 发布树 | `/vePFS-0x0d/home/wangzf_rebuttal` UID 1014 | 与 wangzf 当前 UID 一致；仍不能据此证明姓名/角色 |
| cx 共享树 | `/vePFS-0x0d/home/cx`、`/omni-eeg-01/cx` UID 1001 | 与当前 chenx UID 不同，可能是迁移遗留，原因未核实 |

来源：01、02、03、06。只采集用户名、UID/GID、home、shell 等公开账户字段，不采集 GECOS 联系信息。

## 3. 存储与计算

| 路径/资源 | 采集值 | 可用性边界 |
|---|---|---|
| `/` / 本人 home | overlay 688G，总使用 594G，余 95G（87% 已用） | 不是本人配额；本人新目录位于该层，持久性未验证 |
| `/vePFS-0x0d` | gpfs 6.0T，余约 224G（97% 已用） | 共享，未找到本人所有的大容量命名空间 |
| `/vePFS-0x0e` | gpfs 6.0T，余约 47G（显示 100% 已用） | 共享、接近满；不写入 |
| `/neurobench`、`/omni-eeg-00`、`/omni-eeg-01`、`/omni-mnt`、`/omni-pretrain-database` | hpvs_fs，各自显示 8.0E | 文件系统呈现值，**不能解释为真实剩余容量或个人配额** |
| `/nix` | overlay 3.5T，余约 2.9T | 不是本人可用存储承诺，未写入 |
| 配额 | `quota` 不在 PATH | 个人空间/文件数配额未知 |
| CPU | Xeon Platinum 8457C；lscpu 总 180、online 0–130；affinity 180 | 三者存在视角差异，不能解释为可占用 180 核 |
| 内存 | free 显示总约 1.7Ti、available 约 1.7Ti | 系统/容器可见量，个人限额未知 |
| GPU | 8× NVIDIA H20，每卡 97,871 MiB | 仅设备可见；本轮授权分配为 0 |
| 调度 | PATH 无 sinfo/squeue/sacct/sbatch/qstat/bjobs；无已检查的 Slurm/PBS/LSF/CUDA allocation 环境项 | 无作业分配证明 |
| 容器限额 | /proc/self/cgroup 呈 Kubernetes 路径，/sys/fs/cgroup 目录空 | 本轮无法读取 cgroup CPU/内存限额；未访问集群认证/API |

首次 GPU 快照：0–2 卡内存 0 MiB；3、4、6 卡各 669 MiB；5 卡 2765 MiB/28%；7 卡 1019 MiB/21%。忙/闲会变化，也均不等于获得使用授权。来源：01、02、06。

## 4. 工具与连接

默认 `/usr/bin/python3` 为 Python 3.9.25，Git 2.52.0。PATH 可见 curl/wget/rsync/nvidia-smi；未发现 python、conda、mamba、uv、pip、nvcc。默认 Python 的包元数据中没有 pip、numpy、torch、transformers、mne、safetensors、huggingface-hub、pandas、scipy。没有执行他人的环境或模型代码。

相关 REVE 源码 `/omni-eeg-01/cx/EEG_FM/baseline/REVE/code/repo/pyproject.toml` 明确声明 `requires-python = ">=3.11"`，因此默认 Python 3.9 不满足该项目要求。

无认证 HEAD 探测（8 秒上限）：GitHub TLS 握手超时；Hugging Face 网络不可达；PyPI /simple/ 返回 HTTP 200。结果仅说明当时直接出站情况，不推断长期可达性。来源：03、11。

## 5. 代码与权重候选

### 代码

| 候选 | 已验证路径与证据 | 就绪程度 |
|---|---|---|
| wzf CBraMod 改编树 | `/vePFS-0x0d/home/wzf/code/CBraMod`；存在 finetune/pretrain/models/requirements 和预训练权重 | 可读；未发现可解析 Git HEAD；未运行 |
| wzf 通用下游框架 | `/vePFS-0x0d/home/wzf/code/EEG_FM/code`；有 dataset_registry.py、train_downstream.py、model_hub、trainer | 可读；model_builder.py 含 CBraMod/REVE 路径与模型处理；不等于 BrainPEC |
| cx CBraMod 源码 | `/omni-eeg-01/cx/EEG_FM/baseline/CBraMod/code/repo` | README 指向 wjq-learning/CBraMod；LICENSE 首行为 MIT License；Git HEAD 未解析成功 |
| cx REVE 源码 | `/omni-eeg-01/cx/EEG_FM/baseline/REVE/code/repo` | baseline README 指向 elouayas/reve_eeg；代码 LICENSE 首行为 MIT License；Git HEAD 未解析成功 |
| wangzf 发布快照 | `/vePFS-0x0d/home/wangzf_rebuttal/releases/t171_cf2efd90a1af` | 0555，含 custom、docs、scripts、部署标记；只作为候选快照，未认定为 BrainPEC |
| NeuralBench 示例包 | `/neurobench/pr` | README 说明 BrainOmni/FBMAE demo；未执行安装或缓存脚本 |

该发布快照的 `DEPLOYED_GIT_COMMIT` 文本为 `cf2efd90a1af2714b08365e8a6814e0999594d07`，`ARCHIVE_SHA256` 文本为 `ac583db5fa24eeb95c2dffeee09f492eead3606cad52720c6910a63270a575c4`。这只是部署标记内容，未重算 release.tar 或验证它与仓库对象对应。

BrainPEC：在 `/vePFS-0x0d/home/wzf/code/EEG_FM/code`、`/vePFS-0x0d/home/wzf/code/mdJPT`、`/omni-eeg-01/cx/EEG_FM/baseline` 做过最大深度 3、每树最多 200 目录的**名称**匹配，分别访问 6/10/33 个目录，没有命中 BrainPEC。跳过数据、输出、权重、环境与隐藏目录；没有全文穷举。mdJPT README 自称 Multi-dataset Joint Pretrain Transformer，发布树 custom README 自称实验实现与远端 Runner，均没有提供 BrainPEC 对应证据。**结论是尚未定位，不是服务器不存在。**

### 完整权重哈希

四个 CBraMod 文件均为 19,775,842 字节且完整 SHA-256 相同：

`0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178`

1. `/vePFS-0x0d/home/wzf/code/CBraMod/pretrained_weights/pretrained_weights.pth`
2. `/vePFS-0x0d/home/wangzf_rebuttal/pretrained/cbramod/pretrained_weights.pth`
3. `/omni-eeg-01/cx/EEG_FM/baseline/CBraMod/weights/pretrained_weights.pth`
4. `/neurobench/checkpoints/omni/pretrained_weights.pth`

这证明四个本地候选字节一致；“官方来源”目前来自相邻 README，尚未与远端发布方校验值独立核对。

| 文件 | 字节 | 完整 SHA-256 |
|---|---:|---|
| `/neurobench/checkpoints/omni/reve-base/model.safetensors` | 276773456 | `8ecc650619598748286c2457f81f5c6bd12e8bb59db44f7b02af1955c44de8fe` |
| `/neurobench/checkpoints/omni/reve-positions/model.safetensors` | 6628 | `4b793820b9df0998667deb6c8ce2dbb86b38221d5165c1844bc4971941b13f13` |

REVE base 与 positions 各有对应 config 和实现文件；另在 `/vePFS-0x0d/home/wangzf_rebuttal/pretrained/reve` 观察到同名布局，但未对那份 REVE 权重作字节一致性确认。REVE base 模型卡标注 `license: other`，不能把代码 MIT 自动套用于权重。未加载 pickle/checkpoint，未导入模型，未做推理。来源：06–11。

## 6. 数据候选与 EEGMAT 版本差异

| 候选 | 观察到的结构 | 尚未确认 |
|---|---|---|
| `/omni-eeg-01/raw_data/EEGMAT` | 顶层 68 项；抽样列出 README 和 EDF 文件名/大小 | 未读取 EDF、身份表或信号；完整性与授权沿用需另核实 |
| `/omni-eeg-00/downstream_preprocess/EEGMAT` | EEGMAT.zarr、sample_index.parquet、config/validation/label 文件 | 元数据声明 21 通道版本 |
| `/omni-eeg-01/downstream_preprocess/EEGMAT` | 同类文件，另有 downstream_eegmat/index/meta 的 Lance 目录 | 元数据声明 20 通道版本；split 独立性未查验 |
| `/neurobench/data/Zyma2019Electroencephalograms` | download 子目录 | 未展开或认证数据来源 |
| `/omni-pretrain-database/reve-dataset-hf` | README、data、positions、stats、3 个 CSV；data 顶层 358 项（只 stat 前40项） | README 自称 REVE open subset、约4.85TB；没有重算容量或验证全部内容 |
| `/omni-pretrain-database/reve-dataset` | data 顶层 52 项（只 stat 前40项） | 与 hf 目录关系、重复量与版本均未知 |
| `/omni-eeg-01/downstream_preprocess/wzf_dataset` | 23 个顶层候选，例如 FACED/DEAP/SEED 系列/PACE_pt 等 | 仅名称清单，非可直接使用或已授权证明 |

两份 EEGMAT 的元数据不能混同：

| 字段 | omni-eeg-00 | omni-eeg-01 |
|---|---|---|
| signals_shape | [1515, 21, 1000] | [1515, 20, 1000] |
| 采样率、时长、单位 | 200Hz、5s、uV | 200Hz、5s、uV |
| bandpass / notch | 0 / 0，notch 0 | 0.3–75Hz，notch 50Hz |
| 通道规则 | min_expected_channels 20；validation 为21通道 | 保留 EEG、排除非EEG辅助；明确列出20个通道 |
| normalization / dtype | none / float32 | none / float32 |
| split_counts | validation 未列出 | train 1319、val 148、test 48 |

以上是**现有元数据的声明**，不是本轮重跑验证结果。未读取 sample_index 或信号，未确认 subject-disjoint 划分，也未计算可比指标。两者 config 都指向 `/omni-eeg-01/raw_data/EEGMAT`，但通道/滤波不同，后续必须锁定版本与协议后再用。

## 7. 关键元数据指纹

| 文件 | SHA-256 |
|---|---|
| `/omni-eeg-01/cx/EEG_FM/baseline/README.md` | `9a5f962746796c69f0c46174ae75ef2dd24ce3b162c53928e073c61d8f073adc` |
| `/vePFS-0x0d/home/wzf/code/EEG_FM/code/model_hub/model_builder.py` | `bb635337a3ae8ad4488d4ff2e1ba5aad49137a5898fa2dbebd9d7456c609c403` |
| `/neurobench/checkpoints/omni/reve-base/README.md` | `0555caf36c67c6362a7616e7840740682d576fdc1efc5791837a6a0ec54babe2` |
| `/omni-pretrain-database/reve-dataset-hf/README.md` | `e4eaa66a0176a0c3a30ec4328f4867a4d4e73b28f37b6ece103042784698e7a5` |
| `/omni-eeg-00/downstream_preprocess/EEGMAT/dataset_config.json` | `7ae246e2ce4bf3899366a3b3ab3851a1bb10ea4f926ee8507cd43651f2001d6c` |
| `/omni-eeg-01/downstream_preprocess/EEGMAT/dataset_config.json` | `4404625d448c7ac4979f9d9196305a8e7dea646e4b285a84831e133ff78f0159` |
| `/omni-eeg-00/downstream_preprocess/EEGMAT/validation_summary.json` | `a6bf0b5b72f8a2de54ffcade28cdc83b9292d6e53296bcfcc403ca4fda2f70dd` |
| `/omni-eeg-01/downstream_preprocess/EEGMAT/validation_summary.json` | `c83428acf9a3d61adeb65cd000bd5f76f73b6cdbc3c84cd41be1d9e9f2529d0e` |

SHA-256 只提供本次快照的内容身份，不保证来源可信、未被修改或方法正确。

## 8. 下一步交接

1. 使用本人新目录承接后续最小环境；先确认 home 持久性与个人配额，大数据继续原位只读引用。没有创建共享挂载下的新本人空间。
2. 建立独立 Python >=3.11 环境与锁定依赖后，先做 CPU import/shape 检查；本轮未授权或执行安装。
3. 选择一个已有完整哈希的 CBraMod 与 REVE 权重候选，并为源码制定文件清单/哈希；当前代码副本没有可解析 Git HEAD，不能仅用上游名字证明源码版本。
4. BrainPEC 需要从已有正式项目的来源记录或协作者提供的明确入口建立映射；本轮结果不支持将 mdJPT、EEG_FM 或 rebuttal 发布树直接等同 BrainPEC。
5. 对选定 EEGMAT 版本先审查预处理、通道含义、受试者划分与泄漏风险；不得把20/21通道版本合并为同一实验条件。无需再复制整份现有数据。
6. 获取明确调度/算力分配依据后再讨论 GPU 执行；本轮 GPU 使用额度仍为零。

## 9. 证据索引

私有目录：`.local/research/2026-10-30-extension/volcano/`。

| 文件 | 内容 |
|---|---|
| 01-initial.json | 登录、候选账户、根目录、磁盘/CPU/内存/GPU、工具 |
| 02-top-levels.json | 共享挂载顶层、公开账户名与本人 home 属性 |
| 03-scoped-inventory.json | 数据/权重/代码目录、默认包元数据、HEAD 连通性 |
| 04-own-workspace.json | 创建本人空目录结果 |
| 05-scoped-partial.log | 一次输出被工具截断的记录；**不作为完整 JSON 或完整盘点依据** |
| 06-candidate-resources.json | 紧凑重采集、README、cgroup 可见性 |
| 07-model-data-metadata.json | 模型配置、两版 EEGMAT 元数据 |
| 08-code-provenance.json | 代码候选、README 来源指示、Git HEAD 失败证据 |
| 09-weight-hashes.json | 三份 CBraMod 与 REVE/positions 的完整哈希 |
| 10-bounded-brainpec-search.json | 有界名称查询、第四份 CBraMod 哈希、发布标记、空目录复核 |
| 11-code-identification.json | 指定代码/README/license/pyproject 的指纹与匹配行 |
| SHA256SUMS.json | 上述原始证据文件的本地完整 SHA-256 |

本轮发现均属于特定时刻、限定路径的现场证据；没有产生性能、泛化或方法优劣结论。
