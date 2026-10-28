# Architecture (current)

```text
CLI (project root resolved from any cwd)
├── study  -> study_spec / study_runtime -> ResearchRunner
│   ├── init      generic draft or explicit old-material template
│   ├── validate  files, arms, backends
│   ├── preflight model/task/material/rule hashes + prompt diff (offline)
│   └── run       preflight gate, resolved paths, per-arm ledger
├── review -> review_io (form packet, raw feedback, record, feedback set)
└── old commands (guarded/read-only for archived studies)

ResearchRunner
├── model client: DeepSeek Flash | Anthropic | Gemini
├── input snapshot
│   ├── exact system prompt + task.md body + rule package
│   ├── full tool definitions + SHA-256
│   └── hashes of the first system/user messages
├── tools: read_evidence (local) + optional DeepSeek Search/Fetch
├── evidence.py   source snapshots / read ranges / injections
├── ledger.py     budget, price, usage, UNKNOWN, attribution
└── run_manifest.py
    ├── git metadata (supplementary)
    ├── code_snapshot/ (per-file + aggregate SHA-256; authoritative)
    ├── material/rule/prompt hashes + input snapshot
    └── model/tool/cost attribution
```

## Input boundary

- `task.md` is the authoritative task; `question` is metadata/legacy fallback.
- A rule file is read and snapshotted before the first request. Its exact text is
  appended to the system message as a labelled block and recorded in
  `input_snapshot.json` and `scientist_input.md`.
- Configured but missing/empty rule or system prompt files fail; there is no
  silent fallback to empty instructions.
- On resume, stored messages are checked against the frozen snapshot. Changing
  the task or rule source is refused; old runs without a snapshot are never
  patched.
- `study preflight` builds the same prompt texts with a placeholder time and
  compares arms. A claimed rule contrast with identical effective rule text is
  rejected before a paid run.

## Review boundary

- One fillable Markdown form per proposal; the proposal body sits before
  `<!-- BEGIN REVIEW -->`, so the parser ignores arbitrary proposal headings.
- Binding is packet + display + run_id + full body SHA-256. The import also checks
  the run's `state.json`, rejects cross-study packets and swapped displays, and
  keeps raw reviewer text separate from the structured record.
- Feedback sets are versioned and immutable; identical re-selection is read-only.

## Model protocol boundary

- Vendor-native assistant blocks are stored in `messages.json` and replayed:
  Claude thinking/redacted_thinking blocks with signatures, Gemini parts with
  `thoughtSignature`.
- Tool-call IDs are unique for a conversation (provider IDs for Claude,
  `gcall_NNN` for Gemini when the provider supplies none).
- `max_tokens` / `MAX_TOKENS` set `truncated`; truncated tool arguments are not
  executed, and at most one bounded retry is made within the call/deadline/budget
  limits.
- Gemini `thoughtsTokenCount` is part of billable output and is stored
  separately as `reasoning_tokens`; Anthropic cache tokens are counted as input.

## Boundaries

- `ResearchRunner` owns the tool loop and resumable state; new code must not
  duplicate it.
- `study` is a thin orchestration layer: one directory per study, arms with
  backend/repeats, per-arm budget ledger, first accepted selection.
- `review` binds a proposal to `run_id`, full body SHA-256, packet version, and
  proposal ID; the blind label is packet-local only.
- Human/ChatGPT-manual/model-API reviews are separate source types; raw text is
  never overwritten.
- `archive/` is read-only and indexed by `archive/README.md` plus
  `archive/MIGRATION_MAP.json`.

## Legacy

`src/eeg_scientist/legacy/` contains the old synthetic/reporting implementation;
the root modules of the same names are one-line compatibility shims. New work
must not add features there.

## Explicit non-goals

No multi-agent platform, no automatic infinite Meta loop, no PDF/OCR platform,
no real EEG training in this layer. Legacy synthetic code is kept for
compatibility, not advertised as the current entry.
