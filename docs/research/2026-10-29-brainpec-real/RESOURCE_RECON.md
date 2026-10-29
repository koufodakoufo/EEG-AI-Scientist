# BrainPEC 真实资源核查（R01，Builder 专用）

核查日期：2026-10-29。工作范围：官方公开代码、资源元数据及旧轮次私有源码快照；未下载 EEG/权重 payload，未运行模型、读取当前测试数据或连接服务器。本报告不能作为 Actor 题面或可读参考。**建议主流程采用“官方预训练 CBraMod + EEGMAT + 本项目新任务头”适配路线**，前提是根代理的已有资源检查没有找到训练身份完整的匹配下游权重。

## 1. 资源路线与确证范围

| 优先级 | 核查结论 | 下一步 |
| --- | --- | --- |
| CBraMod × Mumtaz | BrainPEC 给出结构和本地 checkpoint 路径，但已核查的 README、Git tree、release API 未提供下游权重文件或下载地址；release API 为 `[]` | 仅当本地已有权重且能核对监督训练被试、头、划分、哈希时使用；公开源码存在不等于模型已取得 |
| CBraMod × MentalArithmetic/Stress | 同样仅找到任务结构和本地权重路径；未找到公开下游权重 | 不将预训练 backbone 当作已训练的 Stress 分类器 |
| 预训练 CBraMod + EEGMAT | 官方仓库直接指向公开 HF 权重；数据无需登录、版本固定且体积小；CPU backbone 代码可独立导入 | 在训练被试上拟合新头，冻结后研究；名称必须说明是本项目适配分析，不声称复现 BrainPEC 任务模型 |

