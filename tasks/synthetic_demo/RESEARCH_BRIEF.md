<!-- approved "synthetic demo; approved by operator on the user's behalf for the end-to-end check" from run demo_claude_001 -->
# 研究 brief：synthetic_demo

- 运行：demo_claude_001　撰写：Claude Code　日期：2026-10-21
- 状态：待审阅

## 1. 问题与成功标准
调整 `method.yaml` 的三个参数，使 `dsA / dsB / dsC` 三个分片的 validation FT balanced accuracy（`ft_bacc`，%）宏平均尽量高。

- 主指标：三分片 validation `ft_bacc` 的宏平均（`direction: maximize`）。
- 比较对象：baseline（`method.yaml` 初始值：`posttrain_lr_log10=-5.0, temperature=0.1, warmup_epochs=3`）。
- 成功/失败判定：相对 baseline 宏平均提升则 keep；单分片崩溃（抛异常/训练不收敛）视为无效。
- 约束：至少 2 个有效迭代轮次，最多 4 个 iteration attempt；每个候选 test 只跑一次，最多 2 个候选。
- 这是合成任务，结果不是科学证据；只验证完整流程。**不逆推 `run_eval.py` 的隐藏常数，只按 validation 结果决定下一步。**

## 2. 我们自己的实测事实
- 暂无本运行的实测结果（baseline 尚未跑）。
- 来自评估器源码（`runs/demo_claude_001/workspace/run_eval.py`，setup 时冻结）的**结构性**事实（非隐藏最优值）：
  - 每个分片的 `ft_bacc` 是关于 (lr, temperature, warmup) 的平滑单峰函数加上每折噪声；三分片各有不同最优，单一配置需在三者间折中。
  - **硬约束**：`posttrain_lr_log10 > -3.8` 会直接抛 `post-training diverged ... NaN`。允许区间上界 −3.7 落在崩溃区，故可用上界实际是 **−3.8**。
  - 噪声幅度约 ±1.5%（`1.5 * noise`，noise∈[−1,1]），即单次评估存在约 1–2% 的抖动，小差异不可信。
  - val 与 test 使用不同噪声；test 读取 val 选中的配置，不重训（真实评估器的"按 val 选 checkpoint"行为）。
  - 每分片评估约 2 秒（`time.sleep(2)` 代表数小时 GPU 训练）。

## 3. 文献与外部证据
本任务 `research.web_search: false`，不做网页检索。无外部证据。

## 4. 候选假设（选项，不是指令）

### H1 学习率是主导因子，当前 lr 偏低
- 理由：post-training 对 lr 通常最敏感；baseline `lr=-5.0` 是区间 [−6, −3.8(有效)] 的偏低一侧。向 −4.x 方向移动可能同时改善三分片。
- 预期效果：三分片宏平均提升若干个百分点，lr 存在一个折中最优。
- 可证伪的反向结果：向 −4.x 移动后宏平均下降或某分片崩溃 → lr 不是主导或已越过最优/约束。
- 风险与混杂：越过 −3.8 直接崩溃；噪声掩盖 1–2% 的小变化。
- 成本：每 attempt 3 个分片 × ~2s。

### H2 temperature 需要从 0.1 向更小方向调整
- 理由：temperature 以 log 距离进入，baseline 0.1 处于允许区间中部；三分片最优可能偏离 0.1，小幅 sweep 可定位折中。
- 预期效果：在选定 lr 后，调 temperature 带来次级提升（幅度小于 lr）。
- 可证伪的反向结果：temperature 上下微调均不优于当前最优 → 0.1 附近已是折中。
- 风险与混杂：与 lr、warmup 存在交互，需在较优 lr 基础上单独扫。
- 成本：同上。

### H3 warmup_epochs 的影响较弱，围绕 2–5 折中
- 理由：warmup 以线性距离 /4 进入，相对不敏感；三分片最优 warmup 不同，存在一个整数折中。
- 预期效果：在固定较优 (lr, temp) 后，微调 warmup 带来最小一级的提升。
- 可证伪的反向结果：改 warmup 对宏平均无可辨别影响（小于噪声）→ 保持 baseline 值。
- 风险与混杂：整数网格粗，单步变化可能被噪声淹没。
- 成本：同上。

## 5. 已知未知与风险
- **协议风险**：test 隔离——所有决策只看 validation；锁定后每候选只跑一次 test（上限 2）。选 epoch/选配置只用 val。
- **噪声风险**：单次评估 ±1–2% 抖动，差异 < 2% 时不足以区分；避免对噪声过拟合（validation 过拟合）。
- **约束风险**：lr > −3.8 崩溃，sweep 时严格保持 ≤ −3.8。
- **算力/时长**：每 attempt 约 6 秒，`gpu_hours_budget: 0`（合成），预算约束主要是 `max_attempts=4`。

## 6. 初步计划
1. Setup：读 `run_eval.py`，用一次 `--kind setup` attempt 跑通三分片 val 产出 `metrics.json`，确认链路后 `bin/eegfm freeze`。
2. Baseline：`method.yaml` 保持初始值，跑 val 得宏平均基准。
3. 迭代（计划 2–4 轮，先大后小）：
   - A-iter1（H1）：在保持 temp=0.1, warmup=3 下，把 lr 从 −5.0 移向 −4.5 区域，看宏平均方向。
   - A-iter2（H1 继续或 H2）：据 iter1 结果，或继续定位 lr 折中，或在较优 lr 上微调 temperature。
   - 视剩余预算，再用一轮做 warmup（H3）或收敛性复核。
4. 收尾：按 validation 选最终候选，锁定 baseline 与最终候选，各跑一次 test，写 `FINAL_REPORT.md`，整理记忆。
- 预计有效轮数：2–3。

## 补充调研
（运行中追加：日期、触发原因、新发现；不修改上面已批准的内容）
