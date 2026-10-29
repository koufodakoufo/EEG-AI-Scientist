# 火山云本人 CPU 工作区配置（R55，2026-10-30）

本轮使用本人目录 `/home/duandh/projects/EEG-AI-Scientist-20261030`，UID 1027、0700。**独立 Python 3.12.16、CPU 模型依赖、项目导入、CBraMod / REVE 严格权重加载和合成前向均已通过现场验收。** 三个共享权重前后完整 SHA-256 一致，写入与网络负对照均返回 EACCES。最终证据采集于 01:25（Asia/Shanghai）。原 30 分钟预算因公共包下载缓慢而显式延长到 60 分钟；本报告以完成后的实测结果为准。

这是 Builder 基础设施工作，不是 tested Actor、真实 EEG 实验或性能结果。GPU 使用为零，没有读取 EEG 信号、复制数据/权重、导入共享模型代码或访问控制材料。

## 已实测的独立运行时

| 项目 | 结果 |
|---|---|
| Python | `3.12.16 (main, Oct 26 2026, 14:08:45) [Clang 23.1.3]` |
| 可执行文件 | `/home/duandh/projects/EEG-AI-Scientist-20261030/venv/bin/python` |
| 所属解释器 | 同一本人目录下 `runtime/python/bin/python3.12`，不依赖他人的 Python 环境 |
| 核心依赖 | Torch 2.6.0+cpu、NumPy 2.2.6、einops 0.8.1、Transformers 4.56.2、safetensors 0.6.2；pip 26.2.2 |
| 安装验证 | 25 个 PyPI 轮子与官方 Torch CPU wheel 完整哈希验证后离线安装；`pip check`：No broken requirements found；`torch.version.cuda` 为 null |
| CPU / GPU 策略 | 探针固定最多 2 个当前允许 CPU、nice +10、Torch 2 线程；`CUDA_VISIBLE_DEVICES=''`；选用无 CUDA 构建的 CPU wheel |
| 写入位置 | 本人目录内的 `runtime/`、`venv/`、`downloads/`、`source/`、`bin/`、`cache/`、`tmp/`、`evidence/` |
| 缓存隔离 | `environment.sh` 设置 HOME、TMP/TEMP/TMPDIR、XDG、pip、HF、Torch、matplotlib 缓存到本人目录，禁用用户 site 与 `.pyc` 写入；pip 不读取外部配置 |

本轮复核 root、runtime、venv 均为 UID 1027 / 0700；仅对本人工作区审计的 33,523 个条目没有其他 UID 的文件或目录。home 持久性、个人配额与正式 GPU 调度分配仍未证实。可见空闲容量约 101 GB 是文件系统观察值，不是个人空间承诺。

运行时约 99.3 MB，venv 约 1.043 GB，缓存约 0.88 MB。独立运行时没有依赖或修改共享 Python 环境。完整已安装版本清单位于 `evidence/requirements.lock.txt`。

## 归档与源码来源

| 对象 | 完整 SHA-256 | 大小 |
|---|---|---:|
| 官方 CPython standalone 3.12.16 / 20261026 | `ce4f6d0a6cfdb3bed6e44c2f9affd85943c76a42e25ad3a259002f31d6fb8a20` | 34,505,639 B |
| 官方 Torch 2.6.0+cpu / CPython 3.12 wheel | `59e78aa0c690f70734e42670036d6b541930b8eabbaa18d94e090abf14cc4d91` | 178,578,006 B |
| 最小程序源码 tar | `51a2ae496fdbb7e3535e2615ec7deba2d8d2d29f5a42f53278812435efe63943` | 501,760 B |

