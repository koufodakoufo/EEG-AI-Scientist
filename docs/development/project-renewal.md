# EEG RSI Scientist：工程重构与研究准备

本轮只整理、重构和准备，不启动九小时科学研究窗口。

## 设计

目标是可学习科研方法的 EEG Scientist：内环产生可证伪的假设和证据，外环更新科研策略，并在未参与更新的问题上检验收益。现有 BrainPEC 分析是一个实验场，不是项目总目标。

采用一个 Git 仓库、一条 `main` 主线、一个 Python 包。代码按职责分为 `agent`（研究执行）、`evaluation`（可信评估）、`eeg`（具体科学任务）、`improvement`（经验与策略材料）。不会把尚未实现的外环优化器写成已有能力。

比较过三个方案：仅改导航不能解决代码混放；重写调度器会丢失已有验证；选择迁移现有实现、明确边界、保留行为和测试。旧实验以标签和原冻结运行目录复现，不在新主线保留整套旧导入别名。

用户要求自主执行、语义命名、云端优先、允许复制服务器材料，禁止随意移动或删除他人及共享内容。正式本地目录仍为 `X:/projects/EEG-AI-Scientist`。新目录、分支、运行名不使用 overnight、morning 或部署日期作为用途名称。日期只作元数据。

## 实施计划

**Goal:** 清楚的代码布局、统一 Git 主线、多端同步说明和可执行的 RSI ignition 研究设计。

**Architecture:** `src/eegfm` 可安装包；配置和任务定义独立于运行产物；GitHub 分发版本化代码，个人运行目录保存数据和证据。

**Tech Stack:** Python、pytest、Git、现有 SSH 和 CPU 科学环境。GPU 研究不属于本轮。

**Spec:** 本文件“设计”部分及本轮用户要求。

### 全局约束

- 保留现有未提交成果：已提交为 `56055ea`；旧研究基线 `fc8d7e1`。
- 不读取或提交凭据、逐参与者数据、权重、隐藏答案或团队私有材料。
- 不修改旧运行锁、测试预约、候选、原始报告内容；移动报告只改变位置。
- 不 force-push，不重写公开历史；先确认祖先关系和归档标签再移除旧分支名。
- 不创建新 Git bundle 作为同步方式。
- 不把可见 GPU、可写共享目录当作资源分配。

### 1. 源码与入口

- [ ] 将 `framework/eegfm` 迁至 `src/eegfm`，按 agent/evaluation/eeg/improvement 分离。
- [ ] 增加 pyproject、安装入口、显式工作区解析；CLI help 不依赖科学/GPU 环境。
- [ ] 将现有测试迁入 tests；保留预算、隔离、冻结、重放、数值和完整生命周期测试。
- [ ] 将可复用科学脚本纳入包；旧部署和一次性脚本进入历史区。
- [ ] 验证根目录 pytest、仓库外导入、CLI、Linux 生命周期；明确平台限制。

### 2. 目录与命名

- [x] README 成为唯一日常入口；旧报告进入 docs/history；原 archive 保持原位。
- [ ] 任务按问题命名，运行用 study/protocol/generation/condition/repeat 分层；时间是字段。
- [ ] 更新 AGENTS、架构说明、工作区视图和路径迁移表。

### 3. Git 与机器

- [ ] 核对所有分支、标签、干净状态和服务器路径；保留五个语义归档标签。
- [ ] 验证后将主线 fast-forward 到整理结果；收起已归档分支，统一 remote 名 origin。
- [ ] 新代码工作区与旧冻结证据分离；通过 Git 同步代码，不通过 bundle 或整目录复制同步环境。
- [ ] 火山云优先：核查协作者实践与存储规则，建立个人可恢复入口及环境；ncc 保留旧证据并可运行新代码。

### 4. 研究准备

- [ ] 精读 cx 构想、AIDE²、NeuroWeaver、AutoScientists，并检索相关一手工作。
- [ ] 提出 EEG ignition 方案：明确改进对象、任务/评估边界、知识对照、同预算与独立重复。
- [ ] 交付一份可进入下一九小时窗口的协议草案，列出现有能力与尚未实现的部分。

### Review Focus

1. 移动后代码是否仍隐式依赖旧目录或当前工作目录。
2. 冻结检查、隐藏测试和研究者权限是否被重构削弱。
3. 私有材料和运行产物是否意外进入 Git。
4. 新主线是否仍能定位旧阶段的源码和证据。
5. 云端入口是否把临时存储/可见 GPU 错称持久资源/已分配资源。

## 进度与决定

- 已保存既有导航及聚合图表，已建立 `refactor/scientist-workspace`。
- 已建立 archive/brainpec-pilot-v1、archive/synthetic-pilot-v1、archive/workspace-import-v1、archive/proposal-agent-v1、archive/early-harness-v1 五个本地标签；待验证后同步。
- Ruling: 在唯一正式本地目录的主题分支实施，不增加第二个日常工作区；现有内容已有提交和标签保护。
- Baseline: Windows 根目录 pytest 因未安装 eegfm 失败；临时 PYTHONPATH 后因 Linux fcntl 收集失败。初次 ncc 基础 venv 缺 NumPy，正在定位原科学环境。尚未声称基线测试通过。
- Ruling: 自动审批拒绝整体移动 archive，故保留原件与路径；其内容不再作为日常入口，不新增 bundle。
- 已迁移历史文档并重写 README、AGENTS、PROGRAM、架构与机器说明；同步命令仅允许干净 main 发布，非 main 拒绝行为已验证。
- 新 ncc 个人 code/runs/resources/evidence 已创建，旧 integration 和证据保持原位。火山云在 vePFS 本人前缀准备，登记待完成；新环境在临时开发机盘。
- Baseline 更新：旧 ncc 完整套件初次在 SciPy 原生库崩溃；无项目代码的小型 sklearn 程序复现了线程池2→4扩容的触发条件。固定初始 OpenBLAS 线程数4后，原始266项测试全部通过（99.53s）。没有修改冻结科学实现。
- 旧工具复制并逐文件核对SHA256，在 `2d22483` 保存恢复点后移除活动入口。旧 framework 剩余说明和入口也经副本核对后移出当前索引；原位置的未跟踪运行保持不动。
- 独立代码复核提出并修复三项：发布核对远端实际分支/HEAD；科学子命令帮助无需科学依赖；研究者提示与当前说明一致。复核确认三项已解决；新参数定义计入相应源码冻结清单。
- 火山云个人CPU环境安装完成，依赖检查和小型CPU计算通过；普通用户命名空间不可用且未发现原生研究者CLI，因此科学CPU工具与完整隔离Actor的就绪状态分开记录。
