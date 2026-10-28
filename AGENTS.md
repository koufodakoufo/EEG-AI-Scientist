# Project working rules

- The only formal local workspace is X:/projects/EEG-AI-Scientist. Always use it explicitly as the working directory. The C:/Users/14090/Documents/ChatGPT/EEG-FM-RSI folder is temporary/support material, not an active project.
- Use the existing root Git repository and its actual remote. Do not initialize another repository under framework/ or create a replacement local workspace. Do not commit or push merely to make the working tree look clean.
- Active framework source lives in framework/. The imported framework's rules apply within their task scope, but original wzf absolute machine paths are historical context and must not be created or used here.
- Preserve archive/ originals and source provenance. Archived legacy code and its relocated virtual environment are restoration material, not current runnable entrypoints. Do not run historical experiment commands against the archive.
- Do not read, move, print, or upload credentials/. Do not upload local snapshots, authentication, data, model weights, runtime state, or private materials to GitHub.
- Do not modify, move, delete, chmod, or chown dataset/shared storage, existing server projects, or other users' files. The setup remote write scope is /data/duandh/eegfm-stage-a-20261028. The user-requested IDE login repair additionally permits the helper-managed proxy-only /home/duandh/.codex/.env; never replace an unmanaged file or read authentication contents.
- Use the verified per-session campus SSH source address and temporary loopback proxy; do not change global routes, shell profiles, or server configuration as a shortcut.
- Current scope stops before Agent architecture changes, scientific task expansion, or EEG/GPU experiments. New research requires an explicit subsequent task and bounded resources.
- Follow docs/environment-20261028/README.zh-CN.md for operating steps. The historical STATUS.json under archive/setup-20261028 records an earlier layout; current status lives under docs/environment-20261028/current-status.json.
- Python code must have type annotations. Prefer existing verification and avoid unnecessary platform expansion.
