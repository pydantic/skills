# Pydantic AI and Harness Composition Patterns

Use a custom capability when a missing Deep Agents behavior combines tools, instructions, hooks, or model settings and should be reusable. Use a plain tool or `Hooks` when that is all the behavior needs.

## Contents

- [Capability design rules](#capability-design-rules)
- [Turn one skill into a deferred capability](#turn-one-skill-into-a-deferred-capability)
- [Load a directory of existing skills](#load-a-directory-of-existing-skills)
- [Build background subagents](#build-background-subagents)
- [Wrap a remote sandbox](#wrap-a-remote-sandbox)
- [Translate middleware](#translate-middleware)
- [Implement ordered policy](#implement-ordered-policy)

## Capability design rules

1. Keep host resources in typed deps, not on model-facing arguments.
2. Keep capability instances stateless across runs, or implement `for_run()` to return isolated per-run state.
3. Use a dataclass so `id`, `description`, and `defer_loading` initialize consistently.
4. Give every deferred capability a stable explicit ID and a routing description.
5. Put related tools in one toolset. Use wrappers/metadata rather than copying policy into every tool.
6. State security and durability boundaries in code and tests.
7. Make errors intentional: `ModelRetry` for a correctable model choice, approval/defer signals for control flow, and normal exceptions for broken infrastructure or invariants.
8. `AbstractCapability` defaults its serialization name to the class name. Explicitly override `get_serialization_name()` to return `None` for live agents, clients, callables, or non-spec state. Opt into spec reconstruction only when constructor data and `from_spec` behavior are safe and meaningful.
9. Pin and test against the installed Pydantic AI and Harness versions. Hook signatures are an API, not pseudocode.

## Turn one skill into a deferred capability

This is the cleanest translation when a Deep Agents skill is stable and belongs in code:

```python
from dataclasses import dataclass

from pydantic_ai.capabilities import AbstractCapability


@dataclass
class QueryWritingSkill(AbstractCapability[None]):
    id: str = 'query-writing'
    description: str | None = 'Use for read-only SQL queries, joins, aggregation, and query recovery.'
    defer_loading: bool = True

    def get_instructions(self) -> str:
        return '''
Write read-only SQL only. Inspect relevant schemas before joining tables.
Select explicit columns, apply a bounded LIMIT, validate the query, then execute it.
If execution fails, use the concrete database error to correct the query.
'''.strip()
```

Attach it with `capabilities=[QueryWritingSkill()]`. Before activation, the model sees only the ID and description. After `load_capability`, its instructions and tools become active.

If the skill owns domain tools, return a `FunctionToolset` from `get_toolset()`. If it needs audits or request changes, implement the corresponding capability hook. This preserves the main advantage of Agent Skills—progressive disclosure—without treating Markdown as magic runtime state.

## Load a directory of existing skills

For a large or user-editable corpus, keep a single bounded catalog. Parse and validate files in host code, then pass trusted records to the capability. This example deliberately does not accept paths from the model:

The tested copyable implementation is `assets/migration_patterns/application_boundaries.py::SkillCatalog`; an offline spike confirmed that only host-supplied records can be loaded.

```python
from dataclasses import dataclass, field

from pydantic_ai import ModelRetry
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset


@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    body: str


@dataclass
class SkillCatalog(AbstractCapability[None]):
    id: str = 'project-skills'
    description: str | None = 'Load a project workflow when its description matches the task.'
    defer_loading: bool = False
    skills: dict[str, SkillRecord] = field(default_factory=dict)

    def get_instructions(self) -> str:
        listing = '\n'.join(f'- {skill.name}: {skill.description}' for skill in self.skills.values())
        return f'Load a skill before performing a matching workflow. Available skills:\n{listing}'

    def get_toolset(self) -> FunctionToolset[None]:
        skills = self.skills
        tools = FunctionToolset[None](id='project-skill-loader')

        @tools.tool_plain
        def load_skill(name: str) -> str:
            """Load one project skill by its exact catalog name."""
            try:
                return skills[name].body
            except KeyError:
                available = ', '.join(sorted(skills))
                raise ModelRetry(f'Unknown skill {name!r}. Available: {available}') from None

        return tools
```

Production requirements:

- parse frontmatter before constructing the agent;
- validate names and maximum file/body sizes;
- resolve symlinks and ensure every file remains beneath the approved root;
- bound the number of listed skills and description length;
- define project/user precedence explicitly;
- treat model-editable skill text as untrusted user-role context when the trust model requires it;
- cache parsed records by content hash, not by path alone;
- add tool/capability activation if a skill also grants actions.

Use `RepoContext` to inventory where skills live, not as the skill runtime itself.

## Build background subagents

Harness `SubAgents` and `DynamicWorkflow` wait for the child. To reproduce Deep Agents async subagents, put job state in an application-owned store/queue and expose a small capability:

The tested copyable implementation is `assets/migration_patterns/application_boundaries.py::BackgroundSubagents`; an offline spike confirmed propagation of tenant, conversation, run, tool-call, and operation identity.

```python
from dataclasses import dataclass
from typing import Protocol

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset


class TaskQueue(Protocol):
    async def start(
        self,
        *,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        operation_key: str,
        parent_run_id: str,
        agent_name: str,
        task: str,
    ) -> str: ...
    async def list(
        self, *, tenant_id: str, user_id: str, conversation_id: str, status: str | None
    ) -> list[dict]: ...
    async def status(self, *, tenant_id: str, user_id: str, conversation_id: str, task_id: str) -> dict: ...
    async def update(
        self, *, tenant_id: str, user_id: str, conversation_id: str, task_id: str, instruction: str
    ) -> dict: ...
    async def cancel(self, *, tenant_id: str, user_id: str, conversation_id: str, task_id: str) -> dict: ...


class SideEffectLedger(Protocol):
    async def key_for_background_start(
        self,
        *,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        run_id: str,
        tool_call_id: str,
        agent_name: str,
        task: str,
    ) -> str:
        """Return a replay-stable key for this semantic start operation."""
        ...


@dataclass
class AppDeps:
    tasks: TaskQueue
    side_effects: SideEffectLedger
    tenant_id: str
    user_id: str
    conversation_id: str


@dataclass
class BackgroundSubagents(AbstractCapability[AppDeps]):
    id: str = 'background-subagents'
    description: str | None = 'Run long independent work in the background and check it later.'
    defer_loading: bool = True

    def get_instructions(self) -> str:
        return 'Start background work only when the parent can continue independently. Keep every returned task ID.'

    def get_toolset(self) -> FunctionToolset[AppDeps]:
        tools = FunctionToolset[AppDeps](id='background-subagent-tools')

        @tools.tool
        async def start_background_task(ctx: RunContext[AppDeps], agent_name: str, task: str) -> str:
            """Start a self-contained task and return its durable task ID."""
            if ctx.run_id is None or ctx.tool_call_id is None:
                raise RuntimeError('Background start requires run and tool-call identity')
            operation_key = await ctx.deps.side_effects.key_for_background_start(
                tenant_id=ctx.deps.tenant_id,
                user_id=ctx.deps.user_id,
                conversation_id=ctx.deps.conversation_id,
                run_id=ctx.run_id,
                tool_call_id=ctx.tool_call_id,
                agent_name=agent_name,
                task=task,
            )
            return await ctx.deps.tasks.start(
                tenant_id=ctx.deps.tenant_id,
                user_id=ctx.deps.user_id,
                conversation_id=ctx.deps.conversation_id,
                operation_key=operation_key,
                parent_run_id=ctx.run_id,
                agent_name=agent_name,
                task=task,
            )

        @tools.tool
        async def list_background_tasks(ctx: RunContext[AppDeps], status: str | None = None) -> list[dict]:
            """List this conversation's background tasks, optionally filtered by status."""
            return await ctx.deps.tasks.list(
                tenant_id=ctx.deps.tenant_id,
                user_id=ctx.deps.user_id,
                conversation_id=ctx.deps.conversation_id,
                status=status,
            )

        @tools.tool
        async def check_background_task(ctx: RunContext[AppDeps], task_id: str) -> dict:
            """Return status and result metadata for a background task."""
            return await ctx.deps.tasks.status(
                tenant_id=ctx.deps.tenant_id,
                user_id=ctx.deps.user_id,
                conversation_id=ctx.deps.conversation_id,
                task_id=task_id,
            )

        @tools.tool
        async def update_background_task(ctx: RunContext[AppDeps], task_id: str, instruction: str) -> dict:
            """Steer a running background task."""
            return await ctx.deps.tasks.update(
                tenant_id=ctx.deps.tenant_id,
                user_id=ctx.deps.user_id,
                conversation_id=ctx.deps.conversation_id,
                task_id=task_id,
                instruction=instruction,
            )

        @tools.tool
        async def cancel_background_task(ctx: RunContext[AppDeps], task_id: str) -> dict:
            """Request cancellation of a running background task."""
            return await ctx.deps.tasks.cancel(
                tenant_id=ctx.deps.tenant_id,
                user_id=ctx.deps.user_id,
                conversation_id=ctx.deps.conversation_id,
                task_id=task_id,
            )

        return tools

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return None
```

The worker, not the capability, chooses the child agent and credentials from an allowlisted registry. The queue must authorize every operation against tenant, user, and conversation scope, and deduplicate by `operation_key`. A raw `run_id:tool_call_id` key is not durable across a new `Agent.run`; the application ledger must preserve or reconcile semantic start identity across crash/replay. Store parent/conversation lineage, bound retries and cost, and make cancellation observable rather than pretending it is instantaneous.

To surface completion in a live run, the host may call `AgentRun.enqueue()` after authenticating the event. Otherwise, deliver it on the next request or through the product's notification layer.

## Wrap a remote sandbox

Treat a sandbox as a host service. The capability only exposes its narrow model-facing API:

The tested copyable implementation is `assets/migration_patterns/application_boundaries.py::RemoteSandbox`; an offline spike confirmed that model-facing tools route through the external client boundary.

```python
from dataclasses import dataclass
from typing import Protocol

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset


class SandboxClient(Protocol):
    async def read(self, *, path: str, offset: int, limit: int) -> str: ...
    async def edit(self, *, path: str, old_text: str, new_text: str) -> str: ...
    async def run(self, *, command: str, timeout: int) -> dict: ...


@dataclass
class SandboxDeps:
    sandbox: SandboxClient
    user_id: str


@dataclass
class SandboxTools(AbstractCapability[SandboxDeps]):
    id: str = 'workspace-sandbox'
    description: str | None = 'Read, edit, and test code in the isolated task workspace.'
    defer_loading: bool = False

    def get_toolset(self) -> FunctionToolset[SandboxDeps]:
        tools = FunctionToolset[SandboxDeps](id='sandbox-tools')

        @tools.tool
        async def read_file(ctx: RunContext[SandboxDeps], path: str, offset: int = 0, limit: int = 500) -> str:
            """Read bounded text from a path inside the task workspace."""
            return await ctx.deps.sandbox.read(path=path, offset=offset, limit=limit)

        @tools.tool
        async def edit_file(ctx: RunContext[SandboxDeps], path: str, old_text: str, new_text: str) -> str:
            """Replace one exact text fragment inside the task workspace."""
            return await ctx.deps.sandbox.edit(path=path, old_text=old_text, new_text=new_text)

        @tools.tool(timeout=120)
        async def run_command(ctx: RunContext[SandboxDeps], command: str) -> dict:
            """Run a bounded command inside the isolated task workspace."""
            return await ctx.deps.sandbox.run(command=command, timeout=110)

        return tools
```

Host responsibilities:

- allocate one workspace/lease per task and reconnect safely;
- normalize and contain paths server-side;
- isolate processes, filesystem, network, and environment;
- keep provider/API credentials outside the sandbox where possible;
- cap output, runtime, storage, and concurrent processes;
- return stable error types for retryable loss versus permanent policy failure;
- record idempotency and uncertain side effects across crashes;
- clean up leases and background processes.

Reuse Harness `FileSystem` or `Shell` inside the sandbox service if useful, but do not confuse their Python API boundary with the sandbox security boundary.

## Translate middleware

Use this order of preference:

1. agent/deps configuration;
2. tool or toolset feature;
3. built-in capability;
4. `Hooks` for one interception;
5. custom `AbstractCapability` for reusable combined behavior;
6. application orchestration when the behavior owns queues, timers, identity, or deployment.

Examples:

| Middleware behavior | Target |
|---|---|
| Add current tenant/repo context | dynamic instructions from deps |
| Add several related tools and usage guidance | custom capability |
| Audit one tool family | `Hooks.before_tool_execute` / `after_tool_execute` with tool filter |
| Modify tool definitions per step | `prepare_tools` hook or prepared toolset |
| Catch a known retryable tool error | tool wrapper that raises `ModelRetry` |
| Convert every exception to a string | Avoid; it hides infrastructure failures and corrupts retry semantics |
| Inject a queued message | application queue + `AgentRun.enqueue` |
| Notify Slack after completion | application event consumer or `after_run` hook |
| Store a diff artifact | `ToolReturn(metadata=...)` or `after_tool_execute` capability |
| Recreate a dead sandbox | host sandbox client; return a typed retryable error to the tool |

Capability ordering matters: the first capability is outermost. Declare ordering constraints when a guard must see the final transformed value or instrumentation must wrap another capability.

## Implement ordered policy

Deep Agents filesystem permissions may use ordered first-match allow/deny/interrupt rules. Harness `FileSystem` glob lists cover common local path policy, but not every ordered conditional policy.

For a complex policy:

1. represent rules as typed application data;
2. normalize tool names and validated arguments;
3. evaluate the first matching rule in one pure function;
4. deny by raising a stable policy error before execution;
5. interrupt with conditional `ApprovalRequired` or an approval-required toolset;
6. allow only after backend authorization also succeeds;
7. share the same evaluator between parent and children only when inheritance is intended;
8. log rule ID and decision without leaking sensitive arguments;
9. test rule order, default action, path normalization, symlinks, and subagent overrides.

Do not implement authorization solely in a hook if direct backend callers can bypass it. Put the hard check at the backend/service boundary and use capability policy as defense in depth and model guidance.
