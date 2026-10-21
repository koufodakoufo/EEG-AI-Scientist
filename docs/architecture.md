# Architecture (current)

```text
CLI
├── study  -> study_spec / study_runtime -> ResearchRunner
├── review -> review_io (packet, raw feedback, record, feedback set)
└── old commands (guarded/read-only for archived studies)

ResearchRunner
├── model client: DeepSeek Flash | Anthropic | Gemini
├── tools: read_evidence (local) + optional DeepSeek Search/Fetch
├── evidence.py   source snapshots / read ranges / injections
├── ledger.py     budget, price, usage, UNKNOWN, attribution
└── run_manifest.py
    ├── git metadata (supplementary)
    ├── code_snapshot/ (per-file + aggregate SHA-256; authoritative)
    ├── material/rule/prompt hashes
    └── model/tool/cost attribution
```

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
