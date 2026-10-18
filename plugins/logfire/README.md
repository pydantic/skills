# logfire

Add [Logfire](https://logfire.pydantic.dev/) observability to Python applications.

## Features

- `/logfire:connect` - connect Claude's MCP client and optionally set up native session telemetry
- `/logfire:status` - check MCP access, native telemetry configuration, and delivery evidence separately
- `/logfire:disconnect` - stop native Claude telemetry while keeping MCP and skills
- `logfire-coding-agents` skill - configure Claude/Codex recording or coding-agent Gateway routing
- `logfire-frontend` skill - set up browser errors, Web Vitals, and session replays
- `logfire-gateway` skill - route application model calls through Pydantic AI Gateway
- `/instrument` - detect frameworks and add Logfire instrumentation
- `logfire-setup` skill - authenticate, inspect the repository, and route to the right setup workflow
- `logfire-infrastructure` skill - monitor hosts, containers, Kubernetes, databases, and cloud infrastructure
- `logfire-evals` skill - add dataset-based evaluations for AI and agent behavior
- `logfire-datasets` skill - create hosted datasets from traces, query results, or case files via the datasets API
- `/debug` - investigate errors using Logfire traces via MCP
- `/query` - query traces, logs, and metrics interactively or add query capabilities to code
- `logfire-ui` skill - open Logfire project pages, live views, traces, and Explore filters directly in Codex
- SKILL.md with core Logfire patterns (configure, instrument, structured logging, AI/LLM instrumentation)
- MCP server for querying Logfire data

## Query vs UI Routing

The Codex Logfire plugin uses one primary workflow per request:

| User intent | Route |
| --- | --- |
| Analyze, query, count, summarize, compare, or find root cause | Use `logfire-query` and return analysis in chat. |
| Open, show in browser, live view, Explore, Logfire UI, or give a link | Use `logfire-ui` and open or return a Logfire URL without querying first. |
| Ambiguous prompts like "show recent errors" or "view logs" | Ask whether the user wants a UI view or query analysis. |
| Explicit combined prompts like "analyze this and give me a link" | Do the requested query work, then provide the relevant Logfire link. |

For UI requests that omit the organization/project, the agent should resolve the current project through Logfire MCP auth/current-project metadata before asking the user. Environment values such as `LOGFIRE_BASE_URL`, `LOGFIRE_URL`, and exporter config identify the platform/API base only; they are not enough to infer the target organization/project.

## Install In Claude Code

```bash
claude plugin marketplace add pydantic/skills
claude plugin install logfire@pydantic-skills
```

The Claude plugin provides `/instrument`, `/debug`, `/query`, and the Logfire MCP server.

### Connect once

Run `/logfire:connect` inside Claude Code. It guides you through MCP OAuth and,
if you choose, native Claude session telemetry. MCP-only use needs no Logfire
CLI. For telemetry, the command locates its managed CLI or offers to install
one into a private, persistent uv tool environment; you do not need to run CLI
setup commands yourself. Python 3 and uv are needed for that managed install.

Native traces/tool-output capture requires `logfire-cli>=0.1.14,<0.2` (the
release containing logfire-cli#288). The managed installation uses the
package's `logfire-cli` executable, not the Python SDK's `logfire` command.
Older versions are rejected; MCP and existing skills remain usable independently.

The flow asks for the destination project and capture policy. Full capture can
include prompts, code, tool output, and secrets inside raw model API bodies.
Metadata-only excludes message/tool content. Native telemetry is user-wide,
including Claude sessions in other repositories, and requires a restart.

`/logfire:status` distinguishes local configuration from observed ingestion.
`/logfire:disconnect` removes the native configuration using the CLI; restart
Claude afterwards. **Disabling or uninstalling the plugin alone does not stop
native telemetry.** Disconnect before uninstalling. SDK write credentials and
the managed CLI remain outside the plugin cache, under
`~/.logfire/claude-plugin`, so plugin updates/uninstall cannot delete the active
header helper. Project credentials are separated by `CLAUDE_CONFIG_DIR` so
independent Claude installations cannot retarget each other's helpers.
Removal does not revoke the remote write token or clear MCP
OAuth; those are separate actions. This flow installs no transcript exporter.

## Install In Codex

After installing, run plugin setup or ask "Connect Codex to Logfire."
The `logfire-codex-connection` skill guides MCP access and optional recording,
and handles status or disconnect requests. Query-only needs no Logfire CLI.
Recording offers full, messages-without-tools, or metadata-only capture and
uses the supported native CLI to configure native telemetry plus pinned
conversation enrichment. Python 3 and uv are needed for the managed CLI install.
Restart Codex after changing recording; uninstalling the main plugin does not
stop native recording. Ask "Stop recording my Codex sessions" to remove it while
keeping MCP and skills. Setup leaves model-provider and Gateway settings alone.

Add the published Pydantic marketplace to Codex:

```bash
codex plugin marketplace add pydantic/skills
```

Then enable **Logfire** from the Codex plugin UI. The Codex plugin metadata lives in `.codex-plugin/plugin.json` and configures:

- display name **Logfire**
- category **Coding**
- capabilities **Interactive** and **Write**
- Logfire icon and pink brand color
- Logfire skills for instrumentation, querying, and UI-opening workflows
- MCP server from `.codex-plugin/mcp.json`

For local development after changing this plugin, refresh the Codex plugin cache:

```bash
./scripts/reload-codex-plugin.sh logfire
```

A new Codex conversation may be required for updated skills, MCP servers, icons, or metadata to load.

## Install In Cursor

Install the Logfire plugin from the published [pydantic/skills](https://github.com/pydantic/skills) repository:

```bash
git clone https://github.com/pydantic/skills.git
mkdir -p ~/.cursor/plugins/local
cp -R skills/plugins/logfire ~/.cursor/plugins/local/logfire
```

Then restart Cursor or run **Developer: Reload Window**. The Cursor plugin metadata lives in `.cursor-plugin/plugin.json` and configures:

- display name **Logfire**
- Logfire skills for instrumentation, querying, and UI-opening workflows
- hosted Logfire MCP server from `mcp.json`

## MCP

The Logfire MCP server is configured automatically when you install the plugin. By default it
targets the US region endpoint (`https://logfire-us.pydantic.dev/mcp`). The plugin's skills and
commands are region-independent; only the MCP server entry differs per region.

### EU region and self-hosted instances

**Claude Code** reads the endpoint from the `LOGFIRE_MCP_URL` environment variable, so set it in
the shell where you launch Claude Code:

```bash
export LOGFIRE_MCP_URL=https://logfire-eu.pydantic.dev/mcp
```

A value saved in Claude's user settings can override this shell value. Check
the URL reported by `claude mcp get plugin:logfire:logfire`, or use
`/logfire:connect` to reconcile the endpoint before authenticating.

This needs plugin version 0.1.4 or later; on earlier versions the URL is hardcoded. Run
`claude plugin list` to see the installed version and the marketplace it came from, then update
and restart Claude Code:

```bash
claude plugin marketplace update pydantic-skills
claude plugin update logfire@pydantic-skills
```

If you installed from Anthropic's `claude-plugins-official` marketplace instead, substitute that
name. That marketplace pins a specific commit of this repository, so a release can take longer to
appear there than on `pydantic-skills`, which tracks `main`.

**Codex** users can ask "Connect Logfire to my EU account" or provide their
self-hosted MCP URL. The plugin's setup skill disables only the bundled US MCP
server, keeps the plugin and skills enabled, and configures one native regional
connection. Existing matching connections are reused; replacing another connection
requires confirmation. The URL of a bundled server cannot be overridden through
Codex's plugin policy or `LOGFIRE_MCP_URL`.

See the [regional MCP workflow](skills/logfire-codex-connection/references/mcp.md)
for the native commands and scoped policy helper. Restart/reload Codex after
switching, authenticate the selected connection, and verify access. Returning to
US removes only the agreed regional connection before re-enabling the bundled
server. MCP changes do not change session recording or Gateway routing.

**Cursor** installs are a local copy, so edit the `url` in
`~/.cursor/plugins/local/logfire/mcp.json` and reload the window.

In Claude Code, `.mcp.json` configures the `logfire` MCP server. In Codex, `.codex-plugin/mcp.json`
configures it. In Cursor, `mcp.json` configures the same hosted server.

Claude's hosted MCP connection uses Claude's native OAuth flow (`/mcp`). CLI
login and project write credentials are separate; `logfire auth` does not log
Claude's MCP client in. Never paste account credentials into the conversation.
