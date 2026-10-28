# Paths and authority

| Location | Purpose |
|---|---|
| X:/projects/EEG-AI-Scientist | Sole formal Windows repository, branch research/overnight-20261029 |
| framework/ | Active imported wzf framework; new benchmark modules extend it |
| archive/ | Preserved provenance and former project material; not runnable experiments |
| .local/overnight-20261029/private/ | Ignored Builder-only sources, references and gold |
| .local/overnight-20261029/evidence/ | Ignored raw runtime evidence; publish sanitized indices |
| docs/overnight/2026-10-29/ | Reviewable plans, status, methodological notes and recovery |
| /data/duandh/eegfm-stage-a-20261028 | Existing server installation and permitted remote write scope |
| /data/duandh/eegfm-stage-a-20261028/source/eeg-fm-research | Preserved imported fb6c37e snapshot; not the new branch |
| /data/duandh/eegfm-stage-a-20261028/overnight-20261029 | Active integration checkout, runtime, isolated cases and evidence |
| /home/duandh | Actual login home; avoid large writes; existing authentication remains private |
| GitHub remote github | Existing EEG-AI-Scientist history; no overnight push authorized |
| C:/Users/14090/Documents/ChatGPT/EEG-FM-RSI | Historical support location, not an active checkout |

Laboratory dataset/shared mounts remain untouched. Any resource probing must be targeted and read-only, with participant identifiers excluded from prompts and commits.

The `stage-a-20261028` name is a dated deployment/staging container, not the long-term project identity. Its base virtual environment is `.../eegfm-stage-a-20261028/venv/bin/python` (not under the nightly folder). Server jobs live in `overnight-20261029/builders/jobs/Mxx/JOB.json`; the corresponding private Windows job inputs live in `.local/overnight-20261029/private/jobs/`. Actor cases contain only explicit public inputs and their own output. Server integration shares the X repository's history; the preserved imported source has different ancestry and must not be merged as if it were that checkout.
