# 本地项目与 server0：当前用法

更新：2026-10-28，北京时间。正式本地工作区是 **X:\projects\EEG-AI-Scientist**，当前框架在其中的 `framework/`。旧C盘正式副本的安排已撤回。

## 目录与Git关系

| 位置 | 用途 |
| --- | --- |
| X盘项目根 | 唯一正式本地项目，沿用原 .git 和 GitHub remote |
| framework/ | 当前281个框架源文件，没有嵌套 .git |
| archive/legacy-harness-20261028/ | 旧harness代码、配置、文档和旧环境封存 |
| archive/setup-20261028/evidence/ | 恢复快照、原始配置证据、来源清单与Git bundle |
| archive/reorganization-20261028/ | 本轮逐路径迁移及核验 |
| materials/ | 论文、会议、基础设施材料 |
| /data/duandh/eegfm-stage-a-20261028 | server0独立个人工作区 |
| 远端工作区下 source/eeg-fm-research | 在服务器上编辑和测试的框架副本 |
| 远端工作区下 venv、bin、codex-home | Python环境、Codex入口、独立认证与状态 |

本机编辑X盘文件就是改本机；VS Code Remote SSH窗口编辑的是server0文件。SSH不经过GitHub。Git交换已提交代码，不同步环境、登录状态、未提交修改或运行进程。

本机根Git沿用原分支 `overnight/flash-20261020-0058` 与原GitHub remote。用户随后明确授权本地提交，提交顺序是先保全整理前的修改，再记录新布局与所选框架源码；原HEAD `c22df47`仍在祖先历史中，原暂存边界保存在本地归档。实际提交号查看 `git log -2`。本轮不push。

server0仍保存独立来源快照 `fb6c37e`。本机framework的281文件与其原字节一致，**不是整个本机项目与server0的Git HEAD一致**。收到的e6f6e50仅是分发标签，真实团队上游仍未知。原GitHub仓库仍是koufodakoufo/EEG-AI-Scientist；未另建GitHub仓库或合并两套无关历史。后续提交和同步需按这套新布局安排。

上轮C盘工程的两次本地提交仅保留为归档bundle；活动工程和恢复演练clone均已撤除。C盘只剩之前已有的reports。旧状态文件保存在archive下作为历史证据，当前状态看本目录current-status.json。

## 为什么用 /data/duandh

你的登录账号已实测为 `duandh`，`~`是 `/home/duandh`。本轮安装前检查时，home所在系统盘余约9.49 GiB；另一个本地ext4磁盘 `/data` 余约357.66 GiB，因此在那里新建个人目录。余量是当时检查值，不是永久配额。

`/data` 与 `/mnt/dataset0` 至 `/mnt/dataset4` 是不同挂载点。本轮没有在dataset安装、写缓存或输出测试。目录名沿用账号duandh，不改账号或home。

## VS Code具体操作

2026-10-28后续修复：固定18081在网络变化后仍可能被旧监听占用。脚本已改为由SSH申请动态空闲端口，并由前台PowerShell持续看守，兼容Windows PowerShell 5.1。实际验证包括认证端点HTTP 200，以及项目CLI、扩展自带Codex均能收到设备码登录提示。探测产生的设备码未保存，等待进程由探测自行终止；用户仍需本人重新发起并完成浏览器授权，模型短调用仍待验收。

### 1. Windows本机PowerShell：启动临时代理隧道

不要在Linux远程终端执行下面的Windows命令：

```powershell
cd X:\projects\EEG-AI-Scientist
.\scripts\Start-NccServer0Proxy.ps1
```

脚本自动选当前校园WLAN IPv4，使用现有SSH身份，让server0分配一个回环端口并转发到本机已有代理 `127.0.0.1:10808`。确认实际监听和认证端点HTTP 200后，才更新项目environment.sh及个人Codex IDE的代理配置。无法唯一确定校园地址时，核实后使用 `-CampusAddress 当前校园IPv4`；不要抄旧地址。

实际链路是：服务器Codex → 服务器动态回环端口 → SSH反向隧道 → Windows回环10808 → 本机代理出口 → OpenAI。单独在Windows开启代理，不会自动代理服务器进程。看到 `Task tunnel ready` 后，**保持这个PowerShell窗口打开**，在VS Code远端终端继续登录；脚本持续运行是正常状态。网络切换或隧道退出后重新运行脚本，再重新加载环境或重载扩展。

若旧登录命令卡住，先Ctrl+C，再重新source环境并发起登录；运行中的旧进程不会继承后来修改的环境。重复运行脚本会验证并复用本任务仍存活的隧道；来源不明的服务器监听不会被终止。`-VerifyOnlySeconds`仅用于维护验收，会自动结束隧道，日常使用不要加这个参数。

运行记录在本项目 `.local/nccserver0/`，不进Git。它不修改系统路由或全局SSH配置。代理依赖电脑、校园连接和本机代理在线；loopback端口仍可能被同机其他用户访问，不是用户间隔离。结束时可在看守窗口按Ctrl+C，或在另一个本机PowerShell运行：

```powershell
.\scripts\Stop-NccServer0Proxy.ps1
```

### 2. VS Code：连接并打开远端文件夹

