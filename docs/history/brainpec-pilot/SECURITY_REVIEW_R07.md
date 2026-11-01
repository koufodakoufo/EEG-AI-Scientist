# R07 independent security and lifecycle review

2026-10-29. Builder reviewer; not an evaluated Actor or Distiller. Reviewed the working-tree changes based on `58b8d71`, particularly `driver.py`, `driver_bridge.py`, `actor.py`, and `real_worker.py`. Production source was not edited. Probes use synthetic data and local Windows/WSL only; no server action, model call, authentication read, existing dataset access, or private scientific-result access occurred.

**Final review disposition, 15:35 +08:** six findings were reproduced. Three bridge fixes were independently verified locally. The public-view label leak (P1), hard-controller-death recovery (P1), and frozen worker enrollment identity (P2) remain pending verification. Root is implementing those changes. No demonstrated host-file escape or repeated final-test execution was found. Local sandbox checks do not certify the server configuration or scientific validity.

## Findings

### P1 — Raw recording/sample IDs reveal labels; deleting `y` is insufficient

Locations: `framework/eegfm/research_bench/real_data.py:413–425`; `real_worker.py:179–186`, `316–381`.

The prepared data derive `y` from recording suffix `_1`/`_2` and retain that suffix in `sample_ids` and `recording_ids`. Rows are also appended in recording/condition order. The worker's forbidden-array-name check accepts those IDs. A candidate that parses only the ID suffix produces accuracy and balanced accuracy of **1.0** under the trusted classification aggregator on synthetic IDs with this exact format. No EEG or hidden label was needed by the candidate.

Fix: never export the raw prepared NPZ or raw identifier metadata. Mint opaque sample and subject IDs, remove recording/window/condition metadata, and privately permute aligned rows before exporting views. Keep the mapping and permutation private; a public reconstructible seed defeats this protection. Align trusted truth to the opaque IDs. Root confirmed a dedicated view builder is being implemented; this remains an enrollment blocker until independently checked.

Tests: reject views retaining recording IDs or condition-derived IDs; verify aligned train/validation/test rows after permutation; show metadata-only classifiers cannot reconstruct condition; confirm hidden test views are absent from Actor mounts. Probe: `probes.py ids`, result `id-leak.json`.

### P1 — BridgeDriver bypasses the legacy lifetime lock and can run two Actors in one case

Locations: `framework/eegfm/driver.py:330–339`; `driver_bridge.py:538–549` (initial review lines).

The legacy `driver.lock` is acquired only by `driver.main`, while `BridgeDriver` calls the inherited `Driver.loop` directly. Two independent processes can both pass the session-count check and enter their launch callbacks for the same episode. The local probe used actual `BridgeDriver.loop`, `max_sessions=1`, and two subprocesses: **two callbacks entered, two sessions persisted, both exited 0**. Besides exceeding the episode budget, concurrent Actors invalidate the controller's assumption that the shared case is quiescent while requests and candidate snapshots are ingested.

Fix: acquire a nonblocking, episode-wide lifetime lease before any loop/review/launch/ingestion; make it mandatory for the bridge entrypoint. Persist a session reservation before each model launch so a process crash cannot make a launched session disappear from the budget. Keep final-test reservations consumed across uncertain outcomes.

Tests: second actual driver process fails before its callback; restart after a pre-launch/post-launch crash counts the reservation; no Actor can remain active while another controller snapshots that case. Probe: `concurrent_actual_driver_loops` in `bridge-probes.json`.

**Closure verified:** root added a lifetime flock around `super().loop()` and durable pre-launch session reservations. The original two-process probe now enters one callback, persists one session and rejects the second process. Updated bridge suite: 27/27 pass. This fixes concurrent live controllers; the separate hard-death finding below still applies.

### P1 — Hard controller death leaves a child alive; lease availability does not establish safe resume

