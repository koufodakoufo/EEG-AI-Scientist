# Build checkpoint, before real Actor execution

This checkpoint is implementation progress, not scientific/integration acceptance.

- Full Windows framework pytest attempt: 115 passed, 28 skipped, 41 failed. All 41 failures are the POSIX-only driver bridge (27) and legacy program (14); the missing `fcntl` and POSIX executable semantics are recorded, not hidden. Full log is retained privately as `verification/root-framework-windows-checkpoint.log`.
- Current bridge on WSL Linux: 27 tests pass. New regressions first reproduced malformed paths, stale terminal state, concurrent controller lease and a crash consuming its reservation. A mandatory unresolved-reservation gate now blocks automatic case reuse after controller death. This does not claim that SIGKILL automatically kills every descendant.
- Current sandbox worker on WSL Linux: 14 tests, 12 pass and 2 NumPy-dependent tests skip. Actual bwrap isolation/timeout canaries pass. Cache identity now binds train/evaluation files, runtime/dependency manifest, aggregator code/resources, release policy and limits. A changed input was first reproduced returning stale success, then rejected after the fix.
- Numerical and resource primitives pass on native Windows. First official-checkpoint/real-training-window feasibility profile passed with no test access. Formal scientific Linux validation and server sandbox certification remain pending until runtime installation completes.
- Public views use random opaque IDs and private row permutations. Full raw adapters, data locations, model-selection scores and reference methods are excluded from Actor material. Actual exported-view verification remains a later acceptance step.
- Text scoring v3 structure and synthetic contracts are implemented; semantic judge calibration remains pending. Old scores are unchanged.

Evidence is under `.local/research/2026-10-29-brainpec-real/verification/`. No dataset/shared-storage writes, no GitHub push, no formal Actor launch at this checkpoint.
