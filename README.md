# Pydantic Skills

Official [Claude Code](https://claude.com/claude-code) plugin marketplace for the Pydantic ecosystem, plus a local Codex plugin marketplace for Pydantic tools.

## Plugins

| Plugin | Hosts | Description | Capabilities |
|--------|-------|-------------|--------------|
| [logfire](plugins/logfire/) | Claude Code, Codex | Add Logfire observability and query/debug telemetry | Claude commands `/instrument`, `/debug`, `/query`; Codex skills and MCP tools |
| [codex-logfire-exporter](plugins/codex-logfire-exporter/) | Codex | Export Codex activity traces to Logfire | Codex lifecycle hooks |
| [ai](plugins/ai/) | Claude Code | Build AI agents with Pydantic AI | Pydantic AI skill docs |

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

The Codex marketplace metadata is local-only today. From this repository root, add the marketplace with an absolute path:

```bash
codex plugin marketplace add /absolute/path/to/pydantic/skills
```

Then open Codex's plugin UI and enable the plugins you want from the **Pydantic** marketplace:

- **Logfire** - installs Logfire skills, the hosted Logfire MCP server, and a local render MCP server for activity widgets.
- **Codex Logfire Exporter** - installs Codex lifecycle hooks that export completed Codex turns and tool calls to Logfire.

After enabling **Codex Logfire Exporter**, restart Codex and run `/hooks` if Codex asks you to review or trust the new hooks.

For local development after editing a Codex plugin, reload the plugin cache:

```bash
./scripts/reload-codex-plugin.sh logfire
./scripts/reload-codex-plugin.sh codex-logfire-exporter
```

A new Codex conversation may be required for plugin metadata, skills, MCP servers, icons, or hooks to refresh.

## Cross-Agent Skills

The `skills/` directory contains standalone SKILL.md files compatible with 30+ agents via the [agentskills.io](https://agentskills.io) standard - including Codex, Cursor, Gemini CLI, and Claude Code.

| Skill | Description |
|-------|-------------|
| [logfire-instrumentation](skills/logfire-instrumentation/) | Add Logfire observability to Python, JS/TS, and Rust apps |
| [building-pydantic-ai-agents](skills/building-pydantic-ai-agents/) | Build LLM-powered agents with Pydantic AI — tools, capabilities, streaming, testing |

## Development

Test a plugin locally:

```bash
claude --plugin-dir ./plugins/logfire
```

The Codex metadata lives alongside the Claude metadata:

```text
.agents/plugins/marketplace.json
plugins/logfire/.codex-plugin/plugin.json
plugins/codex-logfire-exporter/.codex-plugin/plugin.json
```

The Codex marketplace currently lists `logfire` and `codex-logfire-exporter`; `ai` remains a Claude plugin plus a standalone cross-agent skill.
