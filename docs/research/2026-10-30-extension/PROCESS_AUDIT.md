# 收尾进程与预算核验

2026-10-30上午按用户要求停止新研究。

- nccserver0于10:04:50 +08扫描本人UID、命令参数中引用本轮WORK的进程，结果为空；权威BUDGET中reserved/running调用也为空。E01、E05、E06是实际存在的episode，E07/E08没有运行目录。
- C01/C02两项收尾审查已完成。R92仅预约未派发，终态cancelled，不能计入REVE真实研究。没有新Actor或Distiller调用。
- 火山云本人工作根的同类进程检查为空，见私有CLOUD_PROCESS_SNAPSHOT.json。没有GPU研究进程由本轮遗留。
- 项目记录的Windows临时反向隧道PID41128、远端loopback端口45949已通过Stop-NccServer0Proxy.ps1核对完整命令与创建时刻后停止；随后确认PID不存在。未按进程名终止其他SSH，未停止用户本机代理10808，也未修改全局路由、校园网络或VS Code连接配置。
- 再使用服务器Codex，需要按[RESUME](RESUME.md)重启项目隧道、重新source环境；无需默认重新登录。

范围是本人已知工作区及记录的helper，不宣称扫描了所有系统/共享进程，也不清理未知监听端口。原生会话和可信worker自身收据均记录无遗留已跟踪子进程；这与上述现场扫描相互补充。

私有收据位于本地extension/closeout/backup下的PROCESS_SNAPSHOT.json、CLOUD_PROCESS_SNAPSHOT.json、PROXY_STOP.json和BUDGET_FINAL.json；服务器保留对应原件。ncc当时home空闲4,336,197,632字节、工作盘空闲107,220,062,208字节；仅作现场观察，不修改既有准入下限或清理他人文件。
