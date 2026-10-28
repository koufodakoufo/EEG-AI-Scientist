# EEG FM 阶段 A：环境与日常使用

更新：2026-10-28，北京时间。本地归档、远端安装和离线验证已完成；个人登录与真实模型短调用尚待完成。以下将已验证结果与待办分开记录。

## 当前做到哪里

| 项目 | 状态 |
| --- | --- |
| 旧项目归档 | 1,214份业务文件与Git/index/双patch备份完成，真实恢复演练通过；旧目录原位保留 |
| Windows 新框架工作副本 | 已准备；分支 `snapshot-import`；提交 `fb6c37e64a58d316d98ae087190483d3d4bf1389` |
| 新框架团队上游 | 用户尚无地址；没有配置或假定上游 |
| server0 SSH | 本轮已登录，确认 `nccserv0`、用户 `duandh`、UID 2046 |
| 新个人工作区 | 已建立 `/data/duandh/eegfm-stage-a-20261028` |
| 启动入口 | 新目录内 `bin/codex` 包装器、`environment.sh`、`bin/enter-workspace` 已建立 |
| 新框架远端副本 | 已校验bundle并导入；HEAD与Windows一致，工作树干净 |
| Codex CLI 0.165.0 | 官方安装包SHA-256匹配，`--version`通过 |
| 个人登录 | 设备认证端点已连通；`login status`仍为Not logged in，须本人在浏览器完成 |
| Python依赖 | 独立Python 3.10.12环境，PyYAML 6.0.3、pytest 9.2.0；精确依赖见远端requirements-resolved.txt |
| 离线测试、CPU synthetic、有限恢复 | 12/12通过，44.07秒；使用脚本Agent，无真实模型调用、无GPU/EEG数据实验 |
| 真实模型短调用 | 待本人登录后执行；不能将离线通过写成模型已可调用 |

## 哪一部分运行在哪里

Windows 和 server0 都可以开发。Windows 保存本地文件和本地 Git 工作副本；SSH 让终端命令在 server0 执行。VS Code Remote SSH 窗口编辑的是远端文件。**SSH 不经过 GitHub。**

Git 保存代码版本，提交和同步源码；它不自动同步 Python 环境、Codex 安装、登录状态、未提交修改或运行中的进程。两端分别安装环境、分别登录，运行产物是否同步应另外决定。`local` 后端指在启动框架的那台机器执行：在 server0 启动就使用 server0。

| 位置 | 用途 |
| --- | --- |
| `C:/Users/14090/Documents/ChatGPT/EEG-FM-RSI/workspaces/eeg-fm-research` | Windows 新框架工作副本 |
| `X:/projects/EEG-AI-Scientist` | 保留的旧工程，含既有历史与归档；不覆盖、不搬走 |
| `/data/duandh/eegfm-stage-a-20261028` | server0 本轮独立个人工作区 |
| 工作区下 `source/eeg-fm-research` | 已导入的新框架远端 Git 副本，与Windows同提交 |
| 工作区下 `bin/codex` | 本轮 Codex 专用启动包装器 |
| 工作区下 `environment.sh` | 本轮环境变量入口；只在需要时显式加载 |
| 工作区下 `codex-home` | 独立 `CODEX_HOME`，保存登录状态、配置、日志与缓存；不得提交Git |

`/data` 已核实是本地独立 ext4 磁盘，检查时剩余约 357.66 GiB；这是磁盘余量，不是个人配额。`/home` 检查时只剩约 9.49 GiB，因此本轮安装和输出放入上述新目录。dataset 内容和既有项目保持原状，不在那里安装环境或输出运行结果；复制须先评估来源、权限、大小、目标空间和覆盖风险。

## 从 Windows 进入 server0

以下在 **Windows PowerShell** 执行：

优先使用本轮准备的入口；它会从当前WLAN读取校园IPv4地址，无法唯一确定时明确报错，不改系统路由：

```powershell
cd C:/Users/14090/Documents/ChatGPT/EEG-FM-RSI
./scripts/Start-NccServer0Proxy.ps1
./scripts/Connect-NccServer0.ps1 -Mode Shell
```

