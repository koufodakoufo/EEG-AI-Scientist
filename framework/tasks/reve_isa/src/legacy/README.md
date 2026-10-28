# legacy/：旧 harness 的编排代码（只读参考）

这些文件来自 2026-10-19 运行的冻结源码包。它们通过旧 TiONE broker 的请求契约运行一个目标数据集的后训练与下游评估（`remote_worker.py`、`stages.py`），并包含吞吐预测、云端 smoke 与 CPU 契约测试。

新程序不再使用 broker 契约。setup 阶段请参考这里的调用链，在 `src/run_eval.py` 中写出**单个目标数据集**的完整评估入口（见 TASK.md 的评估契约），复用上一级目录的核心模块。不要修改本目录。
