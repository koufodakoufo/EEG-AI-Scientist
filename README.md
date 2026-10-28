# EEG-AI-Scientist

正式本地工作区只有 **`X:\projects\EEG-AI-Scientist`**。从 VS Code 或 Codex 打开这个目录。C盘 ChatGPT 文件夹只保留先前的临时服务器报告，不再存放活动工程。

## 从哪里开始

- 今早先读：[`MORNING_SUMMARY.md`](MORNING_SUMMARY.md)，再看证据与恢复入口。
- 当前框架源码：[`framework/`](framework/README.md)。导入时保留了wzf原包的281个文件；本夜按新授权增加评测模块并修复少量driver逻辑，原始发行包仍在归档中。该子目录没有独立`.git`。
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

项目继续使用根目录原有`.git`与`github` remote。用户在2026-10-28明确授权本地提交后，以原HEAD `c22df47`为祖先保全整理前修改，再提交目录整理、所选框架源码和连接工具。本夜以 `5df1d9e` 为基线，在 `research/overnight-20261029` 上推进。原暂存边界和备份保存在本地归档；具体提交见 `git log --oneline`。没有推送GitHub。

上轮误建的C盘副本曾产生两次本地提交，最终快照为`fb6c37e`。该活动副本和恢复演练克隆已从C盘移除；其历史仅作为Git bundle保存在上述配置归档中，没有合并进本项目或推到GitHub。

服务器的 `/data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research` 保持该来源快照。**新的活动工程**是 `/data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration`，它与X盘根仓库同源，通过Git bundle同步。旧来源副本不再作为活动开发入口。尚无团队上游地址，后续取得地址再核实，不猜测remote。

服务器Codex 0.165.0已由本人登录，真实模型短调用、隔离试跑、dev与holdout运行均已有日志。最终Linux测试为新模块79项及原框架14项通过。Windows用于编辑和远程操作；原Linux框架仍不宣称支持Windows原生运行。

代理脚本使用服务器自动分配的空闲端口，并保持PowerShell窗口运行；已修复PowerShell 7日期反序列化导致的进程身份误判。脚本更新个人项目CLI环境和Codex IDE代理配置；重新启动后需重新source或重载VS Code窗口。今晚的辅助隧道已经停止，白天操作见[RESUME](docs/overnight/2026-10-29/RESUME.md)。IDE扩展不属于本夜验收。

Git中的框架是经过筛选的源码导入；含受试者标识的split清单、原包及历史示例运行产物只留本地，详见[`docs/source-import.md`](docs/source-import.md)。

## 当前停止边界

本夜新增了可审计的合成科研评测与skill对照，没有重训EEG基础模型，没有证明真实EEG复现或skill收益。24次额外worker预算已耗尽；继续模型实验需要新一轮授权预算与冻结协议。实验室dataset、共享数据和旧服务器项目不得修改或移动。服务器写入只限已建立的独立个人工作区。
