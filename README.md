# Pydantic Skills

Logfire, Pydantic AI, and Pydantic plugins for [Claude Code](https://claude.com/claude-code), [Codex](https://openai.com/codex), and [Cursor](https://cursor.com). Instrument your code with Logfire, query and export the resulting telemetry, build LLM agents with Pydantic AI, and validate data with Pydantic.

## Plugins

| Plugin                                        | Hosts                      | Description                                         | Capabilities                                                                         |
| --------------------------------------------- | -------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| [logfire](plugins/logfire/)                   | Claude Code, Codex, Cursor | Add Logfire observability and query/debug telemetry | Claude commands `/instrument`, `/debug`, `/query`; Codex/Cursor skills and MCP tools |
| [logfire-exporter](plugins/logfire-exporter/) | Codex                      | Export Codex activity traces to Logfire             | Codex lifecycle hooks                                                                |
| [ai](plugins/ai/)                             | Claude Code                | Build AI agents with Pydantic AI                    | Pydantic AI skill docs                                                               |
| [pydantic-ai-harness](plugins/pydantic-ai-harness/) | Claude Code          | Extend Pydantic AI agents with harness capabilities (Code Mode) | Pydantic AI Harness skill docs                                           |
| [pydantic](plugins/pydantic/)                 | Claude Code                | Validate and serialize data with Pydantic           | Pydantic skill docs                                                                  |

## Install In Claude Code

Add this marketplace to Claude Code:

```
claude plugin marketplace add pydantic/skills
```

Then install a plugin:

```
claude plugin install logfire@pydantic-skills
claude plugin install ai@pydantic-skills
claude plugin install pydantic-ai-harness@pydantic-skills
claude plugin install pydantic@pydantic-skills
```

## Install In Codex

Add the published Pydantic marketplace to Codex:

```bash
codex plugin marketplace add pydantic/skills
```

Then open Codex's plugin UI and enable the plugins you want from the **Pydantic** marketplace:

- **Logfire** - installs Logfire skills and the hosted Logfire MCP server.
- **Logfire Exporter** - installs Codex lifecycle hooks that export completed Codex turns and tool calls to Logfire.

Configure **Logfire Exporter** with a Logfire write token in your environment or
`${XDG_CONFIG_HOME:-~/.config}/logfire-exporter/config.env`. Restart Codex after configuration, and run `/hooks` if
Codex asks you to review or trust the new hooks.

To use the EU Logfire MCP endpoint in Codex without editing plugin files, replace the MCP entry and re-authenticate:

```bash
codex mcp remove logfire
codex mcp add logfire --url https://logfire-eu.pydantic.dev/mcp
codex mcp login logfire
codex mcp get logfire
```

Start a new Codex conversation after switching so the MCP tools reload.

### Troubleshooting Codex OAuth

Codex CLI 0.142.0 through at least 0.144.3 has an OAuth regression
([openai/codex#31573](https://github.com/openai/codex/issues/31573)): it drops the RFC 9207 `iss`
parameter from the authorization callback, so `codex mcp login` can fail with
`Authorization server response missing required issuer` even after the browser shows
"Authentication complete". A server-side workaround is being rolled out to the hosted Logfire MCP
servers (mid-July 2026). If you still hit this error (for example against a self-hosted Logfire
instance that hasn't updated yet), either:

- downgrade Codex: `npm install -g @openai/codex@0.141.0`, or
- wait for a Codex release that fixes the issue, then retry `codex mcp login logfire`.

## Install In Cursor

Install the Logfire plugin from the published [pydantic/skills](https://github.com/pydantic/skills) repository:

```bash
git clone https://github.com/pydantic/skills.git
mkdir -p ~/.cursor/plugins/local
cp -R skills/plugins/logfire ~/.cursor/plugins/local/logfire
```

Then restart Cursor or run **Developer: Reload Window**. The plugin configures:

- display name **Logfire**
- Logfire skills for instrumentation, querying, and UI-opening workflows
- hosted Logfire MCP server from `mcp.json`

The Logfire MCP server requires normal Logfire authentication, such as `logfire auth` or a suitable `LOGFIRE_TOKEN`.

## Cross-Agent Skills

The `skills/` directory contains standalone SKILL.md files compatible with 30+ agents via the [agentskills.io](https://agentskills.io) standard - including Codex, Cursor, Gemini CLI, and Claude Code.

| Skill                                                              | Description                                                                         |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| [logfire-instrumentation](skills/logfire-instrumentation/)         | Add Logfire observability to Python, JS/TS, and Rust apps                           |
| [logfire-query](skills/logfire-query/)                             | Query and analyze Logfire traces, logs, spans, metrics, and activity data           |
| [logfire-ui](skills/logfire-ui/)                                   | Open Logfire project pages, live views, traces, and Explore filters                 |
| [building-pydantic-ai-agents](skills/building-pydantic-ai-agents/) | Build LLM-powered agents with Pydantic AI — tools, capabilities, streaming, testing |
| [pydantic-ai-harness](skills/pydantic-ai-harness/)                 | Extend Pydantic AI agents with harness capabilities like Code Mode (sandboxed `run_code`) |
| [pydantic](skills/pydantic/)                                       | Validate and serialize data with Pydantic models, constraints, and custom validators |
