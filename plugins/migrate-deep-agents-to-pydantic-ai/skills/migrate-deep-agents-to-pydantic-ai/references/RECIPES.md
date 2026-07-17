# Migration Recipes

Read only the sections routed from `SKILL.md`. Verify imports against the installed versions before adapting code. Every `model` below means the model selected and pinned by the target project.

## Contents

- [A minimal agent](#a-minimal-agent)
- [A composed long-horizon agent](#a-composed-long-horizon-agent)
- [Typed tools and dependencies](#typed-tools-and-dependencies)
- [Subagents](#subagents)
- [Dynamic workflows](#dynamic-workflows)
- [Context, memory, and history](#context-memory-and-history)
- [Filesystem, shell, and Code Mode](#filesystem-shell-and-code-mode)
- [Approvals and policy](#approvals-and-policy)
- [Streaming and mid-run messages](#streaming-and-mid-run-messages)
- [Persistence](#persistence)
- [Transitional LangChain tools](#transitional-langchain-tools)

## A minimal agent

Start with the agent loop and add only contract-backed behavior:

```python
from pydantic_ai import Agent

agent = Agent(
    model,
    instructions='Complete the request and report verifiable results.',
)
```

Capture the first provider request and tool roster before adding capabilities; this is the clean target baseline.

## A composed long-horizon agent

Start with the smallest capability set that satisfies the source contract:

```python
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai_harness import FileSystem, Shell
from pydantic_ai_harness.compaction import (
    ClearToolResults,
    DeduplicateFileReads,
    SummarizingCompaction,
    TieredCompaction,
)
from pydantic_ai_harness.context import RepoContext
from pydantic_ai_harness.overflowing_tool_output import OverflowingToolOutput
from pydantic_ai_harness.planning import Planning


def file_key(call):
    if call.tool_name != 'read_file' or not isinstance(call.args, dict):
        return None
    return call.args.get('path')


workspace = Path('.').resolve()
agent = Agent(
    model,
    instructions='Solve the task, verify the result, and report evidence.',
    capabilities=[
        # Only autoload repository instructions after establishing that this
        # workspace is trusted for system-level instruction injection.
        RepoContext(workspace_dir=workspace),
        Planning(),
        FileSystem(root_dir=workspace),
        Shell(
            cwd=workspace,
            allowed_commands=['git', 'python', 'pytest', 'ruff', 'rg'],
            denied_commands=[],  # Choose allowlist mode rather than the default denylist mode.
        ),
        OverflowingToolOutput(),
        TieredCompaction(
            tiers=[
                DeduplicateFileReads(file_key=file_key),
                ClearToolResults(max_tokens=1, keep_pairs=3),
                SummarizingCompaction(max_messages=1, keep_messages=20),
            ],
            target_tokens=100_000,
        ),
    ],
)
```

Adjust limits to the actual model and task. `FileSystem` protects a local root. `Shell` is useful process plumbing, not OS isolation.

## Typed tools and dependencies

Replace graph context lookups and global clients with one typed dependency object:

```python
from dataclasses import dataclass

import httpx
from pydantic_ai import Agent, ModelRetry, RunContext


@dataclass
class Deps:
    http: httpx.AsyncClient
    user_id: str
    database: 'Database'


agent = Agent(model, deps_type=Deps)


@agent.tool
async def lookup_customer(ctx: RunContext[Deps], email: str) -> dict:
    customer = await ctx.deps.database.customer_by_email(email)
    if customer is None:
        raise ModelRetry(f'No customer exists for {email!r}; verify the address.')
    return customer
```

Use `@agent.tool_plain` only when no deps, usage, messages, retry count, or run identity are needed. Keep authorization inputs in deps so the model cannot select another tenant in tool arguments.

For related functions, use a `FunctionToolset` and attach policies to the whole set.

## Subagents

Use `SubAgents` when the parent should inspect each delegation result before deciding what happens next:

```python
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness.subagents import SubAgent, SubAgents


researcher = Agent(
    model,
    deps_type=Deps,
    name='researcher',
    description='Researches one self-contained question and returns sourced findings.',
    instructions='Use primary sources. Return findings and URLs, not a polished report.',
    tools=[search, fetch],
)

orchestrator = Agent(
    model,
    deps_type=Deps,
    capabilities=[
        SubAgents(
            agents=[
                SubAgent(
                    researcher,
                    usage_limits=UsageLimits(request_limit=6),
                    timeout_seconds=180,
                    max_calls=3,
                )
            ],
            agent_folders=None,
            inherit_tools=False,
            forward_usage=True,
        )
    ],
)
```

Every task must be self-contained because the child does not see parent history. Harness `SubAgents` also does not reproduce Deep Agents graph-state handoff/merge: place intentional shared state behind deps, or build a typed delegation adapter with an explicit merge policy. Do not enable `inherit_tools` as a shortcut unless every inherited tool is appropriate for every child. Use `shared_capabilities` for behavior that must travel with children.

The built-in delegation tool returns `str(result.output)`. If a child uses a Pydantic output model, do not assume the parent receives schema-valid JSON. Return JSON text deliberately, write a custom adapter that serializes with `model_dump_json()`/`to_jsonable_python`, or use `DynamicWorkflow`; assert the exact parent-visible representation in tests.

An explicit child runs the model/settings it was constructed with; do not assume a parent run-level model override propagates. Disable disk discovery with `agent_folders=None` unless it is intentional, and spike model/profile routing for every explicit or disk child.

Set `contain_errors=True` only when a child infrastructure crash should become a bounded loud retry. Shared usage exhaustion and Pydantic AI control-flow signals still propagate.

## Dynamic workflows

Use `DynamicWorkflow` when fan-out, chaining, filtering, or voting is itself the work:

```python
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness.dynamic_workflow import DynamicWorkflow


class Finding(BaseModel):
    claim: str
    source_url: str
    confidence: float


researcher = Agent(
    model,
    name='researcher',
    description='Researches one question and returns one strongest sourced finding.',
    output_type=Finding,
    tools=[search, fetch],
)

orchestrator = Agent(
    model,
    capabilities=[
        DynamicWorkflow(
            agents=[researcher],
            max_agent_calls=9,
            sub_agent_usage_limits=UsageLimits(request_limit=5),
            resource_limits={'max_duration_secs': 30},
        )
    ],
)
```

Structured child outputs arrive inside workflow code as dictionaries. Instruct the model to use `await researcher(task='...')` and `asyncio.gather` for independent calls. With no printed text, the final expression returns directly. If the workflow both prints and returns a value, the tool returns `{'output': ..., 'result': ...}`. Prefer returning structured data rather than printing evidence.

Do not use this for background jobs: the tool call waits for all child runs. Do not give workflow children their own `DynamicWorkflow`; nested workflows are rejected.

Check the installed `inherit_model` behavior. A parent run-level model override may not reach workflow children, so capture the actual child provider request rather than inferring inheritance from the shared `model` variable in this example.

Use `defer_loading=True` with a stable `id` when the workflow is rare and its catalog would otherwise consume every prompt.

## Context, memory, and history

Choose by trust and lifecycle:

| Concern | Use | Why |
|---|---|---|
| Host-approved static `AGENTS.md` and repository instructions | `RepoContext` | The host must establish trust before constructing/enabling it; the capability does not make that decision. |
| Dynamic request context | typed deps plus dynamic instructions | Keeps identity and clients out of model-controlled arguments. |
| Model-written knowledge across runs | Harness `Memory` | Bounded notebook tools, namespaces, concurrency, and stores. |
| Continue a conversation | `message_history=` | Replays model messages; does not restore arbitrary application state. |
| Shrink long history | compaction capabilities | Applies explicit lossless/lossy policies while preserving tool pairs. |

Example tenant-scoped memory:

```python
from pydantic_ai_harness.memory import Memory, SqliteMemoryStore

memory = Memory(
    SqliteMemoryStore(database='agent-memory.db'),
    namespace=lambda ctx: ctx.deps.user_id,
    inject_memory=False,
)
```

`inject_memory=False` keeps prompts cache-stable and makes retrieval explicit. If automatic injection is enabled, remember that stored text is model-written, lower-trust content.

`RepoContext` injects discovered repository instruction files at system priority. In a cloned PR, customer repository, or attacker-controlled sandbox, disable instruction autoload unless files are allowlisted, signed, or otherwise trusted. Otherwise expose their contents as lower-trust context; backend authorization must still protect every action.

## Filesystem, shell, and Code Mode

### Local file access

```python
from pydantic_ai_harness import FileSystem

FileSystem(
    root_dir='./workspace',
    allowed_patterns=['*.py', '*.toml', 'tests/*'],
    denied_patterns=['.git/*'],
    protected_patterns=['.env', '*.pem', '*.key'],
    max_read_lines=2_000,
)
```

Map Deep Agents tool names in prompts and tests: Harness uses `list_directory`, `search_files`, `find_files`, `read_file`, `write_file`, and `edit_file`. Do not leave stale `ls`, `glob`, or `grep` instructions.

### Local commands

```python
import os

from pydantic_ai_harness import Shell

Shell(
    cwd='./workspace',
    allowed_commands=['git', 'pytest', 'ruff', 'python', 'rg'],
    denied_commands=[],  # Choose allowlist mode rather than the default denylist mode.
    denied_operators=['>', '>>'],
    default_timeout=60,
    env={'PATH': os.environ['PATH'], 'HOME': os.environ['HOME']},
)
```

Use a fixed environment when model-written commands must not inherit API keys. The command allowlist can be bypassed through an allowed interpreter; isolation belongs outside this capability.

### Batch safe tools with Code Mode

```python
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai_harness import CodeMode

read_tools = FunctionToolset(tools=[list_tables, describe_table, run_readonly_query]).with_metadata(code_mode=True)
agent = Agent(
    model,
    toolsets=[read_tools],
    capabilities=[CodeMode(tools={'code_mode': True})],
)
```

Use Code Mode when Python loops, filtering, aggregation, or `asyncio.gather` remove multiple model turns. Select only tools safe for model-written orchestration. Keep approval-required and deferred-execution tools native when an external pause/resume protocol is required. In a pinned Harness spike, folding a statically `requires_approval=True` tool into Code Mode executed its body without calling the external denial handler, while a tool body that explicitly raised `ApprovalRequired` did reach the handler. Treat this as installed-version behavior to re-test, not a stable guarantee. Route guarded tools through Code Mode only with an explicit deferred-call handler and tests proving the complete approve/deny/edit/resume contract.

## Approvals and policy

For a single sensitive tool:

```python
from pydantic_ai import Agent, DeferredToolRequests

agent = Agent(model, output_type=[str, DeferredToolRequests])


@agent.tool_plain(requires_approval=True)
async def publish_release(tag: str) -> str:
    ...
```

The host must persist `result.all_messages()`, collect a decision, and resume with `DeferredToolResults`. Approval is a protocol, not a blocking `input()` inside the tool.

Reauthorize edited arguments against current tenant, path, SQL, network, and environment policy before resuming. If the old Deep Agents flow persisted an interrupt together with arbitrary graph state, messages plus deferred results are not an equivalent checkpoint; persist the pending request and required application state or retain a durable orchestrator.

For a tool family, wrap a toolset with a predicate:

```python
def needs_approval(ctx, tool_def, args):
    return tool_def.name in {'write_file', 'run_command'} and ctx.deps.production


guarded = toolset.approval_required(needs_approval)
```

Keep path containment, SQL read-only enforcement, tenant authorization, and network allowlists inside tool implementations or their backends. Use prompt guidance only to help the model choose correctly.

## Streaming and mid-run messages

Use `event_stream_handler` for tool and progress events while `run()` completes normally:

```python
async def stream_handler(ctx, events):
    async for event in events:
        await ctx.deps.events.publish(ctx.run_id, event)


async def run_agent():
    return await agent.run(prompt, deps=deps, event_stream_handler=stream_handler)
```

For an authenticated follow-up arriving during a run, the application can drive `agent.iter()` and call `AgentRun.enqueue(...)`. A tool or capability can call `ctx.enqueue(...)`. Use priority `asap` for steering and `when_idle` for follow-up work.

Keep the external queue, deduplication, ordering, authorization, and retry policy in application code.

## Persistence

Use `StepPersistence` when you need an append-only event trail, provider-valid message snapshots, tool-effect records, and run lineage:

```python
from pydantic_ai_harness.step_persistence import SqliteStepStore, StepPersistence

step_store = SqliteStepStore(database='runs.db')
agent = Agent(
    model,
    capabilities=[StepPersistence(store=step_store, agent_name='worker')],
)
```

Use `conversation_id` across turns. Treat `run_id` as one `Agent.run` invocation. Before replaying side effects after a crash, inspect unresolved tool effects and use idempotency keys.

For graph-node resume, durable timers, long-running external jobs, or capability-state recovery, use a durable workflow integration or retain an application orchestrator. Do not claim `StepPersistence` supplies those guarantees.

## Transitional LangChain tools

Keep a large working LangChain tool family temporarily when rewriting it would mix framework migration with domain changes:

```python
from pydantic_ai import Agent
from pydantic_ai.ext.langchain import LangChainToolset

agent = Agent(model, toolsets=[LangChainToolset(sql_toolkit.get_tools())])
```

Add characterization tests first. Replace the adapter later with native functions/toolsets so schemas, errors, dependencies, and authorization become explicit Pydantic AI code.
