# Studies

New work belongs here, one directory per study:

```text
studies/<study_id>/
  study.json       # single entry configuration (arms, repeats, limits, budget)
  task.md          # authoritative task body sent to the model
  system_prompt.md # base system prompt (generic template)
  materials/       # manifest.json + evidence/ (generic template)
  runs/<arm>/repeat_XX/   # state, messages, input snapshot, final answer
  reviews/         # packet forms, raw feedback, records, feedback sets
  meta/            # optional rule candidates/decisions
  report.md        # generated current readout
```

`task.md`, not the `question` field, is the task the model actually receives.
Each arm's rule is snapshotted and embedded in the system message; see
`runs/<arm>/repeat_XX/scientist_input.md` and `input_snapshot.json`.

Create a draft with:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m eeg_scientist.cli study init --id my_study
# explicit old material (optional):
& $py -m eeg_scientist.cli study init --id my_study --template emotion_20261021
```

Edit `study.json` to add arms (each arm names a backend and a repeat count).
`study validate` refuses unverified backends, missing model IDs, empty rules, and
an empty material manifest. `study preflight` shows what each arm would actually
send and rejects an identical-text rule contrast. `study run` requires
`--confirm-cost`; no paid run is started by `init/validate/preflight/status/report`.

Do not put historical runs here. Old completed experiments live in
`archive/experiments/` and are read-only.




# Portability
源码层面
可移植：
src/
tests/
configs/
studies/
docs/
pyproject.toml
uv.lock
.python-version
到新机器：

```powershell
cd <项目目录>
uv sync --extra dev
uv run python -m eeg_scientist.cli --help
uv run python -m pytest -q
```