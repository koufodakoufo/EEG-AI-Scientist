# Codex 0.165.0 runtime review — M06

Builder investigation, 2026-10-29. No inference, Actor, Distiller, authentication-content reads, dataset changes, root installation, or global changes were performed. These findings establish runtime/configuration behavior, **not a passing live isolation boundary**. Raw evidence is ignored under `.local/overnight-20261029/evidence/runtime-review/`.

## Findings that affect the launcher

1. **`exec --ignore-user-config -p actor` discards the Actor profile.** In the official `rust-v0.165.0` loader, `ignore_user_config` is passed to both the base config and the selected profile; the loader returns an empty table for each when this flag is true. Thus the flag removes the custom filesystem/network policy, feature restrictions and shell environment. Remove it when using a fresh dedicated control home containing only approved configuration. Keep `--ignore-rules`, `--strict-config`, `--ephemeral`, the case cwd and the selected profile. Alternatively every restriction would need explicit `-c` overrides. [Loader source, lines 292–339 and 515–539](https://github.com/openai/codex/blob/rust-v0.165.0/codex-rs/config/src/loader/mod.rs#L292); [exec wiring](https://github.com/openai/codex/blob/rust-v0.165.0/codex-rs/exec/src/lib.rs#L381).

2. **Model metadata can select code mode despite `features.code_mode=false`.** The requested tool mode starts with `model_info.tool_mode`; feature flags are fallback defaults. The auth-free offline prompt for the selected `gpt-6.1-sol` still contains `functions.exec`. It is therefore inappropriate to infer config failure from that declaration alone. [Tool-mode selection](https://github.com/openai/codex/blob/rust-v0.165.0/codex-rs/core/src/tools/mod.rs#L63).

3. **`features.multi_agent=false` alone does not defeat model-selected V2.** Set `[agents] enabled=false` and ensure `features.multi_agent_v2.enabled=false`. The former supplies an explicit Disabled override ahead of model metadata. Additionally, `features.multi_agent_v2.disable_native_tools=true` removes native collaboration tools. The final offline prompt has neither the collaboration namespace nor the multi-agent role block. [Override precedence](https://github.com/openai/codex/blob/rust-v0.165.0/codex-rs/core/src/config/mod.rs#L1664); [native-tool gate](https://github.com/openai/codex/blob/rust-v0.165.0/codex-rs/core/src/tools/spec_plan.rs#L733).

4. **A 12 GiB address-space limit crashes V8.** An offline host protocol handshake and session open work under `RLIMIT_AS=12 GiB`, but the first text-only JavaScript cell exits with signal 5 and `Failed to reserve the virtual address space for the V8 sandbox`. Without that address-space limit, the same host returns `RUNTIME_CELL_OK`; measured VmSize was approximately 1.35 TiB while RSS was approximately 23 MB. Physical-memory enforcement must account for the actual process tree/cgroup rather than equating virtual reservation with RAM. Do not simply remove the limit without preserving the required RAM enforcement. Both stdio and gRPC host launch code create a separate process group, so a monitor or killer limited to the parent PGID can miss the host. [Stdio host spawn](https://github.com/openai/codex/blob/rust-v0.165.0/codex-rs/code-mode/src/remote_session/connection.rs#L157); [gRPC spawn](https://github.com/openai/codex/blob/rust-v0.165.0/codex-rs/core/src/code_mode_host.rs#L99).

## Prepared runtime

The existing installation is preserved. Use this isolated executable and its sibling:

```text
/data/duandh/eegfm-stage-a-20261028/overnight-20261029/tools/runtime-review/bin/codex
/data/duandh/eegfm-stage-a-20261028/overnight-20261029/tools/runtime-review/bin/codex-code-mode-host
```

Both are x86-64 static PIE executables; no additional shared libraries were needed for help, the IPC handshake or the completed JavaScript cell. The native CLI is an unchanged copy of the existing 0.165.0 binary. The host is the matching official release asset, obtained through GitHub's asset API after direct downloads failed before receiving payload. The archive contained exactly one regular file with the expected basename; its path, type and size were checked before extraction.

| Object | Bytes | SHA-256 |
|---|---:|---|
| Native CLI copy | 309732776 | `c06a67fd8ac76508dc78bd99ce20c9f317b8d568beda59485f3f4134df9962d5` |
| Official host tar.gz | 28137324 | `9577b09b2a546eeb3da8a09807de6d58fbaa207755256390113772ea4f05235e` |
| Extracted host | 77002000 | `522935d4392ec9674fab60b239b5495992c6a93e4deb65113a216b6f5451ccd4` |

[Official release](https://github.com/openai/codex/releases/tag/rust-v0.165.0), [exact asset API](https://api.github.com/repos/openai/codex/releases/assets/682734791). The archive digest matched the release API digest locally and after transfer. Downloaded executable payload was 28.14 MB; fetched source files totaled 1,168,083 bytes.

Use the new native path when generating permission entries and sandbox/apply-patch symlinks. Keep the host adjacent to the actual executable. Set `code_mode_host=true` for this prepared layout. Help and an isolated text cell do not validate shell delegation or the full Actor launch.

## Configuration additions

Merge these settings into the fresh generated profile; replace existing matching keys rather than appending duplicate TOML tables. In particular replace `code_mode_host=false` with `true`. The remainder of the existing restrictive profile, including `web_search="disabled"`, filesystem permissions and `network.enabled=false`, remains required.

```toml
[agents]
enabled = false

[features]
code_mode = false
code_mode_host = true
multi_agent = false
apps = false
plugins = false

[features.multi_agent_v2]
enabled = false
disable_native_tools = true

[skills]
include_instructions = false

[skills.bundled]
enabled = false

[cloud.skills]
enabled = false
```

These are nested TOML tables, **not** quoted keys containing periods. The equivalent CLI overrides were verified with `debug prompt-input` and the copied Actor profile in an authentication-free control home. The final prompt had no web tool, collaboration namespace, multi-agent role block or automatic skills block. The initial profile still included bundled skills despite `skip_host_skill_discovery=true`; the explicit skill controls removed that block.

Remaining tools: `functions.exec`, `functions.wait`, both request-user-input tools, `clock.sleep`; nested `apply_patch`, `exec_command`, `write_stdin`, `clock__curr_time`, `list_mcp_resources`, `list_mcp_resource_templates`, `read_mcp_resource`. Code-mode-only sessions intentionally receive generic MCP resource helpers even with no MCP servers. No connectors were configured in the diagnostic home. A live canary still needs to verify empty listings and an unconfigured-server read failure, alongside shell reads/writes/network and process cleanup. [MCP helper registration](https://github.com/openai/codex/blob/rust-v0.165.0/codex-rs/core/src/tools/spec_plan.rs#L1276).

## Offline verification limits and evidence

- `features list` rejects both `--strict-config` and top-level `-p`; copying the safe profile to an isolated base `config.toml` confirmed the flags parse and show false. This is not an exact exec effective-config dump.
- `debug prompt-input` accepts `-p actor` but rejects `--ignore-user-config` and `--strict-config`. It can inspect the corrected profile path without inference, but cannot reproduce the original broken flag combination. The loader source establishes the latter behavior.
- The final prompt includes the case writable root, explicit deny entries and restricted network text. No inherited project AGENTS document was present; ordinary built-in developer prose still mentions AGENTS/skills generically.
- The debug command has its own extension registry and uses the available model catalog; the real app-server/inference path must still be checked with the launcher canary. Source/API observations do not authorize blind Actor or Distiller evaluation.
- Host protocol probes used an empty tool set, a 128 MiB JavaScript heap ceiling, bounded CPU/time, disabled core dumps and an authentication-free environment. The successful process was deliberately terminated after receiving the marker; exit `-15` is harness cleanup, not a cell failure. Earlier protocol observations are retained, including a premature wait that was rejected because execution still had an active observer.

Evidence files: `host-release-assets.json`, `archive-verification.json`, `host-install-verified.txt`, `binary-layout.txt`, `features-help.txt`, `prompt-input.json`, `prompt-inventory.txt`, `restricted-prompt-inventory.txt`, `final-prompt-inventory.json`, `host-protocol-probe.jsonl`, `host-protocol-cell.jsonl`, `host_probe.py`, and `recommended-overrides.toml`. Official source snapshots are under `source/`; remote diagnostic files are under the night's `tools/runtime-review/` and `evidence/runtime-review/`.
