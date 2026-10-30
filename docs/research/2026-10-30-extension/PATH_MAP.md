# 当前路径与节点关系

本轮收尾状态；目录名中的日期是历史部署标识，不要求迁移或重命名。所有服务器数据/权重、私有参考与原始轨迹都不经GitHub同步。

| 节点/位置 | 职责 |
| --- | --- |
| `X:/projects/EEG-AI-Scientist` | 唯一正式Windows工作区、原有根Git、文档与代码发布入口 |
| `X:/projects/EEG-AI-Scientist/framework` | 当前维护框架，不另建Git |
| GitHub `koufodakoufo/EEG-AI-Scientist` | 现有代码remote名为github；维护分支research/brainpec-real-20261029，未强推、未改main |
| nccserver0 `/data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration` | 同源活动Git根；真实Actor/可信执行层代码 |
| nccserver0 `/data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029` | 本轮WORK：数据视图、运行、私有参考、预算、证据和venv |
| nccserver0 `WORK/episodes/E01,E05,E06` | 原生Actor与Driver运行证据；controls为认证边界，不读取、不复制 |
| nccserver0 `WORK/controller/comparison-v2` | E05–E08冻结配置与EXPERIMENT_FREEZE；E07/E08没运行 |
| nccserver0 `WORK/controller/BUDGET.json` | 权威调用账本；仓库旧BUDGET是历史快照，不可拿来覆盖 |
| nccserver0 `WORK/replays/E05` | E05干净重放与审计 |
| nccserver0 `WORK/builders/semantic-calibration-v1` | 原生校准冻结输入、私有oracle与结果 |
| nccserver0 `WORK/closeout/20261030` | 本轮私有归档、manifest、收尾记录 |
| nccserver0 `/data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research` | 原fb6c37e快照；非开发入口，保持无改动 |
| 火山云 `/home/duandh/projects/EEG-AI-Scientist-20261030/repository` | 同源完整代码Git副本 |
| 火山云同级 `source/` | 早先固定最小接口验收快照，不能与repository的最新HEAD混同 |
| 火山云同级 `venv/`、`runtime/`、`environment.sh`、`evidence/` | 本人CPU环境、缓存隔离与接口验收证据；尚非受测Actor隔离环境 |
| `C:/Users/14090/Documents/ChatGPT/EEG-FM-RSI` | 临时/历史支持目录，非正式工程；app的旧cwd不改变此约定 |

Windows私有路径均位于正式根的`.local/`：

| 相对路径 | 内容 |
| --- | --- |
| `research/2026-10-29-brainpec-real/resources` | 本人新获取的官方EEGMAT/CBraMod资源 |
| `research/2026-10-29-brainpec-real/private/reference-local` | EEGMAT冻结参考结果与预测，禁止提供给Actor |
| `research/2026-10-30-extension/baselines` | 透明、预训练、随机骨干比较 |
| `research/2026-10-30-extension/exact-bootstrap/final` | 精确经验bootstrap结果 |
| `research/2026-10-30-extension/eegmmidb/actor_public` | 新任务允许公共视图，仅用于未来经过准入的隔离挂载 |
| `research/2026-10-30-extension/eegmmidb/private_builder` | 新任务参考、prepared、sealed truth与匿名映射，不给Actor |
| `research/2026-10-30-extension/closeout/backup` | 427文件归档及本地完整校验 |
| `research/2026-10-30-extension/closeout/E06` | 本次已有证据算术/文档审计 |
| `research/2026-10-30-extension/volcano-setup` | 云端部署来源及本地收据 |

代码同步走Git提交/快进；服务器无必要读取Windows的GitHub认证。本轮通过SHA验证的bundle传入本人目录，再快进本人仓库，Windows向既有GitHub分支推送。最终HEAD见[RESUME](RESUME.md)。共享数据路径不纳入任何同步脚本。
