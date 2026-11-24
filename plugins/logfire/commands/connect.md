---
description: Connect Logfire MCP and optionally record Claude Code sessions with native telemetry
---

# Connect Logfire

Guide the user through connection; execute setup for them rather than handing
them a list of CLI commands. This command is for Claude Code. It does not
instrument the user's application or enable an AI Gateway proxy.

## Keep the conversation short

If the user's request does not already say, ask one question: "Would you like
to query Logfire, record your Claude sessions, or both?" Honor an answer in the
command arguments without asking again. Ask only for missing information, not
the entire configuration at once. Explain what the next browser approval is for.

For query-only, finish after the MCP check; do not ask capture questions or
install a runtime. For recording-only, skip MCP authentication: CLI login and
an explicitly chosen project are sufficient. Offer MCP verification afterwards,
but do not require read access just to send telemetry.

## Connect MCP

The plugin already registers the hosted `logfire` HTTP MCP server. Inspect its
actual endpoint and connection state with Claude's `/mcp` interface or
`claude mcp list`. Do not add a second server. Ask for the intended region or
self-hosted endpoint if it is not established by the user or current connection.

The default is `https://logfire-us.pydantic.dev/mcp`; EU uses
`https://logfire-eu.pydantic.dev/mcp`. `LOGFIRE_MCP_URL` overrides the default.
If a change is needed, offer to merge only that environment value into Claude's
user settings, preserving all other settings. Confirm this user-wide change
before editing. Inspect the resolved URL rather than assuming a shell export
overrides saved user settings. Reload the plugin or restart Claude and verify
the resolved endpoint before authenticating.

Use Claude's native OAuth flow (`/mcp`, select Logfire, authenticate), or
`claude mcp login` with the exact registered server name. Never read Claude's
credential store, request tokens in chat, or imply CLI login authenticates
Claude's MCP client. Listing/getting an MCP server can exit successfully while
its reported connection status is failed; exit code zero is not authentication
proof. Verify with a small authenticated MCP read. MCP-only is a
complete, supported connection; do not require a CLI installation for it.

## Offer session telemetry

Explain the choice separately from MCP access:

- **Full capture:** messages, supported tool inputs/outputs, and raw model API
  bodies, which can include conversation history, source code, and secrets.
- **Metadata only:** native traces, timing, and usage without message/tool content.
- **Not now:** leave telemetry unchanged.

Confirm the capture choice and destination organization/project. Explain that
native telemetry settings are user-wide: sessions in other repositories also
send to this destination. Installing or disabling this plugin alone does not
turn native capture on or off. Never infer consent from MCP authentication.

After consent, locate the plugin's persistent runtime:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agent_runtime.py"
```

If it reports `runtime_required`, explain that the plugin needs a persistent
Logfire helper and offer to install it. With permission, run the same script
with `--install`. It installs into a private uv tool environment, not the
application's dependencies. If uv is unavailable or the required CLI has not
been released, report the blocker without enabling partial/older capture.
Do not substitute `uvx`, `npx`, an unpinned Git checkout, or a temporary binary:
Claude's saved header helper must survive runtime cache cleanup.

Use the returned absolute `executable` as the CLI and `data_dir` for the
telemetry project's credentials. Keep this directory separate from the app's
`.logfire`; do not print or open its token file. Quote each path as one argument.

Run these through that executable, with either `--region us`, `--region eu`,
or a user-confirmed `--base-url`, matching the intended Logfire instance.
Replace placeholders with the confirmed values and quote them as shell arguments:

Apply the selected target and `--org <organization>` to every account command,
including `auth status` and `auth login`. CLI browser login is stored in the OS
credential store for that origin and organization. `<data_dir>` stores the
separate SDK write credential; it is not an OAuth login directory, and the
`auth` commands do not accept `--data-dir`.

1. `--output json auth status` to inspect non-secret login metadata.
2. If needed, `auth login` to complete browser authentication. Do not launch a
   competing interactive login when a browser flow is already pending.
3. Inspect `--org <organization> --no-input --output json project --data-dir <data_dir> current`.
   Reuse a verified existing binding to the chosen instance, organization, and
   project. Only initialize when local credentials are missing or the user
   explicitly confirms a different destination:
   `--org <organization> --no-input --output json init use --name <project> --data-dir <data_dir>`.
   This creates a write token. Do not mint another token on every reconnect,
   treat network/authentication failure as missing credentials, or pick another
   project on failure.
4. Run exactly one command matching the capture choice:
   - Full capture: `--org <organization> --beta --no-input --output json agent claude --data-dir <data_dir> configure --capture full`.
   - Metadata only: `--org <organization> --beta --no-input --output json agent claude --data-dir <data_dir> configure --capture metadata-only`.

Use the supported CLI for writes, not a hand-written exporter/settings merge.
Respect an existing independent telemetry exporter: report conflicts rather
than replacing it. If configuration fails after project initialization, report
that a credential was created but telemetry was not configured; do not blindly
retry mutating steps or claim rollback.

## Verify and finish

Run `--beta --no-input --output json agent claude --data-dir <data_dir> status`.
Report configuration separately from delivery: a configured helper is not proof
of ingestion. Ask the user to restart Claude, send one harmless prompt, and use
MCP, if connected, to check recent Claude telemetry in the confirmed project.
Match the current session identity when available, not merely another user's
activity in the same project. If that correlation is unavailable, say delivery
for this session is not verified.
Do not send test data to another project or count unrelated old data as proof.

Finish with a compact result, not a replay of commands: MCP access, session
capture mode and destination, and delivery verified/not yet verified. Omit
unused modes. Give one next action, such as "Restart Claude and send a prompt."
Point to `/logfire:status` and `/logfire:disconnect` without another setup guide.
No custom transcript hooks are installed by this flow.
