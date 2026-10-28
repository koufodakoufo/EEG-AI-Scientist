# Environment Handoff Implementation Plan

> For agentic workers: use the executing-plans workflow for this bounded operational task; preserve evidence and verify each completion claim.

**Goal:** Finish local archival, connect nccserver0, configure Codex, and document the GitHub / Windows / server0 working-copy relationship. Stop before Agent architecture changes or scientific task expansion.

**Architecture:** Preserve the existing EEG-AI-Scientist repository and experiment archive. Keep the colleague's framework snapshot as a separate source lineage. Use an isolated, verified personal directory for remote setup; shared data remain read-only.

**Tech Stack:** Git, PowerShell/OpenSSH, Linux, Python, Codex CLI.

**Spec:** X:/projects/EEG-AI-Scientist/EEG_FM_Codex_Handoff_2026-10-28.md plus the user's current explicit scope and preservation constraints.

## Global Constraints

- Do not modify, move, delete, chmod, or chown dataset/shared storage or existing server project/environment content.
- The new authorization permits setup only in a verified independent personal workspace; inspect capacity and existing content before creation.
- Preserve local user changes, the staged index, original archives, provenance and historical experimental outputs.
- No credentials in logs, Git, reports, or messages. Authentication is performed by the user.
- No formal EEG training, GPU jobs, architecture redesign, or research task expansion.
- Copy operations must use a read-only source, a distinct destination, temporary incomplete output and checksum verification; never delete the source.

## Review Focus

- Campus source-address selection with mobile tethering as default route.
- Shared mounts and symlinks must not turn a personal output directory into protected data storage.
- Existing uncommitted files and Git index must survive archival unchanged.
- Offline tool availability is separate from successful model authentication/call.
- A snapshot import must not be described as the current verified team upstream.

## Tasks

- [x] 1. Inventory local Git/archive/source, verify archived hashes, preserve current working files and index in a recoverable local snapshot with a manifest.
- [x] 2. Connect server0 using the campus interface; inspect identity, storage, path ownership, tools and outbound connectivity without changing existing content.
- [x] 3. Create independent personal workspace and lightweight runtime only after checks; prepare a reproducible source copy and source/version records.
- [ ] 4. Install or reuse Codex in that workspace; complete user authentication and a bounded non-scientific smoke check.
- [x] 5. Establish and verify source exchange using the actual Git remote or a clearly labelled temporary snapshot arrangement; keep old and team framework histories separate.
- [x] 6. Run appropriate offline/CPU checks, document daily operation and exact completion/remaining limitations, then stop before research expansion.

## Execution Ledger

- Initial: user approved continuous execution of this operational scope. No separate design approval is needed for routine choices already covered by that authorization.
- Ruling: this is environment setup and archival, not implementation of new software behavior. Verify by manifests, hashes, Git state, CLI checks and existing tests; do not add artificial tests or alter framework architecture.
- Initial network evidence: default TCP to 10.20.38.38:1022 timed out; binding local campus address 10.14.241.149 connected. No route/config changes were made.
- Task 1 complete: local-archive/restore-check-result.json verifies 1,214 files, HEAD and staged patch. Original X: working tree/index/status preserved. Historical archive 830/830 unchanged; eight missing display paths recovered only in backup from identical-hash archive originals.
- Task 2 complete: SSH identity nccserv0, duandh UID2046; /data local ext4 (357.66GiB free at inspection), /home 9.49GiB free. No existing server projects or dataset inspected recursively or modified.
- Task 3 complete: exclusively created /data/duandh/eegfm-stage-a-20261028. Codex 0.165.0 official asset hash verified; Python3.10.12 venv with PyYAML6.0.3 and pytest9.2.0. Working directory occupies approximately439MiB after setup and tests.
- Network ruling: reuse the laptop's existing127.0.0.1:10808 proxy through an explicit temporary SSH reverse forward on server127.0.0.1:18080. No system route/profile changes. Loopback is not isolation from other users on the same server; document temporary lifecycle. PyPI dependencies installed directly after proxy download slowness was confirmed.
- Installer ruling: stopped only this task's identified stalled download/installer processes; retained incomplete downloads in the new personal tools directory. Download resumed and final asset was verified before execution. No cleanup of other processes/files.
- Task 4 partial: binary/config/wrappers verified; login status Not logged in. Device authorization endpoint successfully generated a code presented only in this chat, not stored in reports. Await user authorization; real read-only model smoke remains pending.
- Task 5 complete (temporary arrangement): user confirms no team upstream address. Independent snapshot-import repo on Windows and server0 atfb6c37e64a58d316d98ae087190483d3d4bf1389; transfer bundle SHA256a0e2131f29ec3ae176887fe69c71149563b593de08aa5d3e366d52fcf0cc13fd. Original distribution label e6f6e50 is not asserted to be a verified commit. A metadata-only correction commit restored fake_agent.py's original644 mode after the initial import accidentally recorded755; final281 files and modes match the tar.
- GitHub ruling: no new repository or speculative remote created. Existing old-project GitHub remote independently accessible via local Git (main d0bbb6e, overnight c22df47); connector's different account visibility does not invalidate it. New framework uses a labelled Git bundle bridge until upstream is known. No push or unrelated-history merge.
- Task 6 complete: server0 full offline suite12 passed in44.07s (44.26s wall), including full synthetic loop and registered-job recovery; source clean before and after. Script agent only, GPU disabled, no real EEG data or paid model call. Daily entry scripts and Chinese manual prepared. Scientific work not started.
- Final review fixed P1: a fresh reviewer reproduced Windows Git dubious-ownership failure under the real user. Corrected ownership only within the newly created Windows framework repository (879 entries); ordinary git status/rev-parse now succeed without safe.directory overrides. Original X: repository untouched.
- Final review fixed P2: proxy startup no longer reports success after an arbitrary500ms delay. It waits within a bound and verifies the remote listener is exactly127.0.0.1:18080, stopping only its own new process on failure. Existing tunnel and actual ss listener verified; evidence proxy-listener-verified.log.
- Final review documentation correction: stage A target includes personal login/smoke, but these remain explicitly pending; do not describe the entire target as completed.
- Runtime usability: installed pip26.2.2 in the private venv, pip check passes; final resolved dependency list saved remotely. Configured Git author identity only in the new remote repository using the user's verified local Git identity; no global profile or Git configuration changed.
- Root independently rechecked all28 local backup artifact hashes: zero mismatches. Ordinary original-repository git status still retains the user's original16 tracked modifications and MM .gitignore state.
