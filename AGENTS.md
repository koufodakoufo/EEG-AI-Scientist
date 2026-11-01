# Project rules

- Goal: EEG RSI Scientist. Separate scientific discovery (inner loop) from improvement of the researcher/update procedure (outer loop). Do not equate a skill, completed run or higher task metric with recursive self-improvement.
- The formal local checkout is X:/projects/EEG-AI-Scientist. The C-drive EEG-FM-RSI folder is historical support material. Use explicit working directories.
- Read README.md, PROGRAM.md and the task definition. Current architecture and machine guidance are docs/architecture.md and docs/workspaces.md. docs/history is evidence, not current execution instructions.
- Maintain one Git repository and one main branch. Use short-lived feat/, fix/, refactor/, or study/ branches with semantic names. Preserve baselines using archive/ tags. Never force-push or rewrite published history merely for appearance.
- Name new studies/runs by purpose, protocol, generation, condition and repeat. Do not use overnight/morning or execution dates as their meaning. Dates remain metadata.
- Code lives in src/eegfm; tasks in tasks; tests in tests. Avoid generic abstractions until more than one real task needs them. Python code uses type annotations.
- Keep README as the single daily entry. Prefer updating one relevant document over overlapping handoff/status/summary documents.
- The user authorizes project reorganization, reversible refactoring, research preparation, Git consolidation and synchronization across owned workspaces. This preparation is separate from the later nine-hour research window; do not launch that study implicitly.
- Prefer huoshanyun for new execution after resource/storage preflight. Keep ncc available for verified CPU runtime and original evidence. GPU visibility does not establish allocation.
- Inspect only relevant, readable collaborator project material. Preserve attribution. Never access authentication or unrelated personal files. Copy reusable material only when needed; never move, delete, chmod or chown others' or shared files.
- Do not read, print, move or upload credentials/. Do not commit authentication, raw/participant data, model weights, hidden truth, runtime state or private reference materials.
- Preserve archive/ originals and frozen research evidence. Historical runs use original tagged code and recorded environment; do not update their hashes, budgets, reservations or results to fit new paths.
- Researcher contexts must not inherit builder answers or private evaluation material. Shared memory and skills are not automatically visible to a tested researcher.
- Keep task and final-test boundaries fixed. Fit on training data, choose on selection/validation, freeze before held-out evaluation. Already viewed data stays exploratory.
- Before moving an owned directory, verify source/destination scope, ownership, active use and recovery route. No destructive cleanup for a visually clean tree.
- Use existing environments where valid. Run relevant regressions and the complete supported suite; distinguish Linux execution tests from portable science checks. Report failures and skips accurately.
- Keep a concise progress record in docs/development/project-renewal.md. Routine decisions are autonomous; record material assumptions and limitations.