进入后已经位于框架源码目录并加载独立环境。查看登录状态、发起本人登录或执行限时短调用，分别使用同一脚本的 `-Mode Status`、`-Mode Login`、`-Mode Smoke`。不需要联网时可以用 `./scripts/Stop-NccServer0Proxy.ps1` 关闭本任务隧道；它先核对进程身份。

手工连接方式：

```powershell
ssh -F C:/Users/14090/.ssh/config -b 10.14.241.149 nccserver0
```

入口为 `10.20.38.38:1022`，SSH 别名配置在 `C:/Users/14090/.ssh/config`。`-F` 明确配置文件，`-b` 给本次连接指定电脑的校园网源地址。校园 IP 会变化，不能永久照抄；重连前核实电脑当前 WLAN 地址。不要使用历史地址 `10.24.87.210`。

电脑同时保留手机热点与校园 Wi-Fi：默认流量可能走热点；本轮 TCP 检查中，默认连接实验室端口超时，绑定校园地址立即成功。上述命令只作用于这次连接，不修改默认路由或 SSH 配置。

以下在 **server0 的远程终端** 执行，用于确认进入正确机器：

```bash
hostname
id -un
pwd
```

预期主机为 `nccserv0`，用户为 `duandh`。若用手工SSH连接，显式加载本轮环境：

```bash
source /data/duandh/eegfm-stage-a-20261028/environment.sh
command -v codex
codex --version
```

预期入口应指向本轮新目录。加载脚本只影响当前终端；没有把本轮环境写入既有 shell profile。新终端须重新加载。

## 源码怎样交换

当前新框架没有已知上游地址，先用 **Git bundle** 把 Windows 已提交的快照及历史传到 server0，再导入全新的远端目录。这是初始准备方式，不能称为“新框架已经同步到 GitHub”。bundle 不包含未提交修改、Python 环境或登录状态；后续继续用 bundle 时应保留来源和提交记录，不强制覆盖另一端修改。

Windows与server0的新框架当前基准均为 `snapshot-import` 的 `fb6c37e64a58d316d98ae087190483d3d4bf1389`。可核对：

```bash
git -C /data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research status --short --branch
git -C /data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research rev-parse HEAD
git -C /data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research remote -v
```

远端remote名为 `windows-transfer`，指向本次已校验的本地bundle文件；它不是GitHub或团队上游。Windows新框架未设remote。后续新改动先在所在工作副本提交，再生成新的带提交号bundle；传输到对端独立新路径、校验后再fetch。更新工作树前先确认没有未提交改动、没有正在使用该目录的实验，只允许可解释的fast-forward，不做强制覆盖。未提交修改不会被bundle同步。

取得团队确认的地址后，先核对来源与历史关系，再添加明确命名的remote、fetch和比较差异。不要把旧工程历史硬merge进新框架，也不要为了接上文档而回退团队版本。本轮没有代建或发布新GitHub仓库。

