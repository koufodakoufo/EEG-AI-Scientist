# Prospective semantic calibration of v3 — development protocol

Builder R84, 2026-10-30. **Candidate prepared; no model invocation has occurred.**
Root must review this package, reserve two new-work R calls, and run `stage`
before either invocation. This directory and the separate runner extend only
the calibration workflow. Frozen `claims_v3.py`, `evidence_v3.py`, their earlier
fixtures, E01 scores, and the sealed E05–E08 comparison are unchanged.

## Scope and preregistered interpretation

This is a small, deliberately constructed **synthetic development calibration**
of actual model extraction and directional judgment. The oracle is manually
authored by Builder before either live call, not independently blind-labeled.
It tests the operational capability to emit semantically correct typed atoms
and directional entailment labels under fixed conventions. It cannot establish
clinical validity, general scientific scoring validity, performance on natural
EEG reports, or absence of model pretraining contamination. A pass does not
authorize retrospective rescoring or replace the initial E01 null score.

No actual EEG references, participant records, scientific outcome tables, or
E05–E08 outcomes are included or used for fixture/prompt tuning. Earlier v3
contract fixtures provide only the list of failure classes, not model answers.
All input names and values are invented. The separately checked synthetic mean
of 0.5 and 1.0 is 0.75; this illustrates a new valid finding not covered by an
accuracy reference, not an EEG result.

## Files and isolation

- `extraction-inputs.json`: 12 raw reports and simulated delivery statuses.
- `judge-inputs.json`: 16 directional requests with typed claims and their exact
  source texts. It contains no expected relations or critical-case labels.
- `private-oracle.json`: Builder answers, critical tags, acceptance thresholds,
  and the invented numerical evidence. It remains outside both public mounts.
  It is Git-ignored and must be supplied privately in the owner's workspace;
  the standalone calibration tests/check/stage commands require that local
  artifact. A source-only checkout cannot reproduce calibration scoring without
  it. The scientific framework's normal test suite is independent of this file.
- `EXTRACTION_PROTOCOL.md`, `JUDGE_PROTOCOL.md`: complete actual call protocols,
  including the unchanged core template texts and separately versioned wrappers.
- `scripts/research/semantic_calibration_v3.py`: offline validator, stager,
  strict parser, scoring functions, and explicit native entrypoint.
- `scripts/research/test_semantic_calibration_v3.py`: meaningful offline tests.

The public bundle allowlist is exactly `INPUT.json` and `PROTOCOL.md`, plus its
generated manifest. `stage` places each independently constructed input/prompt
under its own source directory and places this protocol and oracle under
`private/`. Source `PROMPT.txt` persists the exact bytes passed to native stdin;
it is not separately mounted because it contains the same public content.
The second call receives the preauthored pairs, not first-call output, so an
extractor failure cannot contaminate the judgment calibration.

## Case inventory and manual oracle

| Extraction case | Assertion coverage |
|---|---|
| X01 | Point and confidence interval in one sentence; 50% normalization |
| X02 | Same point and interval across sentences; one-half rephrasing |
| X03 | A point plus an explicitly claimed causal mechanism; separate atoms |
| X04 | Training and validation points; scope override |
| X05 | Literal duplicate; one canonical atom with both source locations |
| X06 | Failure to detect an improvement, qualified to this run |
| X07 | Uncertain effect; no inference of an absent effect |
| X08 | New synthetic mean, explicit evidence ID |
| X09 | Completed empty report |
| X10 | Simulated source delivery failure; empty but not an ability zero |
| X11 | Simulated truncation; one complete point and incomplete interval |
| X12 | Chinese, emoji, accented and combining Unicode; code-point offsets |

There are 13 canonical oracle atoms across complete reports, and one additional
partial-report atom in X11. X10/X11 are tests of reported transport provenance,
not claims that an actual external service failed. Real native failures are
handled separately by persisted status, trace, and parser receipts.

The 16 pairs cover equivalent fraction/percent in both directions, point versus
interval in each direction, point versus mechanism, split/condition/model
mismatches, incompatible numeric values, negative versus positive findings,
uncertainty versus proven absence, a qualified negative paraphrase, a new valid
claim absent from the reference, unresolved referents, and asymmetric entailment
between “at least one” and “exactly two.” Private expected labels are fixed
before execution. A single requested direction counts as one pair observation.

## Acceptance and failure rules, frozen before live calls

1. Require atom recall **>= 0.90**, atom precision **>= 0.90**, pair accuracy
   **>= 0.90**, exact status handling, and **zero critical errors**. At 13 atoms,
   recall requires at least 12; at 16 pairs, accuracy requires at least 15.
2. Critical errors are scope leakage, an invented mechanism or loss of the
   negative/uncertain qualification, invalid support/contradiction across kind
   or scope, and incorrect empty/failure/truncation handling. The private pair
   oracle lists the fixed scope and causal/kind-overreach cases. An incorrect
   label on one critical case fails even if aggregate accuracy exceeds 0.90.
