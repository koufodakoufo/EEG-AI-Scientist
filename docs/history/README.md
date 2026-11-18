# 早期实验与原始记录

想知道项目现在做到哪里，从[项目首页](../../README.md)开始。下面按当时实际做过的实验列出原报告。

| 想查什么 | 从哪里读 |
|---|---|
| 最早的小模型有没有真正做实验？ | [提案试点报告](https://github.com/koufodakoufo/EEG-AI-Scientist/blob/d0bbb6efbed5933275f4d6d9a46b90e4bbe82930/reports/MORNING_REPORT.md)和[结果表](https://github.com/koufodakoufo/EEG-AI-Scientist/blob/d0bbb6efbed5933275f4d6d9a46b90e4bbe82930/reports/RESULTS_TABLE.md) |
| 在答案已知的合成数据上，一份方法提示有帮助吗？ | [配对结果及评分局限](synthetic-pilot/RESULTS.md) |
| BrainPEC 的问题怎样落到真实 EEG 上？ | [构建者做的 EEGMAT 参考实验](brainpec-pilot/SCIENCE_RESULT.zh-CN.md)和[独立 AI 实际完成的部分](reference-expansion/AGENT_CASE_STUDY.zh-CN.md) |
| 换个模型对照或 EEG 任务，结果如何？ | [预训练、随机编码器和手工属性的比较](reference-expansion/REPRESENTATION_BASELINES.zh-CN.md)和[睁眼与闭眼实验](reference-expansion/EEGMMIDB_REFERENCE.zh-CN.md) |

## 查旧版本

旧入口、机器配置、排班、进度稿和交接文档保存在 `archive/paper-workflow-trial-v2`。该标签的固定提交保存了整理前的整个 `docs/history/`，包括后来移出主线的文件。[浏览完整历史目录](https://github.com/koufodakoufo/EEG-AI-Scientist/tree/c53051bd8e0fa1fb05a9417c6a695c32a75e8c49/docs/history)

部分原报告沿用最初目录名，文中的相对路径与那时的代码配套。按当时布局阅读，可打开[合成试点快照](https://github.com/koufodakoufo/EEG-AI-Scientist/tree/58b8d71b2b2b060e6b1d77eefd1b5d1cdb5c6e1f/docs/overnight/2026-10-29)、[EEGMAT 试点快照](https://github.com/koufodakoufo/EEG-AI-Scientist/tree/fc8d7e18ee91bd07d2dc74f8f2a20c00e8b1db79/docs/research/2026-10-29-brainpec-real)和[后续对照快照](https://github.com/koufodakoufo/EEG-AI-Scientist/tree/fc8d7e18ee91bd07d2dc74f8f2a20c00e8b1db79/docs/research/2026-10-30-extension)。

本地也能查看单个旧文件，无需切换当前分支。例如 `git show archive/paper-workflow-trial-v2:docs/history/navigation/HANDOFF.md`。更早的整套工程布局见 `archive/workspace-layout-v1`。仅保存在本地的原件位于 `.local/history/archive/` 和 `.local/history/framework/`，归档复制清单为 `.local/preparation/archive-relocation-manifest.json`。服务器冻结运行按证据记录中的原路径查找。
