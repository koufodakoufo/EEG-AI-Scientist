# 工作区与同步

GitHub 的 `main` 是已验证代码的共同主线。本地与服务器各有工作 checkout；数据、环境、运行结果不靠 Git 同步。当前正式本地路径不变。

| 位置 | 代码入口 | 用途 |
|---|---|---|
| Windows | `X:/projects/EEG-AI-Scientist` | 开发、阅读、发布 |
| 火山云 | `/vePFS-0x0d/home/duandh/projects/EEG-AI-Scientist/code` | Docker科学候选执行、可信评分及原生Builder分析；目录登记由用户办理 |
| nccserver0 | `/data/duandh/EEG-AI-Scientist/code` | 模型会话、可信研究控制器、调用账本及CPU验证 |
| GitHub | `koufodakoufo/EEG-AI-Scientist`，`main` | 版本化源码与可公开文档 |

此前完整研究使用“NCC 控制器 → SSH 传输冻结候选 → 火山云 Docker 执行 → 可信评分返回”。SSH 认证留在可信控制层，不进入候选容器。第一项研究的六个目标 episode 已沿此路径完成；[方法迁移结果](research/method-transfer-results.md)和[Builder 读出结果](research/readout-bottleneck-results.md)保留原证据。

本轮科学计算在火山云个人工程根的 `runs/evidence-guided-research-v1/`：`builder/` 保存 Builder 分析，`coding-readout-v6/base-r01/` 保存独立编码研究者的真实 EEG 作业。本地 `.local/research-renewal/` 保存协议、审查和研究者记录。NCC 旧原生模型通道授权失效；新通道使用本地独立上下文，经 NCC 控制器调用火山云。合成及真实 EEG 流程和预测复算均已完成。模型上下文接受访问审计，科学候选使用 Docker，两种边界不能混为模型进程的 OS 隔离。

## 火山云存储

协作者的代码实践是个人 vePFS 目录、Git 同步和固定版本发布。普通 `/home/duandh` 位于开发机临时文件系统，实例释放可能丢失。代码工作副本在 vePFS，环境/缓存/临时文件在 `/home/duandh/projects/EEG-AI-Scientist`；代码始终另有 GitHub 和本地副本。

资源规范要求 vePFS 目录登记归属和计划结束日期。用户于2026-11-02明确自行办理，并要求继续推进；当前记为 `registration_status=user_handling`，不作为开发、测试和后续研究准备的阻塞项，也不反复请求确认。原2026-11-15是准备阶段预计日期，后续以用户办理的登记为准。源码与独有实验成果仍按正常科研流程保留可恢复副本。

模型和公开 EEG 资源按路径原位只读引用，不重复上传整套数据。vePFS 不放 Python 环境。可见 H20 卡不能代替作业分配，本轮不启动 GPU 研究。

## Git 日常流程

短期分支按目的命名，例如 `feat/strategy-update`、`fix/evaluation-boundary`、`study/ignition-pilot`。实现、验证、提交后合回 main。新研究的协议、策略版本和重复次数写入配置，不为每次运行开一个永久分支。

Windows 状态检查：

```powershell
./scripts/sync-workspaces.ps1
```

在干净的 main 上发布已经验收的代码：

```powershell
./scripts/sync-workspaces.ps1 -Publish
```

脚本先核对本地分支、remote 和远端干净状态，推送 GitHub 后通过 Git-over-SSH 同步两个个人 checkout，并核对提交。服务器启用 Git `receive.denyCurrentBranch=updateInstead`：有本地修改时拒绝更新，不 reset、不覆盖文件。这里不需要服务器持有 GitHub 凭据。

单端可用 `-Target huoshanyun` 或 `-Target nccserver0`。ncc 使用当前校园网地址；多地址时显式传 `-CampusAddress`，不改全局路由。

如果在服务器开发，先提交在主题分支，本地用 Git-over-SSH fetch 取回并审阅，再合到 main 发布。不要在多端同时编辑同一个主线文件，也不要把服务器的未提交文件覆盖回本地。

## 研究证据与备份

源码和公开报告走Git；私有研究证据按研究主题保存在各工程根的`runs/`。2026-11-02收尾时，下列审阅副本已在火山云、NCC逐文件核对大小与SHA256，本地原件保留：

| 相对工程根的入口 | 初始清单范围 |
| --- | --- |
| `runs/method-transfer-v1/review/` | 407个文件：六次目标结果、主张审核、冻结方法、最终账本及复核记录 |
| `runs/readout-bottleneck-v1/review/` | 679个文件：Builder结果、六次研究者结果、参数与统计审计、最终账本及维护验收 |

每处的`BACKUP_MANIFEST.json`列出文件和哈希，`BACKUP_VERIFIED.json`记录核验；读出备份后补的说明文件另由`BACKUP_ADDENDUM.json`绑定，原清单不改写。这些副本包含小型拟合参数和预测产物，不包含原始EEG、缓存输入、基础模型权重、认证或原生会话目录。完整重放还需要原登记的数据与环境；原运行和失败回执保持原位。审阅材料包含参考答案和条件映射，不能整体交给后续受测研究者。

本轮新证据另外保存在 NCC 的 `runs/evidence-guided-research-v1/backup/`：`completed-science-v1/` 和 `spatial-pretraining-v1/` 保存已完成的 EEG 分析；`coding-evidence-v2/` 保存 411 个筛选后的编码流程、失败、报告评价及研究决策证据文件，约 31 MB。后一份已从 NCC 下载到本地恢复检查目录，逐文件与原件核对一致。原生会话正文、平台背景、认证和缓存不包含在此备份中；原文件没有移动或删除。本地核验入口为 `.local/research-renewal/evidence-backup-v2/RESTORE_VERIFIED.json`。