Python 哈希来自[官方 GitHub release asset API](https://api.github.com/repos/astral-sh/python-build-standalone/releases/tags/20261026)；Torch 哈希来自[官方 CPU wheel 索引](https://download.pytorch.org/whl/cpu/torch/)。两者已重算完整归档哈希。GitHub 远端直连超时，Python 经本地官方下载后传入本人目录；慢速单次下载触及上限后仅续传缺失分片。Torch 索引指向的 `download-r2.pytorch.org` 较慢，改用同路径的官方 `download.pytorch.org` 后完成，并继续按原索引 SHA-256 验证。

程序快照固定到正式本地仓库提交 `0b24164977e82619de5ce0ab3d5e8f46f80d8a98`，包含 `framework/eegfm` 与已跟踪的 REVE vendor 文件；没有创建第二个 Git 仓库。另加入本人先前下载、哈希已固定的 CBraMod 上游提交 `b9e961003214326972c567eff390e75b0287e32a` 的两份模型源码和 MIT LICENSE。总计 45 个普通文件，各文件哈希见远端 `evidence/source-provenance.json`。未复制协作者目录中的源码；未带入 credentials、controls、数据、权重、历史 archive 或运行状态。

## 共享资源原位绑定

`volcano_resources.py` 已实际执行成功，只用标准库读取指定文件、重算完整 SHA-256，并解析 safetensors 的有界 JSON header。未创建任何权重副本或指向共享目录的可写工作目录。

| 资源 | 只读路径 | 重算 SHA-256 |
|---|---|---|
| CBraMod | `/neurobench/checkpoints/omni/pretrained_weights.pth` | `0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178` |
| REVE base | `/neurobench/checkpoints/omni/reve-base/model.safetensors` | `8ecc650619598748286c2457f81f5c6bd12e8bb59db44f7b02af1955c44de8fe` |
| REVE positions | `/neurobench/checkpoints/omni/reve-positions/model.safetensors` | `4b793820b9df0998667deb6c8ce2dbb86b38221d5165c1844bc4971941b13f13` |

结果与 R50 一致。清单保存字节数、UID、inode、mtime，以及每个 safetensors 张量的 shape/dtype。标准库结构检查本身没有加载 pickle；后续模型验收采用下述受限加载方式。CBraMod 的官方来源关联沿用先前固定的项目来源记录；本轮没有重新下载发布方权重。REVE 的代码许可与模型卡 `license: other` 不混同。

## 模型接口验收结果

`volcano_probe.py` 实际核对 45 个源码文件后导入本人快照，项目模块 `eegfm`、`eegfm.research_bench.real_data` 导入成功。CBraMod 使用 `torch.load(..., weights_only=True, map_location='cpu')`，REVE 使用 safetensors；三个对象均验证完整键集合、形状一致、张量有限且 `strict=True`。

| 对象 | 严格加载 | CPU 合成输入 / 输出 | 结果 |
|---|---|---|---|
| CBraMod | 211 个状态键，4,924,000 参数 | `[1,20,5,200]` → `[1,20,5,200]` | 通过，输出全部有限 |
| REVE base | 140 个状态键，69,189,632 参数 | EEG `[1,4,1000]` + positions `[1,4,3]` → `[1,4,5,512]` | 通过，CPU Torch SDPA，输出全部有限 |
| REVE positions | 1 个状态键，buffer 型位置表 | 大写 `FP1、FP2、C3、C4` | 全部存在，严格加载通过 |

探针使用 CPU 0、1，8 GiB 虚拟内存上限和 180 秒超时。最终完整验收约 38.8 秒，峰值 RSS 914,532 KiB；此耗时含导入、哈希、初始化与加载，**不是模型性能基准**。固定随机种子为 1729，两轮输出 SHA-256 一致。

REVE 共享 config 的架构字段与本人源码配置一致，位置名称有序列表一致。两个共享 config 的 SHA-256 分别为 `69f4fc06515fe4475ec8262907a3898895c742cec94219b876b0430de360c088`、`8e89acf4d27cf1d24815add8df771e6cf138b68846e60796db57e36f1ec8d6f8`。

远端 bwrap 因不允许普通用户创建 namespace 而失败；Landlock ABI 查询返回 ENOSYS。探针实际安装了 52 条 libseccomp 文件修改/网络拒绝规则，启用跨线程同步；本人临时目标的写入和新建 socket 均被实际阻止。**这不是 Actor 读取隔离环境。** 不将此目录用于 tested Actor 或 Distiller。规则只限制该子进程及其线程，不改变其他进程或系统配置。

首次探针的模型验收已通过，但永久只读规则在 Python 退出时也阻止了库删除本人 import-time 临时文件。最终探针因此在写出并刷新完整结果后直接结束工作进程，保留本人临时文件，不放松防写规则。初次日志保留为 `acceptance-initial.*`；最终结果在 `acceptance.*`。

最终退出码为 0，JSON 的 `status` 为 `passed`；stderr 仅有可选 `flash_attn` 未安装提示，没有异常堆栈，CPU SDPA 验收不依赖该包。最终 `acceptance.json` SHA-256 为 `f13a0c666276707468de698a57642020a2fd628a93e9b9fcf325ce87fb3c468d`。本地与远端 `volcano_probe.py` 的完整 SHA-256 一致：`b473db688c488bea0ac91831cdba7399c91e19b36ba57b8d59a609f5b47318d0`。

串行 pip 下载在 6.2 MB 的 sympy 上明显停滞。最多 8 路、最多 5 分钟的远端 PyPI 下载完成 19 个轮子后，剩余 6 个公共轮子改由本地下载、完整哈希验证后传入本人目录。相同 NumPy 范围请求实测本地约 159 KB/s、远端约 11 KB/s；本地 curl 完整 networkx 下载约 204 KB/s。全部 25 个轮子再次离线验证后，bootstrap 使用 `--no-index` 安装并完成 `pip check`。为保持最小模型运行时，本轮未安装 scipy、scikit-learn、PyWavelets 等非接口验收必需包。

## 可复现入口

在正式本地仓库使用以下脚本；参数示例中的 `.local` 仅为本人下载/证据暂存，不上传 GitHub。

```powershell
python scripts/research/volcano_acquire_runtime.py --output .local/research/2026-10-30-extension/volcano-setup
python scripts/research/volcano_prepare_source.py --owned-cbramod-source .local/research/2026-10-29-brainpec-real/resources/vendor --output .local/research/2026-10-30-extension/volcano-setup
```

把上述已验证归档通过保持原始字节的 scp 传到远端本人 `downloads/`；源码清单放到 `evidence/source-provenance.json`，在空的本人 `source/` 下展开 source.tar。bootstrap、probe、acquire_torch、acquire_dependencies、resources 脚本均放在本人 `bin/`。避免使用会额外附加 CR 的 PowerShell 文本管道传输 shell 脚本。

可用 `volcano_acquire_dependencies.py --plan-only` 生成当前 Linux/Python 对应的固定轮子计划；网络缓慢时，用 `volcano_stage_dependencies.py --manifest PLAN --output OWN_DIR --packages ...` 在本地暂存所需公共轮子并 scp 到本人 `downloads/dependencies/`。存在 `dependency-plan.json` 时 bootstrap 只做离线整文件验证，任何缺失或哈希不符均停止，不静默换包。

```bash
root=/home/duandh/projects/EEG-AI-Scientist-20261030
umask 077
python3 "$root/bin/volcano_acquire_torch.py" --output "$root/downloads"
bash "$root/bin/volcano_bootstrap.sh"
source "$root/environment.sh"
ulimit -v 8388608
timeout 180 "$root/venv/bin/python" -B "$root/bin/volcano_probe.py" \
  > "$root/evidence/acceptance.json" 2> "$root/evidence/acceptance.log"
```

最后一条只有退出码 0 且 acceptance JSON 的 `status` 为 `passed`，才算模型接口验收完成；还必须读取严格加载、CPU 输入输出、写入/网络负对照、前后资源哈希结果。该结果始终只属于合成基础设施测试。

剩余边界：尚未验证真实 EEG 协议、数据拆分、正式 Actor 隔离或完整任务运行；没有 GPU 分配依据，不能启动 GPU 工作。源码仍是上述固定最小快照，不等同后续完整 Git 工作副本。

私有本地证据保存在 `.local/research/2026-10-30-extension/volcano-setup/`。`setup-status.json` 是安装前快照；完成态汇总为 `setup-final.json`。远端原始证据在本人 `evidence/`，包括 `acceptance.json`、`resource-bindings.json`、`source-provenance.json`、`dependency-sources.json`、`requirements.lock.txt`、`runtime.json`、`pip-check.txt`。本轮没有 commit 或 push，交由主 Builder 统一审查。
