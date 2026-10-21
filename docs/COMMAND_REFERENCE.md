# Command reference

Run from the repository root:

```powershell
cd X:\projects\EEG-AI-Scientist
uv run python -m eeg_scientist.cli --help
```

`uv run` uses the project `.venv`. Equivalent explicit form:

```powershell
.\.venv\Scripts\python.exe -m eeg_scientist.cli --help
```

## Active commands

| command | what it does | paid? | writes / touches | copy-paste example |
|---|---|---:|---|---|
| `study init --id <id>` | Create `studies/<id>/study.json` and `task.md`; arms are empty. | no | `studies/<id>/` | `uv run python -m eeg_scientist.cli study init --id my_study` |
| `study validate --study <id>` | Check config, files, arms, verified backends, model IDs, prices. | no | nothing | `uv run python -m eeg_scientist.cli study validate --study my_study` |
| `study run --study <id> --confirm-cost` | Run configured arms/repeats through `ResearchRunner`. | **yes** | run dirs, evidence, budgets, manifests | `uv run python -m eeg_scientist.cli study run --study my_study --confirm-cost` |
| `study run --study <id>` | Print budget/arms and exit; does not run. | no | nothing | `uv run python -m eeg_scientist.cli study run --study my_study` |
| `study status --study <id>` | Show states, accepted flags, budgets. | no | nothing | `uv run python -m eeg_scientist.cli study status --study my_study` |
| `study report --study <id>` | Generate `studies/<id>/report.md`. | no | `report.md` | `uv run python -m eeg_scientist.cli study report --study my_study` |
| `review export --study <id>` | Export accepted proposals as a blind packet; writes packet + coordinator key. | no | `studies/<id>/reviews/` | `uv run python -m eeg_scientist.cli review export --study my_study` |
| `review import --study <id> --file <path>` | Import one Markdown review; bind proposal/body SHA. | no | `reviews/raw/`, `reviews/records/` | `uv run python -m eeg_scientist.cli review import --study my_study --file .\feedback\reviewer_A.md` |
| `review select --study <id> --reviews <ids> --version <v>` | Create a versioned feedback set for later Meta. | no | `reviews/feedback_set_<v>.json` | `uv run python -m eeg_scientist.cli review select --study my_study --reviews r_abc123 --version v1` |
| `check-dataset --path <csv>` | Audit a binary-label feature table's splits; unrelated to study. | no | prints audit | `uv run python -m eeg_scientist.cli check-dataset --path .\features.csv` |

## Read-only archived display

These read the archive and do not call a model. Old paid commands are guarded
and print a migration hint.

| command | what it does | paid? |
|---|---|---:|
| `emotion-study status --config archive/.../study.json` | Show archived emotion state/ledger/subruns. | no |
| `overnight-flash status --config archive/.../study.json` | Show archived Flash state/ledger/subruns. | no |
| `overnight-flash report --config archive/.../study.json` | Print archived report directory; does not rewrite. | no |

Examples:

```powershell
uv run python -m eeg_scientist.cli emotion-study status --config archive/experiments/emotion_20261021/configs/study.json
uv run python -m eeg_scientist.cli overnight-flash status --config archive/experiments/flash_20261020_0058/configs/study.json
```

## Legacy commands that now refuse

These are kept only for a clear migration message:

```text
emotion-study run | evaluate | retry-failed
overnight-flash capability | diagnose | research
overnight | resume | episode | preflight | report | calibrate
```

Use `study`/`review` instead. `overnight-flash report` is read-only display.

## Alternative without `uv`

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m eeg_scientist.cli study status --study my_study
& $py -m eeg_scientist.cli review export --study my_study
& $py -m eeg_scientist.cli review import --study my_study --file .\feedback\reviewer_A.md
& $py -m eeg_scientist.cli study run --study my_study --confirm-cost
```

The installed console script is equivalent:

```powershell
.\.venv\Scripts\eeg-scientist.exe study status --study my_study
```

`study init/validate/status/report/review *` never start a paid run.
`study run` without `--confirm-cost` is also a no-op.
