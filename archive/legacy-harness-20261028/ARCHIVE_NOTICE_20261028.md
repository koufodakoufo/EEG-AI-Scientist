# Legacy harness archive

这些是2026-10-28整理前的旧harness源码、配置、测试、审计与入口文档，保留原文件字节。当前开发入口已切换到项目根的framework/。

此目录不是可直接运行的独立项目：旧脚本引用原项目根archive/等路径，旧.venv中的editable路径和启动器仍指向旧位置。不要在这里运行旧CLI、付费研究命令或尝试自动补写旧实验。需要恢复时，使用../setup-20261028/evidence/local-archive/中的恢复快照，在新的空目录重建原布局，再根据锁文件重建环境。

原根.git、用户暂存区和既有credentials/保留在正式项目根。旧archive/的原实验文件没有移入本目录或改写。逐路径迁移与hash见../reorganization-20261028/。
