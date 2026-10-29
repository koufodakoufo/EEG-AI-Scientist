# R06：固定 sandbox worker 接口

实现：`framework/eegfm/research_bench/real_worker.py`。与 R03 `EvaluationSpec` / `SandboxedEvaluator` 直接匹配；未改 bridge、driver 或 Actor profile。所有配置来自可信 enrollment，Actor 不能指定 runtime、mount、Shell 或 aggregator。

```python
from eegfm.research_bench.real_worker import (
    FileBinding, SplitInputs, RuntimeConfig, SandboxedWorkerEvaluator,
)

runtime = RuntimeConfig(
    bwrap=Path("<verified-bwrap>"),
    python=Path("/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/venv/bin/python"),
    environment_roots=(Path("/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/venv"),),
)
evaluator = SandboxedWorkerEvaluator(
    private_root=Path("<outside-all-Actor-grants>/worker-evidence"),
    public_root=Path("<frozen-public>"), public_manifest_sha256=public_hash,
    split_manifest_path=Path("<private-split-manifest.json>"),
    split_manifest_sha256=split_hash,
    inputs_by_split={
        "validation": SplitInputs(FileBinding(train_view, train_hash),
                                  FileBinding(validation_view, validation_hash)),
        "test": SplitInputs(FileBinding(train_view, train_hash),
                            FileBinding(test_view, test_hash)),
    },
    runtime=runtime, aggregate=trusted_aggregate,
    released_metrics=frozenset({"accuracy", "balanced_accuracy"}),
    timeout_seconds=900,
)
```

若 venv 引用其他环境，只能显式增加该**确切环境目录**的只读 mount。没有 Python 3.12 或共享 conda 的硬依赖；默认可使用本轮独立 Python 3.10 venv。运行前冻结依赖版本/工具身份，并在实际服务器上认证此配置。

## 计算边界

- `submit(spec)` 唯一执行入口；只有可信 bridge 可以调用，test reservation 必须已先持久化。
- `poll(job_id)` 只查询，不补交、不启动、不自动重试。SQLite 保存 job ID、全 spec 指纹、owner PID/start ticks、最终响应。相同请求返回原结果，不同请求复用 ID 拒绝；崩溃后不重新执行。
- 校验实际 candidate 全文件 hash、public manifest 及内容、split manifest、所选 train/evaluation 文件、Python 与 bwrap 二进制。仅访问所选 split 输入；validation 启动不会读取或挂载 test 文件。
- candidate 复制到私有 job snapshot 后再次校验；执行后重新核验 candidate/public/split/inputs。所有数据/产物路径拒绝 symlink、hardlink、特殊文件；public 与 private 必须互不包含。集成方还须确保 private 不在 Actor case 的其他可写目录内。
- 固定 argv：`python -B /candidate/main.py --split validation|test --input /inputs/evaluation.npz --train /inputs/train.npz --public /public --output /out`。controller 从不 import/exec candidate。
- bwrap 使用 `--unshare-all --die-with-parent --new-session --cap-drop ALL --clearenv`；根、`/proc`、`/dev` 只读；只读 mount 系统 `/usr`、`/lib`、`/lib64`、`/etc/ld.so.cache` 及配置的确切环境；candidate/public 只读；输入**逐文件**只读挂载，不挂载其父目录。
- 只有 `/out` 与 256 MiB `/tmp` 可写；HOME、cache、HF/Torch cache 指向该私有临时区；无 proxy、无环境继承、禁 user site/pyc、`CUDA_VISIBLE_DEVICES=''`。没有模型请求通道。
- 复用 `run_bounded`：4 CPU、12 GiB RAM、timeout≤1800s、owned-descendant 清理、16 MiB stdout/stderr、2 GiB job storage、单文件 512 MiB。RAM 为已有 RSS 采样及地址空间限制，不新增 cgroup 保证。
- 沿用 `OwnedProcessTree` 的进程所有权前提：同一 controller Python 进程内顺序执行 worker；并行 episode 使用独立 controller 进程，不在一个进程里同时启动无关子树。已存在但未注册的 evidence 目录拒绝覆盖。

## 输入必须是受审查的 split view

`train.npz` 可以包含训练标签。`evaluation.npz` 不能是当前 `real_data` 生成的带 `y` 原始 split 文件：先由可信准备器生成去标签/去目标的计算视图，保留允许的 EEG/表征和用于配对的行标识。运行器拒绝 `y/label/labels/target/targets/feature_targets/target_features/gold` 数组名及嵌套 archive 成员。

这个字段检查不能证明语义无泄漏；可信准备器仍须确认没有藏在其他字段中的标签、feature targets、其他 split 样本或缓存。Q1 的测试目标必须留在可信 aggregator，不能直接放进 worker evaluation view。`FileBinding` 应绑定自有视图，不复制或改写现有实验室数据库。真正 row/split 身份与模型资源 hash 仍由本轮冻结 manifest / trusted aggregate 核对。

## 聚合与公开结果

`trusted_aggregate(output_dir, spec)` 返回且仅返回：

```python
{"metrics": {"accuracy": 0.75},
 "artifacts": [{"path": "results.npz", "sha256": "<actual-private-file-hash>"}]}
```

aggregator 是可信代码，不能执行 candidate，不能相信候选提供的标签或 scalar metrics JSON。运行器检查所有 metrics 是事前允许名称下的有限数值，逐条验证 artifact 相对路径、普通文件身份与实际 hash。原始 artifact 清单、数组、stdout/stderr 只留在私有 evidence。

返回 bridge 的字段仍是 `job_id,candidate_digest,split,status,metrics,artifacts,sandbox_receipt`。公开 `artifacts` **仅有固定 `released_metrics.json` 与可信 hash**；候选文件名、sample IDs 和 stdout 都不回传。私有 `sandbox_receipt` 指向完整 receipt，bridge 会从 Actor projection 去除它。失败只回传空 metrics/artifacts 和 failed；异常类型与执行日志留在 private。

可选 `NpzClassificationAggregator({split: FileBinding(private_truth, hash)})` 提供最小严格实现：要求 `results.npz` 内仅有 `logits(N,)`、`sample_ids(N,)`、可选 `target_predictions(N,62)`；在分配数组前检查 zip 大小、NPY header/shape/dtype/实际字节数；不允许 pickle/object/structured dtype、候选 labels、NaN/Inf 或 row 重排。真值只从 hash 绑定的 trusted NPZ 的 `y/sample_ids` 读取，计算 accuracy/balanced_accuracy。当前不做 Q1 target recovery 指标或 Q2/Q3 grouped statistics；root 的科学 aggregator 按冻结 schema 扩展。

## 验证与限制

本地 WSL 有 bubblewrap 0.11.1，已实际执行 stdlib canary：私有 sentinel/外网/其他 split 不可见，public/input/candidate/root/dev 不可写，自有 output 可写，无 proxy 环境，重复 submit/poll 不重跑。另实测 1 秒超时后无 owned survivor、输出 symlink 不能成功。NumPy 校验在 Windows NumPy 环境实际运行；WSL 无 NumPy，相关两项在那里跳过。

RED/GREEN 与最终框架回归日志在 `.local/research/2026-10-29-brainpec-real/verification/R06-*.log`。没有服务器操作、模型调用或真实 EEG 运行。服务器实际 runtime/mount、完整依赖、test 数据保护及真实科学聚合仍需 root 做独立 canary 与验收。
