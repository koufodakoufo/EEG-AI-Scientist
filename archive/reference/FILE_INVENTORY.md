# 文件（结构）清单

生成时间：2026-10-21 12:57:08（Asia/Shanghai）

## 范围与读法

- 项目物理文件总数：**9028**；总大小约 **288.28 MB**。
- 其中项目/人工产物：**869** 个，本文逐个列出。
- 工具/依赖/版本控制内部文件：**8159** 个，本文按目录汇总；逐文件信息在 `FILE_INVENTORY.csv`。
- `FILE_INVENTORY.csv` 覆盖全部物理文件（包括 `.venv`、`.git`、缓存），每行有一句话 role；
  这是“每一个文件”的机器可读台账。
- `FILE_TREE.txt` 是项目/人工产物的完整路径树；本文顶部是同一棵树的目录视图。
- 创建时间来自 Windows `st_ctime`；复制/解压/安装时间可能与原始创作时间不同。
- 凭据文件的**内容没有读取或打印**；清单只记录路径、大小和时间。

## 顶层结构（项目/人工产物）

```text
EEG-AI-Scientist/
├── .gitignore
├── .python-version
├── .venv_sync.log
├── .venv_sync2.log
├── .venv_sync3.log
├── .vscode
│   └── settings.json
├── DECISIONS.md
├── EEG_AI_Scientist_Overnight_Plan.md
├── ENVIRONMENT.md
├── FREEZE_MANIFEST.json
├── NEXT_ACTION.md
├── PROGRESS.md
├── artifacts
│   ├── review_bundle.zip
│   ├── review_bundle_20261020.zip
│   └── review_bundle_emotion_20261021.zip
├── configs
│   ├── dev_episode.json
│   ├── eval
│   │   └── emotion_rubric_v1.json
│   ├── materials
│   │   └── emotion_state_trait_v1.json
│   ├── models
│   │   ├── backends_20261021.json
│   │   └── deepseek_flash.json
│   ├── overnight.json
│   ├── prompts
│   │   └── emotion_research_system.md
│   ├── rules
│   │   └── emotion_baseline_v1.md
│   ├── studies
│   │   ├── flash_emotion_20261021.json
│   │   └── overnight_flash_20261020.json
│   └── versions
│       └── next_round_20261021.json
├── credentials
│   ├── claude.env
│   ├── deepseek.env
│   └── gemini.txt
├── data
│   └── private
│       ├── README.md
│       └── case_specs.json
├── docs
│   └── plans
│       └── EEG_AI_Scientist_Overnight_Run_v2.md
├── memory
│   ├── research_methods
│   │   └── rules.json
│   └── scientific_knowledge
│       └── dev_facts.md
├── prompts
│   ├── DIAGNOSTIC_v2.md
│   ├── S0.md
│   └── S1.md
├── pyproject.toml
├── ref
│   └── wechat_group
│       ├── AutoScientists.pdf
│       ├── EEG_AI_Scientist_RSI_Idea.md
│       ├── NeuroWeaver.pdf
│       └── Weco-AIDE2.pdf
├── reports
│   ├── CALIBRATION.md
│   ├── CORE_CODE_WALKTHROUGH.md
│   ├── FAILURE_CASES.md
│   ├── MORNING_REPORT.md
│   ├── OVERNIGHT_RUN.log
│   ├── PREFLIGHT.md
│   ├── REPRODUCE.md
│   ├── RESULTS_TABLE.md
│   ├── flash_20261020_0058
│   │   ├── CAPABILITY_CHECK.md
│   │   ├── CODE_READING_GUIDE.md
│   │   ├── COVERAGE_RECHECK.md
│   │   ├── DATA_REQUIREMENTS.md
│   │   ├── EVIDENCE_AUDIT.md
│   │   ├── EXPERIMENT_PROTOCOL.md
│   │   ├── HANDOFF_SYSTEM.md
│   │   ├── HYPOTHESIS_CARDS.md
│   │   ├── IMPLEMENTATION_MAP.md
│   │   ├── LITERATURE_MAP.md
│   │   ├── METHOD_LESSONS_PROPOSED.md
│   │   ├── MORNING_REPORT.md
│   │   ├── PRECHECK.md
│   │   ├── REASONING_REVIEW.md
│   │   ├── RESULTS.md
│   │   ├── RESUME_CHECK.md
│   │   ├── RUN_INDEX.md
│   │   └── coverage_union.json
│   ├── flash_emotion_20261021
│   │   ├── HANDOFF_NEXT_ROUND.md
│   │   ├── MANUAL_INITIAL_REVIEW.md
│   │   ├── MINIMAL_EMOTION_STUDY.md
│   │   ├── PROPOSAL_CORRECTIONS.md
│   │   ├── RESULT_SUMMARY.md
│   │   └── RUN_INDEX.md
│   ├── report_data.json
│   ├── test_output.txt
│   └── test_summary.json
├── review_only
│   ├── DIAGNOSTIC_MAP.json
│   ├── PRIVATE_CASE_SPECS.json
│   └── README.md
├── runs
│   ├── dev_e1
│   │   ├── case_001_s0
│   │   │   ├── cache
│   │   │   │   ├── 37896c32123cd7dc35dbc0342dd61dbbf195a22b5723620f24ab2492601b0841.json
│   │   │   │   ├── 801b4bf85b96f5aa49c375fd1896a9258afafc615d80182dba4bcccb2bf730d1.json
│   │   │   │   ├── 92a241dd6850ab010f957a8f623b277d8270a6e8f566282344d6407a8b39f718.json
│   │   │   │   ├── d5e85207357d87083c00b94e43a92f6f41e51e4c4db6eaed651bd7ee9b8418ed.json
│   │   │   │   └── fbea462f6e3fe17d5af3bb11669d66f58fa2f0bed0297fefc492fb3993bc4574.json
│   │   │   ├── config_snapshot.json
│   │   │   ├── events.jsonl
│   │   │   ├── final.json
│   │   │   ├── history.json
│   │   │   ├── prediction_004.json
│   │   │   ├── prediction_009.json
│   │   │   ├── prediction_014.json
│   │   │   ├── public_input.json
│   │   │   ├── request_001.json
│   │   │   ├── request_002.json
│   │   │   ├── request_003.json
│   │   │   ├── request_004.json
│   │   │   ├── request_005.json
│   │   │   ├── response_001.json
│   │   │   ├── response_002.json
│   │   │   ├── response_003.json
│   │   │   ├── response_004.json
│   │   │   ├── response_005.json
│   │   │   ├── result_001.json
│   │   │   ├── result_002.json
│   │   │   ├── result_003.json
│   │   │   ├── score_001.json
│   │   │   ├── score_002.json
│   │   │   ├── score_003.json
│   │   │   ├── state.json
│   │   │   └── summary.md
│   │   ├── case_001_s0_attempt1_failed
│   │   │   ├── cache
│   │   │   │   ├── 646418747b83813e47c2e487b00e7c196ebccc1c2d88ef7ef1e35e731a805eeb.json
│   │   │   │   ├── bc64f502d602d258986b4135050451ca80887bac74d5432948dfcdabb0a14e6e.json
│   │   │   │   ├── d77dad3d9611cc5a6e85c380c76ed3aa761a4058c5305df9820980bc0ca32d65.json
│   │   │   │   ├── efde9ffb6ba3db1b3d3cd1a87137f4c4a5b78f7097a0622bac049cfbbdf44163.json
│   │   │   │   └── fdb80f321b7f8be9cd018823bd8accdf1cd66138aa2a256eb9b49d36d80ee024.json
│   │   │   ├── config_snapshot.json
│   │   │   ├── events.jsonl
│   │   │   ├── history.json
│   │   │   ├── prediction_004.json
│   │   │   ├── prediction_009.json
│   │   │   ├── prediction_016.json
│   │   │   ├── public_input.json
│   │   │   ├── request_001.json
│   │   │   ├── request_002.json
│   │   │   ├── request_003.json
│   │   │   ├── request_004.json
│   │   │   ├── request_005.json
│   │   │   ├── response_001.json
│   │   │   ├── response_002.json
│   │   │   ├── response_003.json
│   │   │   ├── response_004.json
│   │   │   ├── response_005.json
│   │   │   ├── result_001.json
│   │   │   ├── result_002.json
│   │   │   ├── result_004.json
│   │   │   ├── score_001.json
│   │   │   ├── score_002.json
│   │   │   ├── score_004.json
│   │   │   ├── state.json
│   │   │   └── summary.md
│   │   ├── case_001_s0_attempt2_failed
│   │   │   ├── cache
│   │   │   │   ├── 0704f0fbb2ba41198b9fff6c574842f2fa658acba1fe24fb4e5410af1dae0e1e.json
│   │   │   │   ├── e5da944c458540fba491ddbafaf671f6b0e92a6d3d412fcc856e378f0fec3787.json
│   │   │   │   └── e8b220660e77c4a007af1ae1fdee0b14e62b418488cf62764f5dd60bdbd83662.json
│   │   │   ├── config_snapshot.json
│   │   │   ├── events.jsonl
│   │   │   ├── history.json
│   │   │   ├── prediction_004.json
│   │   │   ├── public_input.json
│   │   │   ├── request_001.json
│   │   │   ├── request_002.json
│   │   │   ├── request_003.json
│   │   │   ├── response_001.json
│   │   │   ├── response_002.json
│   │   │   ├── response_003.json
│   │   │   ├── result_001.json
│   │   │   ├── score_001.json
│   │   │   ├── state.json
│   │   │   └── summary.md
│   │   └── case_001_s0_attempt3_failed
│   │       ├── cache
│   │       │   ├── 6543b0ad7716e4858c9911b219bb83e53b4f3c360c50f6bb3207b0431640362c.json
│   │       │   └── fbea462f6e3fe17d5af3bb11669d66f58fa2f0bed0297fefc492fb3993bc4574.json
│   │       ├── config_snapshot.json
│   │       ├── events.jsonl
│   │       ├── public_input.json
│   │       ├── request_001.json
│   │       ├── request_002.json
│   │       ├── response_001.json
│   │       ├── response_002.json
│   │       ├── state.json
│   │       └── summary.md
│   ├── flash_20261020_0058
│   │   ├── audit_contexts.txt
│   │   ├── audit_contexts2.txt
│   │   ├── budget.json
│   │   ├── capability
│   │   │   ├── CAPABILITY_CHECK.md
│   │   │   ├── capability.json
│   │   │   ├── evidence
│   │   │   │   ├── index.json
│   │   │   │   ├── injections.jsonl
│   │   │   │   └── sources
│   │   │   │       └── ev_056fb3068eea.json
│   │   │   ├── fetch.json
│   │   │   ├── search.json
│   │   │   └── tool_cycle.json
│   │   ├── capability_stdout.txt
│   │   ├── capability_stdout_2.txt
│   │   ├── claim_contexts.txt
│   │   ├── diagnose_stdout.txt
│   │   ├── diagnostics
│   │   │   ├── cases
│   │   │   │   ├── PRIVATE_MAPPING.json
│   │   │   │   ├── case_a72e
│   │   │   │   │   ├── cache
│   │   │   │   │   │   ├── 29769ed100add937dc25a448cd65e0f61805f5cad992f9891b0762a61f13d54c.json
│   │   │   │   │   │   ├── 75976f72e0531afaa6ca9a4a782a6c648bc7b543f5d93cf95464ba34387ffab1.json
│   │   │   │   │   │   └── ae87f1b70a84f5b9cad2d6681d8fe8437a34ad0ebecf3ea0c93fcac1ae71c1f2.json
│   │   │   │   │   ├── config_snapshot.json
│   │   │   │   │   ├── events.jsonl
│   │   │   │   │   ├── final.json
│   │   │   │   │   ├── history.json
│   │   │   │   │   ├── prediction_004.json
│   │   │   │   │   ├── prediction_009.json
│   │   │   │   │   ├── public_input.json
│   │   │   │   │   ├── request_001.json
│   │   │   │   │   ├── request_002.json
│   │   │   │   │   ├── request_003.json
│   │   │   │   │   ├── response_001.json
│   │   │   │   │   ├── response_002.json
│   │   │   │   │   ├── response_003.json
│   │   │   │   │   ├── result_001.json
│   │   │   │   │   ├── result_002.json
│   │   │   │   │   ├── score_001.json
│   │   │   │   │   ├── score_002.json
│   │   │   │   │   ├── state.json
│   │   │   │   │   └── summary.md
│   │   │   │   ├── case_c41a
│   │   │   │   │   ├── cache
│   │   │   │   │   │   ├── 6bbf17ecb12bc42a5ab5e6ec5d1abed9aaa2db60ace256318fba42ad505a259b.json
│   │   │   │   │   │   ├── 6e44672758872fc784ea911fb4962f49d75a9b7458fd38fedcf3911267fbc871.json
│   │   │   │   │   │   ├── 80d8590e90abead8fa571e0df4e7642ebdd2ab40e3ad6e6411077e54152dce29.json
│   │   │   │   │   │   └── a570fb252d6b72684de6c2c498b867c477e4e8dcc3241d05b6bea94cf5fb2462.json
│   │   │   │   │   ├── config_snapshot.json
│   │   │   │   │   ├── events.jsonl
│   │   │   │   │   ├── final.json
│   │   │   │   │   ├── history.json
│   │   │   │   │   ├── prediction_004.json
│   │   │   │   │   ├── prediction_009.json
│   │   │   │   │   ├── prediction_014.json
│   │   │   │   │   ├── public_input.json
│   │   │   │   │   ├── request_001.json
│   │   │   │   │   ├── request_002.json
│   │   │   │   │   ├── request_003.json
│   │   │   │   │   ├── request_004.json
│   │   │   │   │   ├── response_001.json
│   │   │   │   │   ├── response_002.json
│   │   │   │   │   ├── response_003.json
│   │   │   │   │   ├── response_004.json
│   │   │   │   │   ├── result_001.json
│   │   │   │   │   ├── result_002.json
│   │   │   │   │   ├── result_003.json
│   │   │   │   │   ├── score_001.json
│   │   │   │   │   ├── score_002.json
│   │   │   │   │   ├── score_003.json
│   │   │   │   │   ├── state.json
│   │   │   │   │   └── summary.md
│   │   │   │   ├── case_specs_neutral.json
│   │   │   │   └── diagnostic_summary.json
│   │   │   ├── diagnose_summary.json
│   │   │   └── regression
│   │   │       ├── regression.json
│   │   │       ├── regression_answer.md
│   │   │       ├── regression_prompt.md
│   │   │       └── regression_review.md
│   │   ├── fallahi_contexts.txt
│   │   ├── fixture
│   │   │   └── artificial.csv
│   │   ├── fixture_check.txt
│   │   ├── report_stdout.txt
│   │   ├── research
│   │   │   └── literature_v1
│   │   │       ├── events.jsonl
│   │   │       ├── evidence
│   │   │       │   ├── index.json
│   │   │       │   ├── injections.jsonl
│   │   │       │   └── sources
│   │   │       │       ├── ev_200bb34828cd.json
│   │   │       │       ├── ev_200bb34828cd.md
│   │   │       │       ├── ev_2085e5b7ba26.json
│   │   │       │       ├── ev_2085e5b7ba26.md
│   │   │       │       ├── ev_2f5e3fadf9f0.json
│   │   │       │       ├── ev_2f5e3fadf9f0.md
│   │   │       │       ├── ev_825214c78a59.json
│   │   │       │       ├── ev_825214c78a59.md
│   │   │       │       ├── ev_8d41144afed7.json
│   │   │       │       ├── ev_8d41144afed7.md
│   │   │       │       ├── ev_9da221287269.json
│   │   │       │       ├── ev_9da221287269.md
│   │   │       │       ├── ev_a2ba747cdafd.json
│   │   │       │       ├── ev_a2ba747cdafd.md
│   │   │       │       ├── ev_a4cfb55eee84.json
│   │   │       │       ├── ev_a4cfb55eee84.md
│   │   │       │       ├── ev_b63c716fd707.json
│   │   │       │       ├── ev_b63c716fd707.md
│   │   │       │       ├── ev_f42fa7111e36.json
│   │   │       │       └── ev_f42fa7111e36.md
│   │   │       ├── experiments
│   │   │       │   ├── artificial_fixture.csv
│   │   │       │   └── fixture_split_check.json
│   │   │       ├── final.json
│   │   │       ├── final_answer.md
│   │   │       ├── heartbeat.json
│   │   │       ├── launch.txt
│   │   │       ├── messages.json
│   │   │       ├── pid.txt
│   │   │       ├── requests
│   │   │       │   ├── request_001.json
│   │   │       │   ├── request_002.json
│   │   │       │   ├── request_003.json
│   │   │       │   ├── request_004.json
│   │   │       │   ├── request_005.json
│   │   │       │   ├── request_006.json
│   │   │       │   ├── request_007.json
│   │   │       │   ├── request_008.json
│   │   │       │   ├── request_009.json
│   │   │       │   ├── request_010.json
│   │   │       │   ├── request_011.json
│   │   │       │   ├── request_012.json
│   │   │       │   ├── request_013.json
│   │   │       │   ├── request_014.json
│   │   │       │   ├── request_015.json
│   │   │       │   └── request_016.json
│   │   │       ├── responses
│   │   │       │   ├── response_001.json
│   │   │       │   ├── response_002.json
│   │   │       │   ├── response_003.json
│   │   │       │   ├── response_004.json
│   │   │       │   ├── response_005.json
│   │   │       │   ├── response_006.json
│   │   │       │   ├── response_007.json
│   │   │       │   ├── response_008.json
│   │   │       │   ├── response_009.json
│   │   │       │   ├── response_010.json
│   │   │       │   ├── response_011.json
│   │   │       │   ├── response_012.json
│   │   │       │   ├── response_013.json
│   │   │       │   ├── response_014.json
│   │   │       │   ├── response_015.json
│   │   │       │   └── response_016.json
│   │   │       ├── scientist_input.md
│   │   │       ├── searches
│   │   │       │   ├── search_001.json
│   │   │       │   ├── search_002.json
│   │   │       │   ├── search_003.json
│   │   │       │   ├── search_004.json
│   │   │       │   ├── search_005.json
│   │   │       │   ├── search_006.json
│   │   │       │   ├── search_007.json
│   │   │       │   └── search_008.json
│   │   │       ├── state.json
│   │   │       ├── stderr.log
│   │   │       ├── stdout.log
│   │   │       └── tool_results
│   │   │           ├── fetch_001.json
│   │   │           ├── fetch_002.json
│   │   │           ├── fetch_003.json
│   │   │           ├── fetch_004.json
│   │   │           ├── fetch_005.json
│   │   │           ├── fetch_006.json
│   │   │           ├── fetch_007.json
│   │   │           ├── fetch_008.json
│   │   │           ├── fetch_009.json
│   │   │           └── fetch_010.json
│   │   ├── resume_check.txt
│   │   └── source_heads.txt
│   ├── flash_emotion_20261021
│   │   ├── budget.json
│   │   ├── evaluate_final.log
│   │   ├── evaluate_final2.log
│   │   ├── evaluate_selection.log
│   │   ├── evaluate_stdout.log
│   │   ├── materials
│   │   │   ├── evidence
│   │   │   │   ├── index.json
│   │   │   │   └── sources
│   │   │   │       ├── ev_580a39dd545d.json
│   │   │   │       ├── ev_580a39dd545d.md
│   │   │   │       ├── ev_6619560afa7e.json
│   │   │   │       ├── ev_6619560afa7e.md
│   │   │   │       ├── ev_74eaf4bc0082.json
│   │   │   │       ├── ev_74eaf4bc0082.md
│   │   │   │       ├── ev_97eaa43a3d81.json
│   │   │   │       ├── ev_97eaa43a3d81.md
│   │   │   │       ├── ev_c908ef06754c.json
│   │   │   │       ├── ev_c908ef06754c.md
│   │   │   │       ├── ev_d3f89ccca87f.json
│   │   │   │       ├── ev_d3f89ccca87f.md
│   │   │   │       ├── ev_fad98f5a28bb.json
│   │   │   │       └── ev_fad98f5a28bb.md
│   │   │   ├── fetch_attempts.json
│   │   │   ├── inspection.txt
│   │   │   ├── inspection3.txt
│   │   │   └── searches
│   │   │       ├── search_01.json
│   │   │       ├── search_02.json
│   │   │       ├── search_03.json
│   │   │       ├── search_04.json
│   │   │       ├── search_05.json
│   │   │       ├── search_06.json
│   │   │       └── search_07.json
│   │   ├── meta
│   │   │   ├── META_REVIEW.md
│   │   │   ├── meta_decision.json
│   │   │   ├── meta_input.json
│   │   │   ├── meta_response.json
│   │   │   ├── meta_rule.md
│   │   │   └── rule_snapshots
│   │   │       └── emotion_baseline_v1+meta_98dc75d5b5.md
│   │   ├── proposal_numeric_audit.txt
│   │   ├── proposal_numeric_audit2.txt
│   │   ├── retry2_launch.txt
│   │   ├── retry2_pid.txt
│   │   ├── retry2_stderr.log
│   │   ├── retry2_stdout.log
│   │   ├── retry_launch.txt
│   │   ├── retry_pid.txt
│   │   ├── retry_stderr.log
│   │   ├── retry_stdout.log
│   │   ├── reviews
│   │   │   ├── FORMAT_INTEGRITY_CHECK.md
│   │   │   ├── INITIAL_REVIEW.md
│   │   │   ├── KEY.json
│   │   │   ├── README.md
│   │   │   ├── blinded
│   │   │   │   ├── proposal_01.md
│   │   │   │   ├── proposal_02.md
│   │   │   │   ├── proposal_03.md
│   │   │   │   └── proposal_04.md
│   │   │   └── evaluation.json
│   │   ├── run_launch.txt
│   │   ├── run_pid.txt
│   │   ├── run_stderr.log
│   │   ├── run_stdout.log
│   │   ├── runs
│   │   │   ├── baseline
│   │   │   │   ├── repeat_01
│   │   │   │   │   ├── events.jsonl
│   │   │   │   │   ├── evidence
│   │   │   │   │   │   ├── index.json
│   │   │   │   │   │   ├── injections.jsonl
│   │   │   │   │   │   └── sources
│   │   │   │   │   │       ├── ev_580a39dd545d.json
│   │   │   │   │   │       ├── ev_6619560afa7e.json
│   │   │   │   │   │       ├── ev_74eaf4bc0082.json
│   │   │   │   │   │       ├── ev_97eaa43a3d81.json
│   │   │   │   │   │       ├── ev_c908ef06754c.json
│   │   │   │   │   │       ├── ev_d3f89ccca87f.json
│   │   │   │   │   │       └── ev_fad98f5a28bb.json
│   │   │   │   │   ├── final.json
│   │   │   │   │   ├── final_answer.md
│   │   │   │   │   ├── heartbeat.json
│   │   │   │   │   ├── messages.json
│   │   │   │   │   ├── requests
│   │   │   │   │   │   ├── request_001.json
│   │   │   │   │   │   ├── request_002.json
│   │   │   │   │   │   ├── request_003.json
│   │   │   │   │   │   ├── request_004.json
│   │   │   │   │   │   ├── request_005.json
│   │   │   │   │   │   └── request_006.json
│   │   │   │   │   ├── responses
│   │   │   │   │   │   ├── response_001.json
│   │   │   │   │   │   ├── response_002.json
│   │   │   │   │   │   ├── response_003.json
│   │   │   │   │   │   ├── response_004.json
│   │   │   │   │   │   ├── response_005.json
│   │   │   │   │   │   └── response_006.json
│   │   │   │   │   ├── rules
│   │   │   │   │   │   └── emotion_baseline_v1.md
│   │   │   │   │   ├── run_manifest.json
│   │   │   │   │   ├── scientist_input.md
│   │   │   │   │   └── state.json
│   │   │   │   ├── repeat_02
│   │   │   │   │   ├── events.jsonl
│   │   │   │   │   ├── evidence
│   │   │   │   │   │   ├── index.json
│   │   │   │   │   │   ├── injections.jsonl
│   │   │   │   │   │   └── sources
│   │   │   │   │   │       ├── ev_580a39dd545d.json
│   │   │   │   │   │       ├── ev_6619560afa7e.json
│   │   │   │   │   │       ├── ev_74eaf4bc0082.json
│   │   │   │   │   │       ├── ev_97eaa43a3d81.json
│   │   │   │   │   │       ├── ev_c908ef06754c.json
│   │   │   │   │   │       ├── ev_d3f89ccca87f.json
│   │   │   │   │   │       └── ev_fad98f5a28bb.json
│   │   │   │   │   ├── heartbeat.json
│   │   │   │   │   ├── messages.json
│   │   │   │   │   ├── requests
│   │   │   │   │   │   ├── request_001.json
│   │   │   │   │   │   ├── request_002.json
│   │   │   │   │   │   ├── request_003.json
│   │   │   │   │   │   ├── request_004.json
│   │   │   │   │   │   ├── request_005.json
│   │   │   │   │   │   └── request_006.json
│   │   │   │   │   ├── responses
│   │   │   │   │   │   ├── response_001.json
│   │   │   │   │   │   ├── response_002.json
│   │   │   │   │   │   ├── response_003.json
│   │   │   │   │   │   ├── response_004.json
│   │   │   │   │   │   ├── response_005.json
│   │   │   │   │   │   └── response_006.json
│   │   │   │   │   ├── rules
│   │   │   │   │   │   └── emotion_baseline_v1.md
│   │   │   │   │   ├── run_manifest.json
│   │   │   │   │   ├── scientist_input.md
│   │   │   │   │   └── state.json
│   │   │   │   ├── repeat_02__retry
│   │   │   │   │   ├── events.jsonl
│   │   │   │   │   ├── evidence
│   │   │   │   │   │   ├── index.json
│   │   │   │   │   │   ├── injections.jsonl
│   │   │   │   │   │   └── sources
│   │   │   │   │   │       ├── ev_580a39dd545d.json
│   │   │   │   │   │       ├── ev_6619560afa7e.json
│   │   │   │   │   │       ├── ev_74eaf4bc0082.json
│   │   │   │   │   │       ├── ev_97eaa43a3d81.json
│   │   │   │   │   │       ├── ev_c908ef06754c.json
│   │   │   │   │   │       ├── ev_d3f89ccca87f.json
│   │   │   │   │   │       └── ev_fad98f5a28bb.json
│   │   │   │   │   ├── final.json
│   │   │   │   │   ├── final_answer.md
│   │   │   │   │   ├── heartbeat.json
│   │   │   │   │   ├── messages.json
│   │   │   │   │   ├── requests
│   │   │   │   │   │   ├── request_001.json
│   │   │   │   │   │   ├── request_002.json
│   │   │   │   │   │   ├── request_003.json
│   │   │   │   │   │   ├── request_004.json
│   │   │   │   │   │   ├── request_005.json
│   │   │   │   │   │   └── request_006.json
│   │   │   │   │   ├── responses
│   │   │   │   │   │   ├── response_001.json
│   │   │   │   │   │   ├── response_002.json
│   │   │   │   │   │   ├── response_003.json
│   │   │   │   │   │   ├── response_004.json
│   │   │   │   │   │   ├── response_005.json
│   │   │   │   │   │   └── response_006.json
│   │   │   │   │   ├── rules
│   │   │   │   │   │   └── emotion_baseline_v1.md
│   │   │   │   │   ├── run_manifest.json
│   │   │   │   │   ├── scientist_input.md
│   │   │   │   │   └── state.json
│   │   │   │   └── repeat_02__retry2
│   │   │   │       ├── events.jsonl
│   │   │   │       ├── evidence
│   │   │   │       │   ├── index.json
│   │   │   │       │   ├── injections.jsonl
│   │   │   │       │   └── sources
│   │   │   │       │       ├── ev_580a39dd545d.json
│   │   │   │       │       ├── ev_6619560afa7e.json
│   │   │   │       │       ├── ev_74eaf4bc0082.json
│   │   │   │       │       ├── ev_97eaa43a3d81.json
│   │   │   │       │       ├── ev_c908ef06754c.json
│   │   │   │       │       ├── ev_d3f89ccca87f.json
│   │   │   │       │       └── ev_fad98f5a28bb.json
│   │   │   │       ├── final.json
│   │   │   │       ├── final_answer.md
│   │   │   │       ├── heartbeat.json
│   │   │   │       ├── messages.json
│   │   │   │       ├── requests
│   │   │   │       │   ├── request_001.json
│   │   │   │       │   ├── request_002.json
│   │   │   │       │   ├── request_003.json
│   │   │   │       │   ├── request_004.json
│   │   │   │       │   ├── request_005.json
│   │   │   │       │   ├── request_006.json
│   │   │   │       │   └── request_007.json
│   │   │   │       ├── responses
│   │   │   │       │   ├── response_001.json
│   │   │   │       │   ├── response_002.json
│   │   │   │       │   ├── response_003.json
│   │   │   │       │   ├── response_004.json
│   │   │   │       │   ├── response_005.json
│   │   │   │       │   ├── response_006.json
│   │   │   │       │   └── response_007.json
│   │   │   │       ├── rules
│   │   │   │       │   └── emotion_baseline_v1.md
│   │   │   │       ├── run_manifest.json
│   │   │   │       ├── scientist_input.md
│   │   │   │       └── state.json
│   │   │   └── meta_rule
│   │   │       ├── repeat_01
│   │   │       │   ├── events.jsonl
│   │   │       │   ├── evidence
│   │   │       │   │   ├── index.json
│   │   │       │   │   ├── injections.jsonl
│   │   │       │   │   └── sources
│   │   │       │   │       ├── ev_580a39dd545d.json
│   │   │       │   │       ├── ev_6619560afa7e.json
│   │   │       │   │       ├── ev_74eaf4bc0082.json
│   │   │       │   │       ├── ev_97eaa43a3d81.json
│   │   │       │   │       ├── ev_c908ef06754c.json
│   │   │       │   │       ├── ev_d3f89ccca87f.json
│   │   │       │   │       └── ev_fad98f5a28bb.json
│   │   │       │   ├── heartbeat.json
│   │   │       │   ├── messages.json
│   │   │       │   ├── requests
│   │   │       │   │   ├── request_001.json
│   │   │       │   │   ├── request_002.json
│   │   │       │   │   ├── request_003.json
│   │   │       │   │   ├── request_004.json
│   │   │       │   │   └── request_005.json
│   │   │       │   ├── responses
│   │   │       │   │   ├── response_001.json
│   │   │       │   │   ├── response_002.json
│   │   │       │   │   ├── response_003.json
│   │   │       │   │   ├── response_004.json
│   │   │       │   │   └── response_005.json
│   │   │       │   ├── rules
│   │   │       │   │   └── emotion_baseline_v1+meta_98dc75d5b5.md
│   │   │       │   ├── run_manifest.json
│   │   │       │   ├── scientist_input.md
│   │   │       │   └── state.json
│   │   │       ├── repeat_01__retry
│   │   │       │   ├── events.jsonl
│   │   │       │   ├── evidence
│   │   │       │   │   ├── index.json
│   │   │       │   │   ├── injections.jsonl
│   │   │       │   │   └── sources
│   │   │       │   │       ├── ev_580a39dd545d.json
│   │   │       │   │       ├── ev_6619560afa7e.json
│   │   │       │   │       ├── ev_74eaf4bc0082.json
│   │   │       │   │       ├── ev_97eaa43a3d81.json
│   │   │       │   │       ├── ev_c908ef06754c.json
│   │   │       │   │       ├── ev_d3f89ccca87f.json
│   │   │       │   │       └── ev_fad98f5a28bb.json
│   │   │       │   ├── heartbeat.json
│   │   │       │   ├── messages.json
│   │   │       │   ├── requests
│   │   │       │   │   ├── request_001.json
│   │   │       │   │   ├── request_002.json
│   │   │       │   │   ├── request_003.json
│   │   │       │   │   ├── request_004.json
│   │   │       │   │   ├── request_005.json
│   │   │       │   │   ├── request_006.json
│   │   │       │   │   └── request_007.json
│   │   │       │   ├── responses
│   │   │       │   │   ├── response_001.json
│   │   │       │   │   ├── response_002.json
│   │   │       │   │   ├── response_003.json
│   │   │       │   │   ├── response_004.json
│   │   │       │   │   ├── response_005.json
│   │   │       │   │   ├── response_006.json
│   │   │       │   │   └── response_007.json
│   │   │       │   ├── rules
│   │   │       │   │   └── emotion_baseline_v1+meta_98dc75d5b5.md
│   │   │       │   ├── run_manifest.json
│   │   │       │   ├── scientist_input.md
│   │   │       │   └── state.json
│   │   │       ├── repeat_01__retry2
│   │   │       │   ├── events.jsonl
│   │   │       │   ├── evidence
│   │   │       │   │   ├── index.json
│   │   │       │   │   ├── injections.jsonl
│   │   │       │   │   └── sources
│   │   │       │   │       ├── ev_580a39dd545d.json
│   │   │       │   │       ├── ev_6619560afa7e.json
│   │   │       │   │       ├── ev_74eaf4bc0082.json
│   │   │       │   │       ├── ev_97eaa43a3d81.json
│   │   │       │   │       ├── ev_c908ef06754c.json
│   │   │       │   │       ├── ev_d3f89ccca87f.json
│   │   │       │   │       └── ev_fad98f5a28bb.json
│   │   │       │   ├── final.json
│   │   │       │   ├── final_answer.md
│   │   │       │   ├── heartbeat.json
│   │   │       │   ├── messages.json
│   │   │       │   ├── requests
│   │   │       │   │   ├── request_001.json
│   │   │       │   │   ├── request_002.json
│   │   │       │   │   ├── request_003.json
│   │   │       │   │   ├── request_004.json
│   │   │       │   │   ├── request_005.json
│   │   │       │   │   └── request_006.json
│   │   │       │   ├── responses
│   │   │       │   │   ├── response_001.json
│   │   │       │   │   ├── response_002.json
│   │   │       │   │   ├── response_003.json
│   │   │       │   │   ├── response_004.json
│   │   │       │   │   ├── response_005.json
│   │   │       │   │   └── response_006.json
│   │   │       │   ├── rules
│   │   │       │   │   └── emotion_baseline_v1+meta_98dc75d5b5.md
│   │   │       │   ├── run_manifest.json
│   │   │       │   ├── scientist_input.md
│   │   │       │   └── state.json
│   │   │       ├── repeat_02
│   │   │       │   ├── events.jsonl
│   │   │       │   ├── evidence
│   │   │       │   │   ├── index.json
│   │   │       │   │   ├── injections.jsonl
│   │   │       │   │   └── sources
│   │   │       │   │       ├── ev_580a39dd545d.json
│   │   │       │   │       ├── ev_6619560afa7e.json
│   │   │       │   │       ├── ev_74eaf4bc0082.json
│   │   │       │   │       ├── ev_97eaa43a3d81.json
│   │   │       │   │       ├── ev_c908ef06754c.json
│   │   │       │   │       ├── ev_d3f89ccca87f.json
│   │   │       │   │       └── ev_fad98f5a28bb.json
│   │   │       │   ├── heartbeat.json
│   │   │       │   ├── messages.json
│   │   │       │   ├── requests
│   │   │       │   │   ├── request_001.json
│   │   │       │   │   ├── request_002.json
│   │   │       │   │   ├── request_003.json
│   │   │       │   │   ├── request_004.json
│   │   │       │   │   ├── request_005.json
│   │   │       │   │   ├── request_006.json
│   │   │       │   │   └── request_007.json
│   │   │       │   ├── responses
│   │   │       │   │   ├── response_001.json
│   │   │       │   │   ├── response_002.json
│   │   │       │   │   ├── response_003.json
│   │   │       │   │   ├── response_004.json
│   │   │       │   │   ├── response_005.json
│   │   │       │   │   ├── response_006.json
│   │   │       │   │   └── response_007.json
│   │   │       │   ├── rules
│   │   │       │   │   └── emotion_baseline_v1+meta_98dc75d5b5.md
│   │   │       │   ├── run_manifest.json
│   │   │       │   ├── scientist_input.md
│   │   │       │   └── state.json
│   │   │       ├── repeat_02__retry
│   │   │       │   ├── events.jsonl
│   │   │       │   ├── evidence
│   │   │       │   │   ├── index.json
│   │   │       │   │   ├── injections.jsonl
│   │   │       │   │   └── sources
│   │   │       │   │       ├── ev_580a39dd545d.json
│   │   │       │   │       ├── ev_6619560afa7e.json
│   │   │       │   │       ├── ev_74eaf4bc0082.json
│   │   │       │   │       ├── ev_97eaa43a3d81.json
│   │   │       │   │       ├── ev_c908ef06754c.json
│   │   │       │   │       ├── ev_d3f89ccca87f.json
│   │   │       │   │       └── ev_fad98f5a28bb.json
│   │   │       │   ├── final.json
│   │   │       │   ├── final_answer.md
│   │   │       │   ├── heartbeat.json
│   │   │       │   ├── messages.json
│   │   │       │   ├── requests
│   │   │       │   │   ├── request_001.json
│   │   │       │   │   ├── request_002.json
│   │   │       │   │   ├── request_003.json
│   │   │       │   │   ├── request_004.json
│   │   │       │   │   ├── request_005.json
│   │   │       │   │   └── request_006.json
│   │   │       │   ├── responses
│   │   │       │   │   ├── response_001.json
│   │   │       │   │   ├── response_002.json
│   │   │       │   │   ├── response_003.json
│   │   │       │   │   ├── response_004.json
│   │   │       │   │   ├── response_005.json
│   │   │       │   │   └── response_006.json
│   │   │       │   ├── rules
│   │   │       │   │   └── emotion_baseline_v1+meta_98dc75d5b5.md
│   │   │       │   ├── run_manifest.json
│   │   │       │   ├── scientist_input.md
│   │   │       │   └── state.json
│   │   │       └── repeat_02__retry2
│   │   │           ├── events.jsonl
│   │   │           ├── evidence
│   │   │           │   ├── index.json
│   │   │           │   ├── injections.jsonl
│   │   │           │   └── sources
│   │   │           │       ├── ev_580a39dd545d.json
│   │   │           │       ├── ev_6619560afa7e.json
│   │   │           │       ├── ev_74eaf4bc0082.json
│   │   │           │       ├── ev_97eaa43a3d81.json
│   │   │           │       ├── ev_c908ef06754c.json
│   │   │           │       ├── ev_d3f89ccca87f.json
│   │   │           │       └── ev_fad98f5a28bb.json
│   │   │           ├── final.json
│   │   │           ├── final_answer.md
│   │   │           ├── heartbeat.json
│   │   │           ├── messages.json
│   │   │           ├── requests
│   │   │           │   ├── request_001.json
│   │   │           │   ├── request_002.json
│   │   │           │   ├── request_003.json
│   │   │           │   ├── request_004.json
│   │   │           │   ├── request_005.json
│   │   │           │   ├── request_006.json
│   │   │           │   ├── request_007.json
│   │   │           │   └── request_008.json
│   │   │           ├── responses
│   │   │           │   ├── response_001.json
│   │   │           │   ├── response_002.json
│   │   │           │   ├── response_003.json
│   │   │           │   ├── response_004.json
│   │   │           │   ├── response_005.json
│   │   │           │   ├── response_006.json
│   │   │           │   ├── response_007.json
│   │   │           │   └── response_008.json
│   │   │           ├── rules
│   │   │           │   └── emotion_baseline_v1+meta_98dc75d5b5.md
│   │   │           ├── run_manifest.json
│   │   │           ├── scientist_input.md
│   │   │           └── state.json
│   │   ├── spotcheck.txt
│   │   ├── study_lock.json
│   │   ├── study_state.json
│   │   └── valence_audit.txt
│   └── study_20261019
│       ├── FREEZE_MANIFEST.json
│       ├── development
│       │   ├── case_001
│       │   │   └── s0
│       │   │       ├── cache
│       │   │       │   ├── 85e3c344cbc2825ff1322a9c2a7c639c015ece116aa3a14016fb1ce4adb47b94.json
│       │   │       │   ├── 9012debfff31ee87f9363100f323dd0619dadf39eda229869fdb1f43193aa99a.json
│       │   │       │   ├── 9f7eee0fdf6c9a1b94dd7fff91c5a80badf1426370f7029c6f073a0c4614ed13.json
│       │   │       │   └── fbea462f6e3fe17d5af3bb11669d66f58fa2f0bed0297fefc492fb3993bc4574.json
│       │   │       ├── config_snapshot.json
│       │   │       ├── events.jsonl
│       │   │       ├── final.json
│       │   │       ├── history.json
│       │   │       ├── prediction_004.json
│       │   │       ├── prediction_009.json
│       │   │       ├── prediction_014.json
│       │   │       ├── public_input.json
│       │   │       ├── request_001.json
│       │   │       ├── request_002.json
│       │   │       ├── request_003.json
│       │   │       ├── request_004.json
│       │   │       ├── response_001.json
│       │   │       ├── response_002.json
│       │   │       ├── response_003.json
│       │   │       ├── response_004.json
│       │   │       ├── result_001.json
│       │   │       ├── result_002.json
│       │   │       ├── result_003.json
│       │   │       ├── score_001.json
│       │   │       ├── score_002.json
│       │   │       ├── score_003.json
│       │   │       ├── state.json
│       │   │       └── summary.md
│       │   └── case_002
│       │       └── s0
│       │           ├── cache
│       │           │   ├── 213600f9f8e8ab5187e091726a07e1fa43a25e504aa452a5451ae11aa3ab3db8.json
│       │           │   ├── 21bd99925faf2f770c982fdf63b8a2f0f2beb6f945845b8389528c1eb2c0dec6.json
│       │           │   ├── 28fbf80531668b020946b137d3ded95124a1e5fdd2c0f6414f939a2eda474442.json
│       │           │   └── 2d0c110904f5fd1461de136804f80526c8b039ac4d9f4e27a4dcf0ade6a5e973.json
│       │           ├── config_snapshot.json
│       │           ├── events.jsonl
│       │           ├── final.json
│       │           ├── history.json
│       │           ├── prediction_004.json
│       │           ├── prediction_009.json
│       │           ├── prediction_014.json
│       │           ├── public_input.json
│       │           ├── request_001.json
│       │           ├── request_002.json
│       │           ├── request_003.json
│       │           ├── request_004.json
│       │           ├── response_001.json
│       │           ├── response_002.json
│       │           ├── response_003.json
│       │           ├── response_004.json
│       │           ├── result_001.json
│       │           ├── result_002.json
│       │           ├── result_003.json
│       │           ├── score_001.json
│       │           ├── score_002.json
│       │           ├── score_003.json
│       │           ├── state.json
│       │           └── summary.md
│       ├── events.jsonl
│       ├── holdout
│       │   ├── case_003
│       │   │   ├── s0
│       │   │   │   ├── cache
│       │   │   │   │   └── f88e1bb1bfc8542d7711e22c7bed25afc600ef6d9a3958b903cbc8cab3612505.json
│       │   │   │   ├── config_snapshot.json
│       │   │   │   ├── events.jsonl
│       │   │   │   ├── final.json
│       │   │   │   ├── history.json
│       │   │   │   ├── public_input.json
│       │   │   │   ├── request_001.json
│       │   │   │   ├── response_001.json
│       │   │   │   ├── state.json
│       │   │   │   └── summary.md
│       │   │   └── s1
│       │   │       ├── cache
│       │   │       │   └── d395b8cf5358854c4df650efb9a8fc7bef7a0e19066297ca4f1bea79bcddd69b.json
│       │   │       ├── config_snapshot.json
│       │   │       ├── events.jsonl
│       │   │       ├── final.json
│       │   │       ├── history.json
│       │   │       ├── public_input.json
│       │   │       ├── request_001.json
│       │   │       ├── response_001.json
│       │   │       ├── state.json
│       │   │       └── summary.md
│       │   ├── case_004
│       │   │   ├── s0
│       │   │   │   ├── cache
│       │   │   │   │   └── 17c10fbbf7a863ecfd7585c2606f212b60ff473cab0e706842adf11c99cc40f9.json
│       │   │   │   ├── config_snapshot.json
│       │   │   │   ├── events.jsonl
│       │   │   │   ├── final.json
│       │   │   │   ├── history.json
│       │   │   │   ├── public_input.json
│       │   │   │   ├── request_001.json
│       │   │   │   ├── response_001.json
│       │   │   │   ├── state.json
│       │   │   │   └── summary.md
│       │   │   └── s1
│       │   │       ├── cache
│       │   │       │   └── 9e84592c5d328d93d46529ee6c7b3dcf786b18f04f83c3c53cba2f2b0ff1ed61.json
│       │   │       ├── config_snapshot.json
│       │   │       ├── events.jsonl
│       │   │       ├── final.json
│       │   │       ├── history.json
│       │   │       ├── public_input.json
│       │   │       ├── request_001.json
│       │   │       ├── response_001.json
│       │   │       ├── state.json
│       │   │       └── summary.md
│       │   ├── case_005
│       │   │   ├── s0
│       │   │   │   ├── cache
│       │   │   │   │   └── 51336fa8d87de147273eefbc9ea4421624da2d96a4413f4aa5c73688fe783592.json
│       │   │   │   ├── config_snapshot.json
│       │   │   │   ├── events.jsonl
│       │   │   │   ├── final.json
│       │   │   │   ├── history.json
│       │   │   │   ├── public_input.json
│       │   │   │   ├── request_001.json
│       │   │   │   ├── response_001.json
│       │   │   │   ├── state.json
│       │   │   │   └── summary.md
│       │   │   └── s1
│       │   │       ├── cache
│       │   │       │   └── b057c1f24e875cd178b0bcd779bdede66832850552c9903e80e13b0e27053b61.json
│       │   │       ├── config_snapshot.json
│       │   │       ├── events.jsonl
│       │   │       ├── final.json
│       │   │       ├── history.json
│       │   │       ├── public_input.json
│       │   │       ├── request_001.json
│       │   │       ├── response_001.json
│       │   │       ├── state.json
│       │   │       └── summary.md
│       │   └── case_006
│       │       ├── s0
│       │       │   ├── cache
│       │       │   │   └── 817eb1a6dcfdef5b9ae6478de20437bd2ec9dc302d38ade65d8f03ded875d77a.json
│       │       │   ├── config_snapshot.json
│       │       │   ├── events.jsonl
│       │       │   ├── final.json
│       │       │   ├── history.json
│       │       │   ├── public_input.json
│       │       │   ├── request_001.json
│       │       │   ├── response_001.json
│       │       │   ├── state.json
│       │       │   └── summary.md
│       │       └── s1
│       │           ├── cache
│       │           │   └── 84689f0096546112b6d42c97ce8265ab5ca4a9385f239b4bb93486995bce0115.json
│       │           ├── config_snapshot.json
│       │           ├── events.jsonl
│       │           ├── final.json
│       │           ├── history.json
│       │           ├── public_input.json
│       │           ├── request_001.json
│       │           ├── response_001.json
│       │           ├── state.json
│       │           └── summary.md
│       ├── shared_development_facts.json
│       └── study_state.json
├── src
│   └── eeg_scientist
│       ├── __init__.py
│       ├── backends.py
│       ├── capability.py
│       ├── cases.py
│       ├── cli.py
│       ├── credentials.py
│       ├── dataset_io.py
│       ├── deepseek_api.py
│       ├── diagnostic.py
│       ├── emotion_experiment.py
│       ├── evidence.py
│       ├── experiments.py
│       ├── flash_report.py
│       ├── ledger.py
│       ├── meta.py
│       ├── provider.py
│       ├── reporting.py
│       ├── research.py
│       ├── run_manifest.py
│       ├── runner.py
│       ├── schema.py
│       ├── scientist.py
│       ├── splits.py
│       ├── storage.py
│       └── study.py
├── tests
│   ├── test_core.py
│   ├── test_emotion_experiment.py
│   ├── test_flash_stack.py
│   ├── test_scientist_provider.py
│   ├── test_storage_runner.py
│   └── test_study_reporting.py
└── uv.lock
```

