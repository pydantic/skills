---
name: building-pydantic-ai-agents
description: |
  This skill should be used when building AI agents with Pydantic AI — the Python agent framework
  for LLM-powered applications. Use when the user asks to "build an AI agent", "create an LLM app",
  "use pydantic ai", "add tools to an agent", "add thinking capability", "add web search capability",
  "test my agent", "stream agent output", "define agent from YAML", "delegate between agents",
  when code imports pydantic_ai, or when the user mentions PydanticAI/Pydantic AI in any coding context.
  Do not use when the user asks about the Pydantic validation library alone (pydantic/BaseModel without
  agents), other AI frameworks (LangChain, LlamaIndex, CrewAI), or general Python development.
license: MIT
compatibility: Requires Python 3.10+
metadata:
  version: "1.0.0"
  author: pydantic
---

# Pydantic AI Skill

Pydantic AI is a Python agent framework for building production-grade Generative AI applications.
This skill provides patterns, architecture guidance, and tested code examples for building applications with Pydantic AI.

## When to Use This Skill

Invoke this skill when:
- User asks to build an AI agent, create an LLM-powered app, or mentions Pydantic AI
- User wants to add tools, capabilities (thinking, web search), or structured output to an agent
- User asks to define agents from YAML/JSON specs or use template strings
- User wants to stream agent events, delegate between agents, or test agent behavior
- Code imports `pydantic_ai` or references Pydantic AI classes (`Agent`, `RunContext`, `Tool`)
- User asks about hooks, lifecycle interception, or agent observability with Logfire

Do **not** use this skill for:
- The Pydantic validation library alone (`pydantic`/`BaseModel` without agents)
- Other AI frameworks (LangChain, LlamaIndex, CrewAI, AutoGen)
- General Python development unrelated to AI agents

## Quick-Start Patterns

### Create a Basic Agent

```python
from pydantic_ai import Agent

agent = Agent(
    'anthropic:claude-sonnet-4-6',
    instructions='Be concise, reply with one sentence.',
)

result = agent.run_sync('Where does "hello world" come from?')
print(result.output)
"""
The first known use of "hello, world" was in a 1974 textbook about the C programming language.
"""
```

### Add Tools to an Agent

```python
import random

from pydantic_ai import Agent, RunContext

agent = Agent(
    'google-gla:gemini-3-flash-preview',
    deps_type=str,
    instructions=(
        "You're a dice game, you should roll the die and see if the number "
        "you get back matches the user's guess. If so, tell them they're a winner. "
        "Use the player's name in the response."
    ),
)


@agent.tool_plain
def roll_dice() -> str:
    """Roll a six-sided die and return the result."""
    return str(random.randint(1, 6))


@agent.tool
def get_player_name(ctx: RunContext[str]) -> str:
    """Get the player's name."""
    return ctx.deps


dice_result = agent.run_sync('My guess is 4', deps='Anne')
print(dice_result.output)
#> Congratulations Anne, you guessed correctly! You're a winner!
```

### Structured Output with Pydantic Models

```python
from pydantic import BaseModel

from pydantic_ai import Agent


class CityLocation(BaseModel):
    city: str
    country: str


agent = Agent('google-gla:gemini-3-flash-preview', output_type=CityLocation)
result = agent.run_sync('Where were the olympics held in 2012?')
print(result.output)
#> city='London' country='United Kingdom'
print(result.usage())
#> RunUsage(input_tokens=57, output_tokens=8, requests=1)
```

### Dependency Injection

```python
from datetime import date

from pydantic_ai import Agent, RunContext

agent = Agent(
    'openai:gpt-5.2',
    deps_type=str,
    instructions="Use the customer's name while replying to them.",
)


@agent.instructions
def add_the_users_name(ctx: RunContext[str]) -> str:
    return f"The user's name is {ctx.deps}."


@agent.instructions
def add_the_date() -> str:
    return f'The date is {date.today()}.'


result = agent.run_sync('What is the date?', deps='Frank')
print(result.output)
#> Hello Frank, the date today is 2032-01-02.
```

### Testing with TestModel

```python
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

my_agent = Agent('openai:gpt-5.2', instructions='...')


async def test_my_agent():
    """Unit test for my_agent, to be run by pytest."""
    m = TestModel()
    with my_agent.override(model=m):
        result = await my_agent.run('Testing my agent...')
        assert result.output == 'success (no tool calls)'
    assert m.last_model_request_parameters.function_tools == []
```

### Use Capabilities

Capabilities are reusable, composable units of agent behavior — bundling tools, hooks, instructions, and model settings.

```python
from pydantic_ai import Agent
from pydantic_ai.capabilities import Thinking, WebSearch

agent = Agent(
    'anthropic:claude-opus-4-6',
    instructions='You are a research assistant. Be thorough and cite sources.',
    capabilities=[
        Thinking(effort='high'),
        WebSearch(),
    ],
)
```

### Add Lifecycle Hooks

Use `Hooks` to intercept model requests, tool calls, and runs with decorators — no subclassing needed.