Locations: `framework/eegfm/research_bench/budget.py:184–185`, `214–220`; `driver_bridge.py:487–499`, `591–602` at verification time.

`run_bounded` starts a new session and relies on its `finally` block for owned-descendant cleanup. SIGKILL bypasses that cleanup. A dedicated local probe killed only its own launcher and observed its known child still alive after the launcher exited with `-9`; the probe then killed that child after checking PID/start identity. No model or EEG ran. A dead controller releases the new lifetime flock, while its earlier Actor may still own the case. An unresolved durable session reservation alone initially did not prevent launching the next session below the six-session cap.

Fix: block restart, ingestion and new reservations whenever an earlier reservation is unresolved, until a trusted owned-process cleanup audit establishes quiescence. Persist enough launch/process identity for that audit. A supervisor/cgroup or equivalent design is needed for hard process-death resource enforcement; ordinary `finally` cleanup is not proof that SIGKILL reaps descendants, particularly code-mode hosts with separate process groups.

Root acknowledged this and is adding a fail-closed unresolved-session gate. **Pending independent verification at R07 cutoff.** That gate mitigates unsafe overlap; it must not be described as killing orphan children. Test controller SIGKILL below the session cap, then attempt a second actual loop and ensure no callback or request ingestion occurs. Probe: `parent_death.py`; output `parent-death.json` (`owned_child_survives=true`).

### P2 — Malformed Actor path values crash the driver instead of receiving safe rejection

Locations: `driver_bridge.py:77–92`, `276–283`, `546–558` (initial review lines).

An otherwise valid brief request with `payload={"path": null}` reaches `PurePosixPath(None)` and raises `TypeError`. The session handler catches only `ValueError` and `OSError`, so the real loop exits with no rejection response. Non-string operations and other malformed JSON field types need the same treatment. This is a reproducible reliability/availability defect, not privileged code execution.

Fix: validate bounded request types before path construction or membership operations; normalize expected schema failures to a safe rejection without swallowing programming errors. Test null/list/object paths and operations, malformed batches, and a subsequent corrected request. Probe: `null_actor_path` initially reports `TypeError` and an empty response list.

**Closure verified:** the original null-path probe now returns a safe `ValueError` rejection and the loop continues. Root added bounded path/operation validation and regressions.

### P2 — A stale poll can downgrade an immutable successful job

Locations: `driver_bridge.py:423–463` (initial review lines).

Two polls can observe a pending job. After one records `succeeded`, the other returns an earlier `waiting` response. `_accept_result` correctly rejects the inconsistent terminal update, but `poll_jobs` catches that exception and `_fail_job` unconditionally overwrites the successful job and attempt as failed. The probe observed **succeeded → failed**. A late polling exception has the same overwrite path. This can permanently block completion even though the final test was valid and consumed.

Fix: make `_fail_job` conditional on a still-pending state inside the same transaction; ignore stale waiting responses and preserve terminal evidence. Apply the same terminal-state guard to asynchronous callback errors. Test success followed by stale waiting/error and concurrent duplicate terminal responses. Probe: `stale_poll_overwrites_terminal_result` in `bridge-probes.json`.

**Closure verified:** the original concurrent probe now remains `succeeded`; `_fail_job` preserves terminal states and stale waiting results are ignored. Root added a matching regression.

### P2 — Worker cache identity does not bind its enrolled execution inputs/configuration

Locations: `real_worker.py:132–151`, `156–175`, `226–244`.

The persisted job fingerprint contains the candidate, public manifest and split-manifest hashes, but not the actual selected train/evaluation file bindings, aggregate implementation or runtime/release policy. Reconstructing the evaluator with a changed training file and its new accepted `FileBinding` hash, while retaining the same job/manifests, silently returns the old cached success. The synthetic probe confirmed **input_changed=true**, **same_cached_result=true**, **execution_count=1**. Execution was mocked for this identity test; no candidate ran.

