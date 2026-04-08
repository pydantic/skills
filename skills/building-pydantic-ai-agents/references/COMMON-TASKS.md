# Common Tasks

Detailed implementation guidance with code examples for common Pydantic AI tasks.

## Contents

- [Add Capabilities to an Agent](#add-capabilities-to-an-agent)
- [Intercept Agent Lifecycle with Hooks](#intercept-agent-lifecycle-with-hooks)
- [Define Agents Declaratively with Specs](#define-agents-declaratively-with-specs)
- [Enable Thinking Across Providers](#enable-thinking-across-providers)
- [Use MCP Servers](#use-mcp-servers)
- [Search with DuckDuckGo, Tavily, or Exa](#search-with-duckduckgo-tavily-or-exa)
- [Require Tool Approval (Human in the Loop)](#require-tool-approval-human-in-the-loop)
- [Send Images, Audio, Video, or Documents to the Model](#send-images-audio-video-or-documents-to-the-model)
- [Manage Context Size](#manage-context-size)
- [Work with Message History](#work-with-message-history)
- [Show Real-Time Progress](#show-real-time-progress)
- [Handle Provider Failures](#handle-provider-failures)
- [Make an Agent Resilient with Retries](#make-an-agent-resilient-with-retries)
- [Debug a Failed Agent Run](#debug-a-failed-agent-run)
- [Test Agent Behavior](#test-agent-behavior)
- [Coordinate Multiple Agents](#coordinate-multiple-agents)
- [Build Multi-Step Workflows with Graphs](#build-multi-step-workflows-with-graphs)
- [Debug and Validate Agent Behavior](#debug-and-validate-agent-behavior)
- [Advanced and Less Common Features](#advanced-and-less-common-features)
- [Working with the Installed Pydantic AI Package](#working-with-the-installed-pydantic-ai-package)

## Add Capabilities to an Agent

Use capabilities to bundle reusable behavior. Multiple capabilities compose automatically.

```python
from pydantic_ai import Agent
from pydantic_ai.capabilities import Thinking, WebSearch

# Built-in capabilities: just pass instances
agent = Agent(
    'anthropic:claude-opus-4-6',
    capabilities=[
        Thinking(effort='high'),
        WebSearch(),
    ],
)
```

**WebSearch** auto-detects whether the model supports builtin web search. If so, it uses the native tool; otherwise, it falls back to a local implementation (e.g., DuckDuckGo). Same pattern applies to `WebFetch`, `ImageGeneration`, and `MCP`.

---

## Intercept Agent Lifecycle with Hooks

Use `Hooks` for lightweight lifecycle interception via decorators. For reusable behavior that combines hooks with tools/instructions, subclass `AbstractCapability` instead.

```python
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities.hooks import Hooks
from pydantic_ai.models import ModelRequestContext

hooks = Hooks()


@hooks.on.before_model_request
async def log_request(ctx: RunContext[None], request_context: ModelRequestContext) -> ModelRequestContext:
    print(f'Sending {len(request_context.messages)} messages')
    return request_context


@hooks.on.before_tool_execute(tools=['send_email'])
async def audit_tool(ctx, *, call, tool_def, args):
    print(f'Executing {call.tool_name}')
    return args


agent = Agent('openai:gpt-5.2', capabilities=[hooks])
```

**Hook types:** `before_run`/`after_run`, `run` (wrap), `run_error`, `before_node_run`/`after_node_run`, `node_run` (wrap), `node_run_error`, `before_model_request`/`after_model_request`, `model_request` (wrap), `model_request_error`, `before_tool_validate`/`after_tool_validate`, `tool_validate` (wrap), `tool_validate_error`, `before_tool_execute`/`after_tool_execute`, `tool_execute` (wrap), `tool_execute_error`, `prepare_tools`, `run_event_stream`, `event`.

---

## Define Agents Declaratively with Specs

Use YAML/JSON specs to separate agent configuration from application code. Specs support template strings rendered from dependencies at runtime.

```yaml
# agent.yaml
model: anthropic:claude-opus-4-6
instructions: "You are helping {{user_name}} with research."
capabilities:
  - WebSearch
  - Thinking:
      effort: high
model_settings:
  max_tokens: 8192
```

```python
from dataclasses import dataclass

from pydantic_ai import Agent


@dataclass
class UserContext:
    user_name: str


agent = Agent.from_file('agent.yaml', deps_type=UserContext)
result = agent.run_sync('Find recent papers on AI safety', deps=UserContext(user_name='Alice'))
```

**Capability spec syntax:** `'WebSearch'` (no args), `{'Thinking': {'effort': 'high'}}` (kwargs), `{'Thinking': 'high'}` (single arg).

---

## Enable Thinking Across Providers

Use the unified `Thinking` capability or `thinking` model setting for cross-provider reasoning support.

```python
from pydantic_ai import Agent
from pydantic_ai.capabilities import Thinking

# Via capability (recommended for spec compatibility)
agent = Agent('anthropic:claude-opus-4-6', capabilities=[Thinking(effort='high')])

# Via model_settings (equivalent)
agent = Agent('anthropic:claude-opus-4-6', model_settings={'thinking': 'high'})
```

**Effort levels:** `True` (default effort), `False` (disable), `'minimal'`, `'low'`, `'medium'`, `'high'`, `'xhigh'`. Automatically mapped to each provider's native format (Anthropic adaptive thinking, OpenAI reasoning_effort, Google thinking_level, etc.).

---

## Use MCP Servers

Attach an MCP server as a toolset on the Agent. Use `MCPServerStdio` for subprocess-based servers or `MCPServerStreamableHTTP` for HTTP-based ones.

```python
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

server = MCPServerStdio('python', args=['mcp_server.py'], timeout=10)
agent = Agent('openai:gpt-5.2', toolsets=[server])

async def main():
    result = await agent.run('What is the weather in Paris?')
    print(result.output)
```

**Gotcha:** Use `async with agent` (or `async with server`) for explicit lifecycle control. `MCPServerSSE` exists but is deprecated — prefer `MCPServerStreamableHTTP`.

---

## Search with DuckDuckGo, Tavily, or Exa

Use `pydantic_ai.common_tools` for search-engine tools. DuckDuckGo is free; Tavily and Exa require API keys. Distinct from the `WebSearch` capability — these are explicit tool functions.

```python
from pydantic_ai import Agent
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

agent = Agent(
    'openai:gpt-5.2',
    tools=[duckduckgo_search_tool()],
    instructions='Search DuckDuckGo for the given query and return the results.',
)

result = agent.run_sync(
    'Can you list the top five highest-grossing animated films of 2025?'
)
print(result.output)
```

**Install:** `uv add 'pydantic-ai-slim[duckduckgo]'` (or `[tavily]`/`[exa]`). For Tavily/Exa swap the import for `tavily_search_tool` / `ExaToolset`.

---

## Require Tool Approval (Human in the Loop)

Use deferred tools to pause execution until external approval is granted. Mark a tool with `requires_approval=True`, then resume the run by passing `DeferredToolResults` back.

```python
from pydantic_ai import (
    Agent,
    DeferredToolRequests,
    DeferredToolResults,
    ToolDenied,
)

agent = Agent('openai:gpt-5.2', output_type=[str, DeferredToolRequests])

@agent.tool_plain(requires_approval=True)
def delete_file(path: str) -> str:
    return f'File {path!r} deleted'

result = agent.run_sync('Delete __init__.py')
messages = result.all_messages()

assert isinstance(result.output, DeferredToolRequests)
results = DeferredToolResults()
for call in result.output.approvals:
    results.approvals[call.tool_call_id] = ToolDenied('Deleting files is not allowed')

result = agent.run_sync('Continue', message_history=messages, deferred_tool_results=results)
print(result.output)
```

**Gotcha:** `output_type` MUST include `DeferredToolRequests`. For conditional approval (only some calls need it), `raise ApprovalRequired(...)` from inside the tool instead of using `requires_approval=True`.

---

## Send Images, Audio, Video, or Documents to the Model

Pass multimodal content as a list mixing text with `ImageUrl`/`AudioUrl`/`VideoUrl`/`DocumentUrl` (URL-based) or `BinaryContent` (in-memory).

```python
from pydantic_ai import Agent, ImageUrl

agent = Agent(model='openai:gpt-5.2')
result = agent.run_sync(
    [
        'What company is this logo from?',
        ImageUrl(url='https://iili.io/3Hs4FMg.png'),
    ]
)
print(result.output)
```

**Gotcha:** Not all models support all input types — check provider documentation. `BinaryContent(data=..., media_type='image/png')` is the alternative for in-memory assets.

---

## Manage Context Size

Use `history_processors` to trim or filter messages before each model request.

```python
from pydantic_ai import Agent, ModelMessage


async def keep_recent(messages: list[ModelMessage]) -> list[ModelMessage]:
    return messages[-10:] if len(messages) > 10 else messages


agent = Agent('openai:gpt-5.2', history_processors=[keep_recent])
```

**Also use for:** Privacy filtering (remove PII), summarizing old messages, role-based access.

---

## Work with Message History

Pass `result.new_messages()` from one run as `message_history=` to the next to continue a conversation across runs.

```python
from pydantic_ai import Agent

agent = Agent('openai:gpt-5.2', instructions='Be a helpful assistant.')

result1 = agent.run_sync('Tell me a joke.')
print(result1.output)

result2 = agent.run_sync('Explain?', message_history=result1.new_messages())
print(result2.output)
```

**Gotcha:** `new_messages()` returns only the current run; `all_messages()` returns the full history. When `message_history=` is passed, no new system prompt is generated — the existing history is assumed to include one.

---

## Show Real-Time Progress

Use `event_stream_handler` with `run()` or `run_stream()` to receive events as they happen.

```python
from collections.abc import AsyncIterable

from pydantic_ai import Agent, AgentStreamEvent, FunctionToolCallEvent, RunContext

agent = Agent('openai:gpt-5.2')


async def stream_handler(ctx: RunContext, events: AsyncIterable[AgentStreamEvent]):
    async for event in events:
        if isinstance(event, FunctionToolCallEvent):
            print(f'Calling {event.part.tool_name}...')


async def main():
    await agent.run('Do the task', event_stream_handler=stream_handler)
```

**Also use for:** Logging, analytics, debugging, progress bars in UIs.

---

## Handle Provider Failures

Use `FallbackModel` to automatically switch providers on 4xx/5xx errors.

```python
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIChatModel

fallback = FallbackModel(
    OpenAIChatModel('gpt-5.2'),
    AnthropicModel('claude-sonnet-4-6'),
)
agent = Agent(fallback)
```

**Also use for:** Cost optimization (expensive → cheap), rate limit handling, regional failover.

---

## Make an Agent Resilient with Retries

Raise `ModelRetry` from inside a tool to ask the model to call it again with corrected arguments. Set per-tool `retries=N` to override the Agent default.

```python
from pydantic_ai import Agent, RunContext, ModelRetry

@agent.tool(retries=2)
def get_user_by_name(ctx: RunContext[DatabaseConn], name: str) -> int:
    user_id = ctx.deps.users.get(name=name)
    if user_id is None:
        raise ModelRetry(
            f'No user found with name {name!r}, remember to provide their full name'
        )
    return user_id
```

**Gotcha:** Default is 1 retry. When the limit is exceeded and `ModelRetry` keeps firing, the agent raises `UnexpectedModelBehavior`. Current attempt is on `ctx.retry`.

---

## Debug a Failed Agent Run

Wrap a run in `capture_run_messages()` and catch `UnexpectedModelBehavior` to inspect the full request/response history at the point of failure.

```python
from pydantic_ai import Agent, ModelRetry, UnexpectedModelBehavior, capture_run_messages

with capture_run_messages() as messages:
    try:
        result = agent.run_sync('Please get me the volume of a box with size 6.')
    except UnexpectedModelBehavior as e:
        print('messages:', messages)
```

**Gotcha:** Captured messages include retries and tool-call attempts. Distinct from Logfire — use Logfire for production tracing, this for in-process debugging.

---

## Test Agent Behavior

Use `TestModel` for fast deterministic tests; `FunctionModel` for custom response logic.

```python
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

agent = Agent('openai:gpt-5.2')

# TestModel: fast, auto-generates valid responses based on schema
with agent.override(model=TestModel()):
    result = agent.run_sync('test prompt')
    assert result.output == 'success (no tool calls)'
```

```python
from pydantic_ai import Agent, ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

agent = Agent('openai:gpt-5.2')


# FunctionModel: capture requests, return custom responses
def custom_model(messages, info):
    return ModelResponse(parts=[TextPart(content='mocked response')])


with agent.override(model=FunctionModel(custom_model)):
    result = agent.run_sync('test prompt')
```

**Also use for:** Capturing requests for assertions, simulating errors, testing retries.

---

## Coordinate Multiple Agents

Use **agent delegation** (via tools) when a child returns results to parent; **output functions** for permanent hand-offs.

```python
from pydantic_ai import Agent, RunContext

parent = Agent('openai:gpt-5.2')
researcher = Agent('openai:gpt-5.2', output_type=str)

@parent.tool
async def research(ctx: RunContext, topic: str) -> str:
    """Delegate research to specialist."""
    result = await researcher.run(f'Research: {topic}', usage=ctx.usage)
    return result.output
```

**Also use for:** Triage/routing, specialist hand-off, graph-based workflows.

---

## Build Multi-Step Workflows with Graphs

Use `pydantic_graph` (separate package, ships in the same monorepo) to define typed nodes and run them as a state machine. Outgoing edges are determined by `run()` return type annotations.

```python
from dataclasses import dataclass
from pydantic_graph import BaseNode, End, Graph, GraphRunContext

@dataclass
class FirstNode(BaseNode[None, None, int]):
    value: int

    async def run(self, ctx: GraphRunContext) -> 'SecondNode | End[int]':
        if self.value >= 5:
            return End(self.value)
        return SecondNode(self.value + 1)

@dataclass
class SecondNode(BaseNode):
    value: int

    async def run(self, ctx: GraphRunContext) -> FirstNode:
        return FirstNode(self.value)

graph = Graph(nodes=[FirstNode, SecondNode])
result = graph.run_sync(FirstNode(0))
```

**Gotcha:** `End[T]` terminates the graph with output of type `T`.

---

## Debug and Validate Agent Behavior

Instrument with Logfire to see exact model requests, tool calls, and validate LLM outputs. Each agent run becomes a parent trace with child spans for every tool call and LLM request.

```python
import logfire

logfire.configure()
logfire.instrument_pydantic_ai()

# All agent runs now traced — see tool calls, model requests, and outputs in Logfire dashboard
```

For full HTTP-level visibility into what's sent to model providers (invaluable for debugging tool schema errors or unexpected model behavior):

```python
logfire.instrument_httpx(capture_all=True)
```

**Use for:** Debugging unexpected behavior, validating tool schemas, understanding what's sent to providers, production monitoring.

---

## Advanced and Less Common Features

For features below, the offline reference is the relevant module in the locally-installed `pydantic_ai` package. Run `python -c "import pydantic_ai; print(pydantic_ai.__file__)"` to find the source root, then browse the listed module.

- **Embeddings for RAG** — `from pydantic_ai import Embedder` — `Embedder('openai:text-embedding-3-small')` exposes `embed_query()` for search queries and `embed_documents()` for content indexing.
- **Direct API** — `from pydantic_ai.direct import model_request_sync, model_request` — call a model without constructing an `Agent`. Sync or async.
- **A2A HTTP servers** — `agent.to_a2a()` returns an ASGI app implementing the A2A protocol. Run with uvicorn or any ASGI server.
- **Durable Execution (Temporal)** — `from pydantic_ai.durable_exec.temporal import TemporalAgent, PydanticAIWorkflow, PydanticAIPlugin` — wrap an agent with `TemporalAgent()` to preserve progress across transient failures. DBOS and Prefect have parallel modules.
- **LangChain tools** — `from pydantic_ai.ext.langchain import tool_from_langchain, LangChainToolset` — adapt individual tools or entire toolsets.
- **ACI.dev tools** — `from pydantic_ai.ext.aci import tool_from_aci, ACIToolset`
- **Custom toolsets / models / capabilities** — base classes: `AbstractToolset`/`WrapperToolset` from `pydantic_ai.toolsets`; `Model`/`WrapperModel` from `pydantic_ai.models`; `AbstractAgent`/`WrapperAgent` from `pydantic_ai.agent`; `AbstractCapability` from `pydantic_ai.capabilities`.
- **Evaluations (`pydantic_evals`)** — `from pydantic_evals import Case, Dataset` and `from pydantic_evals.evaluators import IsInstance, Evaluator, EvaluatorContext` — separate package, install with `pip install pydantic-evals`.

---

## Working with the Installed Pydantic AI Package

Useful when the offline reference doesn't cover a specific symbol or you want to read source for an advanced feature.

- **Find the source root:** `python -c "import pydantic_ai; print(pydantic_ai.__file__)"` — browse the package directory for type stubs, docstrings, and submodule layout.
- **Browse real-world examples:** `pip install pydantic-ai-examples`, then `python -c "import pydantic_ai_examples; print(pydantic_ai_examples.__file__)"`.
- **Read the changelog:** the source tree contains `docs/changelog.md`. On PyPI, version history is on the project page.
- **Install variants:** `pip install pydantic-ai` (full) or `pip install pydantic-ai-slim` with provider/feature extras like `[openai,duckduckgo,tavily]`.
