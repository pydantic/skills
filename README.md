# Pydantic Skills

Logfire and Pydantic AI plugins for [Claude Code](https://claude.com/claude-code), [Codex](https://openai.com/codex), and [Cursor](https://cursor.com). Instrument your code with Logfire, query and export the resulting telemetry, and build LLM agents with Pydantic AI.

## Plugins

| Plugin                                        | Hosts                      | Description                                         | Capabilities                                                                         |
| --------------------------------------------- | -------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| [logfire](plugins/logfire/)                   | Claude Code, Codex, Cursor | Add Logfire observability and query/debug telemetry | Claude commands `/instrument`, `/debug`, `/query`; Codex/Cursor skills and MCP tools |
| [logfire-exporter](plugins/logfire-exporter/) | Codex                      | Export Codex activity traces to Logfire             | Codex lifecycle hooks                                                                |
| [ai](plugins/ai/)                             | Claude Code                | Build AI agents with Pydantic AI                    | Pydantic AI skill docs                                                               |

## Install In Claude Code

Add this marketplace to Claude Code:

```
claude plugin marketplace add pydantic/skills
```

Then install a plugin:

```
claude plugin install logfire@pydantic-skills
claude plugin install ai@pydantic-skills
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

For local development after editing a Codex plugin, reload the plugin cache:

```bash
./scripts/reload-codex-plugin.sh logfire
./scripts/reload-codex-plugin.sh logfire-exporter
```

A new Codex conversation may be required for plugin metadata, skills, MCP servers, icons, or hooks to refresh.

To use the EU Logfire MCP endpoint in Codex without editing plugin files, replace the MCP entry and re-authenticate:

```bash
codex mcp remove logfire
codex mcp add logfire --url https://logfire-eu.pydantic.dev/mcp
codex mcp login logfire
codex mcp get logfire
```

Start a new Codex conversation after switching so the MCP tools reload.

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

The Logfire MCP server requires normal Logfire authentication, such as `logfire auth` or a suitable `LOGFIRE_TOKEN`.

## Cross-Agent Skills

The `skills/` directory contains standalone SKILL.md files compatible with 30+ agents via the [agentskills.io](https://agentskills.io) standard - including Codex, Cursor, Gemini CLI, and Claude Code.

| Skill                                                              | Description                                                                         |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| [logfire-instrumentation](skills/logfire-instrumentation/)         | Add Logfire observability to Python, JS/TS, and Rust apps                           |
| [logfire-query](skills/logfire-query/)                             | Query and analyze Logfire traces, logs, spans, metrics, and activity data           |
| [logfire-ui](skills/logfire-ui/)                                   | Open Logfire project pages, live views, traces, and Explore filters                 |
| [building-pydantic-ai-agents](skills/building-pydantic-ai-agents/) | Build LLM-powered agents with Pydantic AI — tools, capabilities, streaming, testing |

## Development

Test a plugin locally:

```bash
claude --plugin-dir ./plugins/logfire
```

While developing this repository, symlink the Cursor plugin instead of copying it:

```bash
ln -s /absolute/path/to/pydantic/skills/plugins/logfire ~/.cursor/plugins/local/logfire
```

Host-specific metadata lives alongside the shared plugin content:

```text
.claude-plugin/marketplace.json
.cursor-plugin/marketplace.json
.agents/plugins/marketplace.json
plugins/logfire/.claude-plugin/plugin.json
plugins/logfire/.cursor-plugin/plugin.json
plugins/logfire/.codex-plugin/plugin.json
plugins/logfire-exporter/.codex-plugin/plugin.json
```

The Cursor and Codex marketplaces currently list `logfire`; Codex also lists `logfire-exporter`. The `ai` plugin remains Claude-only plus a standalone cross-agent skill.
