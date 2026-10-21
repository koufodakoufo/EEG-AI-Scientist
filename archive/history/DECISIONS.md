# DECISIONS

## D1 — Use the actual directory

The plan names `X:\projects\eeg-ai-scients`; the actual repository is `X:\projects\EEG-AI-Scientist`. Renaming would risk the existing `.git`, `.venv`, and paths. Use the actual directory and record the discrepancy.

## D2 — Local model route

No Python cloud API key is configured. DSH Desktop login is separate and was not extracted. The local Ollama `qwen3.5:9b` is a real LLM route, runs on the same machine, has no tools or filesystem access, and keeps the Scientist input isolated. Use native `/api/chat` with `think=false` and `format=json`; the OpenAI-compatible endpoint produced empty visible content under thinking.

## D3 — Flat decision wire format plus normalizer

The 9B model repeatedly mis-nested `stop`/`reasoning_summary` under `action`. Keep the internal `Decision` model nested, but accept a flat wire shape and normalize both forms. This is format normalization, not semantic repair. A malformed output still gets one format-repair call.

## D4 — Prediction reference

Balanced-accuracy metrics (`*_balanced_accuracy`, `*_ba_mean`) are compared with chance 0.5; gaps and `*_minus_chance` metrics with 0. This prevents a raw 0.508 BA from being scored as a large positive direction. The S0 prompt states the reference.

## D5 — Forced-stop constraint repair

The 9B sometimes returns another action when `force_stop=True`. The controller rejects it and makes one constraint-repair call asking for a stop decision using existing evidence. If the repair still returns an action, the episode fails; no fabricated final judgment.

## D6 — Duplicate actions

A repeated tool with the same parameters is a duplicate even with a new request ID. It consumes an action slot but does not execute again. This implements “repeated requests return no new evidence.”

## D7 — Dependency fallback

`uv sync --extra dev` stalled on a hatchling/trove metadata fetch and was killed. The Anaconda base has numpy/scikit-learn/pydantic/httpx/pytest; use it read-only with `PYTHONPATH=src`. Do not modify the base environment.

## D8 — Report reserve

Use 60 minutes for reports instead of the plan's minimum 45; stop starting new episodes at 08:14:21 and use 08:14–09:14 for reports and packaging.

## D9 — Small local model caveat

The Scientist is a 9B local model. All conclusions are model-specific. S0/S1 may show no difference or a regression; that is a valid result. No claim about frontier LLMs or RSI is made.

## D10 — Private data boundary

`data/private/` is gitignored and never serialized into a Scientist request. A `review_only/PRIVATE_CASE_SPECS.json` copy may be included in the review bundle for the human reviewer and is marked evaluator-only.

## D11 — Meta update was `no_update`

The first Meta output exceeded the 600-character rule budget; its single format repair returned invalid JSON. The controller recorded the errors and froze S1 as a no-update label over the unchanged S0 rules. This is legal under the plan (`S1 == S0` is a valid result), but it means the holdout S0/S1 table is a null-rule control, not evidence that a method rule helps. The freeze manifest records the Meta errors and token cost.

## D12 — Some holdout arms stop with zero actions

The 9B model may stop immediately on a holdout case after using the shared development facts. That is a behavioral failure, not a fabricated success. The report lists zero-action arms and marks the paired comparison as weak.

## D13 — Reporting-only edits after freeze

The study/experiment code hashes in `FREEZE_MANIFEST.json` are the frozen values. Presentation-only changes to `reporting.py` after freeze do not alter study data; the final report and bundle note the distinction.

## D14 — Study result is E2 engineering / E1 substantive

All four holdout pairs have complete S0/S1 states, so the engineering count is E2. Every holdout arm stopped with 0 actions, and Meta was `no_update`, so the paired table is a null-rule control rather than an effective method-rule comparison. The substantive evidence is E1. Do not upgrade this to a strong E2 claim.

## D15 — Model digest location

The freeze manifest's `/api/show` metadata does not contain the `/api/tags` digest. The digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` and context length 262144 are recorded in `reports/PREFLIGHT.md` and in the final morning report. A future version should record `/api/tags` digest directly in the freeze manifest.