用已有的 **Remote-SSH → Connect to Host → nccserver0**，确认左下角显示该远程主机。然后 **File → Open Folder**：

```text
/data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research
```

这个窗口操作的是服务器文件。若原VS Code连接正常，无需改配置。

代理脚本只为它自己的SSH连接绑定校园地址，不会改变VS Code独立连接的选路。若VS Code因双网而超时，可先在Windows用下列现成入口完成登录/验收，无需先改全局SSH配置：

```powershell
.\scripts\Connect-NccServer0.ps1 -Mode Login
.\scripts\Connect-NccServer0.ps1 -Mode Status
.\scripts\Connect-NccServer0.ps1 -Mode Smoke
```

需要远程交互终端时用 `-Mode Shell`。

### 3. VS Code远端新终端：加载环境

选择 **Terminal → New Terminal**：

```bash
hostname
whoami
cd /data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research
source /data/duandh/eegfm-stage-a-20261028/environment.sh
command -v codex
codex --version
```

预期为 `nccserv0`、`duandh`，Codex入口为个人工作区的bin/codex，版本 `codex-cli 0.165.0`。source只给当前终端加载PATH、CODEX_HOME与代理；没有修改.bashrc。每开一个新终端，都需要再次加载。

### 4. 远端终端：发起本人登录

```bash
codex login --device-auth
```

在自己的电脑或手机浏览器打开终端显示的官方地址，输入**此次新生成的设备码**并授权。之前聊天的设备码不能视为仍有效。不要把密钥、令牌或认证文件发给助手；认证保存在个人codex-home内，不进Git。

完成后：

```bash
codex login status
```

若仍为Not logged in，尚未完成登录。设备登录可能需个人安全设置或工作区允许，以页面提示为准。[官方认证说明](https://learn.chatgpt.com/docs/auth)

### 5. 登录成功后：一次限时只读短调用

```bash
timeout -k 5s 90s codex exec \
  --skip-git-repo-check --sandbox read-only \
  -C /data/duandh/eegfm-stage-a-20261028/smoke \
  "Reply exactly CODEX_READY. Do not use tools, read files, or run commands."
```

预期返回CODEX_READY。90秒限制运行时间，不是token硬预算。该命令只验证网络、认证和一次模型响应；若失败，保留错误原文，不反复启动研究。

以后在远程源码目录、已加载环境的终端中运行 `codex`，即可进入交互会话。本次先完成短调用验收，停在架构修改与科研扩展之前。

## 已验证和待完成

### VS Code扩展登录

已实际确认扩展的Codex进程运行在服务器，默认CODEX_HOME为 `/home/duandh/.codex`，最初没有代理变量。启动脚本现在只在该目录维护一个**不含凭据的代理专用 `.env`**；遇到已有非本脚本管理的 `.env`会拒绝覆盖。此配置与项目CLI的独立codex-home不同，不会自动合并两处认证。

隧道ready后，取消扩展里旧的登录尝试，然后在VS Code命令面板执行 `Developer: Reload Window`（开发人员：重新加载窗口），再从Codex扩展重新登录。新终端中source环境不会改变已启动的扩展进程。官方说明建议将扩展需要的环境变量放入 `~/.codex/.env` 后重启扩展：[环境继承说明](https://learn.chatgpt.com/docs/amazon-bedrock#desktop-app-and-ide-extension)。

先在SSH窗口打开本项目的远端源码目录。登录后以只读 `hostname`、`pwd` 确认扩展操作的是 `nccserv0` 和正确目录，再做后续开发。

| 项目 | 状态 |
| --- | --- |
| 本地归档 | 1214业务文件备份与恢复演练通过；本次逐路径迁移hash核对通过 |
| C盘撤回 | 本任务误建工程、恢复演练clone及新增docs/scripts撤回；原reports保留 |
| 来源 | framework的281文件与原包逐字节一致 |
| SSH与代理 | 动态端口在PowerShell 5.1实际运行通过；复用与认证端点检查通过 |
| 设备码请求 | 项目CLI和扩展自带Codex均实际收到设备码提示；这不是本人授权完成 |
| Codex | 0.165.0已安装，官方安装包SHA256匹配 |
| Python | 独立3.10.12，PyYAML6.0.3、pytest9.2.0、pip26.2.2；pip check通过 |
| 离线验证 | 12项通过，44.07秒，含CPU合成闭环与已登记作业的有限恢复 |
| 本人登录 | 用户尚未完成，待第4步 |
| 真实模型短调用 | 待登录后第5步，不以离线测试代替 |

安装包摘要：`be635d3486a5bd060d0fff582ae6d30160280c31344dd85719707fa920e187f0`。[官方固定版本](https://github.com/openai/codex/releases/tag/rust-v0.165.0)

离线测试使用脚本Agent，未使用EEG数据或GPU，也未调用真实研究Agent；有限恢复通过不保证任意崩溃时点安全。旧harness、旧.venv和旧VS Code配置已封存，含旧绝对路径，不能直接运行；复现旧工程时在新空目录恢复原布局并重建环境。

dataset、旧服务器项目和其他用户文件保持只读。后续复制仍需核对源目标、挂载别名、空间、中断残片和完整性；不得使用删除源文件的同步。
