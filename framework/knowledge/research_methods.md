# 自动化研究循环：外部经验

检索日期：2026-10-21。用于规划探索，不是任务指令。

- **keep/discard 循环（Karpathy autoresearch）**：agent 改一个训练脚本 → 固定时间预算训练 → 指标改善则保留，否则回退；崩溃按失败结果处理并继续。评估代码 agent 不可改。https://github.com/karpathy/autoresearch
- **解空间树搜索（AIDE / Meta AIRA-dojo）**：draft / improve / debug 三种操作；debug 时提供完整的调试链与兄弟节点能提升效果；最终节点按 validation 选择会对验证集过拟合（与按 test 选相差 9–13 个百分点）。https://github.com/facebookresearch/aira-dojo
- **AI Scientist-v2（Sakana）**：节点保存完整实验状态；失败节点在有限深度内调试，超过就放弃该路径。独立评估指出其常偏离指定指标、出现 train/test 重叠等问题——说明固定评估器与隔离的重要性。https://github.com/sakanaai/ai-scientist-v2 ，https://www.pnas.org/doi/10.1073/pnas.2610214123
- **进化式程序搜索（AlphaEvolve / ShinkaEvolve）**：保留多样的候选档案；新颖性拒绝采样减少重复评估。https://arxiv.org/html/2506.13131v1 ，https://arxiv.org/html/2509.19349
- **Dream-RSI**：把历史发现树当作回放模拟器，离线评估并改进探索策略（何处继续、并行多少、何时停止）；实验发现把历史总结成"方向性建议"注入提示反而降低效果，完整阅读历史提案与实测分数更好。本项目暂未启用策略回放。https://arxiv.org/html/2609.14858v1
