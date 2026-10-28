# 任务：REVE × stimulus ISA（六个情绪数据集，LODO）

完整的历史任务书：`/mnt/cfs-omni/wzf/auto research/docs/research/REVE_ISA_RSI_TASK_BRIEF.md`（setup 前完整阅读）。已有结果：`knowledge/prior_results.md`。

## 1. 科学问题

把 CBraMod 上成功的**同刺激跨被试 ISA 后训练**迁移到 REVE-base：在相同的六个数据集、LODO all-source、被试划分和下游协议下，能否改善 REVE 的下游表现？直接迁移效果不足时，能否根据训练与 validation 证据诊断原因，并在保留 ISA 核心机制的前提下改进？

已知：2026-10-17 的忠实迁移（H1，LR 1e-5）使六集 FT 宏平均下降 0.69 pp，FACED 提升、SEED 明显退化。本任务从这一认识出发，不重复同一配置凑轮次。

## 2. 成功标准

- **性能**：锁定的共同候选在六个数据集上 FT balanced accuracy 均高于同协议 REVE R0（逐集配对差值为正），同时报告 LP、macro-F1、宏平均、paired bootstrap 区间。
- **流程**：至少 2 个有效科研轮次（`task.yaml: search.min_valid_rounds`），每轮覆盖六个目标；test 隔离成立。
- 两者分开判断；负结果如实报告。

## 3. 固定不变

六个数据集及其 release、60ch/10 s、NoClip、SEED session 规则、LODO all-source（目标数据集不进入它自己的后训练）、六次被试划分（seeds 42–47，`src/split_manifest.json`）、官方 REVE-base 初始化（每个目标独立从官方权重开始）、下游 LP/FT 协议与按 validation 选 epoch、后训练 40 epoch、每个 source 的真实对比 batch 64。

## 4. 可以研究的范围

可编辑文件见 `task.yaml: source.editable`。参数范围：

| 参数 | 范围 |
|---|---|
| 后训练 LR | 1e-6 至 2e-4 |
| temperature | 0.03 至 0.3 |
| weight decay | 0 至 1e-2 |
| warmup | 0 至 8 个整数 epoch（总 epoch 固定 40） |
| 梯度裁剪 | 0.5 至 5 |
| 表征/投影 | 先保持 flatten 忠实迁移；有依据时可调整 token 聚合或投影，但必须仍是 stimulus 对比目标，并标明是变体 |
| source 采样与配对 | 可调整平衡与配对效率；不得删除 source、引入目标数据集或改变 stimulus 身份 |
| 工程性能 | AMP、分块、梯度检查点、loader/cache；必须验证数值语义与负样本集合不变 |

不在范围内：续训代替重新后训练、多后训练 seed、MoE/NPD/重建/多阶段、标签 SupCon、新数据集。梯度累积不等价于同一个 InfoNCE 大 batch。

## 5. 评估契约（setup 阶段实现 `src/run_eval.py`）

`run_eval.py` 是冻结的评估入口，**每次处理一个目标数据集**（一个 TiONE 作业，6 GPU）：

```
python3 -B run_eval.py --phase val  --target <T> --out <dir>
python3 -B run_eval.py --phase test --target <T> --from <val_out_dir> --out <dir>
```

- `--phase val`：读 `candidate_plan.json`。`condition=R0` 时不后训练（官方权重直接下游）；`condition=R1` 时用其余五个 source 后训练 40 epoch。然后在目标数据集六个划分上做 LP 与 FT，按 validation 选 epoch，保存每折选中的权重到 `<dir>`。写 `<dir>/metrics.json`：
  - `ft_bacc`：六个划分的 FT validation balanced accuracy 均值（%），这是主指标；
  - 另外可写 `lp_bacc`、`ft_macro_f1`、`lp_macro_f1`、逐折数值、后训练 loss 曲线摘要、梯度诊断、耗时与显存；
  - **不得包含任何 test 数值或以 test 命名的键**。
- `--phase test`：只加载 `--from` 目录中按 validation 选中的权重，在 test 被试上评估一次，写 `<dir>/metrics.json`（键名与 val 相同，例如 `ft_bacc`、`lp_bacc`，再加逐折结果）。不得重新训练或重新选择。
- 复用 `src/` 中的核心模块：`release_io.py`（数据）、`official_model.py`（REVE 加载）、`posttrain.py`（ISA 后训练）、`downstream.py` + `fold_worker.py`（LP/FT）、`evaluation_contract.py` / `analysis_contract.py`（指标）。旧的 TiONE 编排方式见 `src/legacy/remote_worker.py` 与 `stages.py`，可参考其调用链与参数，但不再使用 broker 请求契约。
- 运行时的大文件（checkpoint、缓存）写到 `<dir>` 或 `/omni-eeg-00/home/wzf/scratch/eeg-fm-research/<run>/`，不要写进 workspace。

Setup 必须验证（写进 setup attempt 的 proposal 与 NOTES）：真实加载官方权重；跨被试 stimulus 正对；SEED session 规则；LODO 排除目标；数据行与标签一致；InfoNCE 数值与梯度；REVE token 与位置对齐；baseline 与候选使用同一划分和评价协议；val 输出不含 test。

### 5.1 旧链路的调用方式（`legacy/remote_worker.py`，一个目标一个 6 GPU 作业）

