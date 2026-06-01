# pydantic-ai-harness

Extend [Pydantic AI](https://ai.pydantic.dev/) agents with batteries-included capabilities from
[pydantic-ai-harness](https://github.com/pydantic/pydantic-ai-harness).

## Features

- SKILL.md covering the harness capability model (`capabilities=[...]`)
- Reference docs for Code Mode — wrapping eligible tools into a single sandboxed `run_code` tool so the model orchestrates many tool calls in one Python execution

For the core framework (agents, tools, structured output, streaming, testing), use the `ai` plugin.

## Install

```bash
claude plugin marketplace add pydantic/skills
claude plugin install pydantic-ai-harness@pydantic-skills
```

## Codex

`pydantic-ai-harness` is not currently listed as a Codex plugin in the Pydantic marketplace. Codex users can
still use the standalone cross-agent skill at `skills/pydantic-ai-harness/`.
