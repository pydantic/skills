# logfire

Add [Logfire](https://logfire.pydantic.dev/) observability to Python applications.

## Features

- `/instrument` - detect frameworks and add Logfire instrumentation
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

## Install In Codex

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
- MCP server from `.mcp.json`

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

The Logfire MCP server is configured automatically when you install the plugin (US region).

Codex users can switch to the EU endpoint without editing plugin files by replacing the MCP entry and re-authenticating:

```bash
codex mcp remove logfire
codex mcp add logfire --url https://logfire-eu.pydantic.dev/mcp
codex mcp login logfire
codex mcp get logfire
```

Start a new Codex conversation after switching so the MCP tools reload.

Claude Code users can switch by running:

```
claude mcp add logfire --transport http https://logfire-eu.pydantic.dev/mcp
```

In Codex, `.mcp.json` configures the `logfire` MCP server. In Cursor, `mcp.json` configures the same hosted server.

The Logfire MCP server requires normal Logfire authentication, such as `logfire auth` or a suitable `LOGFIRE_TOKEN`.
