# 历史成果与恢复

这些资料描述过去发生了什么，不是当前运行命令。正文保留原始内容，包括旧目录、版本和编号；原路径在对应 Git 标签中。

| 阶段 | 阅读入口 | 原代码标签 |
|---|---|---|
| 早期提案研究 | 标签中的原 README 和报告 | `archive/proposal-agent-v1` |
| 合成科研与方法提示 | [结果](synthetic-pilot/RESULTS.md) | `archive/synthetic-pilot-v1` |
| 真实 EEG 与受测 AI | [参考结果](brainpec-pilot/SCIENCE_RESULT.zh-CN.md)、[AI 对照](reference-expansion/AGENT_CASE_STUDY.zh-CN.md) | `archive/brainpec-pilot-v1` |
| 表示基线和第二任务 | [基线比较](reference-expansion/REPRESENTATION_BASELINES.zh-CN.md)、[睁闭眼任务](reference-expansion/EEGMMIDB_REFERENCE.zh-CN.md) | `archive/brainpec-pilot-v1` |

旧报告位置变换：`docs/overnight/2026-10-29` → `synthetic-pilot`；`docs/research/2026-10-29-brainpec-real` → `brainpec-pilot`；`docs/research/2026-10-30-extension` → `reference-expansion`。移动不修改历史论断。

本地 `archive/` 原件和 bundle 原位保留，不作为当前源码或同步机制。它们曾用于保全不同来源的 Git 历史及误建工作区的恢复。现在以 Git 提交和标签同步，不新增 bundle。无需在当前入口展开全部原件。

新包已替代的旧工具先复制、逐文件核对并提交到恢复点 `2d22483`，然后从活动 scripts 移除。副本在 `archive/tools/{synthetic-pilot,brainpec-pilot,network-setup}`。它们含旧机器路径，仅供查证；历史执行请用原标签的完整布局。

服务器旧冻结工作区保持原路径。不要用新 checkout 路径直接替换旧锁的绝对路径，更不要修改哈希或测试预约。

原导入框架说明保存在 `imported-framework/`；机器路径和授权状态属于当时记录。当前规则以根 AGENTS 和最新用户指令为准。

本地 `framework/` 中的旧运行及未跟踪材料仍保留原位，整体已从当前源码索引移出；不把它当成第二套可执行工程。旧入口和说明的逐文件校验副本位于 `imported-framework/`。