```python
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities.hooks import Hooks
from pydantic_ai.models import ModelRequestContext

hooks = Hooks()


@hooks.on.before_model_request
async def log_request(ctx: RunContext[None], request_context: ModelRequestContext) -> ModelRequestContext:
    print(f'Sending {len(request_context.messages)} messages')
    return request_context


agent = Agent('openai:gpt-5.2', capabilities=[hooks])
```

### Define Agent from YAML Spec

Use `Agent.from_file` to load agents from YAML or JSON — no Python agent construction code needed.

```python
from pydantic_ai import Agent

# agent.yaml:
# model: anthropic:claude-opus-4-6
# instructions: You are a helpful research assistant.
# capabilities:
#   - WebSearch
#   - Thinking:
#       effort: high

agent = Agent.from_file('agent.yaml')
```

## Task Routing Table

| I want to... | Documentation |
|---|---|
| Create or configure agents | [Agents](https://ai.pydantic.dev/agents/) |
| Bundle reusable behavior (tools, hooks, instructions) | [Capabilities](https://ai.pydantic.dev/capabilities/) |
| Intercept model requests, tool calls, or runs | [Hooks](https://ai.pydantic.dev/hooks/) |
| Define agents in YAML/JSON without Python code | [Agent Specs](https://ai.pydantic.dev/agent-spec/) |
| Use template strings in agent instructions | [Template Strings](https://ai.pydantic.dev/agent-spec/#template-strings) |
| Let my agent call external APIs or functions | [Tools](https://ai.pydantic.dev/tools/) |
| Organize or restrict which tools an agent can use | [Toolsets](https://ai.pydantic.dev/toolsets/) |
| Give my agent web search with automatic provider fallback | [WebSearch Capability](https://ai.pydantic.dev/capabilities/#web-search) |
| Give my agent URL fetching with automatic provider fallback | [WebFetch Capability](https://ai.pydantic.dev/capabilities/#web-fetch) |
| Give my agent web search or code execution (builtin tools) | [Built-in Tools](https://ai.pydantic.dev/builtin-tools/) |
| Search with DuckDuckGo/Tavily/Exa | [Common Tools](https://ai.pydantic.dev/common-tools/) |
| Ensure my agent returns data in a specific format | [Structured Output](https://ai.pydantic.dev/output/#structured-output) |
| Pass database connections, API clients, or config to tools | [Dependencies](https://ai.pydantic.dev/dependencies/) |
| Access usage stats, message history, or retry count in tools | [RunContext](https://ai.pydantic.dev/tools/) |
| Choose or configure models | [Models](https://ai.pydantic.dev/models/) |
| Automatically switch to backup model when primary fails | [Fallback Model](https://ai.pydantic.dev/models/#fallback-model) |
| Show real-time progress as my agent works | [Streaming Events and Final Output](https://ai.pydantic.dev/agents/#streaming-events-and-final-output) |
| Work with messages and multimedia | [Message History](https://ai.pydantic.dev/message-history/) |
| Reduce token costs by trimming or filtering conversation history | [Processing Message History](https://ai.pydantic.dev/message-history/#processing-message-history) |
| Keep long conversations manageable without losing context | [Summarize Old Messages](https://ai.pydantic.dev/message-history/#summarize-old-messages) |
| Use MCP servers | [MCP](https://ai.pydantic.dev/mcp/) |
| Build multi-step graphs | [Graph](https://ai.pydantic.dev/graph/) |
| Debug a failed agent run or see what went wrong | [Model Errors](https://ai.pydantic.dev/agents/#model-errors) |
| Make my agent resilient to temporary failures | [Retries](https://ai.pydantic.dev/retries/) |
| Understand why my agent made specific decisions | [Using Logfire](https://ai.pydantic.dev/logfire/#using-logfire) |
| Write deterministic tests for my agent | [Unit testing with TestModel](https://ai.pydantic.dev/testing/#unit-testing-with-testmodel) |
| Enable thinking/reasoning across any provider | [Thinking](https://ai.pydantic.dev/thinking/) · [Thinking Capability](https://ai.pydantic.dev/capabilities/#thinking) |
| Systematically verify my agent works correctly | [Evals](https://ai.pydantic.dev/evals/) |
| Use embeddings for RAG | [Embeddings](https://ai.pydantic.dev/embeddings/) |
| Use durable execution | [Durable Execution](https://ai.pydantic.dev/durable_execution/overview/) |
| Have one agent delegate tasks to another | [Agent Delegation](https://ai.pydantic.dev/multi-agent-applications/#agent-delegation) |
| Route requests to different agents based on intent | [Programmatic Agent Hand-off](https://ai.pydantic.dev/multi-agent-applications/#programmatic-agent-hand-off) |
| Require tool approval (human-in-the-loop) | [Deferred Tools](https://ai.pydantic.dev/deferred-tools/) |
| Use images, audio, video, or documents | [Input](https://ai.pydantic.dev/input/) |
| Use advanced tool features | [Advanced Tools](https://ai.pydantic.dev/tools-advanced/) |
| Validate or require approval before tool execution | [Advanced Tools](https://ai.pydantic.dev/tools-advanced/) |
| Call the model without using an agent | [Direct API](https://ai.pydantic.dev/direct/) |
| Expose agents as HTTP servers (A2A) | [A2A](https://ai.pydantic.dev/a2a/) |
| Handle network errors and rate limiting automatically | [Retries](https://ai.pydantic.dev/retries/) |
| Use LangChain or ACI.dev tools | [Third-Party Tools](https://ai.pydantic.dev/third-party-tools/) |
| Publish reusable agent extensions as packages | [Extensibility](https://ai.pydantic.dev/extensibility/) |
| Build custom toolsets, models, or agents | [Extensibility](https://ai.pydantic.dev/extensibility/) |
| Debug common issues | [Troubleshooting](https://ai.pydantic.dev/troubleshooting/) |
| Migrate from deprecated APIs | [Changelog](https://ai.pydantic.dev/changelog/) |
| See advanced real-world examples | [Examples](https://ai.pydantic.dev/examples/) |
| Look up an import path | [API Reference](https://ai.pydantic.dev/api/) |

## Architecture and Decisions

Load [Architecture and Decision Guide](./references/ARCHITECTURE.md) for detailed decision trees, comparison tables, and architecture overview:

| Topic | What it covers |
|---|---|
| Decision Trees | Tool registration, output modes, multi-agent patterns, capabilities, testing approaches, extensibility |
| Comparison Tables | Output modes, model provider prefixes, tool decorators, built-in capabilities, agent methods |
| Architecture Overview | Execution flow, generic types, construction patterns, lifecycle hooks, model string format |

**Quick reference — model string format:** `"provider:model-name"` (e.g., `"openai:gpt-5.2"`, `"anthropic:claude-sonnet-4-6"`, `"google-gla:gemini-3-pro-preview"`)

**Quick reference — key agent methods:** `run()`, `run_sync()`, `run_stream()`, `run_stream_sync()`, `run_stream_events()`, `iter()`

## Key Practices

- **Python 3.10+** compatibility required
- **Observability**: Pydantic AI has first-class integration with [Logfire](https://logfire.pydantic.dev/) for tracing agent runs, tool calls, and model requests. Add it with `logfire.instrument_pydantic_ai()`. For deeper HTTP-level visibility, `logfire.instrument_httpx(capture_all=True)` captures the exact payloads sent to model providers.
- **Testing**: Use `TestModel` for deterministic tests, `FunctionModel` for custom logic

## Common Gotchas

These are mistakes agents commonly make with Pydantic AI. Getting these wrong produces silent failures or confusing errors.

- **Removed parameter names**: Use `output_type` (not `result_type`) and `output_retries` (not `result_retries`) — the old names no longer exist. Use `toolsets` (not `mcp_servers`) — `mcp_servers` still works but is deprecated.
- **`instructions` vs `system_prompt`**: Both are valid Agent parameters with different behavior. `instructions` supports dynamic functions/callables and is excluded when explicit `message_history` is provided (re-injected by the agent each run). `system_prompt` is static strings only and persists in message history across subsequent requests. Prefer `instructions` for most use cases.
- **`@agent.tool` requires `RunContext` as first param**; `@agent.tool_plain` must **not** have it. Mixing these up causes runtime errors. Use `tool_plain` when you don't need deps, usage, or messages.
- **Model strings need the provider prefix**: `'openai:gpt-5.2'` not `'gpt-5.2'`. Without the prefix, Pydantic AI can't resolve the provider.
- **`TestModel` requires `agent.override()`**: Don't set `agent.model` directly. Always use the context manager: `with agent.override(model=TestModel()):`.
- **`str` in output_type allows plain text to end the run**: If your union includes `str` (or no `output_type` is set), the model can return plain text instead of structured output. Omit `str` from the union to force tool-based output.
- **Hook decorator names on `.on` don't repeat `on_`**: Use `hooks.on.run_error` and `hooks.on.model_request_error` — not `hooks.on.on_run_error`.
- **`history_processors` is plural**: The Agent parameter is `history_processors=[...]`, not `history_processor=`.
- **Prevent accidental API calls in tests**: Set `from pydantic_ai.models import ALLOW_MODEL_REQUESTS` then `ALLOW_MODEL_REQUESTS = False` globally in test setup to block real model calls outside `override()` blocks.

## Common Tasks

Load [Common Tasks Reference](./references/COMMON-TASKS.md) for detailed implementation guidance with code examples:

| Task | Section |
|---|---|
| Add capabilities (Thinking, WebSearch, etc.) | Add Capabilities to an Agent |
| Intercept model requests and tool calls | Intercept Agent Lifecycle with Hooks |
| Define agents from YAML/JSON config files | Define Agents Declaratively with Specs |
| Enable thinking/reasoning across providers | Enable Thinking Across Providers |
| Trim or filter conversation history | Manage Context Size |
| Stream events and show real-time progress | Show Real-Time Progress |
| Auto-switch providers on failure | Handle Provider Failures |
| Write deterministic tests | Test Agent Behavior |
| Delegate tasks between agents | Coordinate Multiple Agents |
| Instrument with Logfire for debugging | Debug and Validate Agent Behavior |
