# Verification checkpoint — 2026-10-30

Core revision: `6263df8c8bb441cfbd8a3c6ce7ead0617b234ded`, identical on Windows and nccserver0. The original numerical evaluator and frozen reference implementation were not changed by the recovery work.

- R56 independent review found and fixed one error: broad exception classification could have treated trusted aggregation faults as correctable candidate failures. The revised worker uses a closed constraint-message allowlist, exact output-file checks, and separate trusted-response integrity validation.
- Targeted recovery and prompt tests passed. Actual frozen skill bytes, their hash and the full delivered prompt hash were checked through a synthetic native-launch boundary, including the launch failure path. This is a wiring test, not evidence of model benefit.
- The first full Linux test invocation (`full-linux-tests-03`) produced 22 failures, 216 passes and 2 skips. Its outer resource wrapper prevented the tests' own affinity setup, and its PATH omitted the owned bwrap executable. Those were test-launcher errors; the output is preserved.
- The corrected invocation used the owned bwrap on PATH, four CPU affinity cores, four numerical threads, an ordinary pytest process, and a new temporary directory under `/data`. It completed **240 tests, all passed, in 125.86 seconds** (`full-linux-tests-04`). No production code was changed to bypass the initial launcher errors.
- System-disk free space briefly fell below the existing 4 GiB admission floor. Only the newly created `pytest-1` fixture directory from `full-linux-tests-03` was copied to owned `/data` storage, all 909 regular-file hashes and symbolic-link targets were checked against the source, and that temporary source was removed. The older `pytest-0` directory and other users' files were not changed. Full provenance is retained in `evidence/pytest03-temp-archive.json`; this did not discard test evidence. The original admission floor was preserved and passed before E05 enrollment.

Comparison v2 was sealed before its first Actor with SHA256 `113a6a3d719c4c734ec670c9943d174e1ee8a45ff791def1137620434fa36278`. E05 began at 01:11:01 +08. A trailing here-document delimiter produced a launcher-shell error **after** the detached controller had started; its PID/start-tick receipt and running R60 were verified, and it was not launched again.

E05 subsequently completed five genuine model sessions, baseline validation, one Q1 iteration, candidate lock, one final test and a report. Both validation and test contain 24 Q1 feature-layer groups; Q2/Q3 were not implemented (`numeric_scope_complete=0`). This is actual lifecycle acceptance with partial scientific scope. Source review and clean replay remain separate requirements. E06, the predeclared skill condition, was launched at 01:24:51 +08.

Private logs, runtime state, original arrays and model traces stay outside Git. This checkpoint is not a final comparison result or a capability claim.
