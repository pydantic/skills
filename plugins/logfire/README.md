# logfire

Add [Logfire](https://logfire.pydantic.dev/) observability to Python applications.

## Features

- `/instrument` - detect frameworks and add Logfire instrumentation
- `/debug` - investigate errors using Logfire traces via MCP
- `/query` - query traces, logs, and metrics interactively or add query capabilities to code
- SKILL.md with core Logfire patterns (configure, instrument, structured logging, AI/LLM instrumentation)
- MCP server for querying Logfire data (`find_exceptions_in_file`, `arbitrary_query`)

## Install

```
claude plugin marketplace add pydantic/skills
claude plugin install logfire@pydantic-skills
```

## MCP

The Logfire MCP server is configured automatically when you install the plugin (US region). EU users can switch by running:

```
claude mcp add logfire --transport http https://logfire-eu.pydantic.dev/mcp
```
