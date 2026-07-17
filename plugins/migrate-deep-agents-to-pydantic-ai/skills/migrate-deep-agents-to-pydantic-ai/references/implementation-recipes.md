# Implementation Recipes

Read only the recipe matching the selected target shape. These examples emphasize public Pydantic AI primitives. Check the installed Pydantic AI and Harness versions before copying imports.

## Contents

- [A typed vertical slice](#a-typed-vertical-slice)
- [Preserve an application entry point](#preserve-an-application-entry-point)
- [Translate a tool family](#translate-a-tool-family)
- [Typed child-agent delegation](#typed-child-agent-delegation)
- [Fixed fan-out and explicit workflows](#fixed-fan-out-and-explicit-workflows)
- [Plans and mutable state](#plans-and-mutable-state)
- [Files, artifacts, and sandboxes](#files-artifacts-and-sandboxes)
- [Background work](#background-work)
- [Approval and external execution](#approval-and-external-execution)
- [Streaming through an application event contract](#streaming-through-an-application-event-contract)
- [Incremental LangChain interop](#incremental-langchain-interop)
- [Harness capability selection](#harness-capability-selection)

## A typed vertical slice

Start with one agent, typed dependencies, a narrow tool, and a validated output:

```python
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext


class CustomerStore(Protocol):
    async def summary(self, tenant_id: str, customer_id: str) -> str: ...


@dataclass
class Deps:
    tenant_id: str
    customers: CustomerStore


class Answer(BaseModel):
    answer: str
    customer_id: str


agent = Agent(
    'openai:gpt-5.2',
    deps_type=Deps,
    output_type=Answer,
    instructions='Answer from approved customer records.',
)


@agent.tool
async def customer_summary(ctx: RunContext[Deps], customer_id: str) -> str:
    return await ctx.deps.customers.summary(ctx.deps.tenant_id, customer_id)
```

Put authentication and tenancy in the store as well as the tool. Add tools only after this slice has source/target contract tests.

## Preserve an application entry point

Callers may depend on more than the final text. Replace a Deep Agents-shaped response with an explicit application result rather than hiding fields in a loose dictionary:

```python
from dataclasses import dataclass
from pydantic_ai import ModelMessage


@dataclass
class AppResult:
    output: Answer
    new_messages: list[ModelMessage]


async def run_request(prompt: str, deps: Deps, history: list[ModelMessage]) -> AppResult:
    result = await agent.run(prompt, deps=deps, message_history=history)
    return AppResult(output=result.output, new_messages=result.new_messages())
```

Keep durable plans, artifacts, and domain state in their owning repositories and return typed references when callers need them.

## Translate a tool family

Use a toolset when several actions share policy or lifecycle. Add wrappers for filtering, preparation, or approval. Use a capability when instructions or hooks must travel with the toolset. See [pydantic-ai-architecture.md](pydantic-ai-architecture.md) for a minimal capability.

Migration order:

1. snapshot source names, descriptions, and JSON schemas;
2. port the underlying domain functions;
3. expose them through a toolset;
4. apply authorization, approval, timeouts, and result bounds;
5. compare model-visible schemas and failure behavior.

Raise `ModelRetry` only when the model can correct its arguments. Backend, network, and authorization failures should retain their real meaning.

## Typed child-agent delegation

An explicit parent tool makes the handoff and result contract visible:

```python
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext


class Finding(BaseModel):
    claim: str
    evidence: list[str]


researcher = Agent('openai:gpt-5.2', deps_type=Deps, output_type=Finding)
supervisor = Agent('openai:gpt-5.2', deps_type=Deps)


@supervisor.tool
async def research(ctx: RunContext[Deps], question: str) -> Finding:
    result = await researcher.run(
        question,
        deps=ctx.deps,
        usage=ctx.usage,
    )
    return result.output
```

Do not pass parent message history implicitly. If the child may update shared state, return a typed patch and apply it transactionally after success. Define conflict and sibling-order rules. Harness experimental `SubAgents` can be selected instead when its installed text/result, tools, deps, discovery, and budget contracts fit.

## Fixed fan-out and explicit workflows

For a known set of independent child calls, ordinary application code is clear and testable:

```python
import asyncio


async def research_all(questions: list[str], deps: Deps) -> list[Finding]:
    results = await asyncio.gather(
        *(researcher.run(question, deps=deps) for question in questions)
    )
    return [result.output for result in results]
```

Add a semaphore, per-child budgets, an application deadline, and an explicit partial-failure policy. Use model-selected parent tools when the model should adaptively choose the next child. Use `pydantic_graph` when transitions and typed workflow state are part of the domain. When the process must survive crashes, redeploys, timers, or external signals, select and test a Pydantic AI durable-execution integration such as Temporal, DBOS, or Prefect—or retain the source orchestrator during a staged migration.

## Plans and mutable state

Represent plan items with a Pydantic model and store them through a tenant-scoped repository in deps. Expose only the operations the agent needs, such as `replace_plan`, `update_item`, and `read_plan`. Decide deliberately whether one run can replace another run's plan.

Harness experimental `Planning` is an optional composition, not a synonym for Deep Agents `write_todos`. Inspect its installed schema and lifecycle first.

Use the same pattern for model-authored memory: a bounded application store plus narrow read/write/search tools. Keep trusted instructions separate from writable memory and define namespaces, retention, concurrency, and deletion in host code.

## Files, artifacts, and sandboxes

Choose by lifecycle:

| Need | Owner |
|---|---|
| deliberate local workspace files | Harness `FileSystem` |
| conversation/run-scoped virtual files | state or artifact repository in deps |
| durable generated artifacts | object/artifact service |
| commands inside an already isolated host | Harness `Shell` |
| remote execution boundary | sandbox client/service in deps plus narrow tools |

Never treat a path check or command allowlist as the isolation boundary. Test traversal, absolute paths, symlinks, hidden/protected files, environment leakage, timeouts, reconnect, and cleanup.

## Background work

Keep queues and workers outside the agent. A focused toolset should expose:

- `start_task(kind, input, operation_key) -> task_id`;
- `list_tasks()` scoped to the authenticated tenant/conversation;
- `check_task(task_id)`;
- `update_task(task_id, message)` when supported;
- `cancel_task(task_id)`.

The application owns durable job state, idempotency, retries, credentials, worker leases, cancellation, and result delivery. A live parent may receive an authenticated completion through `enqueue()`; otherwise consume it on a later run.

## Approval and external execution

Use Pydantic AI deferred tools when a tool requires approval or must run elsewhere. Persist the pending request and authorization context before returning control, then resume with the corresponding deferred result. Test approve, deny, edited arguments, stale decisions, crash, replay, and side-effect idempotency.

The public stop-and-resume shape is:

```python
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, ToolDenied

agent = Agent('openai:gpt-5.2', output_type=[str, DeferredToolRequests])


@agent.tool_plain(requires_approval=True)
def publish_report(report_id: str) -> str:
    return f'published {report_id}'


first = agent.run_sync('Publish report r-7')
assert isinstance(first.output, DeferredToolRequests)

decisions = DeferredToolResults()
for call in first.output.approvals:
    decisions.approvals[call.tool_call_id] = ToolDenied('Needs another review')

resumed = agent.run_sync(
    'Continue',
    message_history=first.all_messages(),
    deferred_tool_results=decisions,
)
```

The host must persist and reauthorize the request; the Pydantic AI messages carry the protocol, not the application's durable decision record.

Keep approval-required tools outside Code Mode unless an installed-version test proves the complete defer/resume contract. Select Code Mode tools from an explicit safe allowlist or metadata tag.

## Streaming through an application event contract

Use `event_stream_handler` when callers need a stable application stream while `agent.run()` owns the complete run. The handler receives `RunContext` plus an async iterable of Pydantic AI events. Convert each event into the application's versioned event schema before publishing it. Use `run_stream_events()` or `iter()` only when the caller should drive the event/run lifecycle directly. Test lineage, ordering, backpressure, redaction, child/tool events, and final-output timing against the locked version.

## Incremental LangChain interop

For a first vertical slice, a LangChain tool family can remain behind the supported Pydantic AI adapter/toolset if the locked versions provide one. Treat this as a migration seam:

- smoke-test every converted schema;
- test sync/async and exception behavior;
- keep typed deps, authorization, and approval outside hidden LangChain globals;
- replace the adapter when it obscures contracts the application must control.

## Harness capability selection

Harness is a library of compositions built on Pydantic AI. Capabilities may be stable, experimental, moved, or absent in a given revision.

Before selecting one:

1. inspect the installed public exports and README;
2. confirm the capability owns the correct lifecycle;
3. pin experimental APIs deliberately;
4. add import, construction, schema, lifecycle, and concurrency tests;
5. build a focused capability or application service when the required contract differs.

A useful inspection sequence is `python -m pip show pydantic-ai pydantic-ai-harness`, followed by reading the installed package's public `__init__.py` and capability README. Never copy private implementation modules into the migrated application.

This is ordinary extension through Pydantic AI's abstractions, not a framework escape hatch.