## 工具内部目录（汇总）

| 目录 | 文件数 | 作用 |
|---|---:|---|
| `.git/` | 295 | Git 对象/引用/配置 |
| `.mypy_cache/` | 1955 | mypy 缓存 |
| `.pytest_cache/` | 6 | pytest 缓存 |
| `.venv/` | 5860 | uv 虚拟环境（Python、第三方依赖、脚本） |
| `docs/` | 3 | 工具生成/缓存 |
| `src/` | 25 | 工具生成/缓存 |
| `tests/` | 15 | 工具生成/缓存 |

逐文件 role、时间、大小和 Git 索引状态见 `FILE_INVENTORY.csv`。

## 项目/人工产物逐文件清单

按目录分组；每行一句话说明该文件对项目的贡献。

### (根目录)

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `.gitignore` | 2026-10-07 11:45:09 | 2026-10-19 23:27:31 | 1.2 KB | Git 忽略规则；包含 credentials、runs、私有数据等边界。 |
| `.python-version` | 2026-10-07 13:44:00 | 2026-10-07 13:44:00 | 5 B | 项目 Python 版本提示（3.12）。 |
| `.venv_sync.log` | 2026-10-21 11:44:04 | 2026-10-21 11:49:32 | 3.0 KB | 安装/同步环境时生成的日志（第一轮）。 |
| `.venv_sync2.log` | 2026-10-21 11:51:21 | 2026-10-21 11:54:09 | 2.3 KB | 安装/同步环境时生成的日志（第二轮）。 |
| `.venv_sync3.log` | 2026-10-21 11:54:23 | 2026-10-21 11:54:25 | 1.9 KB | 安装/同步环境时生成的日志（最终成功同步）。 |
| `DECISIONS.md` | 2026-10-19 01:49:01 | 2026-10-19 01:56:50 | 4.4 KB | 历史技术决策记录（模型、格式、依赖、冻结等）。 |
| `EEG_AI_Scientist_Overnight_Plan.md` | 2026-10-19 01:01:47 | 2026-10-19 01:02:32 | 68.4 KB | 旧版过夜计划（历史背景，不是本轮任务书）。 |
| `ENVIRONMENT.md` | 2026-10-21 11:51:09 | 2026-10-21 11:58:32 | 2.1 KB | 统一环境说明：canonical .venv、依赖版本、测试/类型检查命令。 |
| `FREEZE_MANIFEST.json` | 2026-10-19 01:49:52 | 2026-10-19 01:49:52 | 164.5 KB | 旧合成过夜研究的冻结清单（模型、代码、依赖、费用）。 |
| `NEXT_ACTION.md` | 2026-10-20 13:26:50 | 2026-10-21 11:58:01 | 5.4 KB | 连续性文件：当前交接、恢复命令和下一项动作。 |
| `PROGRESS.md` | 2026-10-20 13:26:50 | 2026-10-21 11:58:37 | 13.4 KB | 项目进度日志：旧研究、Flash 研究、交接和最终状态。 |
| `pyproject.toml` | 2026-10-07 12:28:43 | 2026-10-21 11:54:18 | 626 B | Python 包元数据、运行依赖和 pytest 配置。 |
| `uv.lock` | 2026-10-07 13:31:28 | 2026-10-21 11:54:23 | 97.4 KB | uv 锁文件，固定依赖解析结果。 |

