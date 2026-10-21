# Archive index

This directory is **read-only history**. Original answers, trajectories, ledgers, and review text were moved without rewriting.
Archived files: **830**; total bytes: **26027618**. Payload: **819** files / **26014720** bytes; aggregate SHA-256 (excluding index README/MIGRATION_MAP): `1c6c972757e9a6a7da35bb1adc42149ad8109edd81cc66fba71d3900272825a6`.

Full machine-readable paths and hashes: `MIGRATION_MAP.json`.

## Completed experiments

| experiment | period | archive path | old entry |
|---|---|---|---|
| `synthetic_20261019` | 旧合成工程/机制诊断（2026-10-19） | `archive/experiments/synthetic_20261019/` | old CLI only; read-only |
| `flash_20261020_0058` | DeepSeek Flash 文献研究（2026-10-20） | `archive/experiments/flash_20261020_0058/` | old CLI only; read-only |
| `emotion_20261021` | 受控情绪 state-vs-trait 研究（2026-10-21） | `archive/experiments/emotion_20261021/` | old CLI only; read-only |

## Old path -> new path

| old | new |
|---|---|
| `runs/dev_e1` | `archive/experiments/synthetic_20261019/runs/dev_e1` |
| `runs/study_20261019` | `archive/experiments/synthetic_20261019/runs/study_20261019` |
| `runs/flash_20261020_0058` | `archive/experiments/flash_20261020_0058/runs/flash_20261020_0058` |
| `runs/flash_emotion_20261021` | `archive/experiments/emotion_20261021/runs/flash_emotion_20261021` |
| `reports/flash_20261020_0058` | `archive/experiments/flash_20261020_0058/reports/flash_20261020_0058` |
| `reports/flash_emotion_20261021` | `archive/experiments/emotion_20261021/reports/flash_emotion_20261021` |
| `reports/*.md (synthetic stage reports)` | `archive/experiments/synthetic_20261019/reports/` |
| `configs/studies/flash_emotion_20261021.json` | `archive/experiments/emotion_20261021/configs/study.json (original in study.original.json)` |
| `configs/studies/overnight_flash_20261020.json` | `archive/experiments/flash_20261020_0058/configs/study.json (original in study.original.json)` |
| `configs/dev_episode.json` | `archive/experiments/synthetic_20261019/configs/dev_episode.json` |
| `configs/overnight.json` | `archive/experiments/synthetic_20261019/configs/overnight.json` |
| `artifacts/review_bundle.zip` | `archive/experiments/synthetic_20261019/artifacts/review_bundle.zip` |
| `docs/plans/EEG_HARNESS_REFACTOR_PLAN.md` | `archive/plans/EEG_HARNESS_REFACTOR_PLAN.md` |
| `docs/FILE_INVENTORY.md / FILE_INVENTORY.csv / FILE_TREE.txt` | `archive/reference/` |
| `prompts/` | `archive/experiments/synthetic_20261019/prompts/` |
| `data/private/` | `archive/experiments/synthetic_20261019/data/private/` |
| `review_only/` | `archive/experiments/synthetic_20261019/review_only/` |
| `memory/` | `archive/experiments/synthetic_20261019/memory/` |
| `configs/models/deepseek_flash.json` | `archive/experiments/flash_20261020_0058/configs/deepseek_flash.json` |
| `artifacts/review_bundle_20261020.zip` | `archive/experiments/flash_20261020_0058/artifacts/review_bundle_20261020.zip` |
| `artifacts/review_bundle_emotion_20261021.zip` | `archive/experiments/emotion_20261021/artifacts/review_bundle_emotion_20261021.zip` |
| `PROGRESS.md / NEXT_ACTION.md / DECISIONS.md / FREEZE_MANIFEST.json` | `archive/history/` |
| `EEG_AI_Scientist_Overnight_Plan.md / docs/plans/EEG_AI_Scientist_Overnight_Run_v2.md` | `archive/plans/` |

## Exported bundles

| path | bytes | SHA-256 |
|---|---:|---|
| `archive/experiments/emotion_20261021/artifacts/review_bundle_emotion_20261021.zip` | 1165318 | `4a6dcd7219231e8e...` |
| `archive/experiments/flash_20261020_0058/artifacts/review_bundle_20261020.zip` | 675391 | `803d68fd245dccd8...` |
| `archive/experiments/synthetic_20261019/artifacts/review_bundle.zip` | 592534 | `771c3ba764da15cd...` |

All three bundles are distinct studies/rounds, not duplicates; they are kept with their experiment. Do not treat a bundle as the primary run record.

## Read-only rules

- Old `emotion-study` / `overnight-flash` paid actions now refuse and print the unified-entry hint.
- Old `status` and report display may read the archive; they must not write new run state.
- Original `final_answer.md`, `messages.json`, `state.json`, `budget.json`, and review files are not edited.
- `study.json` inside each archived config dir is a path-rewritten read-only view; `study.original.json` is the byte-identical source.

## Start here for current work

Use the repository root `README.md` / `HANDOFF.md` and the unified `study` / `review` commands. New work belongs under `studies/`, not `archive/`.
