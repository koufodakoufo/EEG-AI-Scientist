# EEGMMIDB 新任务预注册与准备记录

制定时间：2026-10-30 01:02 +08。R58 Builder 在读取任何 EEG 信号前锁定以下方案。

## 目的和官方依据

准备与 EEGMAT 不同的公开数据和预测任务，用于后续真实开发技能迁移评估；本次仅获取和准备资源，不拟合模型、不计算或查看测试科学结果，不修改 E05–E08 的数据、协议、模块和参考结果。

[PhysioNet EEGMMIDB 1.0.0](https://physionet.org/content/eegmmidb/1.0.0/) 为 109 名志愿者的 64 通道、160 Hz、EDF+ 数据；[原始官方协议](https://archive.physionet.org/pn4/eegmmidb/) 将 R01 定义为睁眼基线，R02 定义为闭眼基线，均约一分钟。本任务只用 R01/R02，不把 T0/T1/T2 运动事件解释成眼状态。

官方版本页面标明 [ODC-By 1.0](https://physionet.org/content/eegmmidb/view-license/1.0.0/)；保留许可与数据集、BCI2000 来源归属。引用：Schalk (2009), DOI 10.13026/C28G6P；Schalk et al. (2004), IEEE TBME 51(6):1034–1043，DOI 10.1109/TBME.2004.827072。实际官方文件校验使用 [SHA256SUMS.txt](https://physionet.org/files/eegmmidb/1.0.0/SHA256SUMS.txt)。

## 在信号读取前固定的协议

| 项目 | 固定值 |
|---|---|
| 人员 | 按官方编号前 36 人：S001–S036；不按质量、效果或人口学筛人 |
| 训练 | S001–S024，24 人、48 个 EDF、预计 576 个窗口 |
| 验证 | S025–S030，6 人、12 个 EDF、预计 144 个窗口 |
| 测试 | S031–S036，6 人、12 个 EDF、预计 144 个窗口 |
| 标签 | R01 → 0（睁眼），R02 → 1（闭眼） |
| 窗口 | 每次记录前 60 秒，12 个连续、不重叠的 5 秒窗口；不足 60 秒则停止而非填补或换人 |
| 采样 | 原始 160 Hz，经 MNE FFT resample 到 200 Hz，单任务 n_jobs=1；不声称获得新的 80 Hz 以上信息 |
| 数值 | 微伏除以 100，float32，(N,20,5,200)；无全局/跨集合标准化 |
| 通道 | Fp1,Fp2,F3,F4,F7,F8,T7,T8,C3,C4,P7,P8,P3,P4,O1,O2,Fz,Cz,Pz,FCz |
| 参考/滤波 | 保留原始参考；官方描述未充分确认采集参考，不能称为 EEGMAT 的 linked-ear；除重采样的频域处理外不额外滤波、ICA、剔伪迹 |
| 异常策略 | 缺通道、无效单位、错误采样率、短记录、非有限值一律停止；不按测试表现改协议 |

原拟保持 EEGMAT 全部 20 通道，但在官方元数据阶段已发现该库不含 A1/A2，不能构造真实 A2−A1。因此在读信号前改为 19 个对应头皮通道加真实 FCz；T7/T8/P7/P8 对应旧命名 T3/T4/T5/T6。输出保留新任务真实通道名，不给 FCz 冒用耳电极名，不插入零通道。维数与既有 62 列通用特征 API 兼容，不宣称电极布局、参考或数据域完全相同。

旧/新命名对应关系另以 [EDF 官方标准文本](https://www.edfplus.info/specs/edftexts.html) 和 [DICOM 标准术语说明](https://dicom.nema.org/medical/dicom/current/output/chtml/part16/chapter_g.html) 核对；本地 MNE 1.9.0 `standard_1020` 的四对电极坐标也逐一相等。适配器按本任务明确通道清单选取，不调用隐式名称替换表。

替代方案包括仅用 19 通道（会改变既有张量接口）及合成第 20 通道（会引入非测量信息）；选择上述 20 个实测头皮通道是固定接口下更可审计的适配。该决定先于信号读取，并与未来技能差异的对照分开。

## 隔离、获取与可恢复性

唯一新原始数据目录是 `.local/research/2026-10-30-extension/eegmmidb/resources`；来自官方 HTTPS 的逐文件下载，最多 4 个并发，单文件上限 4 MiB、总 EDF 上限 288 MiB。允许使用已有 `http://127.0.0.1:10808` 代理，但不更改系统网络配置。只写带本任务标识的自有目录，不读取/移动/复制实验室已有共享数据。

在任何信号读取前落盘协议、人员清单、预期官方文件 SHA256 和来源快照。先仅以 S001 的 R01/R02 做技术探测，再准备全部固定名单。下载到 `.part` 后核验哈希，完成文件通过不覆盖的方式发布；已存在的原文件必须校验一致，错误文件不覆盖，失败的部分下载可恢复。

所有 NPZ 和逐记录来源信息置于 `eegmmidb/private_builder/prepared/`，含测试集文件；不放入 Actor 公共目录，不复制到服务器共享目录，不进 Git。脚本默认只准备 train/validation；显式 `--allow-test` 才能执行已授权的机械测试预处理。该预处理不拟合任何统计量、不选择模型、不汇报测试信号或表现统计。

## 后续评估解释边界

- 睁闭眼与固定的 R01/R02 顺序完全混淆，时序、疲劳或采集漂移不能从该子集单独排除。后续结论应称“跨受试者识别这两个基线记录条件”，不能称眼状态因果效果。
- 眼动/眨眼、肌电及 alpha 节律都可能提供线索；没有独立 EOG 或伪迹控制，不能把可预测性自动解释为期望的神经机制。
- 5 秒窗口同属一个人/记录且有时间相关性。划分按人，统计不把 864 个窗口当 864 个独立志愿者；后续置信区间按受试者聚类。
- 首 36 人是确定的便利子集，不是全库随机代表样本。测试仅 6 人，结论有限。
- 公开数据可能已见于基础模型预训练；此处“新任务”仅指本项目开发与蒸馏流程尚未见的新任务，不能保证预训练数据无重叠。
- 新数据集、标签、参考、采样率、通道替换同时发生域变化。若后续比较技能条件，两条件必须用同一封存适配和完全相同预算；数据域差异不能单独归因于技能。

## 结果与核验

2026-10-30 01:12 +08 完成全部获取和三个集合的机械预处理；01:14 前完成复核。**72/72 个官方 EDF 的 SHA256 均匹配，合计 91,846,752 字节（约 87.59 MiB），没有残留 `.part`。没有拟合分类器、探针或基础模型，没有执行模型推理，也没有计算/读取测试科学结果。**

协议封存日志时间为 `2026-10-29T17:05:29.395434+00:00`，文件清单封存为 `17:05:50.980703+00:00`；二者均早于第一个训练信号探测。协议 SHA256 为 `b9c5e836a6615400dc183438ae180f1da3f65cee53b4a64eafb7224b2e1c7cee`，72 文件清单 SHA256 为 `e74caec4551cb8c0c229e355ffdd33a9a79e0e1f845947eab47723344e1764cb`。运行事件仅记录路径、字节数、哈希和阶段，不含模型结果。

准备文件均在 `X:/projects/EEG-AI-Scientist/.local/research/2026-10-30-extension/eegmmidb/private_builder/prepared/`：

| 文件 | 形状 | 字节 | SHA256 |
|---|---|---:|---|
| train.npz | (576,20,5,200) | 38,977,283 | `97b1621912e279fbaac83b70aa38644c60b851d765fd21fd0289b178b6a1ffbe` |
| validation.npz | (144,20,5,200) | 9,737,949 | `2550d391bb048cf39f7821eb73405250bc04d45ceeea1fc01fb73289b4c8358f` |
| test.npz | (144,20,5,200) | 9,754,002 | `0d5597e23164f36f1863c2f69e031f401b98ab85a84748cd9eb08196998e64b7` |

核验证据：

1. S001 两个训练基线实际各 61 秒；按预先规则只取前 60 秒。原始所选通道均为 uV、160 Hz，FCz 在文件中写作 `Fcz.`，通过明确的大小写/尾点标准化映射选取。
2. 对 S001R01 前一秒的 20 通道，独立解析 EDF int16 数据并按头部校准转为微伏，与 MNE 读取值的最大绝对差为 `1.4210854715202004e-14 uV`。仅核对测量解码，未作条件效应分析。
3. 从训练 NPZ 仅取一个窗口调用冻结的 `compute_feature_panel`，得到有限的 `(1,62)` 输出；未报告特征值、排名、预测或分类性能。原 `real_data.py` SHA256 仍为 `57a3800d655e72f5fc0e2e82c43d35f5915bf61d0813e666bce391276b64e280`。
4. 新增安全/单位检查 6 项加既有数据层检查 9 项，共 **15 passed**；两项模型边界检查未运行。首次扩展命令遗漏 `framework` 导入路径，产生 11 项导入失败；修正测试命令后相关 15 项通过，无冻结模块修改，也没有把失败隐去。
5. 重复 `download` 与 `prepare --allow-test` 后，72 个原始 EDF 和 3 个 NPZ 的哈希与修改时间全部不变，证明已校验文件不会被覆盖。此复核没有重新读取测试 NPZ 的信号或做科学分析。
6. `git check-ignore` 确认原始 EDF 和私有 test.npz 被 `.local/` 规则忽略。没有创建 Actor 公共目录或把数据移至服务器。冻结数据模块无 Git diff。

本次适配脚本 SHA256 为 `c4ffdea65fcc43aa6878a04dc0494b167ce6d70c5fc9d1a25547f16d14a6fcdb`，原样快照保存在 `private_builder/preparation_adapter_snapshot.py`。本机环境为 Python 3.12.4、MNE 1.9.0、NumPy 1.26.4、SciPy 1.13.1；特征接口核验用 CPU PyTorch 2.7.1+cu118，线程上限 4，没有 GPU 作业。

私有证据包含 `PROTOCOL.lock.json`、`METADATA.lock.json`、`RECORDS.lock.json`、`ACQUIRED.json`、`TRAIN_PROBE.json`、`TRAIN_CALIBRATION_QA.json`、`FEATURE_INTERFACE_SMOKE.json`、`PREPARATION_REPORT.json`、`preparation_events.jsonl` 和每集合 JSON 来源记录。官方页面和许可证快照留在 `resources/`，不进入 Git。

## 复核和后续接口

在正式工作区执行以下命令；它们不拟合模型：

```powershell
python scripts/research/prepare_eegmmidb.py --phase verify
python scripts/research/prepare_eegmmidb.py --phase feature-smoke
python -c "import sys,pytest; sys.path.insert(0,'framework'); raise SystemExit(pytest.main(['scripts/research/test_prepare_eegmmidb.py','framework/tests/test_real_data.py','-q','-k','not ModelBoundaryTests']))"
```

若需要在同一自有任务目录恢复未完成下载，使用 `--phase download --proxy http://127.0.0.1:10808 --workers 4`；已验证文件仅重新校验。全新自有目录中的首次执行为 `--phase all --allow-test --proxy http://127.0.0.1:10808 --workers 4`，会先封存协议并执行 S001 训练探测。原文件校验失败会停下并保留现有文件，不自动替换。

**后续 Actor 实验尚未建立。** 当前 `real_public.py` 的来源校验和 `export_real_task.py` 的 run_id 明确绑定 EEGMAT 标识；不能直接把本任务 NPZ 交给该导出器。后续需建立独立版本的 EEGMMIDB 导出适配，按 S001… 原始人员和 R01/R02 标签验证来源后再匿名化；不伪装成 EEGMAT ID，不放宽 E05–E08 冻结校验，也不能把本次资源准备称为技能迁移成功。模型参考、评估协议、配对技能条件和最终一次性测试均属于之后的新任务。
