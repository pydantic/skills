# Pydantic Skills

Official plugin marketplace for the Pydantic ecosystem — supporting [Claude Code](https://claude.com/claude-code) and [Cursor](https://cursor.com).

## Plugins

### Claude Code

| Plugin | Description | Commands |
|--------|-------------|----------|
| [logfire](plugins/logfire/) | Add Logfire observability to Python apps | `/instrument`, `/debug` |
| [ai](plugins/ai/) | Build AI agents with Pydantic AI | — |

### Cursor

| Plugin | Description | Commands |
|--------|-------------|----------|
| [pydantic](.cursor-plugin/) | Pydantic validation, AI agents, and Logfire observability | `/debug-validation-error`, `/add-pydantic-model`, `/add-agent-tool`, `/instrument-logfire`, `/debug-logfire-trace` |

The Cursor plugin also includes [rules](rules/) (`.mdc` files) for Pydantic validation, Pydantic AI, and Logfire, plus the [Logfire MCP server](plugins/logfire/.mcp.json) pre-configured.

## Install

### Claude Code

Add this marketplace to Claude Code:

```
claude plugin marketplace add pydantic/skills
```

Then install a plugin:

```
claude plugin install logfire@pydantic-skills
claude plugin install ai@pydantic-skills
```

### Cursor

Install from the [Cursor Marketplace](https://cursor.com/marketplace):

```
cursor plugin install pydantic
```

## Cross-Agent Skills

The `skills/` directory contains standalone SKILL.md files compatible with 30+ agents via the [agentskills.io](https://agentskills.io) standard — including Codex, Cursor, Gemini CLI, and Claude Code.

| Skill | Description |
|-------|-------------|
| [logfire-instrumentation](skills/logfire-instrumentation/) | Add Logfire observability to Python, JS/TS, and Rust apps |
| [building-pydantic-ai-agents](skills/building-pydantic-ai-agents/) | Build LLM-powered agents with Pydantic AI — tools, capabilities, streaming, testing |
| [pydantic-validation](skills/pydantic-validation/) | Pydantic v2 models, validators, serialization, and schema generation |

## Development

Test a plugin locally:

```bash
# Claude Code
claude --plugin-dir ./plugins/logfire

# Cursor — open the repo root as a Cursor project; the .cursor-plugin/ manifest is auto-detected
```