3. Extraction matching uses the existing typed schema and canonicalization,
   exact scope/payload/qualifiers/evidence IDs, the public fixed vocabulary, and
   complete occurrence coverage. Arbitrary claim IDs are ignored. Every actual
   quote and offset is validated by `assemble_extractions`. Distinct duplicate
   occurrences require distinct returned spans. No fuzzy matcher or new model
   is used to grade the extractor.
4. Unrecognized but potentially equivalent wording is retained as a review
   candidate and a miss in the primary score. A manual development review may
   explain it but cannot change the frozen score, patch the alias table, or
   rerun the same version until it passes. A later revised protocol gets a new
   version, fresh cases, fresh reservation, and an explicit development label.
5. Missing cases, malformed JSON, duplicate keys, nonfinite numbers, wrong IDs,
   non-exact spans, actual native failure, or unverified trace provenance leave
   metrics **null/pending**, with the failure and raw output retained. Validly
   parsed semantic errors produce **failed**, never a silently repaired pass.
6. Empty completed reports have zero atoms; simulated and actual failures never
   become scientific ability zero. No total/taste/composite score is produced.
7. No automatic retries, autotuning, case replacement, cherry-picked repairs,
   or expansion of the private scientific reference. Passing this small set
   means only `passed_synthetic_development_calibration`.

## Exactly two prospective native calls

Root assigns the final call IDs after review (R85/R86 below are placeholders
until actually reserved in the authoritative controller ledger). Both calls
use role `judge`, native CLI **0.165.0**, **gpt-6.1-sol**, **medium**, a fresh
control home, the existing verified **R15** canary, a read-only WORK/venv, a
900-second limit, a 32 MiB case limit, and zero automatic retries. Temperature,
seed, and revision are not invented: the profile does not expose temperature or
seed, and actual model/reasoning metadata are saved from native turns. The only
authentication access is the existing trusted `prepare_control` operation.

1. **Extraction call**: input is the frozen extraction plan for all 12 reports,
   built by unmodified `build_extraction_plan`, plus the extraction protocol.
   Output is one typed segment-response batch with exact code-point offsets.
2. **Directional judge call**: input is the frozen 16 preauthored directional
   pairs, plus the judge protocol. Output is one judgment batch. It has no
   extractor output, oracle, earlier sessions, or Builder conversation.

The helper explicitly calls `validate_isolation_gate` for judge role because
the core launcher gates actor/distiller automatically but not judge. It rejects
a canary other than R15 or mismatched runtime/profile fingerprints. Cases,
control homes, and evidence directories are fresh and may not be overwritten.
Actual prompt/input/protocol/oracle/freeze hashes, stdout JSONL, stderr, raw
final text, sanitized visible native trace, actual turn metadata, and a parsing
receipt persist. It never edits the old M ledger or any new-work budget itself.

## Commands after root review and reservations

Use the existing integration checkout under
`/data/duandh/eegfm-stage-a-20261028/overnight-20261029/integration`; stage into the
new work root. These are templates, not records of executed model calls.

```bash
python -B scripts/research/semantic_calibration_v3.py check \
  --fixtures docs/research/2026-10-30-extension/semantic-calibration

python -B scripts/research/semantic_calibration_v3.py stage \
  --fixtures docs/research/2026-10-30-extension/semantic-calibration \
  --destination /data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/builders/semantic-calibration-v1 \
  --extract-call R85 --judge-call R86
```

Preserve the printed FREEZE SHA256 in a trusted controller record before launch.
Do not recalculate it after mutation as a workaround. Substitute that exact
value for `<FROZEN_SHA256>` in both calls and the offline score command:

```bash
python -B scripts/research/semantic_calibration_v3.py run-native \
  --job /data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/builders/semantic-calibration-v1/jobs/R85.json \
  --freeze-sha256 <FROZEN_SHA256>

python -B scripts/research/semantic_calibration_v3.py run-native \
  --job /data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/builders/semantic-calibration-v1/jobs/R86.json \
  --freeze-sha256 <FROZEN_SHA256>

python -B scripts/research/semantic_calibration_v3.py score \
  --stage /data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/builders/semantic-calibration-v1 \
  --freeze-sha256 <FROZEN_SHA256> \
  --extraction-evidence /data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/evidence/R85 \
  --judge-evidence /data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/evidence/R86 \
  --output /data/duandh/eegfm-stage-a-20261028/brainpec-real-20261029/evidence/semantic-calibration-v1.json
```

The final score command reads actual raw final messages and trace hashes. An
offline oracle self-check is only a test of fixture consistency, never evidence
that a model passed. Root should preserve the candidate/review diff before
staging, inspect the stage public allowlists, and retain failures unchanged.
