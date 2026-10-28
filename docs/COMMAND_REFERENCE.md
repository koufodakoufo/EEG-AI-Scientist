# Command reference

Commands resolve the project root from `EEG_SCIENTIST_ROOT`, the current
directory, or the installed package location, so they also work from a
subdirectory such as `group-meeting/`.

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
| `study init --id <id>` | Create a generic self-contained draft (`task.md`, `system_prompt.md`, empty material manifest). | no | `studies/<id>/` | `uv run python -m eeg_scientist.cli study init --id my_study` |
| `study init --id <id> --template emotion_20261021` | Explicitly select archived emotion material/prompt; not the default. | no | `studies/<id>/` | `uv run python -m eeg_scientist.cli study init --id old_material --template emotion_20261021` |
| `study validate --study <id>` | Check config, task/system/rule files, non-empty material manifest, arms, verified backends, model IDs, prices. | no | nothing | `uv run python -m eeg_scientist.cli study validate --study my_study` |
| `study preflight --study <id>` | Show each arm's model, task/material/rule hashes, prompt hashes and diff; reject identical rule text as a rule contrast. | no | nothing | `uv run python -m eeg_scientist.cli study preflight --study my_study` |
| `study run --study <id> --confirm-cost` | Run configured arms/repeats through `ResearchRunner` after preflight. | **yes** | run dirs, evidence, budgets, manifests | `uv run python -m eeg_scientist.cli study run --study my_study --confirm-cost` |
| `study run --study <id>` | Print budget/arms and exit; does not run. | no | nothing | `uv run python -m eeg_scientist.cli study run --study my_study` |
| `study status --study <id>` | Show states, accepted flags, budgets. | no | nothing | `uv run python -m eeg_scientist.cli study status --study my_study` |
| `study report --study <id>` | Generate `studies/<id>/report.md`. | no | `report.md` | `uv run python -m eeg_scientist.cli study report --study my_study` |
| `review export --study <id>` | Export one fillable form per proposal (`forms/Bxx.md`), an overview packet, and the coordinator key. | no | `studies/<id>/reviews/` | `uv run python -m eeg_scientist.cli review export --study my_study` |
| `review import --study <id> --file <path>` | Import Markdown form(s); bind packet/display/run/full body SHA; reject conflicts. Repeat `--file` for multiple forms. | no | `reviews/raw/`, `reviews/records/` | `uv run python -m eeg_scientist.cli review import --study my_study --file .\forms\B01.md` |
| `review select --study <id> --reviews <ids> --version <v>` | Create an immutable versioned feedback set for later Meta; same version/content is read-only. | no | `reviews/feedback_set_<v>.json` | `uv run python -m eeg_scientist.cli review select --study my_study --reviews r_abc123 --version v1` |
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

## Environment troubleshooting

If your prompt shows both `(base)` and `(eeg-fm-rsi)`, that is **conda + venv
nested activation**, not two projects. `(eeg-fm-rsi)` is only the old prompt name
stored in `.venv/pyvenv.cfg`; it is still this project's `.venv`.

The current `.venv/Scripts/activate` also contains a stale absolute
`VIRTUAL_ENV` from an older copy (`X:\projects\EEG-FM-RSI\.venv`). `uv run` warns
about that and deliberately uses the project environment. You can ignore the
warning, or avoid activation:

```bash
unset VIRTUAL_ENV
cd /x/projects/EEG-AI-Scientist
uv run python -m eeg_scientist.cli study --help
```

There is no `uv activate` command. `uv run` is the command; use `--active` only
if you deliberately want uv to target a currently activated environment.

`--id` is a named option, not a number:

```powershell
# correct
uv run python -m eeg_scientist.cli study init --id my_study

# wrong: `null` is parsed as a subcommand, and `init null` misses --id
uv run python -m eeg_scientist.cli study null
uv run python -m eeg_scientist.cli study init null
```

`study_id` must be 3–80 characters of lowercase letters, digits, `_`, or `-`.
Examples: `emotion_pilot_01`, `flash_compare_02`.

