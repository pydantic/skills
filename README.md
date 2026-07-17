# Pydantic Skills

Logfire and Pydantic AI plugins for [Claude Code](https://claude.com/claude-code), [Codex](https://openai.com/codex), and [Cursor](https://cursor.com). Instrument your code with Logfire, query and export the resulting telemetry, and build LLM agents with Pydantic AI.

## Plugins

| Plugin                                        | Hosts                      | Description                                         | Capabilities                                                                         |
| --------------------------------------------- | -------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| [logfire](plugins/logfire/)                   | Claude Code, Codex, Cursor | Add Logfire observability and query/debug telemetry | Claude commands `/instrument`, `/debug`, `/query`; Codex/Cursor skills and MCP tools |
| [logfire-exporter](plugins/logfire-exporter/) | Codex                      | Export Codex activity traces to Logfire             | Codex lifecycle hooks                                                                |
| [ai](plugins/ai/)                             | Claude Code                | Build AI agents with Pydantic AI                    | Pydantic AI skill docs                                                               |
| [pydantic-ai-harness](plugins/pydantic-ai-harness/) | Claude Code          | Extend Pydantic AI agents with harness capabilities (Code Mode) | Pydantic AI Harness skill docs                                           |
| [migrate-deep-agents-to-pydantic-ai](plugins/migrate-deep-agents-to-pydantic-ai/) | Claude Code | Migrate LangChain Deep Agents projects to Pydantic AI | Inventory, Pydantic AI patterns, recipes, and behavior validation |

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
claude plugin install migrate-deep-agents-to-pydantic-ai@pydantic-skills
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
| [migrate-deep-agents-to-pydantic-ai](skills/migrate-deep-agents-to-pydantic-ai/) | Convert LangChain Deep Agents projects to Pydantic AI and Harness capabilities |
