# 历史成果与恢复

这些资料描述过去发生了什么，不是当前运行命令。正文保留原始内容，包括旧目录、版本和编号；原路径在对应 Git 标签中。

| 阶段 | 阅读入口 | 原代码标签 |
|---|---|---|
| 早期提案研究 | 标签中的原 README 和报告 | `archive/proposal-agent-v1` |
| 合成科研与方法提示 | [结果](synthetic-pilot/RESULTS.md) | `archive/synthetic-pilot-v1` |
| 真实 EEG 与受测 AI | [参考结果](brainpec-pilot/SCIENCE_RESULT.zh-CN.md)、[AI 对照](reference-expansion/AGENT_CASE_STUDY.zh-CN.md) | `archive/brainpec-pilot-v1` |
| 表示基线和第二任务 | [基线比较](reference-expansion/REPRESENTATION_BASELINES.zh-CN.md)、[睁闭眼任务](reference-expansion/EEGMMIDB_REFERENCE.zh-CN.md) | `archive/brainpec-pilot-v1` |

旧报告位置变换：`docs/overnight/2026-10-29` → `synthetic-pilot`；`docs/research/2026-10-29-brainpec-real` → `brainpec-pilot`；`docs/research/2026-10-30-extension` → `reference-expansion`。移动不修改历史论断。

当前主线不再携带整套旧源码和运行副本。原 `archive/` 的977个已跟踪文件可从 `archive/workspace-layout-v1` 标签恢复；完整本地原件（包括未跟踪材料）集中保存在 `.local/history/archive/`，不再随新checkout重复展开。原bundle仅是历史证据，不再用作同步方式。

旧工具的恢复点为 `2d22483`，也包含在上述标签中；本地位置为 `.local/history/archive/tools/`。它们含旧机器路径，仅供查证；历史执行请用原标签的完整布局。

服务器旧冻结工作区保持原路径。不要用新 checkout 路径直接替换旧锁的绝对路径，更不要修改哈希或测试预约。

原导入框架说明保存在 `imported-framework/`；机器路径和授权状态属于当时记录。当前规则以根 AGENTS 和最新用户指令为准。

本地原 `framework/` 的旧运行、缓存和未跟踪材料集中保存在 `.local/history/framework/`。旧入口和说明也保存在 `imported-framework/`，不构成第二套当前工程。

## 如何查证和恢复

查看旧文件无需切换当前工程，例如 `git show archive/workspace-layout-v1:archive/README.md`。需要完整历史checkout时，在独立的复现目录检出对应标签；不要让当前main退回旧布局。涉及绝对路径的旧运行需按原记录恢复路径，不能就地更改锁或哈希。仅本地保有的材料应从上述`.local/history/`原件恢复；迁移前后的逐文件SHA256清单在`.local/preparation/archive-relocation-manifest.json`。
