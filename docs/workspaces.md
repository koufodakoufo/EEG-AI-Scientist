# 工作区与同步

GitHub 的 `main` 是共同代码主线；本地和服务器各有一个工作副本。数据、环境和私有研究证据单独保存，不靠 Git 同步。研究现状见[当前阶段](research/phase-completion.md)。

## 四个入口

| 位置 | 代码入口 | 当前用途 |
| --- | --- | --- |
| Windows | `X:/projects/EEG-AI-Scientist` | 开发、模型会话、审阅与发布 |
| 火山云 | `/vePFS-0x0d/home/duandh/projects/EEG-AI-Scientist/code` | 持久代码副本；科学任务优先在火山云执行 |
| NCC | `/data/duandh/EEG-AI-Scientist/code` | 既有环境、历史证据与备份 |
| GitHub | `koufodakoufo/EEG-AI-Scientist` 的 `main` | 已验证源码和可公开文档 |

`config/workspaces.json` 保存上述路径，不含认证。C 盘的 `EEG-FM-RSI` 是历史支持目录，当前正式工程在 X 盘。旧服务器目录保留用于恢复，不是新的开发入口。

## 本轮实际在哪里运行

本轮 LEACE 残余属性实验的可信控制器和 CPU 科学任务均在火山云，本地保留独立模型会话及审核。控制器经固定主机密钥的本机 SSH 调用科学 worker；候选代码在 Docker 中运行，认证不进入容器。模型上下文的访问审计与候选容器隔离是两件事，不能称模型无记忆或已受操作系统隔离。

本轮已完成两次拟合、两次验证、一次锁定测试、作者报告，以及一次源码重拟合和一次预测复算。科学运行绑定 `3295f23224797a76008ed45f5011e90db5fe5f25`；没有 GPU 作业。早期研究的“NCC 控制器 → 火山云科学 worker”路径仍保留，原运行不迁移、不改写身份。

本地本轮证据入口：`.local/research-renewal/phase-completion-v2/`。实验原报告和候选在其 `execution-r03/research-result/`，论文比较在 `leace/`、`brainpec/`，独立复核在 `numeric-review/independent/`。两份完整论文对照分别位于各自的 `source-assessment/REVIEW.md`，总验收位于 `PHASE_RESULT.json`。

## 火山云存储和环境

2026-11-17 检查时，vePFS 可用空间为零。因此本轮科学执行使用个人临时目录：

`/home/duandh/projects/EEG-AI-Scientist/tmp/residual-recovery-v1/`

原 vePFS 数据和历史成果只读。临时区活动与历史分别限 512 MiB，活动区保留 8 GiB 空间下限；核对后的新成果已导出本地。普通 `/home/duandh` 可能随实例释放而丢失，不能算持久备份。空间恢复前，火山云持久代码同步也不能称已完成；不会删除公共或其他人的文件来腾空间。目录登记由用户办理，不作为反复审批或执行阻塞项。

Python 环境在 `/home/duandh/projects/EEG-AI-Scientist/envs/cpu/`，与源码分开。已验证 Python 3.12.16、CPU Torch 2.6.0、NumPy 2.2.6、SciPy 1.15.3、scikit-learn 1.6.1；版本清单见 [cpu-requirements.txt](../config/cpu-requirements.txt)。

```bash
source /home/duandh/projects/EEG-AI-Scientist/environment.sh
cd /vePFS-0x0d/home/duandh/projects/EEG-AI-Scientist/code
python -m eegfm --help
```

这里会进入持久 checkout，其版本必须先核对。它不自动切换到本轮临时区的冻结执行源码。重建环境先安装官方 CPU Torch wheel，再安装版本清单及项目，避免无意下载整套 CUDA 依赖。

NCC 复用已验证的原科学环境；检查新代码时显式设置 `PYTHONPATH=/data/duandh/EEG-AI-Scientist/code/src`。不覆盖历史环境。可见 GPU 不等于已有资源分配；新研究需重新核对任务和资源。

## CBraMod 权重在哪里

火山云共用模型文件位于 `/neurobench/checkpoints/omni/pretrained_weights.pth`。本地对应文件位于 `X:/projects/EEG-AI-Scientist/.local/research/2026-10-29-brainpec-real/resources/pretrained_weights.pth`。两端均实读核验，文件为 19,775,842 字节，SHA-256 为 `0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178`。

本轮研究者收到的是固定缓存，题面未给 checkpoint 身份。事后核查了训练、验证和测试缓存的生成回执、冻结清单、输入映射，并确认三者均登记上述权重。本轮训练的是读出模型。骨干权重保持原位。

