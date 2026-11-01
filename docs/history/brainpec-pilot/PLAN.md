# Next-stage execution plan

Started 2026-10-29 14:13:58 +08; close new research at 01:28:58, hard stop 02:13:58 next day. Authoritative scope is TASKBOOK.md plus current user messages. Ordinary implementation and scientific slice selection are delegated; no new approval gate. Initial baseline commit: 58b8d71.

## Decision and acceptance

The primary target is a real, isolated Codex Actor completing the existing wzf Driver lifecycle, while studying recoverable EEG features and their effects on a frozen task predictor. Existing shared datasets remain read-only and uncopied. The bounded resource audit has not established a matching downstream checkpoint. Preferred practical fallback: official CBraMod pretrained backbone + publicly downloaded EEGMAT + a small task head fitted only on new training subjects. This is a new adaptation study, not reproduction of BrainPEC's task model or a clinical stress study. Final route and protocol freeze precede test access.

## Work slices

1. **Restore/recon (first 30 min).** Verify paths, Git, proxy, login, CPU/disk, public sources and available model/data interfaces. R01 public-resource audit and R02 driver audit are independent Builder helpers. Deliver RESOURCE_RECON and DRIVER_RECON. Reuse the user's proxy; do not stop it at closeout.
2. **Real resource preparation (within 90 min decision).** Download the pinned official pretrained checkpoint and EEGMAT into owned new storage. Verify hashes, sizes, license, channels, units, paired subject identities and no split overlap. Install a CPU environment under /data, profile one training batch. Predeclare a 12-family-entry panel (62 output columns), train-only scaling, subject splits and useful CPU-feasible layers. Do not inspect final-test results while choosing these.
3. **Trusted driver bridge.** Preserve Driver.loop as lifecycle owner. Add an isolated execution hook and a controller-owned state/request ledger. Brief review is delegated_protocol_review with honest identity. Evaluation uses fixed typed inputs and a separate sandbox; no candidate code gets unrestricted host/data access. Lock hashes are checked on every final-test request, and a crash-safe external ledger consumes the one-shot test before execution. Actor writes cannot declare success or bypass review. Analysis validity, including null/negative results, controls retention.
4. **Science implementation/reference.** Fit a frozen-backbone head on train; use validation for explicitly bounded tuning. Cache train/val interface outputs separately from hidden test. Implement genuine layer activation interventions with the frozen downstream path, feature recovery, actual-rank/strength-matched random controls, residual recovery and subject bootstrap/permutation. Freeze reference protocol before first test. If runtime makes full Q1–Q3 impossible, narrow honestly to Q1 rather than use synthetic data.
5. **Evidence/scoring B (initial timebox 90 min).** Fix replay dependency and split-row binding contracts, explicit environment/command limits, scientific outputs versus diagnostics. Separate point/interval/mechanism claims and reference coverage from numeric validity, new findings and unsupported claims. Freeze scoring before first Actor. Use synthetic calibration only; pending textual calibration is reported, not a reason to delay a valid real pipeline. Keep yesterday's scores unchanged.
6. **Real baseline lifecycle then controlled pairs.** First real Actor target by hours 4–6. Fresh Actor homes/workspaces/history only public material and its own episode; no Builder/history/gold/test access. At most six sessions/90 min per episode. Freeze the existing M15 skill bytes before transfer evaluation. Only after first complete lifecycle, admit complete pairs based on measured costs; maximum three, desired two. Conditions differ only in skill; register order before outcomes.
7. **Verification/closeout.** Independent clean replay, security and real-lifecycle checks, final review, local commits and same-origin server sync. Preserve all failures, one-shot state, source hashes and resume steps. Produce Chinese entry, one-page summary, science results and Actor case study, integration acceptance, manifest/evidence index/change log. Do not push.

## Verification strategy

Use TDD for new security boundaries and scientific invariants. Critical regressions: test before lock, changed code/repeated test, mixed-split/feature escape, cross-episode access, fake human review, failed job or missing shard marked done, capacity errors, attempt limits, waiting/resume, timeout descendants, valid negative analysis retained. Scientific checks cover channel/unit/shape, subject partition, train-only transforms, finite nonconstant features, strict checkpoint load, true model-path intervention, actual control rank/strength and subject-level uncertainty. Run appropriate full suites before commits; record platform-limited legacy checks separately.

## Resource ownership and evidence

- Local: X:/projects/EEG-AI-Scientist only; new evidence .local/research/2026-10-29-brainpec-real.
- Server code: /data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration.
- New compute/cache/evidence: /data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029.
- Protected original source: /data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research; no modification.
- Existing user proxy PID 32164, remote port 36945, started 14:13:48 +08; reuse, not owned by this run.
- New BUDGET.json owns R-series calls (48 max, max 2 parallel, reserve 8); CPU 4 threads, RAM 12 GiB, GPU 0; new storage 20 GiB, downloads 8 GiB.

## Decision log

- 14:26: authentication reports ChatGPT logged in; endpoint HTTP 403 is reachable but is not a model acceptance test. Scientific dependencies are absent in the old venv, so create a separate owned CPU venv. Home free ~5.05 GiB, /data free ~225 GiB; direct all caches to /data.
- 14:27: recent project conversation confirms the priority is real scientific work plus the two workflows connecting; it contains no additional GPU allocation. Driver audit identifies unsafe mutable state, legacy shell evaluation and fake-human approval paths; bridge must isolate these rather than claim old scripted acceptance proves them safe.
