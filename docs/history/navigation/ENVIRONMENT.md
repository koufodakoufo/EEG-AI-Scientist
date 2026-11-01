# Current environment

正式本地入口：`X:\projects\EEG-AI-Scientist`；源码：`framework/`。

当前完整运行环境在nccserver0：

- 用户：`duandh`；主机名：`nccserv0`。
- 工作区：`/data/duandh/eegfm-stage-a-20261028`。
- 加载：`source /data/duandh/eegfm-stage-a-20261028/environment.sh`。
- 源码：`/data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research`。
- Python：工作区下`venv/bin/python`，3.10.12；PyYAML6.0.3、pytest9.2.0、pip26.2.2。
- Codex：工作区下`bin/codex`，0.165.0；独立`CODEX_HOME`在`codex-home/`。
- 验证：12项离线测试通过；本人登录和真实模型短调用待完成。

操作顺序见`docs/environment-20261028/README.zh-CN.md`。Windows可编辑源码与通过SSH操作；没有承诺Linux框架在Windows原生可运行。

原根`.venv`及VS Code Python配置已封存于`archive/legacy-harness-20261028/`。旧虚拟环境含原绝对路径，迁移后不应直接运行；需要复现旧工程时按恢复包重建原布局和环境。