## 运行命名与历史

新运行名按 `study-v<protocol>-g<generation>-<condition>-r<repeat>` 组合，例如 `method-transfer-v1-g1-learned-r01`。当前控制器要求单层 run_id，不允许斜杠；研究、协议和代际的层次同时作为元数据字段，不能把多层路径直接传作 run_id。创建时间、模型版本、代码 commit、资源与父策略也写入元数据；正文用研究问题和条件名。

旧 ncc 部署根及其中 integration checkout、旧火山云 dated 根和旧环境保持原位，仅用于冻结证据和恢复，不再作为新开发入口。旧分支由 `archive/*` 标签保留，原始目录映射见 [历史索引](history/README.md)。

## 环境与验证

最新实现 `cb19082` 的完整支持套件各收集 900 项：Windows 816 通过 / 84 跳过，NCC 881 / 19，火山云 879 / 21。核验清单在正式本地工程 `.local/research-renewal/condition-assessment-v2/validation/VERIFIED.json`，绑定源码、依赖、前后文件身份与清理结果；冻结时记录的是父提交加两项修改，修改内容随后原样提交为 `cb19082`。三台机器均使用独立公开源码快照，Windows 快照也排除了可选私有报告样例；该样例另经本地专项测试。旧真实 EEG 编码运行仍绑定 `0a8456a` 及其原 880 项验收，不替换旧运行源码。

本轮真实 EEG 编码任务使用本地模型会话、NCC 控制器和火山云 Docker，已完成两次公开拟合、两次验证、一次最终测试，随后一次源码重拟合和一次完整预测复算。原始证据分别在两台服务器项目根的 `runs/evidence-guided-research-v1/coding-readout-v6/base-r01/`；本地审阅副本在 `.local/research-renewal/coding-eeg-workflow-v6/`。这条新通道可用；NCC 旧原生模型授权仍未恢复。模型上下文的访问审计不等于其进程受到操作系统隔离。

`config/workspaces.json` 是本人机器路径清单，不含认证；同步脚本读取其中的 code 路径，包不会自动把 runs/python 字段当成运行配置。实际运行显式设置 `EEGFM_ROOT`（其下包含任务、运行和允许的知识），或使用 checkout 默认值。新代码可 `pip install -e`，科学包和 Linux 沙箱能力分别验收；CPU PyTorch 应先从 CPU wheel 安装，避免普通依赖解析安装整套 CUDA 库。

火山云 Python 3.12.16、CPU Torch 2.6.0、NumPy 2.2.6、SciPy 1.15.3、scikit-learn 1.6.1 已安装并检查。基础解释器也在新根的 `runtime/python`，不依赖旧日期目录。完整依赖版本在 [cpu-requirements.txt](../config/cpu-requirements.txt)，仅描述这套 Linux CPU 环境；不要求 Windows 复制全部包。

使用已配置的火山云环境：

```bash
source /home/duandh/projects/EEG-AI-Scientist/environment.sh
cd /vePFS-0x0d/home/duandh/projects/EEG-AI-Scientist/code
python -m eegfm --help
```

包以 editable 方式安装；环境设置独立缓存、临时目录及4线程。重建时先从 PyTorch 官方 CPU wheel 源安装 `torch==2.6.0+cpu`，再安装版本清单和项目；不把环境目录当源码同步。服务器证据位于各新工程根的 `evidence/`。

ncc 只读复用原科学 venv；验证新代码时显式设 `PYTHONPATH=/data/duandh/EEG-AI-Scientist/code/src`。既有环境和冻结实验不被新包安装覆盖。

### 上一阶段验收（维护源码 `0206182`，2026-11-02）

| 环境 | 完整套件结果 | 解释 |
|---|---|---|
| Windows | 380通过，83跳过 | 可移植检查；Linux专属能力另在服务器验证 |
| NCC Linux | 445通过，18跳过 | 使用已部署源码和科学环境；跳过项单独保留 |
| 火山云 Linux | 443通过，20跳过 | 用户命名空间受限；受测候选实际使用Docker后端 |

以上是完整pytest套件结果，依据本地`.local/method-transfer/postrun-maintenance-verification.json`及三份逐端日志。显式Docker/SSH资格检查和未提供的私有校准样例不由这些通过数替代；读出任务的Docker资格另行执行。维护修复统一Windows/Linux的候选文件清单排序，保留原Linux顺序和哈希语义；只在全部科学运行及数值复放结束后应用，没有改变已冻结的实验。

第二组读出对照始终绑定原源码`5f2beb8`：当时完整套件为Windows 374/83、NCC 439/18、云端437/20（通过/跳过）。六份候选均已完成独立拟合、完整预测与统计复核；四份最终报告完成，两次总结会话因后端不可用而中断，未重跑。原验收、失败与追加记录保留，ignition未准入。

火山云`unshare`/`bwrap`用户命名空间仍受环境限制；Docker替代后端已接入`worker.py`并用于实际科学候选执行。其边界包括无网络、只读根目录、非root用户、只挂载准入材料及退出清理。CPU亲和性和地址空间限制、数值库线程限制、磁盘采样监测分别记录；不把命令接受某个参数写成已具备cgroup资源保证。GPU作业仍为0。

每项研究继续使用其准入清单绑定的源码、依赖、输入及预算。新checkout通过测试不能改写旧运行身份；旧探针、失败和修复经过保留在Git历史及运行证据，不在入口文档重复累积日志。

登记标记是项目台账，不是平台权限开关。当前由用户办理，具体安排见上方“火山云存储”，无需为登记重复暂停准备工作。

本轮保持初始`OPENBLAS_NUM_THREADS=4`、`OMP_NUM_THREADS=4`；历史OpenBLAS线程池切换故障的复现记录仍保留，不声称已修复上游数值库。
