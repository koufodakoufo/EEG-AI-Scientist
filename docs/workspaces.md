# 工作区与同步

GitHub 的 `main` 是已验证代码的共同主线。本地与服务器各有工作 checkout；数据、环境、运行结果不靠 Git 同步。当前正式本地路径不变。

| 位置 | 代码入口 | 用途 |
|---|---|---|
| Windows | `X:/projects/EEG-AI-Scientist` | 开发、阅读、发布 |
| 火山云 | `/vePFS-0x0d/home/duandh/projects/EEG-AI-Scientist/code` | 优先执行位置；个人 vePFS 目录登记待完成 |
| nccserver0 | `/data/duandh/EEG-AI-Scientist/code` | CPU 验证和备用执行 |
| GitHub | `koufodakoufo/EEG-AI-Scientist`，`main` | 版本化源码与可公开文档 |

## 火山云存储

协作者的代码实践是个人 vePFS 目录、Git 同步和固定版本发布。普通 `/home/duandh` 位于开发机临时文件系统，实例释放可能丢失。代码工作副本在 vePFS，环境/缓存/临时文件在 `/home/duandh/projects/EEG-AI-Scientist`；代码始终另有 GitHub 和本地副本。

资源规范要求 vePFS 目录提交申请表、登记归属并写计划结束日期。提供的 PDF 没有可访问的申请表链接。当前准备目录记为 `registration_status=pending`，暂定使用至 2026-11-15；这是准备和试点的预计期限，不是已获配额或承诺持久保存。继续使用前须完成登记或调整位置。规范说明未登记目录可能被清理，因此不要把唯一成果放在此处。

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

## 运行命名与历史

新运行名按 `study-v<protocol>-g<generation>-<condition>-r<repeat>` 组合，例如 `method-transfer-v1-g1-learned-r01`。当前控制器要求单层 run_id，不允许斜杠；研究、协议和代际的层次同时作为元数据字段，不能把多层路径直接传作 run_id。创建时间、模型版本、代码 commit、资源与父策略也写入元数据；正文用研究问题和条件名。

旧 ncc 部署根及其中 integration checkout、旧火山云 dated 根和旧环境保持原位，仅用于冻结证据和恢复，不再作为新开发入口。旧分支由 `archive/*` 标签保留，原始目录映射见 [历史索引](history/README.md)。

## 环境与验证

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

### 本轮验收（2026-11-01）

| 环境 | 完整套件结果 | 解释 |
|---|---|---|
| Windows | 225通过，57跳过 | 跳过 Linux 进程/隔离和本机无法创建的链接；同步脚本回归通过 |
| ncc Linux | 280通过，2跳过 | 两项需 PowerShell；全部 Linux 生命周期与真实隔离测试通过 |
| 火山云 Linux | 269通过，2失败，11跳过 | 两项真实沙箱执行失败；9项私有校准样例未提供、2项需 PowerShell |

源码候选 `2ea2ef2` 已分别在两台服务器核验；后续说明修订不改变该源码。旧 ncc 基线另有266项全通过。三项独立复核问题均已修复：远端实际 checkout 校验、无科学依赖的命令帮助、当前研究者启动指令。

火山云 `bwrap` 存在，但普通用户命名空间探针失败；默认 PATH 也未发现原生研究者 CLI。此环境目前可执行 CPU 科学工具，**尚不满足受测研究者的完整隔离运行条件**。不得跳过隔离检查来启动正式对照。ncc 保留为经过验证的执行后备。GPU仍未分配，九小时研究尚未开始。

旧环境中独立小程序复现了 OpenBLAS 线程池从2扩到4时的原生崩溃；本轮统一初始 `OPENBLAS_NUM_THREADS=4`、`OMP_NUM_THREADS=4` 后完成测试。该记录描述已观察到的触发条件，不声称已修复上游数值库。