这是一轮限定范围检索的结论，不证明互联网或作者私有空间中绝无下游 checkpoint。本工作者没有扫描用户/实验室存储。Mumtaz 官方作者数据条目 [Figshare v2](https://figshare.com/articles/dataset/EEG_Data_New/4244171) 元数据为 CC BY 4.0、193 个文件、903,228,416 bytes；这里只取公开元数据，不建议扩大本轮限定 EEGMAT 下载例外。

固定代码：

- BrainPEC：`982b1df393a846e6418cee715bdfaa57d041cee3`，现场 master API 与旧快照一致。[源码](https://github.com/Kian-Chen/BrainPEC/tree/982b1df393a846e6418cee715bdfaa57d041cee3)
- CBraMod：`b9e961003214326972c567eff390e75b0287e32a`，现场 main API 返回值。[源码](https://github.com/wjq-learning/CBraMod/tree/b9e961003214326972c567eff390e75b0287e32a)
- 两个代码仓库均 MIT；checkpoint 的 HF 模型卡另标 Apache-2.0，不能把代码许可证直接代替权重许可。[CBraMod LICENSE](https://github.com/wjq-learning/CBraMod/blob/b9e961003214326972c567eff390e75b0287e32a/LICENSE)、[HF 模型卡](https://huggingface.co/weighting666/CBraMod)

## 2. 官方预训练 checkpoint：可以立即取得

官方来源链为 [CBraMod 权重目录 README](https://github.com/wjq-learning/CBraMod/blob/b9e961003214326972c567eff390e75b0287e32a/pretrained_weights/README.md) → `weighting666/CBraMod`，没有使用第三方镜像。

| 项目 | 现场核对值 |
| --- | --- |
| HF revision | `500543c7e30bda1b22bfd51a49301b238dee21fd` |
| 文件 | `pretrained_weights.pth` |
| 身份 | 预训练 CBraMod state dict；不含 Mumtaz/Stress 训练完成的输出头 |
| 大小 | **19,775,842 bytes**，HF API 与匿名 HEAD Content-Length 一致 |
| SHA256 | `0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178`，来自 HF LFS 元数据，尚未对本地 payload 实算 |
| 访问 | HF API `private=false, gated=false, disabled=false`；固定 resolve URL 匿名 HEAD 最终 HTTP 200 |
| 许可 | 模型卡声明 `apache-2.0`；HF 文件树无单独 LICENSE 文本，须保留模型卡和来源链 |

授权获取者可在**自己的新缓存目录**执行以下命令；R01 未执行：

```bash
curl --fail --location --retry 2 --max-time 300 \
  'https://huggingface.co/weighting666/CBraMod/resolve/500543c7e30bda1b22bfd51a49301b238dee21fd/pretrained_weights.pth' \
  --output pretrained_weights.pth
echo '0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178  pretrained_weights.pth' | sha256sum --check
```

不要用下载 CDN 的 `ETag` 代替以上 LFS SHA256；本次 HEAD 的最终 ETag 与 LFS SHA256 不同。下载、哈希、`strict=True` 加载成功和实际前向成功必须各自留证；本报告只完成资源身份与访问检查。

## 3. EEGMAT 身份、标签、输入与未决项

版本为 [PhysioNet EEGMAT 1.0.0](https://physionet.org/content/eegmat/1.0.0/)，DOI `10.13026/C2JQ1P`，页面标注未压缩 175.1 MB；[许可](https://physionet.org/content/eegmat/view-license/1.0.0/)为 Open Data Commons Attribution v1.0。保留数据名、来源/许可链接及原数据论文引用；公开产物应有 attribution。

- 公开 `RECORDS` 恰有 72 个 EDF 条目：`Subject00_1.edf` 到 `Subject35_2.edf`，36 个 participant，各有两个条件。`_1` 为任务前背景、`_2` 为心算。官方 CBraMod 标签是 `int(file[-5])-1`，即 0/1 条件标签。
- `subject-info.csv` 的 Count quality 是另一种被试层面标签（差/好计数），不可替代上述条件标签。本工作者未读取该 CSV 个体行。
- 规范 participant 应从文件名取 `SubjectNN`；窗口 ID 可为 `SubjectNN_condition-window`。BrainPEC `task_registry.subject_id('stress', id)` 只去掉 `-window`，仍留下 `_1/_2`，实际返回 recording ID；不能用于证明跨条件 participant 不相交。
- 官方 CBraMod 预处理按排序文件的前 56 / 后 8 / 后 8 划分；仅在目录严格包含这 72 个成对 EDF 时，对应 participant 00–27 / 28–31 / 32–35。代码没有过滤额外非 EDF 文件。本项目应先核对完整文件清单，再明确冻结被试划分，不能盲从目录位置。

官方 Stress 预处理实际顺序如下（[代码](https://github.com/wjq-learning/CBraMod/blob/b9e961003214326972c567eff390e75b0287e32a/preprocessing/preprocessing_stress.py)、[loader](https://github.com/wjq-learning/CBraMod/blob/b9e961003214326972c567eff390e75b0287e32a/datasets/stress_dataset.py)）：

```text
选取并重排以下 20 通道 → raw.resample(200)
→ raw.get_data(units='uV') → 截去不足 5 秒尾部
→ 非重叠窗口 (N,20,5,200) → loader /100 → float32 模型输入

EEG Fp1, EEG Fp2, EEG F3, EEG F4, EEG F7, EEG F8,
EEG T3, EEG T4, EEG C3, EEG C4, EEG T5, EEG T6,
EEG P3, EEG P4, EEG O1, EEG O2, EEG Fz, EEG Cz, EEG Pz, EEG A2-A1
```

20 通道包含 19 个头皮位置和 A2-A1 导联；不要写成“20 个头皮 EEG 通道”。上游不重新参考、不补缺通道、不做额外显式 bandpass/notch。MNE 默认返回 SI 单位；应显式取 `units='uV'` 后只除以 100 一次，否则有百万倍单位错误风险。[MNE 单位文档](https://mne.tools/stable/generated/mne.io.Raw.html#mne.io.Raw.get_data)

**待获取者核查 EDF header，不能由本报告替代：**原始采样率、物理单位/标定、每文件 channel names、实际时长、prefilter 字段和缺失/恒定导联。常见“原始 500 Hz”尚未在本次可访问的原始官方文字中独立确认，所以不作为已验证事实填写 manifest。PhysioNet 页面声称全部记录 60 秒，但文件清单大小明显不一致，不能据此假定窗口数一致。页面/README 对 30 Hz 使用了 “high-pass” 表述；其真实含义尚不能可靠判断。BrainPEC registry 的 Stress `lowpass_hz=75` 也不是实际滤波证据。尤其 gamma/PAC 解释必须保留这项不确定性，不根据测试结果补选滤波参数。

获取建议：从 [官方 ZIP 入口](https://physionet.org/content/eegmat/get-zip/1.0.0/)获取固定版本，或由官方 `RECORDS` 产生 **72 个明确 URL 的有限列表**，逐文件下载并用 [SHA256SUMS.txt](https://physionet.org/files/eegmat/1.0.0/SHA256SUMS.txt)校验。直接文件模板为 `https://physionet.org/files/eegmat/1.0.0/SubjectNN_C.edf`。不推荐无上限递归。数据页提供的 `physionet download eegmat --version 1.0.0` 也可使用，但不要为了下载重新安装一个不必要的工具。此次 Web ZIP 检查只返回到官方 S3 地址的不可访问错误，没有取得 ZIP；原始 EDF 下载速度/稳定性尚未测试。

## 4. CPU 路线与模型结构

[BrainPEC inference/run.py](https://github.com/Kian-Chen/BrainPEC/blob/982b1df393a846e6418cee715bdfaa57d041cee3/inference/run.py) 与 `factor_atlas.main()` 都明确拒绝 CPU；不存在可以直接执行的 `--device cpu` 官方分析路线。[CBraMod quick_example](https://github.com/wjq-learning/CBraMod/blob/b9e961003214326972c567eff390e75b0287e32a/quick_example.py) 则显式支持 CPU 设备。骨干只需 `torch` 与两个源文件 `models/cbramod.py`、`models/criss_cross_transformer.py`；完整下游示例另需 `einops`，EDF 处理需 MNE/NumPy，特征适配需 PyTorch/NumPy，完整官方特征函数还导入 SciPy。仓库 requirements 没有版本钉死，须登记实际环境版本。

默认骨干：`in_dim=out_dim=d_model=200, dim_feedforward=800, n_layer=12, nhead=8, seq_len=30`；实际输入为 `(batch,channels,patches,200)`，200 是每秒 patch 点数，EEGMAT 5 秒窗口用 5 patches。先按完整默认骨干严格加载 checkpoint，再将 `proj_out` 替换成 `nn.Identity()`；不要先替换导致 `proj_out.*` 键不匹配，再用 `strict=False` 掩盖。

```python
import torch
from models.cbramod import CBraMod

torch.set_num_threads(4)
model = CBraMod().cpu()
state = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
model.load_state_dict(state, strict=True)
model.proj_out = torch.nn.Identity()
model.requires_grad_(False).eval()
# 下一步只对已获准训练样本做 batch=1 计时和输出/内存检查。
```

以上是待执行适配入口示意，未声称已跑通。不要直接执行 `models/cbramod.py` 的 `__main__`，该演示还有硬编码 `.cuda()`；Transformer 文件自身演示也用 CUDA。需要在导入入口中明确 CPU、float32、线程数、推理模式，实测后再扩量。

官方任务模型的头并非线性头：Mumtaz 是 flatten `19×5×200 → Linear(200) → ELU → Dropout(0.1) → Linear(1)`；Stress 是 `20×5×200`、dropout 0.2，其余同型。[Mumtaz 结构](https://github.com/Kian-Chen/BrainPEC/blob/982b1df393a846e6418cee715bdfaa57d041cee3/inference/models/mumtaz.py)、[Stress 结构](https://github.com/Kian-Chen/BrainPEC/blob/982b1df393a846e6418cee715bdfaa57d041cee3/inference/models/stress.py)。本项目若改用池化表征+小型线性头，须登记这是新模型定义及新训练协议。

## 5. 官方 12 项小面板逐项核对

来自固定版本 [factor_atlas.py](https://github.com/Kian-Chen/BrainPEC/blob/982b1df393a846e6418cee715bdfaa57d041cee3/src/brainpec/experiments/factor_atlas.py) 的 `FACTOR_SPECS`，静态计数为 63，以下全部 ID 存在且按各家族前两项选择。前十项每项 **6 维**，后两项各 1 维，合计 **62 列目标**；不是 12 个标量。每通道特征的聚合顺序为 mean、population std、PyTorch median、q25、q75、max。

| ID | 实现定义/边界 |
| --- | --- |
| `T001_hjorth_activity` | 每通道 population variance；EPS 下限 |
| `T002_hjorth_mobility` | `sqrt(var(diff(x))/var(x))`；差分未乘采样率 |
| `F001_delta_log_power` | `[0.5,4)` Hz 的 `abs(rfft(x))²` 频点和再取自然对数；不是 Welch PSD |
| `F002_theta_log_power` | `[4,8)` Hz，同上；未做 FFT 长度/频宽归一化 |
| `TF001_wavelet_entropy` | 5 级 Haar detail 与最终 approximation 的平均平方能量，共 6 项归一化熵 `/log(6)` |
| `TF002_wavelet_detail_var_l1` | 第 1 级 Haar detail population variance；奇数长度尾点丢弃 |
| `C001_permutation_entropy` | 3 个连续采样点、6 种排序的归一化 Shannon entropy；并列值按实现分支处理 |
| `C002_sample_entropy` | **代理量，不是标准 SampEn**：`r=.2*std(x)`，`log1p(mean(abs(diff²(x)))/r)-log1p(mean(abs(diff(x)))/r)`，含下限截断 |
| `X001_pac_delta_beta` | FFT 矩形频带、解析信号，delta 相位对 beta `[13,30)` 振幅；18 相位 bin 的 Tort MI |
| `X002_pac_theta_gamma` | theta 相位对 gamma 振幅，同上；代码 gamma 上限 `min(45,task.lowpass,Nyquist-.25)` |
| `R001_corr_abs_mean` | 标准化通道相关矩阵上三角、不含对角的绝对值均值 |
| `R002_corr_abs_std` | 同一绝对相关集合的 population std |

实现注意：统一 `EPS=1e-12`，`agg_ch` 将 NaN/Inf 替换为零，相关标准差最小截到 `1e-6`；这些补救不证明特征有定义。须在替换前独立记录非有限值、零方差/缺通道，并在看结果前确定 invalid/replacement 规则。短窗 delta/PAC 估计及 gamma 可用性需保守解释。

官方 `--factor-shard-index/count` 只筛选 erasure 遍历；`compute_factor_arrays` 仍计算全部 63 个，未提供真正的 12 项计算白名单。小面板适配应保留精确定义并只计算所需依赖。特征输入源于 loader 后的 `uV/100` 张量，因此 activity 和频带 power 的量纲不能写成直接 `uV²`；若本项目改从原始微伏求特征，应显式登记单位/尺度差异。

官方逐层 cache 将 `(B,C,S,D)` 在通道和 patch 两轴求均值，保存每层 `(B,200)`；可支持 Q1 探测，但不足以重新构造完整激活并继续原头前向。Q2 必须在完整模型/层激活上实施干预，不能仅以池化缓存上的变换冒充原模型干预。

## 6. 科学限制与交接边界

采用备选路线的研究对象是新配置的冻结预训练骨干与训练集拟合头；所有头训练、标准化、探测拟合和干预估计只用训练被试，验证负责选择，测试由可信执行层封存。另行登记预训练语料身份和潜在暴露；不能仅因为新头没有见过测试被试，就把骨干预训练独立性当作已证明。窗口数不是独立样本数，需按 participant 进行不确定性处理。条件分类不能直接解释为临床压力诊断，表征干预也不能解释为脑生理因果。

本轮取到的是代码、metadata、许可证文字和公开文件清单。严格加载、文件实际 hash、EDF header、CPU 吞吐与内存、真实训练/验证 batch 成功都仍待执行者验证；不将这些待办写成资源实跑已通过。

审计说明：最初宽范围 README 读取意外返回了已发表的汇总/推理数值，随后相关代码默认 checkpoint 文件名也含性能数值。本工作者已通知根代理，未用这些数值挑选数据、特征、层或协议，也未在本报告重述。无当前任务最终测试数据/结果暴露。资源选择依据仅为任务书既定顺序、可访问性、尺寸和代码接口。

公开文本证据快照和逐文件 URL/SHA256 清单保存在 `.local/research/2026-10-29-brainpec-real/resource-recon/SOURCE_INDEX.json`（29 项，约 0.59 MB；不含数据或 checkpoint payload）。本报告和源码快照均应留在 Builder/Reference 一侧；不得整体挂载给 Actor。