### .vscode

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `.vscode/settings.json` | 2026-10-21 11:51:08 | 2026-10-21 11:51:08 | 341 B | VS Code 项目解释器、源码路径和 pytest 设置。 |

### artifacts

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `artifacts/review_bundle.zip` | 2026-10-19 01:54:43 | 2026-10-19 01:57:23 | 578.6 KB | 旧合成过夜研究的 review bundle。 |
| `artifacts/review_bundle_20261020.zip` | 2026-10-20 21:41:22 | 2026-10-20 21:43:26 | 659.6 KB | 2026-10-20 Flash 文献研究的 review bundle。 |
| `artifacts/review_bundle_emotion_20261021.zip` | 2026-10-21 09:47:33 | 2026-10-21 11:59:16 | 1.1 MB | 2026-10-21 情绪 state-vs-trait 研究的 review bundle。 |

### configs

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `configs/dev_episode.json` | 2026-10-19 01:35:40 | 2026-10-19 01:35:40 | 658 B | 旧单案例开发 episode 配置（Ollama/Qwen 路径）。 |
| `configs/eval/emotion_rubric_v1.json` | 2026-10-21 09:26:17 | 2026-10-21 09:26:17 | 1.7 KB | 情绪提案的冻结评价标准（引用、推理、区分力、可执行性、费用）。 |
| `configs/materials/emotion_state_trait_v1.json` | 2026-10-21 09:29:40 | 2026-10-21 09:29:40 | 7.7 KB | 六篇公开论文的冻结材料清单、版本和提取限制。 |
| `configs/models/backends_20261021.json` | 2026-10-21 09:26:04 | 2026-10-21 09:26:04 | 4.5 KB | 模型/工具后端注册表与价格；仅 Flash 已验证。 |
| `configs/models/deepseek_flash.json` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 1.2 KB | 旧 Flash 运行模型/价格/超时配置。 |
| `configs/overnight.json` | 2026-10-19 01:35:40 | 2026-10-19 01:35:40 | 910 B | 旧 synthetic overnight 研究配置（Ollama/Qwen 路径）。 |
| `configs/prompts/emotion_research_system.md` | 2026-10-21 09:26:17 | 2026-10-21 09:26:17 | 2.0 KB | 情绪研究 system prompt，不包含旧表征任务约束。 |
| `configs/rules/emotion_baseline_v1.md` | 2026-10-21 09:26:17 | 2026-10-21 09:26:17 | 1.6 KB | 情绪研究的原始研究规则（基线 arm）。 |
| `configs/studies/flash_emotion_20261021.json` | 2026-10-21 09:26:10 | 2026-10-21 11:50:41 | 3.8 KB | 情绪研究总配置：问题、材料、预算、运行限制、首 accepted 选择和重试策略。 |
| `configs/studies/overnight_flash_20261020.json` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 2.3 KB | 旧 Flash 过夜研究总配置。 |
| `configs/versions/next_round_20261021.json` | 2026-10-21 11:57:37 | 2026-10-21 11:58:37 | 1.9 KB | 下一轮冻结程序版本、代码快照要求、重试/选择策略和后端状态。 |

### credentials

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `credentials/claude.env` | 2026-10-20 23:04:22 | 2026-10-20 23:05:01 | 121 B | Claude 凭据文件；内容未读取/未打印，当前无可用验证。 |
| `credentials/deepseek.env` | 2026-10-19 21:46:04 | 2026-10-20 00:49:48 | 54 B | DeepSeek 凭据文件；内容未读取/未打印，程序按需显式加载。 |
| `credentials/gemini.txt` | 2026-10-21 09:16:42 | 2026-10-21 09:17:15 | 70 B | Gemini 凭据文件；内容未读取/未打印，当前无可用验证。 |

### data

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `data/private/README.md` | 2026-10-19 01:35:40 | 2026-10-19 01:35:40 | 331 B | 私有/evaluator 目录边界说明。 |
| `data/private/case_specs.json` | 2026-10-19 01:35:40 | 2026-10-19 01:35:40 | 1.7 KB | 合成案例生成器的私有 seed/参数，不是真实 EEG 数据。 |

### docs

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `docs/plans/EEG_AI_Scientist_Overnight_Run_v2.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 43.3 KB | 2026-10-20 Flash 过夜任务书（历史执行依据）。 |

### memory

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `memory/research_methods/rules.json` | 2026-10-19 01:49:52 | 2026-10-19 01:49:52 | 219 B | 旧研究的方法规则记忆（未作为本轮新规则）。 |
| `memory/scientific_knowledge/dev_facts.md` | 2026-10-19 01:49:52 | 2026-10-19 01:49:52 | 20.8 KB | 旧研究开发案例事实与 baseline 汇总。 |

### prompts

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `prompts/DIAGNOSTIC_v2.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 5.9 KB | Task C 两个中性合成案例的诊断规则。 |
| `prompts/S0.md` | 2026-10-19 01:35:32 | 2026-10-19 01:42:14 | 5.8 KB | 旧合成过夜研究的 S0 研究规则快照。 |
| `prompts/S1.md` | 2026-10-19 01:49:50 | 2026-10-19 01:49:50 | 6.1 KB | 旧合成过夜研究的 S1 规则快照（最终未更新）。 |

### ref

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `ref/wechat_group/AutoScientists.pdf` | 2026-10-05 00:10:33 | 2026-09-30 21:07:12 | 2.1 MB | 参考 PDF：AutoScientists，仅作背景。 |
| `ref/wechat_group/EEG_AI_Scientist_RSI_Idea.md` | 2026-10-05 00:10:33 | 2026-10-05 15:31:20 | 28.2 KB | 参考 Markdown：EEG AI Scientist/RSI 想法，仅作背景。 |
| `ref/wechat_group/NeuroWeaver.pdf` | 2026-10-05 00:10:33 | 2026-09-30 21:14:30 | 3.1 MB | 参考 PDF：NeuroWeaver，仅作背景。 |
| `ref/wechat_group/Weco-AIDE2.pdf` | 2026-10-05 00:10:33 | 2026-09-30 21:07:11 | 720.3 KB | 参考 PDF：Weco-AIDE2，仅作背景。 |

