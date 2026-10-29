# R13 native isolated episode runner

Entrypoint: `scripts/research/run_real_episode.py --config /absolute/trusted/config.json`.
Run with the scientific Python environment on Linux. The JSON and this document
are Builder-only. They must remain outside every Actor filesystem grant.
The implementation is `framework/eegfm/research_bench/real_episode.py`.

The runner creates the frozen public bundle from an explicit allowlist, constructs
`ScientificAggregator` and `SandboxedWorkerEvaluator`, records immutable enrollment,
and calls the existing `BridgeDriver.loop`. Every callback reserves the next
R-series call in the supplied authoritative budget before preparing a fresh
control home and invoking the existing `launch_actor`. No fallback launch adapter,
global conversation, resumed session, or test-side script mode exists.

The source tree must contain the exported `train.npz`, `validation.npz`,
`eeg_api.py`, and resources produced by `export_real_task.py`. Add only those names
to `public_files`; nested `resources/` files are permitted. The runner supplies
the frozen TASK, INTERFACE, API README, and PUBLIC RESULT SCHEMA documents.
Condition `skill` adds the exact bound `SKILL.md`; condition `no_skill` forbids it.
All other public contents and the task ID are identical between conditions.

Config shape (replace every placeholder with an actual verified value):

```json
{
  "schema_version": "real_episode_config_v1",
  "episode_id": "E01",
  "run_id": "real-E01",
  "condition": "no_skill",
  "case_root": "/owned/cases/E01",
  "trusted_root": "/owned/trusted/E01",
  "public_source": "/owned/task-v1/public-source",
  "public_files": ["train.npz", "validation.npz", "eeg_api.py", "resources/EXPLICIT-FILES-HERE"],
  "model": "gpt-6.1-sol",
  "reasoning_effort": "medium",
  "native_binary": "/owned/tools/bin/codex",
  "bwrap": "/owned/tools/bubblewrap/usr/bin/bwrap",
  "scientific_python": "/owned/venv/bin/python",
  "scientific_roots": ["/owned/venv"],
  "runtime_manifest": {"path": "/owned/frozen-runtime.json", "sha256": "SHA256"},
  "auth_source": "/protected/auth.json",
  "proxy_url": "http://127.0.0.1:PORT",
  "isolation_report": {"path": "/owned/evidence/ISOLATION_REPORT.json", "sha256": "SHA256"},
  "budget_path": "/owned/authoritative/BUDGET.json",
  "call_ids": ["R20", "R21", "R22", "R23", "R24", "R25"],
  "train_input": {"path": "/owned/task-v1/public-source/train.npz", "sha256": "SHA256"},
  "validation_input": {"path": "/owned/task-v1/private/evaluation/validation.npz", "sha256": "SHA256"},
  "test_input": {"path": "/owned/task-v1/private/evaluation/test.npz", "sha256": "SHA256"},
  "split_manifest": {"path": "/owned/task-v1/private/split-manifest.json", "sha256": "SHA256"},
  "train_truth": {"path": "/owned/task-v1/private/train-truth.npz", "sha256": "SHA256"},
  "truth_by_split": {
    "validation": {"path": "/owned/task-v1/private/validation-truth.npz", "sha256": "SHA256"},
    "test": {"path": "/owned/task-v1/private/test-truth.npz", "sha256": "SHA256"}
  },
  "bootstrap_resamples": 2000,
  "worker_timeout_seconds": 900,
  "max_attempts": 2
}
```

For condition `skill`, also set `skill` to a `{path,sha256}` binding of the frozen
M15 bytes. Do not expose its source location or any Builder transfer history.
Call IDs must be allocated by the budget owner and still unused; the runner
reserves each immediately before its launch. Unused IDs are never charged.
The runner does not synchronize different copies of a budget ledger: provide
the authoritative one and keep every other launcher using that same ledger.
The frozen runtime manifest should identify Python, package versions and wheel
or dependency hashes; it is mandatory with the scientific runtime. Worker
enrollment additionally hashes executable binaries and all aggregate truth
bindings. Do not change installed dependencies after enrollment.

The passing live certificate must match the actual native executable, code-mode
host, bwrap, and profile-template hash, including the exact scientific roots.
It must contain successful scientific-read/Python and denied scientific-write
probes. Model identity and medium effort are checked from retained native trace
metadata on every session. Authentication is copied only by `prepare_control`
and never read or printed by this runner.

The Actor receives only the immutable public bundle and a trusted JSON projection
embedded in each fresh prompt. The projection includes only this episode's
controller outputs. Brief, code, notes and reports persist in the same case.
Only bounded session status/request-count feedback is added as own-session
history; host paths, worker stdout, private receipts and other episodes are
absent. Requests are read from the exact session-specific filename after owned
process cleanup. Duplicate JSON keys, links, oversized batches, and foreign
episode IDs are rejected. The bridge owns operation validation and one-shot
test reservation. The scope reviewer checks the frozen brief declaration plus
a substantive plan and records delegated mechanical review, never human review.

The five-stage route is brief; contract+baseline; iteration; lock+test; report.
At most six sessions of 900 seconds are launched. A persisted 5400-second wall
deadline prevents further model reservations and refuses worker dispatch when
its full bound cannot fit. Worker resource bounds remain four CPUs, 12 GiB,
no GPU, and at most 900 seconds. Failed model sessions consume a reservation;
failed allocated worker jobs remain failures. Unknown interrupted native calls
are blocked by the bridge's existing crash-resume guard and never silently
relaunched. Do not delete enrollment to reuse a nonempty case.

`ENROLLMENT.json`, native launch evidence, filtered visible traces, controller
journal, and worker evidence remain private. `FINAL_PUBLIC_PROJECTION.json` is
the same filtered projection, retained privately for deliberate publication.
`EPISODE_RESULT.json` distinguishes verified native model turns from merely
invoked processes and labels scientific completion as requiring independent
review. Classification-only execution or partial Q1 is never promoted to Q2/Q3
evidence. Numeric/source honesty still requires independent replay and review.
Episode completion additionally requires the locked candidate to be an iteration
with positive `q1_groups` in both validation and final-test aggregate metrics.
The controller enforces this before accepting a report and when validating a
done state. Repeated classification-only baselines cannot finish the episode.

Verification: `framework/tests/test_real_episode.py` uses scripted native-boundary
hooks only. It exercises the real inherited driver loop through five sessions,
five fresh control homes, budget reservations, delegated review, baseline,
iteration, unique lock/test, and final report. These tests are not actual model,
scientific-data, server-runtime, or live-isolation acceptance evidence.
