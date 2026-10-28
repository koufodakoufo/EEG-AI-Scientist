# Resume safely

Start with root `MORNING_SUMMARY.md`, then `RESULTS.md`, `PROCESS_AUDIT.md` and a few specific evidence rows. Formal local workspace is **X:/projects/EEG-AI-Scientist**; branch **research/overnight-20261029**. No push. The C support folder is not a development checkout.

The current same-origin server checkout is:

```text
/data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration
```

Open that directory in the VS Code Remote SSH window for `nccserver0` to see the project tree and Git branch. Opening only a terminal leaves the VS Code file workspace empty. Active framework is its `framework/` subdirectory. The old `/source/eeg-fm-research` checkout remains the separate `fb6c37e` import snapshot; do not merge unrelated histories or continue development there.

## Network and login

All nightly model workers are terminal. The helper-owned reverse tunnel was stopped and its supervisor exited normally; there is no overnight background model job to resume. Other SSH sessions and base Codex authentication were left alone. Temporary worker auth copies were removed. Do not try to resume one of those worker homes.

To use Codex again, keep the Windows proxy application running and start a new scoped tunnel in a Windows PowerShell window:

```powershell
cd X:\projects\EEG-AI-Scientist
.\scripts\Start-NccServer0Proxy.ps1
```

Keep that window open. It selects a server loopback port and updates only the managed project/IDE proxy settings. Campus connectivity and the Windows proxy must remain online. The PowerShell 7 JSON-date identity bug has been fixed; do not edit PIDs or kill unknown listeners to work around a failure.

In the VS Code SSH terminal:

```bash
source /data/duandh/eegfm-stage-a-20261028/environment.sh
cd /data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration
codex login status
git status --short
git log -5 --oneline
```

Login succeeded previously and real CLI invocations completed tonight; repeated device login should not be the default troubleshooting step. An IDE extension is optional and was not part of this night's acceptance. Source the environment again after a new tunnel; the former port 34001 is intentionally no longer live. To stop a future helper tunnel, run `scripts/Stop-NccServer0Proxy.ps1` from the same X project.

## Scientific continuation boundary

All **24/24** extra worker reservations are consumed. The original nightly budget must not be reset to evade that cap, and M01–M24 must not be relaunched. A future authorized session should create a new dated budget and protocol version. Preserve this baseline even if the next version fixes its evaluator limitations.

Priorities: (1) make replay inputs/options/command caps explicit and separate runtime diagnostics from scientific artifacts; (2) manually inspect the few concrete extraction/coverage disputes, redesign atomic granularity/reference completeness on development material, then freeze a new evaluation; (3) verify one real model/data/head/preprocessing/split combination before any real pilot. A new generic-prompt or equal-length-prompt condition also needs a new frozen plan. The candidate skill is not installed globally and has no demonstrated benefit yet.

Minimum information still needed for real EEG work: exact authorized dataset/preprocessed-feature path, exact checkpoint and head identity/hash, corresponding loader/units/channels/splits, applicable access/license terms, and any GPU allocation. Wzf's latest team GitHub upstream remains unknown. Do not guess paths or copy dataset contents while looking for them.

## Verification and recovery

Linux tests use `/data/duandh/eegfm-stage-a-20261028/venv/bin/python`, not a venv under the nightly folder. Framework suites already passed; rerun them when a relevant change warrants it. The trusted Actor launcher uses the pinned native CLI in `overnight-20261029/tools/runtime-review/bin/`; an interactive base CLI is not automatically the same isolated evaluation configuration.

`X:/projects/EEG-AI-Scientist/.local/overnight-20261029/recovery/` holds the verified private evidence tar, per-file inventory and Git bundle. `RECOVERY_MANIFEST.json` records final hashes and commit; `FINAL_SYNC.json` records the final local/server HEAD check. These are private local recovery files, not GitHub deliverables. Restore only into a deliberately chosen empty recovery destination, verify hashes, and then select files to recover. Do not extract over the live workspace or restore credentials from a report. Current working files and server originals have not been deleted.
