# Legacy modules

These modules are the old synthetic/reporting implementation. They remain for
old commands and regression tests; new work must use `study` / `review` and
`ResearchRunner`.

```text
cases.py               synthetic case generation
experiments.py         fixed classifiers/tools/split audits
splits.py              old window/trial/subject splitter
scientist.py           old decision prompt/parser
capability.py          old Flash capability check
meta.py                old restricted Meta rule call
runner.py              old synthetic episode state machine
study.py               old synthetic study orchestration
provider.py            old Ollama/OpenAI provider
reporting.py           old report renderer
flash_report.py        old Flash report renderer
diagnostic.py          old diagnostics
emotion_experiment.py  archived emotion study orchestration
```

Root-level files with the same names are compatibility shims. Do not add new
features here. The new path is:

```text
cli -> study_cli -> study_runtime -> research.ResearchRunner
```