## Git 怎么同步

日常只保留一个共同 `main`。开发使用短期目的分支，如 `fix/evaluation-boundary` 或 `study/ignition-pilot`；验证后合回主线。阶段用 `archive/` 标签保留，每次运行不另建永久分支。不强推、不重写已发布历史。

Windows 检查状态：

```powershell
./scripts/sync-workspaces.ps1
```

干净的 `main` 上发布：

```powershell
./scripts/sync-workspaces.ps1 -Publish
```

脚本核对本地和远端状态，推送 GitHub，再用 Git-over-SSH 更新个人服务器 checkout；服务器不需要 GitHub 凭据。有本地修改时拒绝覆盖，不 reset。只同步一端可加 `-Target nccserver0` 或 `-Target huoshanyun`。NCC 使用当前校园网地址；多地址时显式给 `-CampusAddress`，不改全局路由。

`-Publish` 会先检查选中的服务器，某端不可用时会在 GitHub 推送前停止。收尾可以分别发布 GitHub、逐端同步并记录结果；其中一端成功不代表全部同步成功。本轮科学源码为 `3295f23`。最终说明和阶段归档使用 `archive/paper-workflow-trial-v2`，GitHub、本地和 NCC 共用 `main`。火山云持久工作副本停在 `2a02ab4`，vePFS 当时可用空间为零。火山云用于本次科学执行的个人临时区另有本轮精确版本。

如果在服务器开发，先提交到目的分支，本地 fetch、审阅、合入后再发布。避免多端同时编辑同一主线文件。模型、公开 EEG 和冻结输入均原位只读引用，不复制整套资源。

## 证据备份和恢复

私有证据按研究主题放在各工程根的 `runs/`。精选备份排除认证、参与者输入数组、骨干权重、原生会话正文和平台记忆。每份备份有文件清单、大小和 SHA256；上传后实际下载还原，再核对原件未变。筛选备份用于恢复审阅证据；完整科研重放仍需要原数据、环境和冻结版本。

本轮已完成的 EEG 实验在 NCC 有一份可恢复快照，位于 `runs/evidence-guided-research-v1/backup/residual-recovery-leace-r03-science/evidence.zip`。实际下载解包后，31 个文件、766,474 字节均与本地原件一致。原报告、候选代码与参数、评分和独立复核都在其中。恢复回执位于 `.local/research-renewal/phase-completion-v2/backup/completed-eeg-snapshot/RESTORE_VERIFIED.json`。

本阶段最终证据位于 NCC 的 `/data/duandh/EEG-AI-Scientist/runs/evidence-guided-research-v1/backup/paper-workflow-trial-v2/`。共 137 个文件、46,593,906 字节，下载还原后逐字节相同。还原副本上的两篇全文对照、全部数值证据引用、38 批模型对齐和 EEG 复核索引均可重新核验。清单哈希为 `89f2a3492882674107155ea9805d438db1f355909976244c8bf4c32a7bf63b64`，本地回执为 `.local/research-renewal/phase-completion-v2/backup/RESTORE_VERIFIED.json`。

上一次失败阶段已有 452 个精选文件、8,534,107 字节，位于同一 NCC 备份根的 `paper-workflow-trial-v1/`，全部下载核对通过。本地回执为 `.local/research-renewal/phase-completion-v1/backup/RESTORE_VERIFIED.json`；备份成功不改变该阶段科研链未完成的事实。

此前的备份、代码版本和检查明细保留在原研究目录以及 Git 历史；无需在日常入口重复累计。可用 `git show archive/paper-workflow-trial-v1:docs/workspaces.md` 查看上一阶段的完整机器记录。更早的原目录与恢复方式见[历史索引](history/README.md)。

## 新运行与检查原则

运行名按研究目的、协议、代际、条件和重复次数组织，例如 `method-transfer-v1-g1-learned-r01`。控制器要求单层 run_id，路径层次另写元数据；日期只作时间信息。源码提交、输入、依赖、模型和预算均记录在各次准入清单中，不能用新 checkout 改写旧实验身份。

本轮完整 Windows 套件为 1,292 通过 / 86 跳过，相关 Linux 变更专项为 156 通过 / 0 跳过。Linux 专项不是完整套件，软件测试也不是科研结论。精确回执见本轮证据目录。Docker 的实际限制和退出清理需按任务验收，不能把命令接受参数当成资源保证。
