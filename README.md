# EEG-AI-Scientist

正式本地工作区只有 **`X:\projects\EEG-AI-Scientist`**。从 VS Code 或 Codex 打开这个目录。C盘 ChatGPT 文件夹只保留先前的临时服务器报告，不再存放活动工程。

## 从哪里开始

- 当前框架源码：[`framework/`](framework/README.md)。它来自收到的wzf源码包，281个文件与原包逐字节一致；该子目录没有独立`.git`。
- 连接服务器、登录Codex：[`docs/environment-20261028/README.zh-CN.md`](docs/environment-20261028/README.zh-CN.md)。按其中“VS Code具体操作”执行。
- 本轮整理与当前状态：[`docs/environment-20261028/current-status.json`](docs/environment-20261028/current-status.json)。
- 科研交接原件：[`docs/handoffs/EEG_FM_Codex_Handoff_2026-10-28.md`](docs/handoffs/EEG_FM_Codex_Handoff_2026-10-28.md)。其路径和部署建议以当前说明与用户最新约束为准。

## 目录分工

| 目录 | 内容 |
| --- | --- |
| `framework/` | 当前wzf框架源码；不在原始来源副本中开发 |
| `docs/` | 当前说明、状态与交接 |
| `scripts/` | Windows连接、代理隧道启动/停止入口 |
| `materials/` | 论文、会议和基础设施参考材料；默认不上传Git |
| `archive/legacy-harness-20261028/` | 旧自建harness代码、配置、测试、文档和旧环境封存 |
| `archive/experiments/`、`archive/history/`等 | 原有实验归档，原件未改写 |
| `archive/sources/wzf-20261022/` | 收到的tar/gz与原解包副本，保留来源 |
| `archive/setup-20261028/evidence/` | 上轮配置证据、恢复快照、Git bundle和核验记录 |
| `archive/reorganization-20261028/` | 本轮逐路径迁移清单、校验及原Git状态 |
| `.local/` | 本机临时PID和日志，不进Git |
| `credentials/` | 既有个人凭据目录；未读取、未移动，不进Git |

## Git和服务器关系

项目继续使用根目录原有`.git`与`github` remote。用户在2026-10-28明确授权本地提交后，以原HEAD `c22df47`为祖先保全整理前修改，再提交目录整理、所选框架源码和连接工具。原暂存边界和备份保存在本地归档；具体提交见 `git log -2`。本次没有推送GitHub。

上轮误建的C盘副本曾产生两次本地提交，最终快照为`fb6c37e`。该活动副本和恢复演练克隆已从C盘移除；其历史仅作为Git bundle保存在上述配置归档中，没有合并进本项目或推到GitHub。

server0使用`/data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research`，其Git仍是该来源快照。**当前两端对应的是framework文件内容一致，不是整个项目的Git HEAD一致。**本机工程还包含历史、材料和操作文档。尚无团队上游地址，后续取得地址再核实来源并安排同步，不猜测remote。

服务器已装Codex 0.165.0与独立Python环境，12项离线测试通过。本人登录和真实模型短调用尚未完成。Windows当前用于编辑和远程操作；未验证该Linux框架能在Windows原生运行。

代理脚本现使用服务器自动分配的空闲端口，并保持PowerShell前台窗口运行，避免旧固定端口残留导致再次启动失败。脚本同时更新个人项目CLI环境和Codex IDE代理配置；运行后按操作说明重新source或重载VS Code窗口。本人浏览器授权与模型调用仍需单独验收。

Git中的框架是经过筛选的源码导入；含受试者标识的split清单、原包及历史示例运行产物只留本地，详见[`docs/source-import.md`](docs/source-import.md)。

## 当前停止边界

先完成本人登录与短调用验收；本轮未修改Agent架构、扩展科研任务或启动EEG训练。实验室dataset、共享数据和旧服务器项目不得修改或移动。服务器写入只限已建立的独立个人工作区。