```
set_scratch()                                  # TMPDIR/TMP/TEMP 指向 run 专属 scratch
releases = {t: Release.open(t) for t in TARGETS}          # release_io.py，六个数据集
release.preload_signals(artifacts, deadline)               # 解码一次，缓存在 <artifacts>/cache/signals/<release 指纹>/
# R0（官方权重）
complete_condition(release, identity, dir, artifacts, encoder_checkpoint=None, deadline)
    build_validation_features(release, folds, dir/"lp_features", device="cuda:0", ...)   # downstream.py
    run_fold_processes(...)     # 6 个 fold_worker.py 进程，cuda:0..5，--phase validation
    # 每个 <dir>/<lp|ft>/fold<k>/validation.json 里有 validation.balanced_accuracy（0–1）、macro_f1、accuracy
# R1（ISA 后训练）
run_posttrain(target, releases, parameters, dir/"posttrain", device="cuda:0", identity, deadline)  # posttrain.py，5 个 source 副本用 5 张卡
release_source_signals(releases); torch.cuda.empty_cache()
complete_condition(..., encoder_checkpoint=dir/"posttrain/encoder.pt")
# test（锁定后）：fold_worker.py --phase final_test → downstream.final_test_unit(...) → test.json
```

### 5.2 setup 时必须切断的旧耦合（冻结前可以改任何文件）

1. `fold_worker.py` 调用 `artifact_io.verify_source_snapshot(root)`，它要求代码目录上一级有旧 harness 的 `snapshot.json`。新程序里代码完整性由 `eegfm freeze` 保证，这一调用应去掉或改成 no-op。
2. `fold_worker.py` 的 final_test 分支 `import broker_contract` 并读取 `test_plan.json` 中的 `method_lock`，循环 R0/R1 两个条件。新程序每个 test 作业只评估**一个**候选：让 `run_eval.py --phase test` 从 `--from` 指向的 validation 目录读取选中的 checkpoint，自己构造 `method_lock`（`downstream.final_test_unit` 会用 `evaluation_contract.locked_round_limit` 校验它；字段：`round_limit`、`complete_validation_rounds`、`selected_round`、`selection_data="validation_only"`、`test_started_before_lock=False`），并相应修改 `fold_worker.py`。
3. `remote_worker.set_scratch()` 的 scratch 路径依赖旧部署契约。改为 `/omni-eeg-00/home/wzf/scratch/eeg-fm-research/<run>/<attempt>/<target>/`（`<run>`、`<attempt>` 可从 `--out` 路径推出），启动子进程前设置 `TMPDIR/TMP/TEMP` 并验证可写。
4. 旧链路要求先完成六个目标的 R0 campaign 才能跑 R1（`development/baseline_campaign.json`）。新程序中 R0 是独立的 baseline attempt，不需要这道门。

其他要点：
- `--artifacts`（信号缓存根）请用共享缓存 `/omni-eeg-00/home/wzf/cache/eeg-fm-research/reve_isa`，所有 attempt 复用，避免每次重新解码。缓存按 release 指纹寻址，`COMPLETE.json` 会校验大小与 mtime。2026-10-17 运行的缓存在 `logs/research_controller/reve_isa_recovery_20261017/runs/reve_isa_recovery_20261017/artifacts/cache/signals/`，若要复用必须 `cp -p` 保留 mtime，并在 NOTES 记录。
- 作业内只暴露 6 张 GPU；`torch.cuda.device_count()` 应为 6。作业镜像（TiONE helper 默认镜像）内用 `python3`，自带 torch；CFS 在作业内挂载到同一路径 `/mnt/cfs-omni`，数据与权重通过 COS 挂载到 `/mnt/omni-eeg-01`。
- `metrics.json`：`ft_bacc = 100 × mean(六个 FT fold 的 validation.balanced_accuracy)`，同理 `lp_bacc`、`ft_macro_f1`、`lp_macro_f1`，再附逐折数值、后训练 loss 摘要与耗时。
- `--smoke`（只用于 setup attempt，见 `task.yaml: evaluation.smoke_command`）：真实数据、真实 GPU，但极短。例如后训练只跑 `posttrain.PROBE_WARMUP_STEPS + PROBE_MEASURED_STEPS` 步（`run_posttrain(..., smoke_steps=...)` 已支持），下游每折 1 个 epoch。smoke 的分数不参与任何比较。
- 预计耗时（2026-10-19 的实测吞吐）：R0 一个目标的 LP+FT 约 1 小时；R1 再加后训练约 2–3.6 小时。六个目标并行，所以一次完整评估约 4–6 小时，含余量约 8 小时。smoke 估计 20–40 分钟（含排队与数据加载；尚未实测）。
- 复用 2026-10-17 的 R0 结果：只有在数据、划分、权重和评估代码哈希完全一致并有证据时才允许（PROGRAM.md §4）。改过 fold_worker/downstream 之后通常不满足，直接重跑 R0。

## 6. Baseline 与轮次

- Baseline（R0）：`candidate_plan.json` 设为 `condition=R0`，作为 `--kind baseline` 提交。
- 每个 iteration：设 `condition=R1` 和一组参数（或在范围内的方法改动），覆盖全部六个目标。
- 时长：一次完整评估约 8 小时（6 个目标并行）。预算见 `task.yaml: search`。
- 收尾：锁定 R0 与最终候选，各跑一次 test（共 2 个候选 × 6 个目标），然后写最终报告，报告中注明这套划分的 test 在 2026-10-18 已被看过（见 `knowledge/prior_results.md`），结论属于开发性比较。
