# R84 candidate verification

2026-10-30, local workspace `X:/projects/EEG-AI-Scientist`.

**Model calibration is not run.** No native call, remote staging, reservation,
ledger write, commit, or push was performed by this preparation task. A local
temporary staging test was created and removed by the test fixture; it is not
the root's authoritative freeze.

Fresh verification completed successfully:

```text
python -B -m unittest discover -s scripts/research -p test_semantic_calibration_v3.py -v
Ran 9 tests; OK.

PYTHONPATH=framework python -B -m unittest discover -s framework/tests/research_bench -p test_protocol_v3.py -v
Ran 10 existing contract tests; OK.

python -B scripts/research/semantic_calibration_v3.py check --fixtures docs/research/2026-10-30-extension/semantic-calibration
fixtures_valid_not_model_calibrated
12 extraction reports; 16 directional pairs; 13 complete-report oracle atoms
synthetic_numeric_self_check=0.75; semantic_model_calibration=not_run
```

`git diff --exit-code` confirmed no changes to `claims_v3.py`, `evidence_v3.py`,
or `framework/tests/research_bench/fixtures/scoring_v3_calibration.json`.
The initial missing-harness test failed as expected; the two added regression
tests for cross-split reassignment and repeated giant source spans also failed
before their fixes, then the full nine-test suite passed.

Candidate SHA256 values (root must revalidate after review and stage a fresh
authoritative freeze before either actual call):

| File | SHA256 |
|---|---|
| semantic_calibration_v3.py | f46174aea4f414966a3dfd6c1c2e6e27874154807ab3d8f17f7ee531a530a059 |
| test_semantic_calibration_v3.py | 6517ade7fc45ca322d228280edfe788187870b0c7620f9170068c354522a47ba |
| private-oracle.json | 6c5197062ed77a04a4f4f50f06e708bbb3af87e14b379c484148af1b9e1e5f20 |
| extraction-inputs.json | 7daca7143e91ee6db74d3b54873fd390c9d4abd8df70b1e2f1819b1a5ed749ad |
| judge-inputs.json | c443499f0ba8099b1e0d8b5c5cdafcc079d277a3799e53db33ba1fccec4648d5 |
| EXTRACTION_PROTOCOL.md | 3b18e727d265dd936e07565c6c506531778034a5eac386cda04011be6b3ba3e4 |
| JUDGE_PROTOCOL.md | 30d9bed714d8bace5524b7b73000bb598b6eebdd5f03f6c85063dbd58fa4dc55 |
| PROTOCOL.md | 0911797b6dbaedcc6f4eb9077f90b387fa8448313e58bf8a980c147477fc1e20 |

The only intended live calls are the extraction batch and independently
preauthored directional judgment batch specified in `PROTOCOL.md`. Both await
root review and reservation. The small synthetic development result, even if
both calls later pass, does not establish general or clinical validity.