### reports

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `reports/CALIBRATION.md` | 2026-10-19 01:49:38 | 2026-10-19 01:49:38 | 2.7 KB | 旧合成研究的工程校准结果。 |
| `reports/CORE_CODE_WALKTHROUGH.md` | 2026-10-19 01:54:43 | 2026-10-19 01:57:23 | 6.7 KB | 旧合成研究的代码阅读指南。 |
| `reports/FAILURE_CASES.md` | 2026-10-19 01:54:43 | 2026-10-19 01:57:23 | 9.9 KB | 旧研究的失败案例/零动作/Meta 失败记录。 |
| `reports/MORNING_REPORT.md` | 2026-10-19 01:54:43 | 2026-10-19 01:57:23 | 13.8 KB | 旧 2026-10-19 合成研究的晨报（历史）。 |
| `reports/OVERNIGHT_RUN.log` | 2026-10-19 01:45:29 | 2026-10-19 01:54:30 | 348 B | 旧 overnight 运行日志。 |
| `reports/PREFLIGHT.md` | 2026-10-19 01:37:08 | 2026-10-19 01:37:44 | 4.3 KB | 旧研究 preflight 记录。 |
| `reports/REPRODUCE.md` | 2026-10-19 01:54:43 | 2026-10-19 01:57:23 | 850 B | 旧研究复现命令。 |
| `reports/RESULTS_TABLE.md` | 2026-10-19 01:54:43 | 2026-10-19 01:57:23 | 14.7 KB | 旧研究结果表。 |
| `reports/flash_20261020_0058/CAPABILITY_CHECK.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 3.4 KB | 真实模型/工具/Search/Fetch 能力检查。 |
| `reports/flash_20261020_0058/CODE_READING_GUIDE.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 5.3 KB | 从 CLI 到证据/预算/研究循环的阅读指南。 |
| `reports/flash_20261020_0058/COVERAGE_RECHECK.md` | 2026-10-20 21:38:41 | 2026-10-20 21:38:41 | 2.5 KB | 读取覆盖率区间并集修正。 |
| `reports/flash_20261020_0058/DATA_REQUIREMENTS.md` | 2026-10-20 13:26:50 | 2026-10-20 21:38:26 | 6.4 KB | 真实 EEG 数据要求与 E2 备用分支。 |
| `reports/flash_20261020_0058/EVIDENCE_AUDIT.md` | 2026-10-20 13:26:50 | 2026-10-20 21:38:13 | 7.7 KB | 数字/主张与注入记录的逐条审计。 |
| `reports/flash_20261020_0058/EXPERIMENT_PROTOCOL.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 6.6 KB | 缩减版 M1、备用 M2、资源与阻塞。 |
| `reports/flash_20261020_0058/HANDOFF_SYSTEM.md` | 2026-10-20 21:39:00 | 2026-10-20 21:41:41 | 4.5 KB | 2026-10-20 Flash 报告文件 `HANDOFF_SYSTEM.md`。 |
| `reports/flash_20261020_0058/HYPOTHESIS_CARDS.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 8.7 KB | 三张假设卡、优先级/备用和 dsh 复核注记。 |
| `reports/flash_20261020_0058/IMPLEMENTATION_MAP.md` | 2026-10-20 13:26:50 | 2026-10-20 21:38:31 | 5.1 KB | 任务书边界到实际模块的映射。 |
| `reports/flash_20261020_0058/LITERATURE_MAP.md` | 2026-10-20 13:26:50 | 2026-10-20 21:38:13 | 5.7 KB | 7 篇引用文献、读取范围和未读/失败来源。 |
| `reports/flash_20261020_0058/METHOD_LESSONS_PROPOSED.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 4.9 KB | 开发者观察到的候选方法改进（未激活）。 |
| `reports/flash_20261020_0058/MORNING_REPORT.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 3.3 KB | 2026-10-20 Flash 文献研究的一页晨报。 |
| `reports/flash_20261020_0058/PRECHECK.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 5.7 KB | 运行前环境/凭证/数据/网络核查。 |
| `reports/flash_20261020_0058/REASONING_REVIEW.md` | 2026-10-20 21:38:49 | 2026-10-20 21:38:49 | 4.7 KB | 对旧文献答案三条推理的单独更正。 |
| `reports/flash_20261020_0058/RESULTS.md` | 2026-10-20 13:26:50 | 2026-10-20 21:39:37 | 5.5 KB | 能力检查、回归、合成案例和文献运行的结果表。 |
| `reports/flash_20261020_0058/RESUME_CHECK.md` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 2.7 KB | 完成后恢复不重复付费的验证。 |
| `reports/flash_20261020_0058/RUN_INDEX.md` | 2026-10-20 13:26:50 | 2026-10-20 21:41:50 | 4.1 KB | 运行阶段、预算、命令和产物索引。 |
| `reports/flash_20261020_0058/coverage_union.json` | 2026-10-20 21:37:49 | 2026-10-20 21:37:49 | 3.0 KB | 修正后的机器可读覆盖率数据。 |
| `reports/flash_emotion_20261021/HANDOFF_NEXT_ROUND.md` | 2026-10-21 11:57:47 | 2026-10-21 11:58:32 | 5.2 KB | 下一轮一页中文交接：环境、阻塞、比较计划。 |
| `reports/flash_emotion_20261021/MANUAL_INITIAL_REVIEW.md` | 2026-10-21 09:45:17 | 2026-10-21 11:56:16 | 5.4 KB | 四份主要提案的 dsh 人工初审与评分。 |
| `reports/flash_emotion_20261021/MINIMAL_EMOTION_STUDY.md` | 2026-10-21 11:56:57 | 2026-10-21 11:56:57 | 5.2 KB | 基于现有公开数据的最小情绪研究方案与缺失元数据。 |
| `reports/flash_emotion_20261021/PROPOSAL_CORRECTIONS.md` | 2026-10-21 11:56:09 | 2026-10-21 11:56:09 | 7.3 KB | 四份提案关键数字与三条推理的单独更正（不改原文）。 |
| `reports/flash_emotion_20261021/RESULT_SUMMARY.md` | 2026-10-21 09:45:25 | 2026-10-21 11:58:54 | 3.7 KB | 情绪研究一页结果摘要（运行数、规则、改善、限制）。 |
| `reports/flash_emotion_20261021/RUN_INDEX.md` | 2026-10-21 09:45:32 | 2026-10-21 11:58:04 | 6.3 KB | 情绪研究运行索引、首 accepted 选择、费用和产物。 |
| `reports/report_data.json` | 2026-10-19 01:54:43 | 2026-10-19 01:57:23 | 635.8 KB | 旧研究报告的机器可读数据。 |
| `reports/test_output.txt` | 2026-10-19 01:49:40 | 2026-10-19 01:57:22 | 164 B | 旧测试运行输出。 |
| `reports/test_summary.json` | 2026-10-19 01:50:17 | 2026-10-19 01:57:22 | 246 B | 旧测试摘要。 |

### review_only

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `review_only/DIAGNOSTIC_MAP.json` | 2026-10-20 01:09:11 | 2026-10-20 01:09:11 | 223 B | Task C 中性别名到合成案例的 evaluator 映射。 |
| `review_only/PRIVATE_CASE_SPECS.json` | 2026-10-19 01:54:43 | 2026-10-19 01:57:23 | 1.7 KB | review-only 私有案例规格副本。 |
| `review_only/README.md` | 2026-10-19 01:54:43 | 2026-10-19 01:57:23 | 105 B | review-only 材料边界说明。 |

### runs

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `runs/dev_e1/case_001_s0/cache/37896c32123cd7dc35dbc0342dd61dbbf195a22b5723620f24ab2492601b0841.json` | 2026-10-19 01:44:59 | 2026-10-19 01:44:59 | 4.4 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0/cache/801b4bf85b96f5aa49c375fd1896a9258afafc615d80182dba4bcccb2bf730d1.json` | 2026-10-19 01:44:40 | 2026-10-19 01:44:40 | 6.0 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0/cache/92a241dd6850ab010f957a8f623b277d8270a6e8f566282344d6407a8b39f718.json` | 2026-10-19 01:45:18 | 2026-10-19 01:45:18 | 4.7 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0/cache/d5e85207357d87083c00b94e43a92f6f41e51e4c4db6eaed651bd7ee9b8418ed.json` | 2026-10-19 01:44:14 | 2026-10-19 01:44:14 | 5.7 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0/cache/fbea462f6e3fe17d5af3bb11669d66f58fa2f0bed0297fefc492fb3993bc4574.json` | 2026-10-19 01:43:51 | 2026-10-19 01:43:51 | 4.4 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0/config_snapshot.json` | 2026-10-19 01:43:35 | 2026-10-19 01:43:35 | 955 B | 旧 episode 配置快照。 |
| `runs/dev_e1/case_001_s0/events.jsonl` | 2026-10-19 01:43:35 | 2026-10-19 01:45:18 | 12.4 KB | 哈希链事件日志。 |
| `runs/dev_e1/case_001_s0/final.json` | 2026-10-19 01:45:18 | 2026-10-19 01:45:18 | 28.6 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/dev_e1/case_001_s0/history.json` | 2026-10-19 01:45:18 | 2026-10-19 01:45:18 | 25.0 KB | 旧 episode 决策/执行历史。 |
| `runs/dev_e1/case_001_s0/prediction_004.json` | 2026-10-19 01:43:52 | 2026-10-19 01:43:52 | 1.2 KB | 封存预测记录。 |
| `runs/dev_e1/case_001_s0/prediction_009.json` | 2026-10-19 01:44:14 | 2026-10-19 01:44:14 | 2.5 KB | 封存预测记录。 |
| `runs/dev_e1/case_001_s0/prediction_014.json` | 2026-10-19 01:44:40 | 2026-10-19 01:44:40 | 2.6 KB | 封存预测记录。 |
| `runs/dev_e1/case_001_s0/public_input.json` | 2026-10-19 01:43:35 | 2026-10-19 01:43:35 | 4.2 KB | 旧合成案例的公开输入。 |
| `runs/dev_e1/case_001_s0/request_001.json` | 2026-10-19 01:43:35 | 2026-10-19 01:43:35 | 13.1 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0/request_002.json` | 2026-10-19 01:43:52 | 2026-10-19 01:43:52 | 17.9 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0/request_003.json` | 2026-10-19 01:44:15 | 2026-10-19 01:44:15 | 23.8 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0/request_004.json` | 2026-10-19 01:44:41 | 2026-10-19 01:44:41 | 29.8 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0/request_005.json` | 2026-10-19 01:44:59 | 2026-10-19 01:44:59 | 13.0 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0/response_001.json` | 2026-10-19 01:43:51 | 2026-10-19 01:43:51 | 4.4 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0/response_002.json` | 2026-10-19 01:44:14 | 2026-10-19 01:44:14 | 5.7 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0/response_003.json` | 2026-10-19 01:44:40 | 2026-10-19 01:44:40 | 6.0 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0/response_004.json` | 2026-10-19 01:44:59 | 2026-10-19 01:44:59 | 4.4 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0/response_005.json` | 2026-10-19 01:45:18 | 2026-10-19 01:45:18 | 4.7 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0/result_001.json` | 2026-10-19 01:43:52 | 2026-10-19 01:43:52 | 7.5 KB | 实验工具执行结果。 |
| `runs/dev_e1/case_001_s0/result_002.json` | 2026-10-19 01:44:15 | 2026-10-19 01:44:15 | 6.3 KB | 实验工具执行结果。 |
| `runs/dev_e1/case_001_s0/result_003.json` | 2026-10-19 01:44:41 | 2026-10-19 01:44:41 | 6.3 KB | 实验工具执行结果。 |
| `runs/dev_e1/case_001_s0/score_001.json` | 2026-10-19 01:43:52 | 2026-10-19 01:43:52 | 8.4 KB | 预测评分结果。 |
| `runs/dev_e1/case_001_s0/score_002.json` | 2026-10-19 01:44:15 | 2026-10-19 01:44:15 | 7.1 KB | 预测评分结果。 |
| `runs/dev_e1/case_001_s0/score_003.json` | 2026-10-19 01:44:41 | 2026-10-19 01:44:41 | 7.1 KB | 预测评分结果。 |
| `runs/dev_e1/case_001_s0/state.json` | 2026-10-19 01:45:18 | 2026-10-19 01:45:18 | 627 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/dev_e1/case_001_s0/summary.md` | 2026-10-19 01:45:18 | 2026-10-19 01:45:18 | 1005 B | 旧 episode 摘要。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/cache/646418747b83813e47c2e487b00e7c196ebccc1c2d88ef7ef1e35e731a805eeb.json` | 2026-10-19 01:39:18 | 2026-10-19 01:39:18 | 5.2 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/cache/bc64f502d602d258986b4135050451ca80887bac74d5432948dfcdabb0a14e6e.json` | 2026-10-19 01:39:44 | 2026-10-19 01:39:44 | 6.5 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/cache/d77dad3d9611cc5a6e85c380c76ed3aa761a4058c5305df9820980bc0ca32d65.json` | 2026-10-19 01:38:37 | 2026-10-19 01:38:37 | 6.6 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/cache/efde9ffb6ba3db1b3d3cd1a87137f4c4a5b78f7097a0622bac049cfbbdf44163.json` | 2026-10-19 01:38:10 | 2026-10-19 01:38:10 | 5.6 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/cache/fdb80f321b7f8be9cd018823bd8accdf1cd66138aa2a256eb9b49d36d80ee024.json` | 2026-10-19 01:39:00 | 2026-10-19 01:39:00 | 5.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/config_snapshot.json` | 2026-10-19 01:37:49 | 2026-10-19 01:37:49 | 955 B | 旧 episode 配置快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/events.jsonl` | 2026-10-19 01:37:49 | 2026-10-19 01:39:44 | 10.3 KB | 哈希链事件日志。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/history.json` | 2026-10-19 01:39:18 | 2026-10-19 01:39:18 | 25.5 KB | 旧 episode 决策/执行历史。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/prediction_004.json` | 2026-10-19 01:38:11 | 2026-10-19 01:38:11 | 2.2 KB | 封存预测记录。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/prediction_009.json` | 2026-10-19 01:38:37 | 2026-10-19 01:38:37 | 2.5 KB | 封存预测记录。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/prediction_016.json` | 2026-10-19 01:39:18 | 2026-10-19 01:39:18 | 2.0 KB | 封存预测记录。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/public_input.json` | 2026-10-19 01:37:49 | 2026-10-19 01:37:49 | 4.2 KB | 旧合成案例的公开输入。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/request_001.json` | 2026-10-19 01:37:49 | 2026-10-19 01:37:49 | 12.6 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/request_002.json` | 2026-10-19 01:38:12 | 2026-10-19 01:38:12 | 18.3 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/request_003.json` | 2026-10-19 01:38:38 | 2026-10-19 01:38:38 | 24.4 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/request_004.json` | 2026-10-19 01:39:00 | 2026-10-19 01:39:00 | 10.8 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/request_005.json` | 2026-10-19 01:39:18 | 2026-10-19 01:39:18 | 29.7 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/response_001.json` | 2026-10-19 01:38:10 | 2026-10-19 01:38:10 | 5.6 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/response_002.json` | 2026-10-19 01:38:37 | 2026-10-19 01:38:37 | 6.6 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/response_003.json` | 2026-10-19 01:39:00 | 2026-10-19 01:39:00 | 5.3 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/response_004.json` | 2026-10-19 01:39:18 | 2026-10-19 01:39:18 | 5.2 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/response_005.json` | 2026-10-19 01:39:44 | 2026-10-19 01:39:44 | 6.5 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/result_001.json` | 2026-10-19 01:38:12 | 2026-10-19 01:38:12 | 6.3 KB | 实验工具执行结果。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/result_002.json` | 2026-10-19 01:38:38 | 2026-10-19 01:38:38 | 6.3 KB | 实验工具执行结果。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/result_004.json` | 2026-10-19 01:39:18 | 2026-10-19 01:39:18 | 7.5 KB | 实验工具执行结果。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/score_001.json` | 2026-10-19 01:38:12 | 2026-10-19 01:38:12 | 7.1 KB | 预测评分结果。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/score_002.json` | 2026-10-19 01:38:38 | 2026-10-19 01:38:38 | 7.1 KB | 预测评分结果。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/score_004.json` | 2026-10-19 01:39:18 | 2026-10-19 01:39:18 | 8.4 KB | 预测评分结果。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/state.json` | 2026-10-19 01:39:44 | 2026-10-19 01:39:44 | 423 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/dev_e1/case_001_s0_attempt1_failed/summary.md` | 2026-10-19 01:39:44 | 2026-10-19 01:39:44 | 702 B | 旧 episode 摘要。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/cache/0704f0fbb2ba41198b9fff6c574842f2fa658acba1fe24fb4e5410af1dae0e1e.json` | 2026-10-19 01:41:46 | 2026-10-19 01:41:46 | 5.7 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/cache/e5da944c458540fba491ddbafaf671f6b0e92a6d3d412fcc856e378f0fec3787.json` | 2026-10-19 01:40:59 | 2026-10-19 01:40:59 | 5.9 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/cache/e8b220660e77c4a007af1ae1fdee0b14e62b418488cf62764f5dd60bdbd83662.json` | 2026-10-19 01:41:26 | 2026-10-19 01:41:26 | 6.7 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/config_snapshot.json` | 2026-10-19 01:40:35 | 2026-10-19 01:40:35 | 955 B | 旧 episode 配置快照。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/events.jsonl` | 2026-10-19 01:40:35 | 2026-10-19 01:41:46 | 5.9 KB | 哈希链事件日志。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/history.json` | 2026-10-19 01:41:00 | 2026-10-19 01:41:00 | 8.9 KB | 旧 episode 决策/执行历史。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/prediction_004.json` | 2026-10-19 01:40:59 | 2026-10-19 01:40:59 | 2.8 KB | 封存预测记录。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/public_input.json` | 2026-10-19 01:40:35 | 2026-10-19 01:40:35 | 4.2 KB | 旧合成案例的公开输入。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/request_001.json` | 2026-10-19 01:40:35 | 2026-10-19 01:40:35 | 12.8 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/request_002.json` | 2026-10-19 01:41:00 | 2026-10-19 01:41:00 | 18.7 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/request_003.json` | 2026-10-19 01:41:26 | 2026-10-19 01:41:26 | 12.1 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/response_001.json` | 2026-10-19 01:40:59 | 2026-10-19 01:40:59 | 5.9 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/response_002.json` | 2026-10-19 01:41:26 | 2026-10-19 01:41:26 | 6.7 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/response_003.json` | 2026-10-19 01:41:46 | 2026-10-19 01:41:46 | 5.7 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/result_001.json` | 2026-10-19 01:41:00 | 2026-10-19 01:41:00 | 6.3 KB | 实验工具执行结果。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/score_001.json` | 2026-10-19 01:41:00 | 2026-10-19 01:41:00 | 7.1 KB | 预测评分结果。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/state.json` | 2026-10-19 01:41:46 | 2026-10-19 01:41:46 | 450 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/dev_e1/case_001_s0_attempt2_failed/summary.md` | 2026-10-19 01:41:46 | 2026-10-19 01:41:46 | 478 B | 旧 episode 摘要。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/cache/6543b0ad7716e4858c9911b219bb83e53b4f3c360c50f6bb3207b0431640362c.json` | 2026-10-19 01:43:02 | 2026-10-19 01:43:02 | 4.4 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/cache/fbea462f6e3fe17d5af3bb11669d66f58fa2f0bed0297fefc492fb3993bc4574.json` | 2026-10-19 01:42:45 | 2026-10-19 01:42:45 | 4.4 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/config_snapshot.json` | 2026-10-19 01:42:26 | 2026-10-19 01:42:26 | 955 B | 旧 episode 配置快照。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/events.jsonl` | 2026-10-19 01:42:26 | 2026-10-19 01:43:03 | 4.5 KB | 哈希链事件日志。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/public_input.json` | 2026-10-19 01:42:26 | 2026-10-19 01:42:26 | 4.2 KB | 旧合成案例的公开输入。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/request_001.json` | 2026-10-19 01:42:26 | 2026-10-19 01:42:26 | 13.1 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/request_002.json` | 2026-10-19 01:42:45 | 2026-10-19 01:42:45 | 11.9 KB | 模型请求快照。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/response_001.json` | 2026-10-19 01:42:45 | 2026-10-19 01:42:45 | 4.4 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/response_002.json` | 2026-10-19 01:43:02 | 2026-10-19 01:43:02 | 4.4 KB | 模型响应快照。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/state.json` | 2026-10-19 01:43:03 | 2026-10-19 01:43:03 | 449 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/dev_e1/case_001_s0_attempt3_failed/summary.md` | 2026-10-19 01:43:03 | 2026-10-19 01:43:03 | 261 B | 旧 episode 摘要。 |
| `runs/flash_20261020_0058/audit_contexts.txt` | 2026-10-20 01:20:53 | 2026-10-20 01:20:53 | 89.4 KB | 运行产物 `audit_contexts.txt`。 |
| `runs/flash_20261020_0058/audit_contexts2.txt` | 2026-10-20 01:21:03 | 2026-10-20 01:21:03 | 72.6 KB | 运行产物 `audit_contexts2.txt`。 |
| `runs/flash_20261020_0058/budget.json` | 2026-10-20 01:18:13 | 2026-10-20 01:18:13 | 27.0 KB | 该研究/运行的预算账本。 |
| `runs/flash_20261020_0058/capability/CAPABILITY_CHECK.md` | 2026-10-20 01:08:18 | 2026-10-20 01:08:18 | 3.4 KB | 能力检查人类可读结果。 |
| `runs/flash_20261020_0058/capability/capability.json` | 2026-10-20 01:08:18 | 2026-10-20 01:08:18 | 4.3 KB | 能力检查机器可读结果。 |
| `runs/flash_20261020_0058/capability/evidence/index.json` | 2026-10-20 01:08:18 | 2026-10-20 01:08:18 | 427 B | 该运行证据索引。 |
| `runs/flash_20261020_0058/capability/evidence/injections.jsonl` | 2026-10-20 01:08:18 | 2026-10-20 01:08:18 | 203 B | 该运行逐次读取/注入记录。 |
| `runs/flash_20261020_0058/capability/evidence/sources/ev_056fb3068eea.json` | 2026-10-20 01:08:18 | 2026-10-20 01:08:18 | 52.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/capability/fetch.json` | 2026-10-20 01:08:18 | 2026-10-20 01:08:18 | 1.4 KB | 能力检查抓取结果。 |
| `runs/flash_20261020_0058/capability/search.json` | 2026-10-20 01:08:12 | 2026-10-20 01:08:12 | 44.9 KB | 能力检查搜索结果。 |
| `runs/flash_20261020_0058/capability/tool_cycle.json` | 2026-10-20 01:08:11 | 2026-10-20 01:08:11 | 1.1 KB | 能力检查原生工具循环记录。 |
| `runs/flash_20261020_0058/capability_stdout.txt` | 2026-10-20 01:07:47 | 2026-10-20 01:07:47 | 8.8 KB | 运行产物 `capability_stdout.txt`。 |
| `runs/flash_20261020_0058/capability_stdout_2.txt` | 2026-10-20 01:08:18 | 2026-10-20 01:08:18 | 9.6 KB | 运行产物 `capability_stdout_2.txt`。 |
| `runs/flash_20261020_0058/claim_contexts.txt` | 2026-10-20 01:20:31 | 2026-10-20 01:20:31 | 65.5 KB | 运行产物 `claim_contexts.txt`。 |
| `runs/flash_20261020_0058/diagnose_stdout.txt` | 2026-10-20 01:11:22 | 2026-10-20 01:11:22 | 22.3 KB | 诊断命令 stdout。 |
| `runs/flash_20261020_0058/diagnostics/cases/PRIVATE_MAPPING.json` | 2026-10-20 01:09:11 | 2026-10-20 01:09:11 | 223 B | evaluator-only 别名映射，不应进入 Scientist 上下文。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/cache/29769ed100add937dc25a448cd65e0f61805f5cad992f9891b0762a61f13d54c.json` | 2026-10-20 01:11:22 | 2026-10-20 01:11:22 | 2.6 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/cache/75976f72e0531afaa6ca9a4a782a6c648bc7b543f5d93cf95464ba34387ffab1.json` | 2026-10-20 01:10:55 | 2026-10-20 01:10:55 | 2.8 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/cache/ae87f1b70a84f5b9cad2d6681d8fe8437a34ad0ebecf3ea0c93fcac1ae71c1f2.json` | 2026-10-20 01:10:43 | 2026-10-20 01:10:43 | 2.8 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/config_snapshot.json` | 2026-10-20 01:10:16 | 2026-10-20 01:10:16 | 805 B | 旧 episode 配置快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/events.jsonl` | 2026-10-20 01:10:16 | 2026-10-20 01:11:22 | 7.0 KB | 哈希链事件日志。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/final.json` | 2026-10-20 01:11:22 | 2026-10-20 01:11:22 | 15.9 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/history.json` | 2026-10-20 01:11:22 | 2026-10-20 01:11:22 | 14.6 KB | 旧 episode 决策/执行历史。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/prediction_004.json` | 2026-10-20 01:10:43 | 2026-10-20 01:10:43 | 2.3 KB | 封存预测记录。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/prediction_009.json` | 2026-10-20 01:10:55 | 2026-10-20 01:10:55 | 2.3 KB | 封存预测记录。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/public_input.json` | 2026-10-20 01:10:16 | 2026-10-20 01:10:16 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/request_001.json` | 2026-10-20 01:10:16 | 2026-10-20 01:10:16 | 13.2 KB | 模型请求快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/request_002.json` | 2026-10-20 01:10:44 | 2026-10-20 01:10:44 | 19.2 KB | 模型请求快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/request_003.json` | 2026-10-20 01:10:55 | 2026-10-20 01:10:55 | 23.0 KB | 模型请求快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/response_001.json` | 2026-10-20 01:10:43 | 2026-10-20 01:10:43 | 2.8 KB | 模型响应快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/response_002.json` | 2026-10-20 01:10:55 | 2026-10-20 01:10:55 | 2.8 KB | 模型响应快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/response_003.json` | 2026-10-20 01:11:22 | 2026-10-20 01:11:22 | 2.6 KB | 模型响应快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/result_001.json` | 2026-10-20 01:10:44 | 2026-10-20 01:10:44 | 6.3 KB | 实验工具执行结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/result_002.json` | 2026-10-20 01:10:55 | 2026-10-20 01:10:55 | 3.3 KB | 实验工具执行结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/score_001.json` | 2026-10-20 01:10:44 | 2026-10-20 01:10:44 | 7.2 KB | 预测评分结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/score_002.json` | 2026-10-20 01:10:55 | 2026-10-20 01:10:55 | 3.9 KB | 预测评分结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/state.json` | 2026-10-20 01:11:22 | 2026-10-20 01:11:22 | 728 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_a72e/summary.md` | 2026-10-20 01:11:22 | 2026-10-20 01:11:22 | 949 B | 旧 episode 摘要。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/cache/6bbf17ecb12bc42a5ab5e6ec5d1abed9aaa2db60ace256318fba42ad505a259b.json` | 2026-10-20 01:09:53 | 2026-10-20 01:09:53 | 2.7 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/cache/6e44672758872fc784ea911fb4962f49d75a9b7458fd38fedcf3911267fbc871.json` | 2026-10-20 01:10:16 | 2026-10-20 01:10:16 | 2.9 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/cache/80d8590e90abead8fa571e0df4e7642ebdd2ab40e3ad6e6411077e54152dce29.json` | 2026-10-20 01:09:26 | 2026-10-20 01:09:26 | 2.8 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/cache/a570fb252d6b72684de6c2c498b867c477e4e8dcc3241d05b6bea94cf5fb2462.json` | 2026-10-20 01:10:03 | 2026-10-20 01:10:03 | 2.8 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/config_snapshot.json` | 2026-10-20 01:09:11 | 2026-10-20 01:09:11 | 805 B | 旧 episode 配置快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/events.jsonl` | 2026-10-20 01:09:11 | 2026-10-20 01:10:16 | 9.6 KB | 哈希链事件日志。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/final.json` | 2026-10-20 01:10:16 | 2026-10-20 01:10:16 | 22.4 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/history.json` | 2026-10-20 01:10:16 | 2026-10-20 01:10:16 | 21.6 KB | 旧 episode 决策/执行历史。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/prediction_004.json` | 2026-10-20 01:09:26 | 2026-10-20 01:09:26 | 2.3 KB | 封存预测记录。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/prediction_009.json` | 2026-10-20 01:09:54 | 2026-10-20 01:09:54 | 2.2 KB | 封存预测记录。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/prediction_014.json` | 2026-10-20 01:10:03 | 2026-10-20 01:10:03 | 2.3 KB | 封存预测记录。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/public_input.json` | 2026-10-20 01:09:11 | 2026-10-20 01:09:11 | 4.2 KB | 旧合成案例的公开输入。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/request_001.json` | 2026-10-20 01:09:11 | 2026-10-20 01:09:11 | 13.2 KB | 模型请求快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/request_002.json` | 2026-10-20 01:09:27 | 2026-10-20 01:09:27 | 19.1 KB | 模型请求快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/request_003.json` | 2026-10-20 01:09:54 | 2026-10-20 01:09:54 | 23.8 KB | 模型请求快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/request_004.json` | 2026-10-20 01:10:03 | 2026-10-20 01:10:03 | 27.6 KB | 模型请求快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/response_001.json` | 2026-10-20 01:09:26 | 2026-10-20 01:09:26 | 2.8 KB | 模型响应快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/response_002.json` | 2026-10-20 01:09:53 | 2026-10-20 01:09:53 | 2.7 KB | 模型响应快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/response_003.json` | 2026-10-20 01:10:03 | 2026-10-20 01:10:03 | 2.8 KB | 模型响应快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/response_004.json` | 2026-10-20 01:10:16 | 2026-10-20 01:10:16 | 2.9 KB | 模型响应快照。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/result_001.json` | 2026-10-20 01:09:27 | 2026-10-20 01:09:27 | 6.3 KB | 实验工具执行结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/result_002.json` | 2026-10-20 01:09:54 | 2026-10-20 01:09:54 | 4.7 KB | 实验工具执行结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/result_003.json` | 2026-10-20 01:10:03 | 2026-10-20 01:10:03 | 3.3 KB | 实验工具执行结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/score_001.json` | 2026-10-20 01:09:27 | 2026-10-20 01:09:27 | 7.1 KB | 预测评分结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/score_002.json` | 2026-10-20 01:09:54 | 2026-10-20 01:09:54 | 5.4 KB | 预测评分结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/score_003.json` | 2026-10-20 01:10:03 | 2026-10-20 01:10:03 | 3.9 KB | 预测评分结果。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/state.json` | 2026-10-20 01:10:16 | 2026-10-20 01:10:16 | 762 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_c41a/summary.md` | 2026-10-20 01:10:16 | 2026-10-20 01:10:16 | 1.2 KB | 旧 episode 摘要。 |
| `runs/flash_20261020_0058/diagnostics/cases/case_specs_neutral.json` | 2026-10-20 01:09:11 | 2026-10-20 01:09:11 | 513 B | 中性别名案例规格（不进入模型 prompt）。 |
| `runs/flash_20261020_0058/diagnostics/cases/diagnostic_summary.json` | 2026-10-20 01:11:22 | 2026-10-20 01:11:22 | 4.0 KB | 运行产物 `diagnostic_summary.json`。 |
| `runs/flash_20261020_0058/diagnostics/diagnose_summary.json` | 2026-10-20 01:11:22 | 2026-10-20 01:11:22 | 13.3 KB | 诊断阶段汇总。 |
| `runs/flash_20261020_0058/diagnostics/regression/regression.json` | 2026-10-20 01:09:11 | 2026-10-20 01:09:11 | 8.9 KB | 解释回归的原始回答与规则检查。 |
| `runs/flash_20261020_0058/diagnostics/regression/regression_answer.md` | 2026-10-20 01:09:11 | 2026-10-20 01:09:11 | 6.9 KB | 解释回归原始回答。 |
| `runs/flash_20261020_0058/diagnostics/regression/regression_prompt.md` | 2026-10-20 01:08:27 | 2026-10-20 01:08:27 | 1.4 KB | 解释回归实际 prompt。 |
| `runs/flash_20261020_0058/diagnostics/regression/regression_review.md` | 2026-10-20 01:09:11 | 2026-10-20 01:09:11 | 1.0 KB | 解释回归规则检查说明。 |
| `runs/flash_20261020_0058/fallahi_contexts.txt` | 2026-10-20 01:21:18 | 2026-10-20 01:21:19 | 58.7 KB | 运行产物 `fallahi_contexts.txt`。 |
| `runs/flash_20261020_0058/fixture/artificial.csv` | 2026-10-20 01:25:11 | 2026-10-20 01:25:11 | 36.7 KB | 运行产物 `artificial.csv`。 |
| `runs/flash_20261020_0058/fixture_check.txt` | 2026-10-20 01:25:11 | 2026-10-20 01:25:11 | 4.6 KB | 人工夹具 CLI 输出。 |
| `runs/flash_20261020_0058/report_stdout.txt` | 2026-10-20 01:22:28 | 2026-10-20 01:22:28 | 2.6 KB | 运行产物 `report_stdout.txt`。 |
| `runs/flash_20261020_0058/research/literature_v1/events.jsonl` | 2026-10-20 01:11:46 | 2026-10-20 01:24:29 | 39.0 KB | 哈希链事件日志。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/index.json` | 2026-10-20 01:17:06 | 2026-10-20 01:17:06 | 4.4 KB | 该运行证据索引。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/injections.jsonl` | 2026-10-20 01:12:19 | 2026-10-20 01:17:10 | 3.8 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_200bb34828cd.json` | 2026-10-20 01:14:05 | 2026-10-20 01:14:05 | 116.6 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_200bb34828cd.md` | 2026-10-20 01:14:05 | 2026-10-20 01:14:05 | 111.9 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_2085e5b7ba26.json` | 2026-10-20 01:12:40 | 2026-10-20 01:12:40 | 92.5 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_2085e5b7ba26.md` | 2026-10-20 01:12:40 | 2026-10-20 01:12:40 | 85.5 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_2f5e3fadf9f0.json` | 2026-10-20 01:13:58 | 2026-10-20 01:13:58 | 102.5 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_2f5e3fadf9f0.md` | 2026-10-20 01:13:58 | 2026-10-20 01:13:58 | 96.9 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_825214c78a59.json` | 2026-10-20 01:13:26 | 2026-10-20 01:13:26 | 165.0 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_825214c78a59.md` | 2026-10-20 01:13:26 | 2026-10-20 01:13:26 | 149.6 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_8d41144afed7.json` | 2026-10-20 01:16:25 | 2026-10-20 01:16:25 | 39.1 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_8d41144afed7.md` | 2026-10-20 01:16:25 | 2026-10-20 01:16:25 | 36.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_9da221287269.json` | 2026-10-20 01:12:48 | 2026-10-20 01:12:48 | 9.9 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_9da221287269.md` | 2026-10-20 01:12:48 | 2026-10-20 01:12:48 | 8.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_a2ba747cdafd.json` | 2026-10-20 01:16:40 | 2026-10-20 01:16:40 | 119.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_a2ba747cdafd.md` | 2026-10-20 01:16:40 | 2026-10-20 01:16:40 | 95.5 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_a4cfb55eee84.json` | 2026-10-20 01:17:06 | 2026-10-20 01:17:06 | 3.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_a4cfb55eee84.md` | 2026-10-20 01:17:06 | 2026-10-20 01:17:06 | 3.1 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_b63c716fd707.json` | 2026-10-20 01:12:09 | 2026-10-20 01:12:09 | 106.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_b63c716fd707.md` | 2026-10-20 01:12:09 | 2026-10-20 01:12:09 | 100.6 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_f42fa7111e36.json` | 2026-10-20 01:12:14 | 2026-10-20 01:12:14 | 126.5 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/evidence/sources/ev_f42fa7111e36.md` | 2026-10-20 01:12:14 | 2026-10-20 01:12:14 | 119.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_20261020_0058/research/literature_v1/experiments/artificial_fixture.csv` | 2026-10-20 01:16:56 | 2026-10-20 01:16:56 | 36.7 KB | 人工夹具特征表（不是 EEG 数据）。 |
| `runs/flash_20261020_0058/research/literature_v1/experiments/fixture_split_check.json` | 2026-10-20 01:16:56 | 2026-10-20 01:16:56 | 2.3 KB | 人工夹具切分检查（不是 EEG 证据）。 |
| `runs/flash_20261020_0058/research/literature_v1/final.json` | 2026-10-20 01:18:13 | 2026-10-20 01:18:13 | 27.3 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/flash_20261020_0058/research/literature_v1/final_answer.md` | 2026-10-20 01:18:13 | 2026-10-20 01:18:13 | 21.2 KB | Scientist/诊断的原始最终回答（未被后续更正覆盖）。 |
| `runs/flash_20261020_0058/research/literature_v1/heartbeat.json` | 2026-10-20 01:24:29 | 2026-10-20 01:24:29 | 193 B | 进程/调用心跳。 |
| `runs/flash_20261020_0058/research/literature_v1/launch.txt` | 2026-10-20 01:11:44 | 2026-10-20 01:11:44 | 135 B | 启动命令和时间。 |
| `runs/flash_20261020_0058/research/literature_v1/messages.json` | 2026-10-20 01:18:14 | 2026-10-20 01:18:14 | 242.1 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_20261020_0058/research/literature_v1/pid.txt` | 2026-10-20 01:11:44 | 2026-10-20 01:11:44 | 7 B | 运行进程 ID。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_001.json` | 2026-10-20 01:11:52 | 2026-10-20 01:11:52 | 6.1 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_002.json` | 2026-10-20 01:12:03 | 2026-10-20 01:12:03 | 44.3 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_003.json` | 2026-10-20 01:12:19 | 2026-10-20 01:12:19 | 67.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_004.json` | 2026-10-20 01:12:53 | 2026-10-20 01:12:53 | 79.4 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_005.json` | 2026-10-20 01:12:58 | 2026-10-20 01:12:58 | 103.2 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_006.json` | 2026-10-20 01:13:31 | 2026-10-20 01:13:31 | 131.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_007.json` | 2026-10-20 01:14:08 | 2026-10-20 01:14:08 | 142.6 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_008.json` | 2026-10-20 01:14:12 | 2026-10-20 01:14:12 | 163.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_009.json` | 2026-10-20 01:14:16 | 2026-10-20 01:14:16 | 112.9 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_010.json` | 2026-10-20 01:14:25 | 2026-10-20 01:14:25 | 134.7 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_011.json` | 2026-10-20 01:14:34 | 2026-10-20 01:14:34 | 169.2 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_012.json` | 2026-10-20 01:16:34 | 2026-10-20 01:16:34 | 175.4 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_013.json` | 2026-10-20 01:16:42 | 2026-10-20 01:16:42 | 183.1 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_014.json` | 2026-10-20 01:16:59 | 2026-10-20 01:16:59 | 186.2 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_015.json` | 2026-10-20 01:17:10 | 2026-10-20 01:17:10 | 189.1 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/requests/request_016.json` | 2026-10-20 01:18:13 | 2026-10-20 01:18:13 | 197.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_001.json` | 2026-10-20 01:11:52 | 2026-10-20 01:11:52 | 9.2 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_002.json` | 2026-10-20 01:12:03 | 2026-10-20 01:12:03 | 9.6 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_003.json` | 2026-10-20 01:12:19 | 2026-10-20 01:12:19 | 4.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_004.json` | 2026-10-20 01:12:53 | 2026-10-20 01:12:53 | 7.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_005.json` | 2026-10-20 01:12:58 | 2026-10-20 01:12:58 | 7.3 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_006.json` | 2026-10-20 01:13:31 | 2026-10-20 01:13:31 | 3.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_007.json` | 2026-10-20 01:14:08 | 2026-10-20 01:14:08 | 4.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_008.json` | 2026-10-20 01:14:12 | 2026-10-20 01:14:12 | 4.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_009.json` | 2026-10-20 01:14:16 | 2026-10-20 01:14:16 | 4.2 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_010.json` | 2026-10-20 01:14:25 | 2026-10-20 01:14:25 | 12.9 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_011.json` | 2026-10-20 01:14:34 | 2026-10-20 01:14:34 | 9.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_012.json` | 2026-10-20 01:16:34 | 2026-10-20 01:16:34 | 12.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_013.json` | 2026-10-20 01:16:42 | 2026-10-20 01:16:42 | 2.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_014.json` | 2026-10-20 01:16:59 | 2026-10-20 01:16:59 | 4.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_015.json` | 2026-10-20 01:17:10 | 2026-10-20 01:17:10 | 5.2 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/responses/response_016.json` | 2026-10-20 01:18:13 | 2026-10-20 01:18:13 | 91.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_20261020_0058/research/literature_v1/scientist_input.md` | 2026-10-20 01:11:46 | 2026-10-20 01:11:46 | 6.0 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_20261020_0058/research/literature_v1/searches/search_001.json` | 2026-10-20 01:11:53 | 2026-10-20 01:11:53 | 52.6 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/searches/search_002.json` | 2026-10-20 01:11:55 | 2026-10-20 01:11:55 | 62.2 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/searches/search_003.json` | 2026-10-20 01:11:56 | 2026-10-20 01:11:56 | 35.8 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/searches/search_004.json` | 2026-10-20 01:12:15 | 2026-10-20 01:12:15 | 30.6 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/searches/search_005.json` | 2026-10-20 01:12:16 | 2026-10-20 01:12:16 | 57.1 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/searches/search_006.json` | 2026-10-20 01:13:27 | 2026-10-20 01:13:27 | 57.2 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/searches/search_007.json` | 2026-10-20 01:13:28 | 2026-10-20 01:13:28 | 56.3 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/searches/search_008.json` | 2026-10-20 01:14:26 | 2026-10-20 01:14:26 | 25.4 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/state.json` | 2026-10-20 01:24:29 | 2026-10-20 01:24:29 | 514 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_20261020_0058/research/literature_v1/stderr.log` | 2026-10-20 01:11:44 | 2026-10-20 01:11:46 | 277 B | 运行 stderr 日志。 |
| `runs/flash_20261020_0058/research/literature_v1/stdout.log` | 2026-10-20 01:11:44 | 2026-10-20 01:18:14 | 1.4 KB | 运行 stdout 日志。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_001.json` | 2026-10-20 01:12:09 | 2026-10-20 01:12:09 | 106.7 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_002.json` | 2026-10-20 01:12:14 | 2026-10-20 01:12:14 | 126.5 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_003.json` | 2026-10-20 01:12:40 | 2026-10-20 01:12:40 | 92.4 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_004.json` | 2026-10-20 01:12:48 | 2026-10-20 01:12:48 | 9.8 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_005.json` | 2026-10-20 01:13:26 | 2026-10-20 01:13:26 | 164.9 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_006.json` | 2026-10-20 01:13:58 | 2026-10-20 01:13:58 | 102.5 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_007.json` | 2026-10-20 01:14:05 | 2026-10-20 01:14:05 | 116.5 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_008.json` | 2026-10-20 01:16:25 | 2026-10-20 01:16:25 | 39.1 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_009.json` | 2026-10-20 01:16:40 | 2026-10-20 01:16:40 | 119.1 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/research/literature_v1/tool_results/fetch_010.json` | 2026-10-20 01:17:06 | 2026-10-20 01:17:06 | 3.3 KB | 该运行的抓取工具结果快照。 |
| `runs/flash_20261020_0058/resume_check.txt` | 2026-10-20 01:24:29 | 2026-10-20 01:24:29 | 4.2 KB | 运行产物 `resume_check.txt`。 |
| `runs/flash_20261020_0058/source_heads.txt` | 2026-10-20 01:21:53 | 2026-10-20 01:21:53 | 19.6 KB | 运行产物 `source_heads.txt`。 |
| `runs/flash_emotion_20261021/budget.json` | 2026-10-21 09:44:37 | 2026-10-21 09:44:37 | 51.4 KB | 该研究/运行的预算账本。 |
| `runs/flash_emotion_20261021/evaluate_final.log` | 2026-10-21 09:46:19 | 2026-10-21 09:46:21 | 32.2 KB | 运行产物 `evaluate_final.log`。 |
| `runs/flash_emotion_20261021/evaluate_final2.log` | 2026-10-21 11:57:00 | 2026-10-21 11:57:02 | 32.1 KB | 最终格式/完整性检查日志。 |
| `runs/flash_emotion_20261021/evaluate_selection.log` | 2026-10-21 11:55:19 | 2026-10-21 11:55:21 | 32.1 KB | 首次 accepted 重评日志。 |
| `runs/flash_emotion_20261021/evaluate_stdout.log` | 2026-10-21 09:44:12 | 2026-10-21 09:44:12 | 9.6 KB | 运行产物 `evaluate_stdout.log`。 |
| `runs/flash_emotion_20261021/materials/evidence/index.json` | 2026-10-21 09:29:04 | 2026-10-21 09:29:04 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:28:19 | 2026-10-21 09:28:19 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_580a39dd545d.md` | 2026-10-21 09:28:19 | 2026-10-21 09:28:19 | 89.0 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:28:07 | 2026-10-21 09:28:07 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_6619560afa7e.md` | 2026-10-21 09:28:07 | 2026-10-21 09:28:07 | 35.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:27:49 | 2026-10-21 09:27:49 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_74eaf4bc0082.md` | 2026-10-21 09:27:49 | 2026-10-21 09:27:49 | 50.0 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:28:15 | 2026-10-21 09:28:15 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_97eaa43a3d81.md` | 2026-10-21 09:28:15 | 2026-10-21 09:28:15 | 33.9 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:28:37 | 2026-10-21 09:28:37 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_c908ef06754c.md` | 2026-10-21 09:28:37 | 2026-10-21 09:28:37 | 4.1 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:27:57 | 2026-10-21 09:27:57 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_d3f89ccca87f.md` | 2026-10-21 09:27:57 | 2026-10-21 09:27:57 | 67.9 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:29:04 | 2026-10-21 09:29:04 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/evidence/sources/ev_fad98f5a28bb.md` | 2026-10-21 09:29:04 | 2026-10-21 09:29:04 | 43.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/materials/fetch_attempts.json` | 2026-10-21 09:29:04 | 2026-10-21 09:29:04 | 3.2 KB | 材料抓取尝试与预算记录。 |
| `runs/flash_emotion_20261021/materials/inspection.txt` | 2026-10-21 09:29:14 | 2026-10-21 09:29:14 | 83.9 KB | 材料正文检索/数字核对记录。 |
| `runs/flash_emotion_20261021/materials/inspection3.txt` | 2026-10-21 09:29:20 | 2026-10-21 09:29:20 | 29.8 KB | 材料准备阶段产物 `inspection3.txt`。 |
| `runs/flash_emotion_20261021/materials/searches/search_01.json` | 2026-10-21 09:27:17 | 2026-10-21 09:27:17 | 83.3 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_emotion_20261021/materials/searches/search_02.json` | 2026-10-21 09:27:18 | 2026-10-21 09:27:18 | 70.8 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_emotion_20261021/materials/searches/search_03.json` | 2026-10-21 09:27:19 | 2026-10-21 09:27:19 | 61.8 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_emotion_20261021/materials/searches/search_04.json` | 2026-10-21 09:27:21 | 2026-10-21 09:27:21 | 71.5 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_emotion_20261021/materials/searches/search_05.json` | 2026-10-21 09:27:29 | 2026-10-21 09:27:29 | 76.0 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_emotion_20261021/materials/searches/search_06.json` | 2026-10-21 09:27:30 | 2026-10-21 09:27:30 | 71.7 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_emotion_20261021/materials/searches/search_07.json` | 2026-10-21 09:27:32 | 2026-10-21 09:27:32 | 95.8 KB | 该运行的搜索请求/结果快照。 |
| `runs/flash_emotion_20261021/meta/META_REVIEW.md` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 225 B | Meta 决策说明。 |
| `runs/flash_emotion_20261021/meta/meta_decision.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 1.4 KB | Meta 结构验收结果（规则或 no_update）。 |
| `runs/flash_emotion_20261021/meta/meta_input.json` | 2026-10-21 09:32:10 | 2026-10-21 09:32:10 | 38.7 KB | Meta 的独立输入（旧轨迹+标注评审反馈）。 |
| `runs/flash_emotion_20261021/meta/meta_response.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 11.9 KB | Meta 原始响应与 usage。 |
| `runs/flash_emotion_20261021/meta/meta_rule.md` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 530 B | 冻结的 Meta 规则文本。 |
| `runs/flash_emotion_20261021/meta/rule_snapshots/emotion_baseline_v1+meta_98dc75d5b5.md` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 2.1 KB | Meta 阶段产物 `emotion_baseline_v1+meta_98dc75d5b5.md`。 |
| `runs/flash_emotion_20261021/proposal_numeric_audit.txt` | 2026-10-21 11:55:37 | 2026-10-21 11:55:37 | 14.4 KB | 提案关键数字源文检索记录。 |
| `runs/flash_emotion_20261021/proposal_numeric_audit2.txt` | 2026-10-21 11:55:41 | 2026-10-21 11:55:41 | 15.3 KB | 归一化后数字检索记录。 |
| `runs/flash_emotion_20261021/retry2_launch.txt` | 2026-10-21 09:41:25 | 2026-10-21 09:41:25 | 53 B | 运行产物 `retry2_launch.txt`。 |
| `runs/flash_emotion_20261021/retry2_pid.txt` | 2026-10-21 09:41:25 | 2026-10-21 09:41:25 | 7 B | 运行产物 `retry2_pid.txt`。 |
| `runs/flash_emotion_20261021/retry2_stderr.log` | 2026-10-21 09:41:25 | 2026-10-21 09:41:25 | 0 B | 运行产物 `retry2_stderr.log`。 |
| `runs/flash_emotion_20261021/retry2_stdout.log` | 2026-10-21 09:41:25 | 2026-10-21 09:44:37 | 6.9 KB | 运行产物 `retry2_stdout.log`。 |
| `runs/flash_emotion_20261021/retry_launch.txt` | 2026-10-21 09:36:13 | 2026-10-21 09:36:13 | 52 B | 运行产物 `retry_launch.txt`。 |
| `runs/flash_emotion_20261021/retry_pid.txt` | 2026-10-21 09:36:13 | 2026-10-21 09:36:13 | 6 B | 运行产物 `retry_pid.txt`。 |
| `runs/flash_emotion_20261021/retry_stderr.log` | 2026-10-21 09:36:13 | 2026-10-21 09:36:13 | 0 B | 运行产物 `retry_stderr.log`。 |
| `runs/flash_emotion_20261021/retry_stdout.log` | 2026-10-21 09:36:13 | 2026-10-21 09:39:38 | 5.2 KB | 运行产物 `retry_stdout.log`。 |
| `runs/flash_emotion_20261021/reviews/FORMAT_INTEGRITY_CHECK.md` | 2026-10-21 11:57:02 | 2026-10-21 11:57:02 | 1.4 KB | ('自动格式/轨迹完整性检查，不是科学评分。',) |
| `runs/flash_emotion_20261021/reviews/INITIAL_REVIEW.md` | 2026-10-21 11:57:02 | 2026-10-21 11:57:02 | 1.4 KB | ('自动格式/轨迹完整性检查，不是科学评分。',) |
| `runs/flash_emotion_20261021/reviews/KEY.json` | 2026-10-21 11:57:02 | 2026-10-21 11:57:02 | 1.1 KB | ('盲评提案的未盲 key（评分后再打开）。',) |
| `runs/flash_emotion_20261021/reviews/README.md` | 2026-10-21 11:57:02 | 2026-10-21 11:57:02 | 516 B | ('盲评说明。',) |
| `runs/flash_emotion_20261021/reviews/blinded/proposal_01.md` | 2026-10-21 11:57:02 | 2026-10-21 11:57:02 | 10.9 KB | 隐藏模型/规则组标识的盲评提案副本。 |
| `runs/flash_emotion_20261021/reviews/blinded/proposal_02.md` | 2026-10-21 11:57:02 | 2026-10-21 11:57:02 | 15.3 KB | 隐藏模型/规则组标识的盲评提案副本。 |
| `runs/flash_emotion_20261021/reviews/blinded/proposal_03.md` | 2026-10-21 11:57:02 | 2026-10-21 11:57:02 | 12.8 KB | 隐藏模型/规则组标识的盲评提案副本。 |
| `runs/flash_emotion_20261021/reviews/blinded/proposal_04.md` | 2026-10-21 11:57:02 | 2026-10-21 11:57:02 | 9.6 KB | 隐藏模型/规则组标识的盲评提案副本。 |
| `runs/flash_emotion_20261021/reviews/evaluation.json` | 2026-10-21 11:57:02 | 2026-10-21 11:57:02 | 16.1 KB | ('提案评估的机器可读汇总。',) |
| `runs/flash_emotion_20261021/run_launch.txt` | 2026-10-21 09:32:08 | 2026-10-21 09:32:08 | 106 B | 运行产物 `run_launch.txt`。 |
| `runs/flash_emotion_20261021/run_pid.txt` | 2026-10-21 09:32:08 | 2026-10-21 09:32:08 | 6 B | 运行产物 `run_pid.txt`。 |
| `runs/flash_emotion_20261021/run_stderr.log` | 2026-10-21 09:32:08 | 2026-10-21 09:32:08 | 0 B | 运行产物 `run_stderr.log`。 |
| `runs/flash_emotion_20261021/run_stdout.log` | 2026-10-21 09:32:08 | 2026-10-21 09:34:31 | 3.6 KB | 运行产物 `run_stdout.log`。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/events.jsonl` | 2026-10-21 09:32:17 | 2026-10-21 09:33:39 | 12.1 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/evidence/index.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/evidence/injections.jsonl` | 2026-10-21 09:32:20 | 2026-10-21 09:32:34 | 2.0 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/final.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 21.4 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/final_answer.md` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 15.2 KB | Scientist/诊断的原始最终回答（未被后续更正覆盖）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/heartbeat.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 191 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/messages.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 132.2 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/requests/request_001.json` | 2026-10-21 09:32:19 | 2026-10-21 09:32:19 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/requests/request_002.json` | 2026-10-21 09:32:22 | 2026-10-21 09:32:22 | 21.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/requests/request_003.json` | 2026-10-21 09:32:25 | 2026-10-21 09:32:25 | 37.0 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/requests/request_004.json` | 2026-10-21 09:32:28 | 2026-10-21 09:32:28 | 52.6 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/requests/request_005.json` | 2026-10-21 09:32:34 | 2026-10-21 09:32:34 | 70.0 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/requests/request_006.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 85.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/responses/response_001.json` | 2026-10-21 09:32:19 | 2026-10-21 09:32:19 | 2.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/responses/response_002.json` | 2026-10-21 09:32:22 | 2026-10-21 09:32:22 | 3.1 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/responses/response_003.json` | 2026-10-21 09:32:25 | 2026-10-21 09:32:25 | 3.6 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/responses/response_004.json` | 2026-10-21 09:32:28 | 2026-10-21 09:32:28 | 3.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/responses/response_005.json` | 2026-10-21 09:32:34 | 2026-10-21 09:32:34 | 8.6 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/responses/response_006.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 94.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/rules/emotion_baseline_v1.md` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 1.6 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/run_manifest.json` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 14.2 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/scientist_input.md` | 2026-10-21 09:32:17 | 2026-10-21 09:32:17 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_01/state.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 570 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/events.jsonl` | 2026-10-21 09:33:39 | 2026-10-21 09:33:54 | 14.1 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/evidence/index.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/evidence/injections.jsonl` | 2026-10-21 09:33:41 | 2026-10-21 09:33:54 | 2.8 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/heartbeat.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 189 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/messages.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 113.5 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/requests/request_001.json` | 2026-10-21 09:33:41 | 2026-10-21 09:33:41 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/requests/request_002.json` | 2026-10-21 09:33:43 | 2026-10-21 09:33:43 | 21.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/requests/request_003.json` | 2026-10-21 09:33:45 | 2026-10-21 09:33:45 | 37.0 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/requests/request_004.json` | 2026-10-21 09:33:47 | 2026-10-21 09:33:47 | 52.1 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/requests/request_005.json` | 2026-10-21 09:33:50 | 2026-10-21 09:33:50 | 67.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/requests/request_006.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 88.0 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/responses/response_001.json` | 2026-10-21 09:33:41 | 2026-10-21 09:33:41 | 2.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/responses/response_002.json` | 2026-10-21 09:33:43 | 2026-10-21 09:33:43 | 2.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/responses/response_003.json` | 2026-10-21 09:33:45 | 2026-10-21 09:33:45 | 2.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/responses/response_004.json` | 2026-10-21 09:33:47 | 2026-10-21 09:33:47 | 2.6 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/responses/response_005.json` | 2026-10-21 09:33:50 | 2026-10-21 09:33:50 | 4.9 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/responses/response_006.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 4.4 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/rules/emotion_baseline_v1.md` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 1.6 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/run_manifest.json` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 14.2 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/scientist_input.md` | 2026-10-21 09:33:39 | 2026-10-21 09:33:39 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02/state.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 593 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/events.jsonl` | 2026-10-21 09:36:14 | 2026-10-21 09:37:33 | 12.1 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/evidence/index.json` | 2026-10-21 09:36:14 | 2026-10-21 09:36:14 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/evidence/injections.jsonl` | 2026-10-21 09:36:17 | 2026-10-21 09:36:37 | 2.0 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:36:14 | 2026-10-21 09:36:14 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:36:14 | 2026-10-21 09:36:14 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:36:14 | 2026-10-21 09:36:14 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:36:14 | 2026-10-21 09:36:14 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:36:14 | 2026-10-21 09:36:14 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:36:14 | 2026-10-21 09:36:14 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:36:14 | 2026-10-21 09:36:14 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/final.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 16.9 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/final_answer.md` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 10.8 KB | Scientist/诊断的原始最终回答（未被后续更正覆盖）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/heartbeat.json` | 2026-10-21 09:36:37 | 2026-10-21 09:36:37 | 197 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/messages.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 120.5 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/requests/request_001.json` | 2026-10-21 09:36:16 | 2026-10-21 09:36:16 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/requests/request_002.json` | 2026-10-21 09:36:19 | 2026-10-21 09:36:19 | 21.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/requests/request_003.json` | 2026-10-21 09:36:22 | 2026-10-21 09:36:22 | 37.1 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/requests/request_004.json` | 2026-10-21 09:36:32 | 2026-10-21 09:36:32 | 52.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/requests/request_005.json` | 2026-10-21 09:36:37 | 2026-10-21 09:36:37 | 68.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/requests/request_006.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 82.4 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/responses/response_001.json` | 2026-10-21 09:36:16 | 2026-10-21 09:36:16 | 2.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/responses/response_002.json` | 2026-10-21 09:36:19 | 2026-10-21 09:36:19 | 3.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/responses/response_003.json` | 2026-10-21 09:36:22 | 2026-10-21 09:36:22 | 3.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/responses/response_004.json` | 2026-10-21 09:36:32 | 2026-10-21 09:36:32 | 3.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/responses/response_005.json` | 2026-10-21 09:36:37 | 2026-10-21 09:36:37 | 6.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/responses/response_006.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 77.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/rules/emotion_baseline_v1.md` | 2026-10-21 09:36:14 | 2026-10-21 09:36:14 | 1.6 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/run_manifest.json` | 2026-10-21 09:36:15 | 2026-10-21 09:36:15 | 14.4 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/scientist_input.md` | 2026-10-21 09:36:15 | 2026-10-21 09:36:15 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry/state.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 584 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/events.jsonl` | 2026-10-21 09:41:27 | 2026-10-21 09:42:35 | 13.9 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/evidence/index.json` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/evidence/injections.jsonl` | 2026-10-21 09:41:29 | 2026-10-21 09:42:01 | 2.4 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/final.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 17.0 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/final_answer.md` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 10.9 KB | Scientist/诊断的原始最终回答（未被后续更正覆盖）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/heartbeat.json` | 2026-10-21 09:42:01 | 2026-10-21 09:42:01 | 198 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/messages.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 129.0 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/requests/request_001.json` | 2026-10-21 09:41:29 | 2026-10-21 09:41:29 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/requests/request_002.json` | 2026-10-21 09:41:32 | 2026-10-21 09:41:32 | 21.7 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/requests/request_003.json` | 2026-10-21 09:41:34 | 2026-10-21 09:41:34 | 37.1 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/requests/request_004.json` | 2026-10-21 09:41:37 | 2026-10-21 09:41:37 | 52.4 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/requests/request_005.json` | 2026-10-21 09:41:40 | 2026-10-21 09:41:40 | 68.4 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/requests/request_006.json` | 2026-10-21 09:42:01 | 2026-10-21 09:42:01 | 84.0 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/requests/request_007.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 107.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/responses/response_001.json` | 2026-10-21 09:41:29 | 2026-10-21 09:41:29 | 2.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/responses/response_002.json` | 2026-10-21 09:41:32 | 2026-10-21 09:41:32 | 3.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/responses/response_003.json` | 2026-10-21 09:41:34 | 2026-10-21 09:41:34 | 3.4 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/responses/response_004.json` | 2026-10-21 09:41:37 | 2026-10-21 09:41:37 | 3.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/responses/response_005.json` | 2026-10-21 09:41:40 | 2026-10-21 09:41:40 | 3.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/responses/response_006.json` | 2026-10-21 09:42:01 | 2026-10-21 09:42:01 | 28.3 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/responses/response_007.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 43.9 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/rules/emotion_baseline_v1.md` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 1.6 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/run_manifest.json` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 14.4 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/scientist_input.md` | 2026-10-21 09:41:27 | 2026-10-21 09:41:27 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/baseline/repeat_02__retry2/state.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 614 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/events.jsonl` | 2026-10-21 09:33:54 | 2026-10-21 09:34:09 | 13.7 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/evidence/index.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/evidence/injections.jsonl` | 2026-10-21 09:33:56 | 2026-10-21 09:34:09 | 2.8 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/heartbeat.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 189 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/messages.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 115.5 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/requests/request_001.json` | 2026-10-21 09:33:56 | 2026-10-21 09:33:56 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/requests/request_002.json` | 2026-10-21 09:33:58 | 2026-10-21 09:33:58 | 29.1 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/requests/request_003.json` | 2026-10-21 09:34:02 | 2026-10-21 09:34:02 | 51.7 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/requests/request_004.json` | 2026-10-21 09:34:05 | 2026-10-21 09:34:05 | 76.0 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/requests/request_005.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 99.6 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/responses/response_001.json` | 2026-10-21 09:33:56 | 2026-10-21 09:33:56 | 3.4 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/responses/response_002.json` | 2026-10-21 09:33:58 | 2026-10-21 09:33:58 | 2.9 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/responses/response_003.json` | 2026-10-21 09:34:02 | 2026-10-21 09:34:02 | 5.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/responses/response_004.json` | 2026-10-21 09:34:05 | 2026-10-21 09:34:05 | 3.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/responses/response_005.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 5.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/rules/emotion_baseline_v1+meta_98dc75d5b5.md` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 2.1 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/run_manifest.json` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 14.4 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/scientist_input.md` | 2026-10-21 09:33:54 | 2026-10-21 09:33:54 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01/state.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 594 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/events.jsonl` | 2026-10-21 09:37:33 | 2026-10-21 09:38:18 | 14.8 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/evidence/index.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/evidence/injections.jsonl` | 2026-10-21 09:37:35 | 2026-10-21 09:38:18 | 2.8 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/heartbeat.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 189 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/messages.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 132.9 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/requests/request_001.json` | 2026-10-21 09:37:35 | 2026-10-21 09:37:35 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/requests/request_002.json` | 2026-10-21 09:37:38 | 2026-10-21 09:37:38 | 21.6 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/requests/request_003.json` | 2026-10-21 09:37:40 | 2026-10-21 09:37:40 | 36.9 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/requests/request_004.json` | 2026-10-21 09:37:43 | 2026-10-21 09:37:43 | 52.3 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/requests/request_005.json` | 2026-10-21 09:37:46 | 2026-10-21 09:37:46 | 68.4 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/requests/request_006.json` | 2026-10-21 09:37:49 | 2026-10-21 09:37:49 | 86.4 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/requests/request_007.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 101.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/responses/response_001.json` | 2026-10-21 09:37:35 | 2026-10-21 09:37:35 | 2.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/responses/response_002.json` | 2026-10-21 09:37:38 | 2026-10-21 09:37:38 | 3.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/responses/response_003.json` | 2026-10-21 09:37:40 | 2026-10-21 09:37:40 | 2.9 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/responses/response_004.json` | 2026-10-21 09:37:43 | 2026-10-21 09:37:43 | 3.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/responses/response_005.json` | 2026-10-21 09:37:46 | 2026-10-21 09:37:46 | 4.1 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/responses/response_006.json` | 2026-10-21 09:37:49 | 2026-10-21 09:37:49 | 3.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/responses/response_007.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 41.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/rules/emotion_baseline_v1+meta_98dc75d5b5.md` | 2026-10-21 09:37:33 | 2026-10-21 09:37:33 | 2.1 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/run_manifest.json` | 2026-10-21 09:37:34 | 2026-10-21 09:37:34 | 14.5 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/scientist_input.md` | 2026-10-21 09:37:34 | 2026-10-21 09:37:34 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry/state.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 592 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/events.jsonl` | 2026-10-21 09:42:35 | 2026-10-21 09:43:31 | 12.1 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/evidence/index.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/evidence/injections.jsonl` | 2026-10-21 09:42:37 | 2026-10-21 09:42:47 | 2.0 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/final.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 15.5 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/final_answer.md` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 9.5 KB | Scientist/诊断的原始最终回答（未被后续更正覆盖）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/heartbeat.json` | 2026-10-21 09:42:47 | 2026-10-21 09:42:47 | 198 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/messages.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 113.0 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/requests/request_001.json` | 2026-10-21 09:42:37 | 2026-10-21 09:42:37 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/requests/request_002.json` | 2026-10-21 09:42:39 | 2026-10-21 09:42:39 | 21.7 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/requests/request_003.json` | 2026-10-21 09:42:41 | 2026-10-21 09:42:41 | 36.9 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/requests/request_004.json` | 2026-10-21 09:42:44 | 2026-10-21 09:42:44 | 53.2 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/requests/request_005.json` | 2026-10-21 09:42:47 | 2026-10-21 09:42:47 | 69.2 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/requests/request_006.json` | 2026-10-21 09:43:30 | 2026-10-21 09:43:30 | 83.3 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/responses/response_001.json` | 2026-10-21 09:42:37 | 2026-10-21 09:42:37 | 2.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/responses/response_002.json` | 2026-10-21 09:42:39 | 2026-10-21 09:42:39 | 2.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/responses/response_003.json` | 2026-10-21 09:42:41 | 2026-10-21 09:42:41 | 2.9 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/responses/response_004.json` | 2026-10-21 09:42:44 | 2026-10-21 09:42:44 | 3.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/responses/response_005.json` | 2026-10-21 09:42:47 | 2026-10-21 09:42:47 | 5.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/responses/response_006.json` | 2026-10-21 09:43:30 | 2026-10-21 09:43:30 | 60.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/rules/emotion_baseline_v1+meta_98dc75d5b5.md` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 2.1 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/run_manifest.json` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 14.5 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/scientist_input.md` | 2026-10-21 09:42:35 | 2026-10-21 09:42:35 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_01__retry2/state.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 616 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/events.jsonl` | 2026-10-21 09:34:09 | 2026-10-21 09:34:31 | 14.6 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/evidence/index.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/evidence/injections.jsonl` | 2026-10-21 09:34:11 | 2026-10-21 09:34:31 | 2.8 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/heartbeat.json` | 2026-10-21 09:34:31 | 2026-10-21 09:34:31 | 189 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/messages.json` | 2026-10-21 09:34:31 | 2026-10-21 09:34:31 | 115.1 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/requests/request_001.json` | 2026-10-21 09:34:11 | 2026-10-21 09:34:11 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/requests/request_002.json` | 2026-10-21 09:34:15 | 2026-10-21 09:34:15 | 21.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/requests/request_003.json` | 2026-10-21 09:34:18 | 2026-10-21 09:34:18 | 38.0 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/requests/request_004.json` | 2026-10-21 09:34:20 | 2026-10-21 09:34:20 | 54.3 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/requests/request_005.json` | 2026-10-21 09:34:24 | 2026-10-21 09:34:24 | 70.3 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/requests/request_006.json` | 2026-10-21 09:34:27 | 2026-10-21 09:34:27 | 90.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/requests/request_007.json` | 2026-10-21 09:34:31 | 2026-10-21 09:34:31 | 106.4 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/responses/response_001.json` | 2026-10-21 09:34:11 | 2026-10-21 09:34:11 | 2.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/responses/response_002.json` | 2026-10-21 09:34:15 | 2026-10-21 09:34:15 | 4.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/responses/response_003.json` | 2026-10-21 09:34:18 | 2026-10-21 09:34:18 | 4.6 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/responses/response_004.json` | 2026-10-21 09:34:20 | 2026-10-21 09:34:20 | 2.9 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/responses/response_005.json` | 2026-10-21 09:34:24 | 2026-10-21 09:34:24 | 5.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/responses/response_006.json` | 2026-10-21 09:34:27 | 2026-10-21 09:34:27 | 4.3 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/responses/response_007.json` | 2026-10-21 09:34:31 | 2026-10-21 09:34:31 | 4.8 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/rules/emotion_baseline_v1+meta_98dc75d5b5.md` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 2.1 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/run_manifest.json` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 14.4 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/scientist_input.md` | 2026-10-21 09:34:09 | 2026-10-21 09:34:09 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02/state.json` | 2026-10-21 09:34:31 | 2026-10-21 09:34:31 | 594 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/events.jsonl` | 2026-10-21 09:38:18 | 2026-10-21 09:39:38 | 12.8 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/evidence/index.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/evidence/injections.jsonl` | 2026-10-21 09:38:20 | 2026-10-21 09:38:34 | 2.2 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/final.json` | 2026-10-21 09:39:38 | 2026-10-21 09:39:38 | 19.0 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/final_answer.md` | 2026-10-21 09:39:38 | 2026-10-21 09:39:38 | 12.7 KB | Scientist/诊断的原始最终回答（未被后续更正覆盖）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/heartbeat.json` | 2026-10-21 09:38:34 | 2026-10-21 09:38:34 | 197 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/messages.json` | 2026-10-21 09:39:38 | 2026-10-21 09:39:38 | 130.1 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/requests/request_001.json` | 2026-10-21 09:38:20 | 2026-10-21 09:38:20 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/requests/request_002.json` | 2026-10-21 09:38:23 | 2026-10-21 09:38:23 | 19.6 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/requests/request_003.json` | 2026-10-21 09:38:26 | 2026-10-21 09:38:26 | 35.2 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/requests/request_004.json` | 2026-10-21 09:38:29 | 2026-10-21 09:38:29 | 49.2 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/requests/request_005.json` | 2026-10-21 09:38:34 | 2026-10-21 09:38:34 | 64.7 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/requests/request_006.json` | 2026-10-21 09:39:38 | 2026-10-21 09:39:38 | 89.1 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/responses/response_001.json` | 2026-10-21 09:38:20 | 2026-10-21 09:38:20 | 2.6 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/responses/response_002.json` | 2026-10-21 09:38:23 | 2026-10-21 09:38:23 | 3.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/responses/response_003.json` | 2026-10-21 09:38:26 | 2026-10-21 09:38:26 | 3.2 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/responses/response_004.json` | 2026-10-21 09:38:29 | 2026-10-21 09:38:29 | 3.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/responses/response_005.json` | 2026-10-21 09:38:34 | 2026-10-21 09:38:34 | 7.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/responses/response_006.json` | 2026-10-21 09:39:38 | 2026-10-21 09:39:38 | 83.4 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/rules/emotion_baseline_v1+meta_98dc75d5b5.md` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 2.1 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/run_manifest.json` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 14.5 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/scientist_input.md` | 2026-10-21 09:38:18 | 2026-10-21 09:38:18 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry/state.json` | 2026-10-21 09:39:38 | 2026-10-21 09:39:38 | 586 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/events.jsonl` | 2026-10-21 09:43:31 | 2026-10-21 09:44:37 | 16.0 KB | 哈希链事件日志。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/evidence/index.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 3.3 KB | 该运行证据索引。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/evidence/injections.jsonl` | 2026-10-21 09:43:33 | 2026-10-21 09:43:59 | 2.8 KB | 该运行逐次读取/注入记录。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/evidence/sources/ev_580a39dd545d.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 97.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/evidence/sources/ev_6619560afa7e.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 37.7 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/evidence/sources/ev_74eaf4bc0082.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 53.2 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/evidence/sources/ev_97eaa43a3d81.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 35.3 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/evidence/sources/ev_c908ef06754c.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 4.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/evidence/sources/ev_d3f89ccca87f.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 71.8 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/evidence/sources/ev_fad98f5a28bb.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 46.4 KB | 该运行读取的公开来源快照（JSON，含正文/哈希）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/final.json` | 2026-10-21 09:44:37 | 2026-10-21 09:44:37 | 18.2 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/final_answer.md` | 2026-10-21 09:44:37 | 2026-10-21 09:44:37 | 11.4 KB | Scientist/诊断的原始最终回答（未被后续更正覆盖）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/heartbeat.json` | 2026-10-21 09:43:59 | 2026-10-21 09:43:59 | 198 B | 进程/调用心跳。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/messages.json` | 2026-10-21 09:44:37 | 2026-10-21 09:44:37 | 149.0 KB | 模型实际消息序列（含 reasoning_content 与 tool_call_id）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/requests/request_001.json` | 2026-10-21 09:43:33 | 2026-10-21 09:43:33 | 6.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/requests/request_002.json` | 2026-10-21 09:43:36 | 2026-10-21 09:43:36 | 21.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/requests/request_003.json` | 2026-10-21 09:43:38 | 2026-10-21 09:43:38 | 37.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/requests/request_004.json` | 2026-10-21 09:43:41 | 2026-10-21 09:43:41 | 52.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/requests/request_005.json` | 2026-10-21 09:43:44 | 2026-10-21 09:43:44 | 69.2 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/requests/request_006.json` | 2026-10-21 09:43:57 | 2026-10-21 09:43:57 | 83.8 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/requests/request_007.json` | 2026-10-21 09:43:59 | 2026-10-21 09:43:59 | 106.1 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/requests/request_008.json` | 2026-10-21 09:44:37 | 2026-10-21 09:44:37 | 122.5 KB | 模型请求快照（消息、工具列表、时间）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/responses/response_001.json` | 2026-10-21 09:43:33 | 2026-10-21 09:43:33 | 2.7 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/responses/response_002.json` | 2026-10-21 09:43:36 | 2026-10-21 09:43:36 | 4.3 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/responses/response_003.json` | 2026-10-21 09:43:38 | 2026-10-21 09:43:38 | 2.6 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/responses/response_004.json` | 2026-10-21 09:43:41 | 2026-10-21 09:43:41 | 4.0 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/responses/response_005.json` | 2026-10-21 09:43:44 | 2026-10-21 09:43:44 | 4.1 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/responses/response_006.json` | 2026-10-21 09:43:57 | 2026-10-21 09:43:57 | 18.5 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/responses/response_007.json` | 2026-10-21 09:43:59 | 2026-10-21 09:43:59 | 2.9 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/responses/response_008.json` | 2026-10-21 09:44:37 | 2026-10-21 09:44:37 | 54.6 KB | 模型原始响应快照（content/reasoning/tool_calls/usage/raw）。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/rules/emotion_baseline_v1+meta_98dc75d5b5.md` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 2.1 KB | 该运行实际使用的规则快照。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/run_manifest.json` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 14.5 KB | 该运行的代码/配置/模型/材料/规则/费用来源。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/scientist_input.md` | 2026-10-21 09:43:31 | 2026-10-21 09:43:31 | 6.6 KB | 首轮实际 system/user 输入及哈希。 |
| `runs/flash_emotion_20261021/runs/meta_rule/repeat_02__retry2/state.json` | 2026-10-21 09:44:37 | 2026-10-21 09:44:37 | 615 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/flash_emotion_20261021/spotcheck.txt` | 2026-10-21 09:44:43 | 2026-10-21 09:44:43 | 13.2 KB | 运行产物 `spotcheck.txt`。 |
| `runs/flash_emotion_20261021/study_lock.json` | 2026-10-21 09:29:40 | 2026-10-21 09:29:40 | 563 B | 问题/材料/rubric/规则/prompt 的冻结哈希。 |
| `runs/flash_emotion_20261021/study_state.json` | 2026-10-21 09:44:37 | 2026-10-21 09:44:37 | 6.9 KB | 情绪研究的运行/attempt 状态。 |
| `runs/flash_emotion_20261021/valence_audit.txt` | 2026-10-21 11:55:53 | 2026-10-21 11:55:54 | 23.2 KB | 30–40%/25% 等数字的源文上下文。 |
| `runs/study_20261019/FREEZE_MANIFEST.json` | 2026-10-19 01:49:52 | 2026-10-19 01:49:52 | 164.5 KB | 运行产物 `FREEZE_MANIFEST.json`。 |
| `runs/study_20261019/development/case_001/s0/cache/85e3c344cbc2825ff1322a9c2a7c639c015ece116aa3a14016fb1ce4adb47b94.json` | 2026-10-19 01:46:35 | 2026-10-19 01:46:35 | 6.0 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/development/case_001/s0/cache/9012debfff31ee87f9363100f323dd0619dadf39eda229869fdb1f43193aa99a.json` | 2026-10-19 01:46:09 | 2026-10-19 01:46:09 | 5.7 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/development/case_001/s0/cache/9f7eee0fdf6c9a1b94dd7fff91c5a80badf1426370f7029c6f073a0c4614ed13.json` | 2026-10-19 01:46:59 | 2026-10-19 01:46:59 | 5.8 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/development/case_001/s0/cache/fbea462f6e3fe17d5af3bb11669d66f58fa2f0bed0297fefc492fb3993bc4574.json` | 2026-10-19 01:45:47 | 2026-10-19 01:45:47 | 4.4 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/development/case_001/s0/config_snapshot.json` | 2026-10-19 01:45:31 | 2026-10-19 01:45:31 | 992 B | 旧 episode 配置快照。 |
| `runs/study_20261019/development/case_001/s0/events.jsonl` | 2026-10-19 01:45:31 | 2026-10-19 01:46:59 | 9.8 KB | 哈希链事件日志。 |
| `runs/study_20261019/development/case_001/s0/final.json` | 2026-10-19 01:46:59 | 2026-10-19 01:46:59 | 29.7 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/development/case_001/s0/history.json` | 2026-10-19 01:46:59 | 2026-10-19 01:46:59 | 24.9 KB | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/development/case_001/s0/prediction_004.json` | 2026-10-19 01:45:47 | 2026-10-19 01:45:47 | 1.3 KB | 封存预测记录。 |
| `runs/study_20261019/development/case_001/s0/prediction_009.json` | 2026-10-19 01:46:09 | 2026-10-19 01:46:09 | 2.5 KB | 封存预测记录。 |
| `runs/study_20261019/development/case_001/s0/prediction_014.json` | 2026-10-19 01:46:35 | 2026-10-19 01:46:35 | 2.6 KB | 封存预测记录。 |
| `runs/study_20261019/development/case_001/s0/public_input.json` | 2026-10-19 01:45:31 | 2026-10-19 01:45:31 | 4.2 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/development/case_001/s0/request_001.json` | 2026-10-19 01:45:31 | 2026-10-19 01:45:31 | 13.1 KB | 模型请求快照。 |
| `runs/study_20261019/development/case_001/s0/request_002.json` | 2026-10-19 01:45:47 | 2026-10-19 01:45:47 | 17.9 KB | 模型请求快照。 |
| `runs/study_20261019/development/case_001/s0/request_003.json` | 2026-10-19 01:46:11 | 2026-10-19 01:46:11 | 23.8 KB | 模型请求快照。 |
| `runs/study_20261019/development/case_001/s0/request_004.json` | 2026-10-19 01:46:36 | 2026-10-19 01:46:36 | 29.7 KB | 模型请求快照。 |
| `runs/study_20261019/development/case_001/s0/response_001.json` | 2026-10-19 01:45:47 | 2026-10-19 01:45:47 | 4.4 KB | 模型响应快照。 |
| `runs/study_20261019/development/case_001/s0/response_002.json` | 2026-10-19 01:46:09 | 2026-10-19 01:46:09 | 5.7 KB | 模型响应快照。 |
| `runs/study_20261019/development/case_001/s0/response_003.json` | 2026-10-19 01:46:35 | 2026-10-19 01:46:35 | 6.0 KB | 模型响应快照。 |
| `runs/study_20261019/development/case_001/s0/response_004.json` | 2026-10-19 01:46:59 | 2026-10-19 01:46:59 | 5.8 KB | 模型响应快照。 |
| `runs/study_20261019/development/case_001/s0/result_001.json` | 2026-10-19 01:45:47 | 2026-10-19 01:45:47 | 7.5 KB | 实验工具执行结果。 |
| `runs/study_20261019/development/case_001/s0/result_002.json` | 2026-10-19 01:46:10 | 2026-10-19 01:46:10 | 6.3 KB | 实验工具执行结果。 |
| `runs/study_20261019/development/case_001/s0/result_003.json` | 2026-10-19 01:46:36 | 2026-10-19 01:46:36 | 6.3 KB | 实验工具执行结果。 |
| `runs/study_20261019/development/case_001/s0/score_001.json` | 2026-10-19 01:45:47 | 2026-10-19 01:45:47 | 8.4 KB | 预测评分结果。 |
| `runs/study_20261019/development/case_001/s0/score_002.json` | 2026-10-19 01:46:10 | 2026-10-19 01:46:10 | 7.1 KB | 预测评分结果。 |
| `runs/study_20261019/development/case_001/s0/score_003.json` | 2026-10-19 01:46:36 | 2026-10-19 01:46:36 | 7.1 KB | 预测评分结果。 |
| `runs/study_20261019/development/case_001/s0/state.json` | 2026-10-19 01:46:59 | 2026-10-19 01:46:59 | 1.1 KB | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/development/case_001/s0/summary.md` | 2026-10-19 01:46:59 | 2026-10-19 01:46:59 | 1.5 KB | 旧 episode 摘要。 |
| `runs/study_20261019/development/case_002/s0/cache/213600f9f8e8ab5187e091726a07e1fa43a25e504aa452a5451ae11aa3ab3db8.json` | 2026-10-19 01:47:19 | 2026-10-19 01:47:19 | 4.6 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/development/case_002/s0/cache/21bd99925faf2f770c982fdf63b8a2f0f2beb6f945845b8389528c1eb2c0dec6.json` | 2026-10-19 01:48:41 | 2026-10-19 01:48:41 | 4.2 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/development/case_002/s0/cache/28fbf80531668b020946b137d3ded95124a1e5fdd2c0f6414f939a2eda474442.json` | 2026-10-19 01:48:20 | 2026-10-19 01:48:20 | 7.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/development/case_002/s0/cache/2d0c110904f5fd1461de136804f80526c8b039ac4d9f4e27a4dcf0ade6a5e973.json` | 2026-10-19 01:47:47 | 2026-10-19 01:47:47 | 7.0 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/development/case_002/s0/config_snapshot.json` | 2026-10-19 01:46:59 | 2026-10-19 01:46:59 | 992 B | 旧 episode 配置快照。 |
| `runs/study_20261019/development/case_002/s0/events.jsonl` | 2026-10-19 01:46:59 | 2026-10-19 01:48:41 | 10.5 KB | 哈希链事件日志。 |
| `runs/study_20261019/development/case_002/s0/final.json` | 2026-10-19 01:48:41 | 2026-10-19 01:48:41 | 28.4 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/development/case_002/s0/history.json` | 2026-10-19 01:48:41 | 2026-10-19 01:48:41 | 26.3 KB | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/development/case_002/s0/prediction_004.json` | 2026-10-19 01:47:19 | 2026-10-19 01:47:19 | 1.4 KB | 封存预测记录。 |
| `runs/study_20261019/development/case_002/s0/prediction_009.json` | 2026-10-19 01:47:47 | 2026-10-19 01:47:47 | 3.8 KB | 封存预测记录。 |
| `runs/study_20261019/development/case_002/s0/prediction_014.json` | 2026-10-19 01:48:20 | 2026-10-19 01:48:20 | 3.6 KB | 封存预测记录。 |
| `runs/study_20261019/development/case_002/s0/public_input.json` | 2026-10-19 01:46:59 | 2026-10-19 01:46:59 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/development/case_002/s0/request_001.json` | 2026-10-19 01:46:59 | 2026-10-19 01:46:59 | 13.1 KB | 模型请求快照。 |
| `runs/study_20261019/development/case_002/s0/request_002.json` | 2026-10-19 01:47:19 | 2026-10-19 01:47:19 | 18.0 KB | 模型请求快照。 |
| `runs/study_20261019/development/case_002/s0/request_003.json` | 2026-10-19 01:47:49 | 2026-10-19 01:47:49 | 24.5 KB | 模型请求快照。 |
| `runs/study_20261019/development/case_002/s0/request_004.json` | 2026-10-19 01:48:22 | 2026-10-19 01:48:22 | 31.1 KB | 模型请求快照。 |
| `runs/study_20261019/development/case_002/s0/response_001.json` | 2026-10-19 01:47:19 | 2026-10-19 01:47:19 | 4.6 KB | 模型响应快照。 |
| `runs/study_20261019/development/case_002/s0/response_002.json` | 2026-10-19 01:47:47 | 2026-10-19 01:47:47 | 7.0 KB | 模型响应快照。 |
| `runs/study_20261019/development/case_002/s0/response_003.json` | 2026-10-19 01:48:20 | 2026-10-19 01:48:20 | 7.3 KB | 模型响应快照。 |
| `runs/study_20261019/development/case_002/s0/response_004.json` | 2026-10-19 01:48:41 | 2026-10-19 01:48:41 | 4.2 KB | 模型响应快照。 |
| `runs/study_20261019/development/case_002/s0/result_001.json` | 2026-10-19 01:47:19 | 2026-10-19 01:47:19 | 7.6 KB | 实验工具执行结果。 |
| `runs/study_20261019/development/case_002/s0/result_002.json` | 2026-10-19 01:47:49 | 2026-10-19 01:47:49 | 6.3 KB | 实验工具执行结果。 |
| `runs/study_20261019/development/case_002/s0/result_003.json` | 2026-10-19 01:48:22 | 2026-10-19 01:48:22 | 6.3 KB | 实验工具执行结果。 |
| `runs/study_20261019/development/case_002/s0/score_001.json` | 2026-10-19 01:47:19 | 2026-10-19 01:47:19 | 8.4 KB | 预测评分结果。 |
| `runs/study_20261019/development/case_002/s0/score_002.json` | 2026-10-19 01:47:49 | 2026-10-19 01:47:49 | 7.2 KB | 预测评分结果。 |
| `runs/study_20261019/development/case_002/s0/score_003.json` | 2026-10-19 01:48:22 | 2026-10-19 01:48:22 | 7.1 KB | 预测评分结果。 |
| `runs/study_20261019/development/case_002/s0/state.json` | 2026-10-19 01:48:41 | 2026-10-19 01:48:41 | 635 B | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/development/case_002/s0/summary.md` | 2026-10-19 01:48:41 | 2026-10-19 01:48:41 | 1015 B | 旧 episode 摘要。 |
| `runs/study_20261019/events.jsonl` | 2026-10-19 01:45:30 | 2026-10-19 01:54:30 | 4.8 KB | 哈希链事件日志。 |
| `runs/study_20261019/holdout/case_003/s0/cache/f88e1bb1bfc8542d7711e22c7bed25afc600ef6d9a3958b903cbc8cab3612505.json` | 2026-10-19 01:51:03 | 2026-10-19 01:51:03 | 9.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/holdout/case_003/s0/config_snapshot.json` | 2026-10-19 01:50:30 | 2026-10-19 01:50:30 | 1.0 KB | 旧 episode 配置快照。 |
| `runs/study_20261019/holdout/case_003/s0/events.jsonl` | 2026-10-19 01:50:30 | 2026-10-19 01:51:03 | 2.2 KB | 哈希链事件日志。 |
| `runs/study_20261019/holdout/case_003/s0/final.json` | 2026-10-19 01:51:03 | 2026-10-19 01:51:03 | 5.6 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/holdout/case_003/s0/history.json` | 2026-10-19 01:51:03 | 2026-10-19 01:51:03 | 2 B | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/holdout/case_003/s0/public_input.json` | 2026-10-19 01:50:30 | 2026-10-19 01:50:30 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/holdout/case_003/s0/request_001.json` | 2026-10-19 01:50:30 | 2026-10-19 01:50:30 | 29.1 KB | 模型请求快照。 |
| `runs/study_20261019/holdout/case_003/s0/response_001.json` | 2026-10-19 01:51:03 | 2026-10-19 01:51:03 | 9.3 KB | 模型响应快照。 |
| `runs/study_20261019/holdout/case_003/s0/state.json` | 2026-10-19 01:51:03 | 2026-10-19 01:51:03 | 1.3 KB | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/holdout/case_003/s0/summary.md` | 2026-10-19 01:51:03 | 2026-10-19 01:51:03 | 1.1 KB | 旧 episode 摘要。 |
| `runs/study_20261019/holdout/case_003/s1/cache/d395b8cf5358854c4df650efb9a8fc7bef7a0e19066297ca4f1bea79bcddd69b.json` | 2026-10-19 01:50:30 | 2026-10-19 01:50:30 | 9.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/holdout/case_003/s1/config_snapshot.json` | 2026-10-19 01:49:52 | 2026-10-19 01:49:52 | 1.0 KB | 旧 episode 配置快照。 |
| `runs/study_20261019/holdout/case_003/s1/events.jsonl` | 2026-10-19 01:49:52 | 2026-10-19 01:50:30 | 2.2 KB | 哈希链事件日志。 |
| `runs/study_20261019/holdout/case_003/s1/final.json` | 2026-10-19 01:50:30 | 2026-10-19 01:50:30 | 5.6 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/holdout/case_003/s1/history.json` | 2026-10-19 01:50:30 | 2026-10-19 01:50:30 | 2 B | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/holdout/case_003/s1/public_input.json` | 2026-10-19 01:49:52 | 2026-10-19 01:49:52 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/holdout/case_003/s1/request_001.json` | 2026-10-19 01:49:52 | 2026-10-19 01:49:52 | 29.3 KB | 模型请求快照。 |
| `runs/study_20261019/holdout/case_003/s1/response_001.json` | 2026-10-19 01:50:30 | 2026-10-19 01:50:30 | 9.3 KB | 模型响应快照。 |
| `runs/study_20261019/holdout/case_003/s1/state.json` | 2026-10-19 01:50:30 | 2026-10-19 01:50:30 | 1.3 KB | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/holdout/case_003/s1/summary.md` | 2026-10-19 01:50:30 | 2026-10-19 01:50:30 | 1.1 KB | 旧 episode 摘要。 |
| `runs/study_20261019/holdout/case_004/s0/cache/17c10fbbf7a863ecfd7585c2606f212b60ff473cab0e706842adf11c99cc40f9.json` | 2026-10-19 01:51:37 | 2026-10-19 01:51:37 | 9.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/holdout/case_004/s0/config_snapshot.json` | 2026-10-19 01:51:04 | 2026-10-19 01:51:04 | 1.0 KB | 旧 episode 配置快照。 |
| `runs/study_20261019/holdout/case_004/s0/events.jsonl` | 2026-10-19 01:51:04 | 2026-10-19 01:51:37 | 2.2 KB | 哈希链事件日志。 |
| `runs/study_20261019/holdout/case_004/s0/final.json` | 2026-10-19 01:51:37 | 2026-10-19 01:51:37 | 5.6 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/holdout/case_004/s0/history.json` | 2026-10-19 01:51:37 | 2026-10-19 01:51:37 | 2 B | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/holdout/case_004/s0/public_input.json` | 2026-10-19 01:51:04 | 2026-10-19 01:51:04 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/holdout/case_004/s0/request_001.json` | 2026-10-19 01:51:04 | 2026-10-19 01:51:04 | 29.1 KB | 模型请求快照。 |
| `runs/study_20261019/holdout/case_004/s0/response_001.json` | 2026-10-19 01:51:37 | 2026-10-19 01:51:37 | 9.3 KB | 模型响应快照。 |
| `runs/study_20261019/holdout/case_004/s0/state.json` | 2026-10-19 01:51:37 | 2026-10-19 01:51:37 | 1.3 KB | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/holdout/case_004/s0/summary.md` | 2026-10-19 01:51:37 | 2026-10-19 01:51:37 | 1.1 KB | 旧 episode 摘要。 |
| `runs/study_20261019/holdout/case_004/s1/cache/9e84592c5d328d93d46529ee6c7b3dcf786b18f04f83c3c53cba2f2b0ff1ed61.json` | 2026-10-19 01:52:12 | 2026-10-19 01:52:12 | 9.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/holdout/case_004/s1/config_snapshot.json` | 2026-10-19 01:51:37 | 2026-10-19 01:51:37 | 1.0 KB | 旧 episode 配置快照。 |
| `runs/study_20261019/holdout/case_004/s1/events.jsonl` | 2026-10-19 01:51:37 | 2026-10-19 01:52:12 | 2.2 KB | 哈希链事件日志。 |
| `runs/study_20261019/holdout/case_004/s1/final.json` | 2026-10-19 01:52:12 | 2026-10-19 01:52:12 | 5.6 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/holdout/case_004/s1/history.json` | 2026-10-19 01:52:12 | 2026-10-19 01:52:12 | 2 B | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/holdout/case_004/s1/public_input.json` | 2026-10-19 01:51:37 | 2026-10-19 01:51:37 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/holdout/case_004/s1/request_001.json` | 2026-10-19 01:51:37 | 2026-10-19 01:51:37 | 29.3 KB | 模型请求快照。 |
| `runs/study_20261019/holdout/case_004/s1/response_001.json` | 2026-10-19 01:52:12 | 2026-10-19 01:52:12 | 9.3 KB | 模型响应快照。 |
| `runs/study_20261019/holdout/case_004/s1/state.json` | 2026-10-19 01:52:12 | 2026-10-19 01:52:12 | 1.3 KB | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/holdout/case_004/s1/summary.md` | 2026-10-19 01:52:12 | 2026-10-19 01:52:12 | 1.1 KB | 旧 episode 摘要。 |
| `runs/study_20261019/holdout/case_005/s0/cache/51336fa8d87de147273eefbc9ea4421624da2d96a4413f4aa5c73688fe783592.json` | 2026-10-19 01:53:21 | 2026-10-19 01:53:21 | 9.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/holdout/case_005/s0/config_snapshot.json` | 2026-10-19 01:52:46 | 2026-10-19 01:52:46 | 1.0 KB | 旧 episode 配置快照。 |
| `runs/study_20261019/holdout/case_005/s0/events.jsonl` | 2026-10-19 01:52:46 | 2026-10-19 01:53:21 | 2.2 KB | 哈希链事件日志。 |
| `runs/study_20261019/holdout/case_005/s0/final.json` | 2026-10-19 01:53:21 | 2026-10-19 01:53:21 | 5.6 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/holdout/case_005/s0/history.json` | 2026-10-19 01:53:21 | 2026-10-19 01:53:21 | 2 B | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/holdout/case_005/s0/public_input.json` | 2026-10-19 01:52:46 | 2026-10-19 01:52:46 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/holdout/case_005/s0/request_001.json` | 2026-10-19 01:52:46 | 2026-10-19 01:52:46 | 29.1 KB | 模型请求快照。 |
| `runs/study_20261019/holdout/case_005/s0/response_001.json` | 2026-10-19 01:53:21 | 2026-10-19 01:53:21 | 9.3 KB | 模型响应快照。 |
| `runs/study_20261019/holdout/case_005/s0/state.json` | 2026-10-19 01:53:21 | 2026-10-19 01:53:21 | 1.3 KB | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/holdout/case_005/s0/summary.md` | 2026-10-19 01:53:21 | 2026-10-19 01:53:21 | 1.1 KB | 旧 episode 摘要。 |
| `runs/study_20261019/holdout/case_005/s1/cache/b057c1f24e875cd178b0bcd779bdede66832850552c9903e80e13b0e27053b61.json` | 2026-10-19 01:52:46 | 2026-10-19 01:52:46 | 9.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/holdout/case_005/s1/config_snapshot.json` | 2026-10-19 01:52:13 | 2026-10-19 01:52:13 | 1.0 KB | 旧 episode 配置快照。 |
| `runs/study_20261019/holdout/case_005/s1/events.jsonl` | 2026-10-19 01:52:13 | 2026-10-19 01:52:46 | 2.2 KB | 哈希链事件日志。 |
| `runs/study_20261019/holdout/case_005/s1/final.json` | 2026-10-19 01:52:46 | 2026-10-19 01:52:46 | 5.6 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/holdout/case_005/s1/history.json` | 2026-10-19 01:52:46 | 2026-10-19 01:52:46 | 2 B | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/holdout/case_005/s1/public_input.json` | 2026-10-19 01:52:13 | 2026-10-19 01:52:13 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/holdout/case_005/s1/request_001.json` | 2026-10-19 01:52:13 | 2026-10-19 01:52:13 | 29.3 KB | 模型请求快照。 |
| `runs/study_20261019/holdout/case_005/s1/response_001.json` | 2026-10-19 01:52:46 | 2026-10-19 01:52:46 | 9.3 KB | 模型响应快照。 |
| `runs/study_20261019/holdout/case_005/s1/state.json` | 2026-10-19 01:52:46 | 2026-10-19 01:52:46 | 1.3 KB | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/holdout/case_005/s1/summary.md` | 2026-10-19 01:52:46 | 2026-10-19 01:52:46 | 1.1 KB | 旧 episode 摘要。 |
| `runs/study_20261019/holdout/case_006/s0/cache/817eb1a6dcfdef5b9ae6478de20437bd2ec9dc302d38ade65d8f03ded875d77a.json` | 2026-10-19 01:53:55 | 2026-10-19 01:53:55 | 9.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/holdout/case_006/s0/config_snapshot.json` | 2026-10-19 01:53:22 | 2026-10-19 01:53:22 | 1.0 KB | 旧 episode 配置快照。 |
| `runs/study_20261019/holdout/case_006/s0/events.jsonl` | 2026-10-19 01:53:22 | 2026-10-19 01:53:55 | 2.2 KB | 哈希链事件日志。 |
| `runs/study_20261019/holdout/case_006/s0/final.json` | 2026-10-19 01:53:55 | 2026-10-19 01:53:55 | 5.6 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/holdout/case_006/s0/history.json` | 2026-10-19 01:53:55 | 2026-10-19 01:53:55 | 2 B | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/holdout/case_006/s0/public_input.json` | 2026-10-19 01:53:22 | 2026-10-19 01:53:22 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/holdout/case_006/s0/request_001.json` | 2026-10-19 01:53:22 | 2026-10-19 01:53:22 | 29.1 KB | 模型请求快照。 |
| `runs/study_20261019/holdout/case_006/s0/response_001.json` | 2026-10-19 01:53:55 | 2026-10-19 01:53:55 | 9.3 KB | 模型响应快照。 |
| `runs/study_20261019/holdout/case_006/s0/state.json` | 2026-10-19 01:53:55 | 2026-10-19 01:53:55 | 1.3 KB | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/holdout/case_006/s0/summary.md` | 2026-10-19 01:53:55 | 2026-10-19 01:53:55 | 1.1 KB | 旧 episode 摘要。 |
| `runs/study_20261019/holdout/case_006/s1/cache/84689f0096546112b6d42c97ce8265ab5ca4a9385f239b4bb93486995bce0115.json` | 2026-10-19 01:54:30 | 2026-10-19 01:54:30 | 9.3 KB | 模型响应缓存，用于恢复/去重；不是新的科学证据。 |
| `runs/study_20261019/holdout/case_006/s1/config_snapshot.json` | 2026-10-19 01:53:55 | 2026-10-19 01:53:55 | 1.0 KB | 旧 episode 配置快照。 |
| `runs/study_20261019/holdout/case_006/s1/events.jsonl` | 2026-10-19 01:53:55 | 2026-10-19 01:54:30 | 2.2 KB | 哈希链事件日志。 |
| `runs/study_20261019/holdout/case_006/s1/final.json` | 2026-10-19 01:54:30 | 2026-10-19 01:54:30 | 5.6 KB | 该运行的结构化最终结果（accepted、引用、覆盖、预算）。 |
| `runs/study_20261019/holdout/case_006/s1/history.json` | 2026-10-19 01:54:30 | 2026-10-19 01:54:30 | 2 B | 旧 episode 决策/执行历史。 |
| `runs/study_20261019/holdout/case_006/s1/public_input.json` | 2026-10-19 01:53:55 | 2026-10-19 01:53:55 | 4.1 KB | 旧合成案例的公开输入。 |
| `runs/study_20261019/holdout/case_006/s1/request_001.json` | 2026-10-19 01:53:55 | 2026-10-19 01:53:55 | 29.3 KB | 模型请求快照。 |
| `runs/study_20261019/holdout/case_006/s1/response_001.json` | 2026-10-19 01:54:30 | 2026-10-19 01:54:30 | 9.3 KB | 模型响应快照。 |
| `runs/study_20261019/holdout/case_006/s1/state.json` | 2026-10-19 01:54:30 | 2026-10-19 01:54:30 | 1.3 KB | 该运行的可恢复状态（阶段、调用数、accepted、stop_reason）。 |
| `runs/study_20261019/holdout/case_006/s1/summary.md` | 2026-10-19 01:54:30 | 2026-10-19 01:54:30 | 1.1 KB | 旧 episode 摘要。 |
| `runs/study_20261019/shared_development_facts.json` | 2026-10-19 01:49:50 | 2026-10-19 01:49:50 | 20.8 KB | 运行产物 `shared_development_facts.json`。 |
| `runs/study_20261019/study_state.json` | 2026-10-19 01:54:30 | 2026-10-19 01:54:30 | 11.3 KB | 情绪研究的运行/attempt 状态。 |

### src

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `src/eeg_scientist/__init__.py` | 2026-10-19 01:33:01 | 2026-10-19 01:33:01 | 75 B | 包标记文件，声明 eeg_scientist 模块。 |
| `src/eeg_scientist/backends.py` | 2026-10-21 09:25:58 | 2026-10-21 09:27:12 | 5.3 KB | 模型/工具后端注册表；只有 DeepSeek Flash 标为已验证，Claude/Gemini/Pro 仅保留未验证配置入口。 |
| `src/eeg_scientist/capability.py` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 13.1 KB | 真实模型、原生工具循环、Search/Fetch 的连通性检查。 |
| `src/eeg_scientist/cases.py` | 2026-10-19 01:29:55 | 2026-10-19 01:34:08 | 7.2 KB | 生成合成 EEG 风格案例、全局试次编号和公开案例视图。 |
| `src/eeg_scientist/cli.py` | 2026-10-20 13:26:50 | 2026-10-21 09:48:44 | 25.2 KB | 命令行入口，包含旧过夜命令、Flash 研究命令和 emotion-study 命令。 |
| `src/eeg_scientist/credentials.py` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 4.5 KB | 显式读取 credentials/deepseek.env，校验密钥且不打印值。 |
| `src/eeg_scientist/dataset_io.py` | 2026-10-20 13:26:50 | 2026-10-20 21:36:58 | 7.5 KB | 二元标签 CSV 特征表入口与 window/trial/subject 切分审计；明确未实现 session 切分。 |
| `src/eeg_scientist/deepseek_api.py` | 2026-10-20 13:26:50 | 2026-10-21 09:23:57 | 27.9 KB | DeepSeek Chat Completions/Search/Fetch 客户端，处理 thinking、tool_calls、usage 和预算。 |
| `src/eeg_scientist/diagnostic.py` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 14.3 KB | Task C 的 99%/50% 解释回归与两个中性合成案例诊断。 |
| `src/eeg_scientist/emotion_experiment.py` | 2026-10-21 09:30:23 | 2026-10-21 11:56:45 | 24.1 KB | 受控情绪 state-vs-trait 研究：Meta、基线/规则运行、首 accepted 选择、盲评与格式检查。 |
| `src/eeg_scientist/evidence.py` | 2026-10-20 13:26:50 | 2026-10-21 09:24:29 | 11.2 KB | 证据快照、读取区间、注入记录和区间并集覆盖率。 |
| `src/eeg_scientist/experiments.py` | 2026-10-19 01:30:42 | 2026-10-19 01:40:08 | 21.7 KB | 固定分类器、五种合成诊断工具、随机化对照与预测评分。 |
| `src/eeg_scientist/flash_report.py` | 2026-10-20 13:26:50 | 2026-10-21 09:48:44 | 10.4 KB | 从持久状态渲染旧 Flash 运行的索引/结果报告。 |
| `src/eeg_scientist/ledger.py` | 2026-10-20 13:26:50 | 2026-10-21 09:23:40 | 16.4 KB | 持久预算账本：价格、预留、usage 结算、UNKNOWN 和按运行归因。 |
| `src/eeg_scientist/meta.py` | 2026-10-21 09:26:31 | 2026-10-21 09:46:14 | 9.1 KB | 受控 Meta：只读旧 literature_v1 轨迹与标注评审反馈，最多一条规则或 no_update。 |
| `src/eeg_scientist/provider.py` | 2026-10-19 01:31:12 | 2026-10-19 01:37:16 | 13.1 KB | 旧脚本/本地 Ollama 及 OpenAI 兼容 provider 实现，不属于本轮 Flash 路径。 |
| `src/eeg_scientist/reporting.py` | 2026-10-19 01:36:43 | 2026-10-19 01:56:52 | 33.6 KB | 旧合成过夜研究的报告渲染。 |
| `src/eeg_scientist/research.py` | 2026-10-20 13:26:50 | 2026-10-21 09:49:25 | 51.3 KB | 可恢复的文献研究工具循环；分离模型/工具、材料冻结、规则快照、accepted 状态。 |
| `src/eeg_scientist/run_manifest.py` | 2026-10-21 09:24:03 | 2026-10-21 11:51:02 | 6.2 KB | 运行来源：git 状态、完整配置、代码快照、模型/材料/规则/费用归属。 |
| `src/eeg_scientist/runner.py` | 2026-10-19 01:32:18 | 2026-10-19 01:43:29 | 24.3 KB | 旧合成案例的 episode 状态机：决策、封存预测、实验、恢复。 |
| `src/eeg_scientist/schema.py` | 2026-10-19 01:29:39 | 2026-10-21 11:49:22 | 11.6 KB | 跨模块的 Pydantic/数据类模型与严格校验。 |
| `src/eeg_scientist/scientist.py` | 2026-10-19 01:31:29 | 2026-10-21 11:49:18 | 17.0 KB | 决策 JSON 解析/归一化、prompt 构造、旧 Meta 规则管道。 |
| `src/eeg_scientist/splits.py` | 2026-10-19 01:30:06 | 2026-10-19 01:30:06 | 7.3 KB | window/trial/subject 分组切分与身份交集审计。 |
| `src/eeg_scientist/storage.py` | 2026-10-19 01:30:57 | 2026-10-19 01:31:55 | 8.6 KB | 哈希链事件日志、原子写、封存请求、缓存和恢复。 |
| `src/eeg_scientist/study.py` | 2026-10-19 01:35:13 | 2026-10-19 01:46:34 | 21.4 KB | 旧 overnight 研究的并行/冻结/恢复编排。 |

### tests

| 文件 | 创建时间 | 修改时间 | 大小 | 作用 |
|---|---|---|---:|---|
| `tests/test_core.py` | 2026-10-19 01:46:01 | 2026-10-19 01:46:05 | 10.0 KB | 案例生成、切分、实验工具和预测评分的核心测试。 |
| `tests/test_emotion_experiment.py` | 2026-10-21 09:31:30 | 2026-10-21 11:54:57 | 9.3 KB | 情绪研究/后端/账本/代码快照/Meta 输入隔离的离线测试。 |
| `tests/test_flash_stack.py` | 2026-10-20 13:26:50 | 2026-10-20 21:42:57 | 18.8 KB | Flash 客户端、证据、预算、研究循环和引用一致性的离线测试。 |
| `tests/test_scientist_provider.py` | 2026-10-19 01:46:42 | 2026-10-19 01:46:42 | 5.5 KB | 决策解析、修复、Meta 请求和 provider 边界测试。 |
| `tests/test_storage_runner.py` | 2026-10-20 13:26:50 | 2026-10-20 13:26:50 | 10.1 KB | 事件链、封存预测、episode 状态机和恢复测试。 |
| `tests/test_study_reporting.py` | 2026-10-19 01:46:57 | 2026-10-19 01:46:57 | 8.2 KB | 旧 study 编排与报告渲染测试。 |

## 备注

- `docs/FILE_INVENTORY.md`、`docs/FILE_INVENTORY.csv`、`docs/FILE_TREE.txt` 是本次生成的清单自身；它们出现在 CSV 的 generated 类别，但不列入上面的项目/人工产物逐文件表。
- `runs/` 中每个 run 的 `messages.json`、`final_answer.md`、`final.json` 等是原始运行材料；任何更正都写在独立的评审文件里，不覆盖这些原文件。
- `credentials/` 仅列路径；没有读取密钥内容。
