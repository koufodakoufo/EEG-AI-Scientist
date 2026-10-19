# RESULTS — flash_20261020_0058

Only executed checks and measured values are listed. Synthetic data and fixture checks are not EEG evidence.

## Capability (engineering)

- `list_models`: PASS — `{"model_ids": ["deepseek-flash", "deepseek-v4-pro"], "http": 200}`
- `chat_json_thinking`: PASS — `{"returned_model": "deepseek-flash", "finish_reason": "stop", "usage": {"prompt_tokens": 77, "completion_tokens": 54, "total_tokens": 131, "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 77}, "content_preview": "{\"ok\": true, \"route\": \"deepseek-flash\"}", "reasoning_chars": 152, "request_id": "2316a71d-ea45-4f81-867f-96ac56a7a2bc"}`
- `native_tool_cycle`: PASS — `{"turns": [{"turn": 1, "finish_reason": "tool_calls", "content": "", "tool_calls": [{"id": "call_00_ET_8Ki8wDKOy1yPjfCdK8eq5068", "name": "echo_probe", "arguments": "{\"text\": \"ping\"}"}], "reasoning_chars": 0, "executed": [{"status": "ok", "text": "ping", "note": "engineering echo only"}]}, {"turn": 2, "finish_reason": "stop", "content": "The tool returned the text: **ping**\n\n(The full result was `{\"status\": \"ok\", \"text\": \"ping\", \"note\": \"engineering echo only\"}` — the `text` fi`
- `search`: PASS — `{"query": "EEG cross-subject decoding generalization trial-wise split", "n_results": 5, "first_url": "https://www.sciencedirect.com/science/article/pii/S2589238X26000021#3", "titles": ["Neural decoding for EEG-BCI: from conventional machine learning to deep learning models - It is important to note that if preprocessing steps (e", "Leakage and evaluation", "A Mixture-of-Expert Model for Cross-Subject Motor Imagery Decoding", "Evaluation and Benchmarking", "Cross-Subject Data Splitting for Brain-`
- `fetch_and_read`: PASS — `{"url": "https://ar5iv.labs.arxiv.org/html/2312.10987", "title": "Cross-Subject Data Splitting for Brain-to-Text Decoding", "chars": 48687, "evidence_id": "ev_056fb3068eea", "slice_chars": 500, "page_start": null, "attempts": [{"url": "https://ar5iv.labs.arxiv.org/html/2312.10987", "ok": true, "chars": 48687, "evidence_id": "ev_056fb3068eea"}]}`

## Explanation regression (Task C)

- rule checks: 6/6
- [PASS] `recognizes_trial_baseline_near_chance`: 49.6% must be described as already near chance, not as a post-randomization collapse.
- [PASS] `recognizes_window_stays_high`: window-level values 99.3% and 99.2% should be compared; the change is about 0.1 percentage point.
- [PASS] `mentions_both_deltas`: Expected deltas: window -0.1 pp; trial +1.2 pp. This checks arithmetic presence, not correctness of interpretation.
- [PASS] `rejects_trial_collapse_claim`: No sentence should claim that randomization moved trial performance from ~99% to chance.
- [PASS] `mentions_split_or_shared_trial`: The window/trial split distinction or shared-trial structure should be named.
- [PASS] `states_a_limit_on_generalization_claim`: The answer should say what cannot be concluded about semantic generalization or leakage.
- verbatim answer: `runs\flash_20261020_0058\diagnostics/regression/regression_answer.md`

## Neutral synthetic case diagnostics (Task C)

- `case_c41a`: status=completed, actions=3, predictions=3/3, numeric_grounded=False
- `case_a72e`: status=completed, actions=2, predictions=2/2, numeric_grounded=False

## Literature run (Task D)

- phase: completed
- model calls: 16; tool calls: 42
- searches: 8; fetches: 10
- stop reason: finish_study
- final answer: `runs\flash_20261020_0058\research\literature_v1/final_answer.md`
- cited evidence: 7
- read coverage (injected characters / fetched characters):
  - `ev_200bb34828cd`: 5500/113435 (4.9%)
  - `ev_2085e5b7ba26`: 16300/85799 (19.0%)
  - `ev_2f5e3fadf9f0`: 5500/97933 (5.6%)
  - `ev_825214c78a59`: 26700/148770 (17.9%)
  - `ev_8d41144afed7`: 0/36843 (0.0%)
  - `ev_9da221287269`: 8579/8579 (100.0%)
  - `ev_a2ba747cdafd`: 0/92049 (0.0%)
  - `ev_a4cfb55eee84`: 0/2802 (0.0%)
  - `ev_b63c716fd707`: 21300/101545 (21.0%)
  - `ev_f42fa7111e36`: 15500/120604 (12.8%)

## Honest limits

- Synthetic feature tables and artificial fixtures are not recorded EEG.
- Windows are not independent participants; no population-level EEG inference is made.
- Rule checks are not a scientific score.
- `numeric_grounded=False` for the two synthetic cases means the final judgment did not quote a result value; it does not mean the tool results were wrong. The values remain in each trajectory's `history.json`.
- Successful research searches/fetches are lower than ledger attempts because retries and failed requests are counted separately.
- Project API spend is separate from the dsh development-agent account.
