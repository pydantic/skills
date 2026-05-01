# Pydantic Skills

Official [Claude Code](https://claude.com/claude-code) plugin marketplace for the Pydantic ecosystem.

## Plugins

| Plugin | Description | Commands |
|--------|-------------|----------|
| [logfire](plugins/logfire/) | Add Logfire observability to Python apps | `/instrument`, `/debug` |
| [ai](plugins/ai/) | Build AI agents with Pydantic AI | — |

## Install

Add this marketplace to Claude Code:

```
claude plugin marketplace add pydantic/skills
```

Then install a plugin:

```
claude plugin install logfire@pydantic-skills
claude plugin install ai@pydantic-skills
```

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

Validate Agent Skills metadata and local/plugin sync:

```bash
uvx --from skills-ref agentskills validate ./skills/building-pydantic-ai-agents
uvx --from skills-ref agentskills validate ./skills/logfire-instrumentation
./scripts/check-skill-sync.sh
```
