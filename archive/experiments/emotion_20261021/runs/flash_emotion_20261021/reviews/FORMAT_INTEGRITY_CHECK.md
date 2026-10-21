# FORMAT / INTEGRITY CHECK — not a scientific score

This file records only programmatic format and trace-integrity checks. It is not a scientific quality score, not an independent expert review, and not evidence that a proposal is correct.

- Meta decision: `rules`; accepted: `True`
- Attempts: 10; accepted: 6; primary proposals: 4
- Baseline attempts: 4; meta-rule attempts: 6
- Total cost by arm: {"baseline": 0.852288, "meta_rule": 1.30081}

| run | arm | accepted | cited IDs | format checks passed | cost CNY |
|---|---|---|---:|---:|---:|
| `flash_emotion_20261021__baseline__01` | baseline | True | 6 | 7/7 | 0.2365 |
| `flash_emotion_20261021__baseline__02__retry` | baseline | True | 6 | 6/7 | 0.2185 |
| `flash_emotion_20261021__meta_rule__01__retry2` | meta_rule | True | 4 | 6/7 | 0.1988 |
| `flash_emotion_20261021__meta_rule__02__retry` | meta_rule | True | 4 | 6/7 | 0.2254 |

## What this check can and cannot say

- It checks format and trace integrity: accepted status, citation ID validity, and presence of required proposal elements.
- It cannot establish that a proposal is scientifically correct or that the proposed experiment would identify a mechanism.
- With at most two runs per arm, differences are descriptive only; no p-value or population claim is warranted.
- The blinded files in `blinded/` omit model/rule labels for human reading; `KEY.json` is the separate key.
