# Connection setup

## Query Logfire

Follow [MCP connection selection](mcp.md) for US, EU, or self-hosted access.
It keeps one selected connection active without changing plugin cache files.
Never print a full Codex configuration file: it may contain exporter credentials.
CLI account login does not authenticate Codex's MCP client.

Query-only ends here. No runtime installation or capture questions are needed.

## Record Codex sessions

Confirm destination origin, organization, and project, and explain the choices:

- **Full:** native logs/traces with prompts, tool arguments and bounded result
  previews; enrichment adds final assistant responses. Content can contain source
  code or secrets. Native logs can also include account email and host name.
- **Messages without tool content:** prompt/final-response enrichment and native
  traces, without native logs or tool content (`no-tool-content`).
- **Metadata only:** timing and usage without message or tool content.
- **Not now:** leave recording unchanged.

Record the user's capture choice explicitly. These settings apply across
repositories, not just this conversation. Native export uses `CODEX_HOME`, while
enrichment configuration uses `XDG_CONFIG_HOME` (or `~/.config`): separate Codex
homes can still share an enrichment destination. Do not retarget an existing
installation without confirmation. Disabling this plugin does not stop native
capture. Codex currently stores a project write token in its native configuration
and exporter configuration; do not print, commit, or sync those files.

Run the bundled helper with `--agent codex` (see the skill entrypoint). If it
reports `runtime_required`, offer to install the private persistent CLI with the
same helper plus `--install`; Python 3 and uv are required. Do not silently install
packages into the user's app or fall back to the old Python SDK CLI. Status
checks must omit `--install`. Use its returned absolute executable and `data_dir`.

For every command below, use the confirmed `--region us`, `--region eu`, or
`--base-url <origin>` and `--org <organization>`. Omit ambient `LOGFIRE_BASE_URL`
when using a cloud region. For browser login, omit ambient `LOGFIRE_API_KEY`,
`LOGFIRE_TOKEN`, and `LOGFIRE_MCP_TOKEN` from child environments without exposing
their values or changing the parent environment. Preserve explicitly requested
headless credentials. Quote all substituted paths/names as arguments.

1. Inspect `--no-input --output json auth status`. If needed, run `auth login`
   against that same origin and organization, explaining browser approval.
   Do not start competing pending logins. `auth` does not accept `--data-dir`.
2. Inspect `--no-input --output json project --data-dir <data_dir> current`.
   Reuse credentials matching the confirmed origin/org/project. Only when absent
   (not on network/auth errors), or after explicit retargeting approval, run
   `--no-input --output json init use --name <project> --data-dir <data_dir>`.
   This creates a write token; do not repeat initialization on reconnect or pick
   another project on failure.
3. Run `--beta --no-input --output json agent codex --data-dir <data_dir> configure --capture <mode>`
   with exactly `full`, `no-tool-content`, or `metadata-only` as selected.
   The CLI owns native export and installation of the pinned enrichment plugin.
   Do not separately install `logfire-exporter` from another marketplace.
4. Recheck `--beta --no-input --output json agent codex status`. Inspect native
   export and enrichment separately, including credential/file-permission state.

Respect independent exporter conflicts. A failure can leave the pinned plugin
installed or a token created; report the actual partial state, not an invented
rollback, and inspect status before retrying mutations.

Ask the user to restart Codex and review new exporter hooks in native hook
controls before trusting them. Send a harmless prompt after restart, then use
MCP if available to look for matching recent Codex session data in the confirmed
project. Do not treat unrelated historical activity as proof. If session
correlation or read access is unavailable, report delivery as not yet verified.
