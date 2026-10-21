# Legacy modules

These modules are the old synthetic/reporting implementation. They remain for
old commands and regression tests; new work must use `study` / `review` and
`ResearchRunner`.

Root-level files such as `runner.py`, `study.py`, `provider.py`,
`reporting.py`, `flash_report.py`, `diagnostic.py`, and
`emotion_experiment.py` are compatibility shims that re-export these modules.

Do not add new features here. The new path is:

```text
cli -> study_cli -> study_runtime -> research.ResearchRunner
```
