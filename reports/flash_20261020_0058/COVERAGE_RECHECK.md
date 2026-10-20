# COVERAGE RECHECK — overlapping reads must be merged

This note corrects a reporting-only overcount in the completed `literature_v1` run. The original Scientist answer (`final_answer.md`) and structured `final.json` are **not** modified.

## Why the old number was too high

The old `estimate_injection_fraction` added `(end_char - start_char)` for every `read_evidence` call. If two calls read overlapping character ranges, the overlap was counted twice. The code now merges half-open `[start, end)` intervals and counts their union. This is a character-coverage measure, not a claim that the text was understood.

## Corrected coverage for the cited sources

| evidence ID | old read chars | union read chars | total chars | old fraction | corrected fraction |
|---|---:|---:|---:|---:|---:|
| `ev_200bb34828cd` | 5,500 | 5,500 | 113,435 | 4.85% | 4.85% |
| `ev_2085e5b7ba26` | 16,300 | 16,300 | 85,799 | 19.00% | 19.00% |
| `ev_2f5e3fadf9f0` | 5,500 | 5,500 | 97,933 | 5.62% | 5.62% |
| `ev_825214c78a59` | 26,700 | 26,700 | 148,770 | 17.95% | 17.95% |
| `ev_9da221287269` | 8,579 | **5,100** | 8,579 | 100.00% | **59.45%** |
| `ev_b63c716fd707` | 21,300 | 21,300 | 101,545 | 20.98% | 20.98% |
| `ev_f42fa7111e36` | 15,500 | 15,500 | 120,604 | 12.85% | 12.85% |

Only the Yin et al. ACL page changed: two read ranges overlap, so the union is 5,100 characters, not 8,579. The page was still the abstract/metadata page, not the paper body.

Uncited sources with zero reads (`ev_8d41144afed7`, `ev_a2ba747cdafd`, `ev_a4cfb55eee84`) remain at 0. The corrected machine-readable table is `coverage_union.json`.

## What this changes

- The literature map, evidence audit, and results table now show 59.4% for the Yin page (interval union), not 100%.
- The claim “Yin et al. was read only at the abstract page” is unchanged.
- The original `final.json` still contains the old `coverage` field as a historical record. It was deliberately not rewritten; a future run using the fixed code will store the union value.
- This correction does not add or remove any paper, citation, or scientific conclusion.

## Reproduction

```powershell
cd X:\projects\EEG-AI-Scientist
$env:PYTHONPATH='src'
C:\Users\14090\anaconda3\python.exe -c "from pathlib import Path; from eeg_scientist.evidence import EvidenceStore, estimate_injection_fraction; s=EvidenceStore(Path('runs/flash_20261020_0058/research/literature_v1/evidence')); print(estimate_injection_fraction(s))"
```

The command is read-only with respect to the original run.
