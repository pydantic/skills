# Pydantic AI Architecture for Deep Agents Migrations

Pydantic AI is a set of typed, composable primitives rather than a fixed agent harness. Build the smallest agent loop that fits the task, then add reusable behavior through toolsets, capabilities, hooks, graphs, or application services.

Pydantic AI Harness is optional. It supplies higher-level capabilities built on those primitives; use them when their contracts fit the application, and extend the same abstractions when the application needs a different shape.

## Contents

- [Core mental model](#core-mental-model)
- [Where Harness fits](#where-harness-fits)
- [Choose the owner](#choose-the-owner)
- [Separate state by lifecycle](#separate-state-by-lifecycle)
- [Extend through strong abstractions](#extend-through-strong-abstractions)
- [Common migration compositions](#common-migration-compositions)
- [Safety and version discipline](#safety-and-version-discipline)

## Core mental model

| Primitive | Owns | Does not own |
|---|---|---|
| `Agent` | model loop, instructions, model settings, output contract | durable business state or deployment orchestration |
| `deps_type` + `RunContext` | typed access to clients, stores, identity, configuration, usage | checkpointed mutable graph state |
| Pydantic output types | validation and typed final results | application persistence |
| tools and toolsets | model-facing actions, schemas, retries, timeouts, approval policy | hidden authorization outside the tool/backend boundary |
| capabilities | reusable instructions, tools, hooks, model settings, deferred loading | queues, leases, or cross-run mutable state unless backed by deps |
| `Hooks` | focused lifecycle observation or transformation | broad reusable behavior that also needs tools/instructions |
| `ProcessHistory` capability | provider-visible message shaping and compaction | arbitrary workflow-state recovery |
| deferred tools | pause, external execution, approval, and resume protocol | durable storage of the pending decision by themselves |
| `pydantic_graph` | explicit typed state machines and transitions | production durability unless paired with a durable runtime |
| application services | tenancy, durable state, queues, sandboxes, artifacts, credentials | model reasoning |

This separation is the main migration advantage: state, policy, tools, and orchestration become explicit rather than arriving as one implicit constructor bundle.

## Where Harness fits

Harness is an optional, version-sensitive library of useful Pydantic AI compositions. In the revision reviewed while authoring this skill (`v0.5.0-6-g1ad638f`), stable capability classes include `CodeMode`, `FileSystem`, `ManagedPrompt`, and `Shell`. Repository context, planning, delegation, compaction, overflow handling, and step persistence are available under `pydantic_ai_harness.experimental.*`; experimental capabilities may change or disappear without deprecation. Other concepts mentioned by a source project may not exist in the installed Harness revision at all.

Treat each Harness capability as an optional implementation choice:

1. Start with the Pydantic AI core primitive that owns the concern.
2. Select a Harness capability when its observable behavior and lifecycle match the contract.
3. Configure or wrap it when only policy, naming, or presentation differs.
4. Build a focused capability when the behavior is reusable but application-specific.
5. Keep the concern in an application service when it owns durability, security, identity, scheduling, or remote resources.

Harness accelerates composition; it does not replace the application runtime or limit how Pydantic AI can be extended.

## Choose the owner

| Requirement | First choice | Move outward when |
|---|---|---|
| one action | `@agent.tool` / `tool_plain` | several tools need shared policy or lifecycle |
| related action family | `FunctionToolset` and wrappers | instructions/hooks must travel with the tools |
| reusable agent behavior | built-in or custom capability | it owns cross-run state or external scheduling |
| lifecycle observation | `Hooks` | behavior also contributes tools/instructions |
| typed result | Pydantic `output_type` | downstream storage or workflow transitions are required |
| conversation continuation | messages + `message_history` | arbitrary state or node recovery is required |
| explicit multi-step control | application code or `pydantic_graph` | crash-safe timers, signals, and replay are required |
| background work | application queue/worker + narrow tools | never place queue ownership inside the capability |
| remote execution | sandbox client in deps + narrow tools | isolation always remains in the sandbox service |
| approval | deferred tools and durable host decision | the application must persist and authorize resume |

## Separate state by lifecycle

Classify every Deep Agents state field before writing target code:

| State kind | Pydantic AI shape |
|---|---|
| live clients, authenticated identity, configuration | typed deps |
| provider conversation | messages and `message_history` |
| one explicit state-machine execution | `pydantic_graph` state |
| durable application/domain state | transactional repository in deps |
| model-authored memory | bounded tenant-scoped application memory service |
| artifacts and virtual files | artifact/object/state store with model-facing tools |
| external jobs | queue and task store |
| remote workspace | sandbox service and lease identifier |
| pending approval | durable request/decision record plus deferred-tool messages |

Do not use one store merely because Deep Agents exposed these concerns through one graph-state dictionary or file-like namespace.

## Extend through strong abstractions

For ordinary bundles of instructions, tools, and toolsets, start with the public `Capability` convenience class. Keep external resources in typed deps:

```python
from dataclasses import dataclass
from typing import Protocol

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Capability


class RecordStore(Protocol):
    async def lookup(self, tenant_id: str, key: str) -> str | None: ...


@dataclass
class AppDeps:
    tenant_id: str
    records: RecordStore


project_records = Capability[AppDeps](
    id='project-records',
    description='Read approved project records when the task needs them.',
    instructions='Use project records only when they are relevant to the request.',
    defer_loading=True,
)


@project_records.tool
async def read_record(ctx: RunContext[AppDeps], key: str) -> str:
    value = await ctx.deps.records.lookup(ctx.deps.tenant_id, key)
    return value or 'Record not found.'
```

Design rules:

- Use a stable explicit ID and description for deferred capabilities.
- Keep capability instances stateless across runs, or isolate run state with `for_run()`.
- Put hard authorization in the backend/service as well as model-facing policy.
- Use `ModelRetry` only for model-correctable choices; keep infrastructure failures loud.
- Opt out of spec serialization for live clients, callables, or other non-reconstructable state.
- Pin and test public hook/toolset APIs used by custom capabilities.
- Never import `pydantic_ai._*`, private Harness modules, or copy Harness internals into application code. Consume public module exports and pin a tested Pydantic AI/Harness pair.

Subclass `AbstractCapability` only when the composition needs hooks, model settings, native tools, wrapper toolsets, or custom per-run behavior.

## Common migration compositions

### Skills

Represent a small stable skill as a deferred capability. For a large or user-editable catalog, parse and validate files in host code, then expose a bounded `load_skill(name)` tool over trusted records. Keep path resolution, precedence, size limits, trust, and authorization outside model arguments.

### Synchronous delegation

Make the parent tool call a typed child `Agent`. Forward shared usage when budgets must be global. Return the child's typed result directly or serialize it deliberately. If children update shared state, define an explicit transactional merge contract rather than sharing mutable dictionaries.

### Background work

Keep the worker and durable queue in the application. Expose only start/list/check/update/cancel tools through a toolset or capability. Scope every operation by tenant and conversation, use replay-stable operation keys, bound worker retries/cost, and make cancellation observable.

### Virtual files and artifacts

Choose storage from the required lifecycle. Use Harness `FileSystem` for deliberate host-workspace files; use a state or artifact service for conversation-scoped virtual files. Preserve one virtual namespace only when consumers actually depend on it.

### Remote sandboxes

Put the authenticated sandbox client and workspace ID in deps. Expose narrow read/edit/run tools. The remote service owns containment, process/network isolation, credentials, reconnect, timeouts, and cleanup; tool filters are not the isolation boundary.

### Middleware and policy

Translate in this order: agent/deps configuration → tool feature → toolset wrapper → built-in capability → `Hooks` → custom capability → application orchestration. Put ordered authorization in a pure policy function and enforce the final decision at the backend boundary.

### Approval and Code Mode

Use Pydantic AI deferred tools for approval and persist the pending request before returning control. Keep approval-required tools outside Code Mode unless the installed-version test proves the complete pause/resume path. With metadata-based Code Mode selection, admit only explicitly tagged safe tools rather than selecting every tool.

## Safety and version discipline

- Inspect the lockfile and public imports before writing recipes; Harness paths can move, including under `experimental`.
- Prefer Pydantic AI public APIs and official docs; avoid `pydantic_ai._*` and private Harness modules.
- Test the model-visible tool schema, not only Python import success.
- Treat an installed Harness experimental step-persistence capability as event/message-step persistence, not arbitrary graph-state recovery.
- Treat local shell filtering as process plumbing, not a security sandbox.
- Re-run contract tests after Pydantic AI, Harness, provider, or model upgrades.

See [implementation-recipes.md](implementation-recipes.md) for implementation examples and [validation.md](validation.md) for contract tests.
