# Imported framework and local-only artifacts

The local `framework/` directory preserves the 281 regular files supplied in the wzf source distribution. Its source manifest and original package are retained in the local setup archive. The current upstream repository and latest team revision remain unverified.

The versioned framework deliberately excludes the supplied `examples/demo_claude_001/` run directory and `tasks/reve_isa/src/split_manifest.json`. The former contains historical runtime state and outputs; the latter contains participant identifiers. Both remain present locally without content changes. Original distribution archives and review ZIPs also remain local because they include those artifacts. A Git checkout therefore contains a selected source snapshot, not a complete reproduction of all 281 supplied files.

`release_reference.json` and aggregate knowledge files are retained as historical source context. They do not establish that the scientific experiments have been run or reproduced in this environment. A future research task must arrange an authorized local split manifest separately before using the corresponding task; do not commit participant lists or copy laboratory datasets into Git.

The initial two snapshot commits, now retained in a local bundle and the isolated server source checkout, are import records created during setup. They are not the team's upstream commit history and have not been pushed to GitHub.
