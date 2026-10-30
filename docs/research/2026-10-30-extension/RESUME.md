# 本轮收尾与恢复

用户2026-10-30上午选择“本轮先收尾并报告”。**没有待继续的后台科研任务；不要自动启动E07/E08、Distiller或REVE。** 进一步研究需新时间窗口，旧预算/协议记录不能重置。

## 当前版本

维护分支为`research/brainpec-real-20261029`，remote为`github`，地址`https://github.com/koufodakoufo/EEG-AI-Scientist.git`。本轮收尾提交及三节点/远端实际核验将保存为本目录`SYNC_RECEIPT.json`；它记录同步的内容提交，后续仅记录收据的提交可能在其后。不得把早期23f9df7或30cac6f检查点当最终状态。

原来源`/data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research`应为`fb6c37e64a58d316d98ae087190483d3d4bf1389`，工作树干净。不要在其中继续开发。

## 先打开正确工程

Windows打开`X:\projects\EEG-AI-Scientist`。VS Code Remote-SSH连接nccserver0后，再打开服务器文件夹：

```text
/data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration
```

终端只读核对：

```bash
git status --short
git branch --show-current
git log -3 --oneline
```

Git根是integration，不是/data整个目录，也不是framework子目录。

## 网络与Codex

校园Wi-Fi提供实验室SSH路径，现有本地代理提供模型服务网络；二者职责不同。每次校园IPv4可能变化，沿用项目脚本动态核验，不改全局路由或硬编码旧地址。

需要使用服务器Codex时，在Windows PowerShell运行并保留该窗口：

```powershell
cd X:\projects\EEG-AI-Scientist
.\scripts\Start-NccServer0Proxy.ps1
```

成功后在服务器新终端执行：

```bash
source /data/duandh/eegfm-stage-a-20261028/environment.sh
codex --version
codex login status
```

已经成功登录过，不默认重新device-auth，也不复制auth.json。CLI可用与VS Code扩展登录是不同验收；本轮没有宣称修复了所有IDE情形。Start脚本动态分配loopback端口，重启后需要重新source；IDE要重载窗口。只有终止本项目记录的隧道才使用`Stop-NccServer0Proxy.ps1`，它核对PID、创建时刻和完整命令，不能按进程名杀所有SSH。收尾实测代理状态见`PROCESS_AUDIT.md`。

## 安全恢复研究的顺序（本轮未执行）

1. 读取最新账本、冻结协议、磁盘与已运行进程；不是重复启动已有episode。
2. E05/E06均终态，E01失败保留；E07/E08没有启动。旧冻结截止已过，不绕过准入函数，重新登记授权、时间与公开结果暴露。
3. E06如需干净重放，使用新审计目录、原锁定候选和既有可信执行器；不能把重放变成让Actor修测试答案。
4. 新任务需要完成controller范围与公共文档绑定适配。不可把EEGMMIDB套用EEGMAT任务ID。
5. 真实dev材料与新任务隔离后，才启动全新Distiller；不给Builder诊断、参考实现、测试gold或本报告。新skill冻结后在新任务成对评价。
6. 火山云先确认真实模型输入协议、个人资源分配与所需隔离；当前CPU合成验收不授权共享GPU、不证明Actor读取隔离。

可恢复证据见[EVIDENCE_INDEX](EVIDENCE_INDEX.md)。全部原始权威证据仍在服务器原位置，备份不包含凭据；数据/权重分别在本人私有目录，不能从Git克隆就假设自动齐备。当前没有自动定时恢复任务。
