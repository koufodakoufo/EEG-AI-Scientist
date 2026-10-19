# METHOD LESSONS PROPOSED — flash_20261020_0058

These are **developer observations and candidate changes**, not active Scientist rules. Nothing here was fed back into the running Scientist, and no Meta loop was run. Each item says what was observed and what to test next.

## 1. Heartbeat before long tool execution

Observed: `heartbeat.json` stayed at `call_016` for ~2.5 minutes while a `fetch_source` hit a 504 and retried. The process was alive, but a reviewer could not tell whether it was stalled. Candidate: write heartbeat immediately before each tool call and after each retry, not only before model calls and after tool results.

## 2. Record failed fetch attempts explicitly

Observed: two fetches failed (504 on the EEGManyPipelines EuropePMC page; 404 on an arxiv mirror). The errors are in `messages.json` and the event log, but there is no compact `fetch_attempts.jsonl`. The final answer mis-counted the irrelevant fetches (said two; actually three successful irrelevant fetches plus two failures). Candidate: append a single attempt record `{url, status, error, attempt, elapsed}` for every search/fetch call, and have the final-report renderer use it.

## 3. Keep `finish_study` evidence-read validation

Observed: the model tried to finish after fetching but before reading one source; the tool rejected it and listed the unread IDs. The model then read the source and finished correctly. This is a good guard against citing previews as full text. Candidate: keep it; also expose the injection fraction in the rejection message so the model knows how much it has read.

## 4. Turn budget was reached, but batching worked

Observed: the model issued 3–4 tools per response; the 10-tool-per-turn cap produced four turns. The turn-boundary nudge did not cause duplicate searches. Candidate: keep the per-turn cap but make the boundary explicit in the system prompt ("you have N tool calls this turn") so the model can plan. Do not raise the cap just to reduce turns.

## 5. Context size was manageable; compaction never triggered

Observed: the run used 16 model calls and ~53k output tokens; the 150k-character context target was not reached, so `context_compacted` never fired. Candidate: keep the compaction code, but test it with a synthetic 200k-character trace. Do not add a summarizer until a real run needs it.

## 6. `reasoning_content` can be empty with tools

Observed: the tiny probe returned 152–161 reasoning characters, but the native tool-cycle responses returned zero reasoning characters and still worked. Candidate: never require reasoning to be non-empty; preserve it when present and omit it when empty (current behavior). Do not treat "no visible reasoning" as a failed call.

## 7. Numeric grounding in the final text

Observed: both neutral case finals cited evidence IDs and tool results but did not quote the key BAs; the regression answer did quote every number. Candidate: add a final-answer checklist item ("quote at least the primary endpoint values you rely on") and a programmatic check that the final text contains at least one executed result value. This is a presentation/verifiability rule, not a scientific constraint.

## 8. PDF extraction is still missing

Observed: the run used HTML/ar5iv/PMC pages; no PDF was extracted. Several relevant papers are PDF-first. Candidate: add an optional local PDF path with page-preserving extraction (pypdf or pdftotext) and an explicit "PDF text unavailable" status. Do not install a large OCR stack.

## 9. Prefer canonical open-access hosts; record mirrors

Observed: direct `arxiv.org` fetches sometimes failed; the model used an `arxiv-org.ezproxy.obspm.fr` mirror. The evidence URL is recorded honestly, but a future reader may not be able to resolve it. Candidate: normalize known mirrors to canonical arXiv IDs in the citation layer while keeping the fetched URL in the evidence record.

## 10. The report renderer must be tested against nested summaries

Observed: `flash_report.py` initially iterated the `cases` object instead of its `cases` list and crashed. Fixed offline. Candidate: add a renderer smoke test with the actual `diagnose_summary.json` shape; renderers should never require a live run to catch schema drift.

## 11. What not to change

- Do not lower the reserve or the peak-rate accounting because actual spend was low.
- Do not auto-fallback to Ollama/Qwen when a fetch or a publisher page fails.
- Do not let the Scientist cite a search snippet as a read source.
- Do not turn the same-model audit into "independent expert review".

## 12. Cost/size observations (this run)

- 30 model attempts total across capability + diagnostics + literature; 10 searches; 18 fetch attempts.
- 560,786 input tokens and 52,938 output tokens cumulatively; peak-rate accounting CNY 1.65 of the CNY 20 cap (CNY 2 reserved).
- 16 literature model calls, 42 tool calls, 7 cited papers, 19 read slices.
- These are measured; they are not a benchmark of model efficiency.