现有 GitHub 仓库 [koufodakoufo/EEG-AI-Scientist](https://github.com/koufodakoufo/EEG-AI-Scientist) 仍保存旧工程。本机 `git ls-remote` 已成功读到其 HEAD/main 短提交 `d0bbb6e`，旧 overnight 短提交为 `c22df47`；没有因此向它推送新框架。连接器的 `to2one` 身份无法访问，与本机 Git CLI 能访问是两条不同认证路径，不能把插件失败当作用户 GitHub 账号失效。

## Codex 登录与验收

Codex CLI `0.165.0` 已安装，使用官方 Linux x86_64 原生二进制，安装包SHA-256为 `be635d3486a5bd060d0fff582ae6d30160280c31344dd85719707fa920e187f0`。无需Node/npm，未改系统级软件或profile。配置默认要求审批并使用workspace-write沙箱；没有开放dataset写入。

在已加载本轮环境的 **server0 终端** 运行：

```bash
codex login --device-auth
```

用户在**自己的浏览器**打开终端给出的官方登录地址，选择本人正确账户并完成认证。设备登录可能需要个人安全设置或工作区管理员允许。不要把密钥、令牌、认证文件或设备码提交Git、贴到共享日志或群聊，不复制本机 `auth.json` 代替本人登录。

若设备认证不可用，可使用只绑定电脑 loopback 的 SSH 1455 端口转发，再运行 `codex login`，由用户浏览器完成回调；具体命令由执行会话按当前网络和端口占用核实后给出。[官方认证说明](https://learn.chatgpt.com/docs/auth)

认证后按顺序检查：

```bash
codex login status
codex exec --help
```

`login status` 成功只说明存在登录状态；还需一次限时、只读的短模型调用，才能证明服务实际可用。首轮不擅自指定模型或付费方式，使用已登录账户可用的默认设置；遇到访问或额度错误，保留错误并定位，不自动切换账户。

验收记录：

| 检查 | 实际结果与证据 |
| --- | --- |
| binary版本与SHA-256 | 0.165.0；官方安装包摘要一致 |
| 新框架远端HEAD、Python解释器 | fb6c37e；新工作区venv/bin/python，3.10.12 |
| 离线测试 | 本轮server0实跑12 passed in 44.07s，见本地reports/environment-20261028/server-tests.log |
| `login status` | 待本人登录后核验 |
| 一次短模型调用 | 待本人登录；准备了90秒限时只读Smoke入口 |
| CPU synthetic和有限恢复 | 完整合成闭环、driver中断后已登记作业恢复测试通过；不证明所有崩溃时点安全 |

## 当前临时网络桥接

本轮使用 SSH 临时反向转发：**server0 `127.0.0.1:18080` → Windows 已有代理 `127.0.0.1:10808`**。记录时本机对应 SSH PID 为 `10280`。这是当前会话记录，PID会变化，重开终端或电脑后不能假定仍存在。

它让服务器通过当前 Windows 连接使用已有代理；不改系统路由、profile或dataset。转发依赖电脑在线、现有代理运行及SSH会话存活，不能当永久服务器服务。只有执行会话验证连通后，才在本轮环境内使用该地址；连接失败时不要复制别人的代理端口。排查或停止时先核实进程身份，不按旧PID盲目结束进程。

反向代理在共享服务器上仅绑定loopback，不开放校园网端口；同一服务器上的其他本地用户仍可能访问该TCP端口，因此只在需要时启用，不将它视为用户间权限隔离。已验证官方设备认证请求成功，网页curl的403本身不等于登录API失败。

## 本地归档入口

`C:/Users/14090/Documents/ChatGPT/EEG-FM-RSI/reports/environment-20261028/local-archive/README.md` 说明备份和恢复方法。1,214份文件、完整refs bundle、原index、暂存blob和暂存/未暂存patch均已校验，并在新的restore-check目录完成恢复演练。原X盘工作区的HEAD、status、index保持不变。

历史归档830份原件全部逐字节相同。旧838条路径基线中的8份展示副本原路径已缺失，但原内容均从archive按原hash找到并只在备份中恢复；不能声称原X目录838个路径全部存在。凭据、环境、缓存不打包，不把本地备份上传GitHub。新快照及来源manifest位于同级 `source-provenance/`。

## 阶段 A 到哪里停止

阶段A目标范围：独立目录、可追溯源码、轻量Python环境、Codex本人登录、短自检、离线测试、CPU synthetic及有限恢复检查。其中本人登录与真实模型短调用尚待完成；其余已有上表证据。全部通过后，也只能说开发与最小执行链可用。

不自动启动正式 REVE、多数据集训练、大规模微调或框架扩建。不移动、修改dataset与旧工程；不终止他人进程。`--once` 不能当作会话内部尝试次数或费用的硬上限，正式运行另定资源边界。

科研阶段需区分构建者资料与受测Agent输入。当前会话及交接已包含参考论文方法、结论和评分线索，不能直接作为“未看答案”的盲测会话；重新发现运行须用独立新会话及限定题包，不能把交接全文、隐藏答案或含答案的记忆同步进去。
