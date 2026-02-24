# Pydantic Skills

Official [Claude Code](https://claude.com/claude-code) plugin marketplace for the Pydantic ecosystem.

## Plugins

| Plugin | Description | Commands |
|--------|-------------|----------|
| [instrument-with-logfire](plugins/instrument-with-logfire/) | Add Logfire observability to Python apps | `/instrument`, `/debug` |

## Install

Add this marketplace to Claude Code to get all plugins:

```
claude /install-plugin https://github.com/pydantic/skills
```

Or install a single plugin:

```
claude /install-plugin https://github.com/pydantic/skills --plugin instrument-with-logfire
```

## Cross-Agent Skills

The `skills/` directory contains standalone SKILL.md files compatible with 30+ agents via the [agentskills.io](https://agentskills.io) standard - including Codex, Cursor, Gemini CLI, and Claude Code.

## Development

Test a plugin locally:

```bash
cc --plugin-dir ./plugins/instrument-with-logfire
```
