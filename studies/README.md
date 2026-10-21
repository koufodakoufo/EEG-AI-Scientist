# Studies

New work belongs here, one directory per study:

```text
studies/<study_id>/
  study.json       # single entry configuration
  task.md          # frozen question and deliverables
  runs/<arm>/<repeat>/   # ResearchRunner state, messages, final answer
  reviews/         # packets, raw feedback, records, feedback sets
  meta/            # optional rule candidates/decisions
  report.md        # generated current readout
```

Create a draft with:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m eeg_scientist.cli study init --id my_study
```

Edit `study.json` to add arms (each arm names a backend and a repeat count).
`study validate` refuses unverified backends and missing model IDs. `study run`
requires `--confirm-cost`; no paid run is started by `init/validate/status/report`.

Do not put historical runs here. Old completed experiments live in
`archive/experiments/` and are read-only.
