# Pydantic Skills

Official [Claude Code](https://claude.com/claude-code) plugin marketplace for the Pydantic ecosystem.

## Plugins

| Plugin | Description | Commands |
|--------|-------------|----------|
| [logfire](plugins/logfire/) | Add Logfire observability to Python apps | `/instrument`, `/debug`, `/query` |

## Install

Add this marketplace to Claude Code:

```
claude plugin marketplace add pydantic/skills
```

Then install a plugin:

```
claude plugin install logfire@pydantic-skills
```

## Cross-Agent Skills

The `skills/` directory contains standalone SKILL.md files compatible with 30+ agents via the [agentskills.io](https://agentskills.io) standard - including Codex, Cursor, Gemini CLI, and Claude Code.

## Development

Test a plugin locally:

```bash
claude --plugin-dir ./plugins/logfire
```
