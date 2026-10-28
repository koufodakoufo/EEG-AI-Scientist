# Overnight implementation plan — 2026-10-29

Authority: the user's explicit overnight request and `EEG_FM_Codex_Overnight_Taskbook_2026-10-29.md` (SHA256 e203618cea72e09e881f54870bc5dd6d5c96f265a9a0012f64e923d58439c562). This supersedes the previous stop before research expansion and permits Builder changes to framework tooling. Actor permissions remain narrower. No GitHub push, dataset/shared-storage mutation, or GPU work is authorized tonight.

Start 00:29:40 +08; initial reconnaissance ends by 00:49:40; stop starting research at 07:59:40; hard finish by 08:29:40. Limits and model reservations are in BUDGET.json. Price is unknown, not zero.

## Concrete sequence

1. **P0, 00:30–01:05:** verify disk, identity, CLI auth, proxy and one 90-second model preflight; inspect usable user namespaces. Record exact versions and evidence. Do not mistake login for an inference test.
2. **P1, 00:40–02:05:** implement standard-library research_bench contracts, immutable task/resource/evidence manifests, directional claim scoring, explicit unknown/empty statuses, and bounded execution. Test adversarial scoring fixtures and failure recovery. Keep the original wzf driver independently runnable.
3. **P2, 00:40–01:20:** reference Builder obtains primary FIRE/BrainPEC sources, grounded research tree and three candidate slices. Select public task descriptions without target conclusions. Freeze gold, scoring policy, budgets and fallback tier before any dev Actor. If real resources are unavailable, use a clearly labeled mechanism pilot and retain real EEG work as blocked.
4. **P3, 01:00–02:30:** prepare a same-origin server integration checkout from this branch via bundle. Keep the prior imported snapshot and installation. Build fresh Actor launches with minimal configuration and actual read/network canary tests. Model control traffic must work while tools cannot read other cases, private gold, launcher state or credentials. An unproven boundary blocks blind evaluation.
5. **P4, after P1–P3:** run a bounded development episode, extract claims/evidence and score. Provide only its public task, trace and feedback to a fresh Distiller. Freeze a versioned skill and its injected bytes. If no valid dev episode exists, label any skill as builder-designed candidate; do not invent distilled experience.
6. **P5:** if isolation and frozen packages pass, run one matched holdout baseline/treatment pair, sequentially, with equal budgets and anonymously scored submissions. A second pair is optional within limits. Report case counts, infrastructure blocks, launched failures and uncertainty. Same-paper holdout is not a new-paper result.
7. **P6:** continue valuable offline work if a live branch blocks: crash/timeout/restart fault injection, score counterexamples, preregistered ablations, and a short primary-source research queue. No repetitive unbounded login/network retries.
8. **P7:** final verification, recoverable local commits/bundles, evidence index, RESUME instructions and one-page MORNING_SUMMARY.md (<=1000 Chinese characters). Report L1–L4 separately and all unproven boundaries.

## Implementation boundaries

- Add `framework/eegfm/research_bench/`, `framework/tests/research_bench/`, benchmark templates and skill candidates within the existing root repository. No nested git init; no new local workspace on C:.
- Keep scientific references/gold under ignored `.local/overnight-20261029/private/`; export public bundles through an explicit allowlist. Published methodological notes must not be mounted into Actor contexts.
- Builders may share implementation context. Evaluated Actors and Distillers use fresh processes, separate homes, no resumed conversations, no inherited Builder history. A fresh context alone does not prove filesystem isolation.
- Existing framework read/write rules apply to legacy researcher runs; the new Builder work is explicitly authorized. Do not use the legacy network-enabled Adapter as a blind Actor launcher.
- Use one branch `research/overnight-20261029` because the user requires X: as the sole local workspace. Preserve the base 5df1d9e and archives; no unrelated-history merge.
- Model calls reserve a ledger slot before dispatch; max24, two model workers, 30 minutes each. CPU4, RAM12GiB, GPU0. Enforce limits outside prompts, with owned process-group termination and persisted states.

## Reconnaissance already observed

At start, X: had only the untracked taskbook; remote source HEAD fb6c37e was clean. Native server CLI is 0.165.0 and reports ChatGPT login. Home free ~6.60GiB, /data free ~327.9GiB. `unshare -Urn true` succeeds; Python3.10.12 environment has pytest/PyYAML but no NumPy/SciPy/sklearn/torch. Existing proxy was stopped. No inference or blind isolation has yet passed.