Fix: persist and compare an enrollment fingerprint covering all split input hashes, private truth bindings, runtime/dependency identity, aggregator/protocol identity, released metrics and limits. Bind that fingerprint into job records and receipts; reject changed enrollment on resume rather than reexecute a consumed test. It is acceptable for a mandatory trusted integration layer to provide this binding, but it must be verified, not inferred from filenames. This is a trusted configuration drift/reproducibility issue, not a demonstrated Actor escape.

Test: reconstruct with changed train/evaluation bytes, aggregator version, runtime dependencies or policy and verify rejection before any cached success is attributed to the new configuration. Probe: `probes.py worker`, result `worker-binding-probe.json`.

## Verified boundaries and remaining acceptance conditions

- The reviewed bridge commits final-test reservation before calling the worker; duplicate IDs, changed candidates, test-before-lock, and concurrent test requests have regression coverage. The review did not find a repeat-test execution bypass.
- The local WSL worker canary denied the private sentinel, external network, other split access, and writes to public/input/candidate/root/dev; own output was writable. Timeout and symlink-output paths failed safely. Raw stdout, candidate filenames and arrays are not projected through the concrete worker result; only fixed released-metric artifacts are returned.
- The corrected Actor profile binds the canary to the profile template and native/host/bwrap binaries, rechecks actual configuration/binary bytes, and changes the template fingerprint when scientific read roots change. Actual server path/configuration validation remains required; this review did not perform a server canary or launch an Actor.
- The documented v3 evidence module correctly states that CSV arithmetic and execution provenance do not authenticate a submitted target column. Likewise, the classification aggregator and `done` lifecycle state cannot establish Q1 recovery, genuine intervention through the frozen model, or Q2/Q3 mechanism claims. Since an evaluation view may contain raw EEG, a candidate can directly calculate Q1 feature targets. Scientific acceptance must check the frozen computation path and controls independently; this is an explicit integration condition, not a claim that the unfinished scientific evaluator has already failed.
- Dependency/environment contents and private inputs need immutable enrollment identity, beyond Python executable hashes. Confirm only the dedicated owned venv and required immutable assets are mounted. Server probes must verify the actual configuration, including absent GPU-device access, before claiming isolation or the zero-GPU policy has been enforced.

## Reproduction and validation

Probe directory: `.local/research/2026-10-29-brainpec-real/review-R07/`. All test data are synthetic. `probes.py` is bounded and does not edit production files.

```powershell
# Linux bridge repros; includes actual inherited Driver.loop in two subprocesses.
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/x/projects/EEG-AI-Scientist && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=framework python3 .local/research/2026-10-29-brainpec-real/review-R07/probes.py'
# Same command with trailing worker tests cached-input identity (mock execution).
# Windows NumPy synthetic ID-only classifier:
python .local/research/2026-10-29-brainpec-real/review-R07/probes.py ids
```

Existing tests, observed during R07:

- WSL system Python: `unittest discover -s framework/tests -p test_driver_bridge.py -v`: **23 passed**.
- Independently rerun after root fixes: same bridge command, **27 passed**. The original adversarial probes were also rerun; results are in `bridge-probes-after.json`.
- WSL system Python: corresponding `test_real_worker.py`: **13 tests, 11 passed, 2 NumPy skips**, including actual bubblewrap and timeout canaries.
- Windows Anaconda Python 3.12.4 / NumPy 1.26.4: `pytest framework/tests/test_real_actor_profile.py framework/tests/test_real_worker.py -q -p no:cacheprovider`: **9 passed, 11 Linux skips**.
- An initial Windows bridge run could not import legacy `fcntl`; it was rerun successfully in WSL. This platform limitation is not counted as a production bug.

The root is implementing the three remaining changes. This report preserves the original failure evidence and marks only the three independently rerun fixes closed. Public-view export, hard-death recovery, worker-enrollment identity and actual server deployment require their own acceptance evidence. No final system or real-science acceptance is claimed here.
