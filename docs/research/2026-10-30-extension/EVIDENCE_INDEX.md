# 证据与恢复索引

下列公开报告与私有原件分开。本轮新增发布内容不含原始EEG、模型权重、认证、私有gold、原始模型对话或逐参与者预测。此前远端的历史归档不在此绝对声明范围内；新增历史审计范围与保留的训练摘要见PUBLICATION_AUDIT.md。

| 结论 | 公共报告 | 权威原件 |
| --- | --- | --- |
| EEGMAT参考 | ../2026-10-29-brainpec-real/SCIENCE_RESULT.zh-CN.md | 本地`.local/research/2026-10-29-brainpec-real/private/reference-local/` |
| 透明/随机/预训练比较 | REPRESENTATION_BASELINES.zh-CN.md | 本地extension/baselines/ |
| 精确bootstrap | EXACT_BOOTSTRAP_SENSITIVITY.zh-CN.md | 本地extension/exact-bootstrap/final/ |
| EEGMMIDB参考/导出 | EEGMMIDB_REFERENCE.zh-CN.md | 本地extension/eegmmidb/private_builder/ |
| E01失败 | E01_NUMERICAL_DIAGNOSIS.md | ncc WORK/episodes/E01/ |
| E05原生与重放 | E05_SOURCE_REPLAY_AUDIT.zh-CN.md | ncc WORK/episodes/E05/、replays/E05/ |
| E06与一对比较 | E06_AND_PAIR_AUDIT.zh-CN.md | ncc WORK/episodes/E06/；本地extension/closeout/E06/AUDIT.json |
| 双流程节点 | INTEGRATION_ACCEPTANCE.md | 各episode的controller/runs/real-E*/events、audit、freeze、lock、STATE、FINAL_REPORT |
| 语义开发校准 | semantic-calibration/RESULTS.zh-CN.md | ncc WORK/builders/semantic-calibration-v1/CALIBRATION_RESULT.json与evidence/R85,R86 |
| 隔离/测试 | VERIFICATION_CHECKPOINT.md | ncc WORK/evidence/ISOLATION_REPORT.json、full-linux-tests-04/ |
| 火山云CPU | HUOSHANYUN_SETUP.zh-CN.md | 云本人工作根/evidence/acceptance.json及来源/资源绑定 |

WORK与本地extension的完整根路径见[PATH_MAP](PATH_MAP.md)。不能把控制器/凭据目录当作普通可迁移证据包。

## 本次增量私有备份

服务器源：`WORK/closeout/20261030/`；Windows副本：`X:/projects/EEG-AI-Scientist/.local/research/2026-10-30-extension/closeout/backup/`。

- `evidence.tar.gz`：427个文件、压缩后11,457,327字节。
- archive SHA256：`c3a5b330d5f776cecac5fdb99ab2e17de6cd690305d6c9012887394223b2e7a3`。
- `EVIDENCE_MANIFEST.json` SHA256：`13b742675a5271beda0ef2c808a5e9fcfd82c172378c6b4b7ad57a4e58db7571`。
- `ARCHIVE_RECEIPT.json`证明源文件在打包前后哈希一致、每个tar成员一致；`LOCAL_VERIFICATION.json`证明接收后整包、manifest及427个成员全部一致。
- 明确排除controls/control、auth、home、公共挂载重复副本、符号链接和运行锁。原始数据与模型资源按既有私有位置保留，没把全工作目录打包。

复制只打开源文件读取，未搬移/删除源。网络失败可能产生不完整目标，完整哈希未通过前不采纳副本；不会据网络传输成功与否修改源文件。当前两端归档已核验，原权威路径继续保留。

这是09:51附近的快照；其中BUDGET包含当时进行中的两个closeout审查。其终态、进程快照和最终同步另存收尾收据，不回写已封存归档。旧夜646文件归档继续保留，未重打包或覆盖。

## 关键身份

| 对象 | SHA256 |
| --- | --- |
| comparison-v2 seal | 113a6a3d719c4c734ec670c9943d174e1ee8a45ff791def1137620434fa36278 |
| M15 skill | 54d5ce036ebb184bc653060196bed701807bb516b63dfc40d892d9938079191d |
| EEGMAT参考结果 | 57921432aa9ddbfc4252f0a97148bb957b786e88ac2bf6d767550ee32819fd18 |
| EEGMMIDB参考结果 | 0b7e87a2af5d776c2a1d94333bb37a84b243f96564d7985d471a417f5370e51d |
| 云CPU验收 | f13a0c666276707468de698a57642020a2fd628a93e9b9fcf325ce87fb3c468d |

可公开的摘要收据为`semantic-calibration/RESULT_SUMMARY.json`、`CURRENT_RESOURCE_STATUS.json`、`SYNC_RECEIPT.json`与`PROCESS_AUDIT.md`。摘要不代替原始身份绑定；复查时以对应私有原件和固定SHA为准。
