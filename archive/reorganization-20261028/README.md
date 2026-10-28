# 2026-10-28 本地目录纠正记录

本次整理将 `X:/projects/EEG-AI-Scientist` 恢复为唯一正式本地项目。沿用原根目录 `.git`，没有新建仓库、提交或推送；原 HEAD、Git 配置和暂存区保持原样。前一轮错误创建的 C 盘源码仓库确实有两次本地提交，另有一个恢复演练 clone；这些活动仓库已撤除，历史和恢复材料已保存在 X 盘。

## 证据入口

- `migration.json`：本轮复制、同盘移动及撤回的操作记录。
- `original-files-map.json`：1,214 个原有业务文件的原位置、现位置和 SHA256 对照。
- `verification.json`：迁移后原文件、281 个框架文件及 Git 状态关键项的校验结果。
- `verify-reorganization.py`：可重新执行的只读内容检查；仅更新本目录的校验结果文件。
- `completed.json`：本次纠正完成时的计数和 Git 摘要。
- `gitignore-before.txt`：本次追加本地材料忽略规则之前的完整 `.gitignore`。
- `previous-environment-description.md`：已被替代的 C 盘工程安排，仅作为纠错记录。

本轮迁移脚本之后，还将原根目录 `.pytest_cache` 同盘移入 `archive/legacy-harness-20261028/.pytest_cache`。这是运行缓存的原样封存，不计入 1,214 个业务文件，也不计入原迁移脚本的移动清单。

## 如何理解历史材料

`../setup-20261028/evidence/` 内保存上一轮备份、恢复演练结果、来源清单和 Git bundle。其 JSON、日志、脚本中的 C 盘绝对路径是**当时的历史路径**，不是当前入口，不应据此重新建立 C 盘工作副本。恢复演练 clone 本体未保留；经过校验的备份包和 bundle 保留。

前一轮 C 盘源码仓库的两次提交保存在：

`../setup-20261028/evidence/source-provenance/eeg-fm-research-source-snapshot-corrected.bundle`

旧实验归档保持原样。旧 harness 的代码、配置、文档、VS Code 配置和虚拟环境位于 `../legacy-harness-20261028/`。旧环境包含原绝对路径，移动后不承诺可运行；复现时应在空的恢复目录还原原布局并重建环境。不得在封存目录直接启动旧实验。

本机当前用法请看 `../../docs/environment-20261028/README.zh-CN.md`，当前状态看同目录 `current-status.json`。本次文件整理形成尚未提交的删除和新增，不能用 `git reset --hard` 或 `git clean` 来消除这些正常变化。

后续状态说明：用户随后明确授权本地Git提交，整理前修改和新布局分开记录。因此本目录的HEAD/index“保持原样”结论及 `verify-reorganization.py` 是授权提交之前的历史检查；新提交后HEAD/index按预期改变，不应再用该旧断言判断当前仓库损坏。原文件清单、原暂存区备份和来源包仍保留，当前提交查看根目录 `git log -2`。
