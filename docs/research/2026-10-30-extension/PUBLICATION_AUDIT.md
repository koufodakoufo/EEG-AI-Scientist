# GitHub publication audit — R52

Audited on 2026-10-30 in the sole formal workspace `X:/projects/EEG-AI-Scientist`.
Scope: existing branch history through `0b24164977e82619de5ce0ab3d5e8f46f80d8a98`; later working-tree changes and later commits require a delta audit.

## Decision

No real secret, credential file, raw EEG dataset, model-weight payload, current private benchmark gold file, compressed bundle, or hidden local artifact was identified among the new Git objects. The audit does **not** certify literal trace-free publication: one historical imported validation summary contains aggregate per-epoch training history, described below. This is a concrete scope gate for an unqualified “no run traces” claim, not evidence of an authentication leak.

## Exact destination and history

- Existing remote: `github`, fetch and push URL `https://github.com/koufodakoufo/EEG-AI-Scientist.git`; no embedded URL credentials.
- Active branch: `research/brainpec-real-20261029`; no upstream configured.
- Live `git ls-remote --symref github HEAD refs/heads/* refs/tags/*` returned default/main `d0bbb6efbed5933275f4d6d9a46b90e4bbe82930` and `overnight/flash-20261020-0058` at `c22df47b6d79a49f691838122abb4eff0b01ff0e`. No research branch or tags were advertised. The local tracking refs matched these live values; no fetch was needed.
- `c22df47b6d79a49f691838122abb4eff0b01ff0e` is an ancestor of HEAD. **26 commits** reachable from HEAD are absent from all advertised GitHub refs. The previous-night checkpoint `58b8d71` is itself unpublished; auditing only its five successor commits would miss 21 unpublished commits.
- New reachable objects: 26 commits, 251 trees, and 373 distinct blobs (650 objects total). Historical trees contain 1,259 unique paths; 316 paths are associated with new blob versions. All new blob contents were scanned, including versions no longer at HEAD.
- GitHub repository metadata via both the connected GitHub tool and the anonymous REST API returned 404. Git transport authenticated successfully and returned the refs above. Repository visibility and account permissions were therefore **not independently verified**; the URL establishes the intended existing repository, and 404 alone does not prove private visibility.

After the trace-scope gate is resolved and any later commit is audited, the precise non-force branch-creation command is:

```powershell
git -C X:/projects/EEG-AI-Scientist push --set-upstream github HEAD:refs/heads/research/brainpec-real-20261029
```

No push, dry-run push, commit, checkout, reset, history rewrite, remote change, or visibility change was performed by this audit.

## Content findings

1. **Credential and key paths:** zero forbidden credential/authentication/private-key paths in HEAD or any of the 26 unpublished commit trees. The audit did not read, enumerate inside, move, print, or upload `credentials/`, authentication files, or SSH keys.
2. **Secret scan:** 373 new blobs, 3,882,017 bytes, all decoded and scanned. Three NUL-containing files were UTF-16 JSON audit summaries, not binary datasets. The largest blob was the 499,786-byte reorganization filename/hash manifest. There were no undecoded blobs, archives, model/data binaries, Git LFS payload pointers, or long encoded payloads among the new blobs.
3. **Matches adjudicated:** three secret-pattern matches correspond to two explicit fake literals in `tests/test_adapter_roundtrip.py` and its archived alias, lines 105 and 284, in the `_anthropic_client` and `_gemini_client` test helpers. A supplemental match in `scripts/overnight/legacy_smoke.py:50` is a user/task authorization label, not an authentication credential. No token values were emitted in the audit evidence. All 26 unpublished commit messages were also scanned, with zero matches.
4. **New aggregate training history — scope gate:** `framework/knowledge/evidence/reve_isa_H1_validation_summary.json`, introduced by `5df1d9e`, is a 66,547-byte validation-summary JSON. Alongside aggregate validation metrics it contains `training/<dataset>/loss_by_epoch`: 6 datasets × 40 epochs = **240 rows** of epoch number, mean loss, mean gradient norm, ending learning rate, and wall seconds. These are aggregate training records, not raw EEG, weights, participant-level predictions, private benchmark gold, or agent/tool transcripts. A strict exclusion of all run histories would include this section. Deleting it only in a new tip commit would not remove its unpublished historical blob from a push. Resolve whether aggregate epoch summaries are within the authorized publication scope before claiming a trace-free push.
5. **Run ledger:** `docs/overnight/2026-10-29/RUN_LEDGER.jsonl` contains 24 compact budget/status/resource/usage/hash records; it references local evidence by path or hash and does not embed agent/tool message traces. The relocated `configs/materials/emotion_state_trait_v1.json` is a research-material selection configuration, with an unchanged pre-existing blob.
6. **Already remote archival evidence:** 766 risk-pattern paths under legacy experiment archives and `archive/reference/FILE_INVENTORY.csv` have identical blob IDs in the remote ancestor and HEAD. These include old run/history files already in GitHub. They are not newly uploaded blob contents, but the existing repository is not globally trace-free. The only new change under the old experiment/reference archives is a 12-line correction document.
7. **Local exclusions:** `.local/`, `credentials/`, `data/private/`, and the supplied `framework/examples/demo_claude_001/` artifact location are ignored; no tracked `.local/` payload was found. Current local private reference outputs are outside the audited Git content. No actual credential file was accessed to test these exclusions.

## Non-blocking checks and limits

Builder disposition, 2026-10-30: the 240 epoch rows were independently checked at the schema level and classified as permitted aggregate research summaries under the user's explicit publication authorization. They contain epoch/loss/gradient/lr/time summaries, not raw participant data, weights, private benchmark answers, or message traces. This resolves the scope gate; it does not justify claiming the repository is trace-free. No history rewrite is required. New working-tree additions still receive a delta review.

- `git diff --check c22df47... HEAD` returned existing trailing-whitespace/EOF findings in archived source, imported vendor documentation, and a few research documents. These are formatting findings, not publication-content blockers; no historical content was changed by this audit.
- This was a bounded publication audit, not scientific-result validation or a new test run. Secret matching is evidence of inspected patterns and adjudicated matches, not a mathematical guarantee that arbitrary prose can never encode a secret.
- Concurrent new files and edits from the extension work are outside this commit-bound result. Stage only the reviewed source/docs intended for publication, and audit the final staged/committed delta before pushing.

## Local evidence

Detailed filename/object/count evidence is deliberately kept under ignored `.local/research/2026-10-30-extension/git/`:

- `inventory.json`: 26 commits, historical blob paths and net changed paths.
- `content_scan.json`: blob IDs, sizes, encodings, and token-free match locations.
- `supplemental_scan.json`: additional auth/key/encoded-payload/LFS checks.
- `risky_paths.json`, `payload_classification.json`: path and structural classifications.
- `verified_facts.json`: destination, remote refs, metadata limitations and explicit scope finding.
- `scan_publication.py`: repeatable local scan implementation; it does not read credential paths or emit matched token text.
