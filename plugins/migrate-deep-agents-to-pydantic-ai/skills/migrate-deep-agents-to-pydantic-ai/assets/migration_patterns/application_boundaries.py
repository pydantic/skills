from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.toolsets import FunctionToolset


@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    body: str


@dataclass
class SkillCatalog(AbstractCapability[object]):
    """Bounded, host-validated replacement for backend-discovered skill files."""

    id: str | None = 'project-skills'
    description: str | None = 'Load an approved project workflow when it matches the task.'
    defer_loading: bool = False
    skills: dict[str, SkillRecord] = field(default_factory=dict)

    def get_instructions(self) -> str:
        listing = '\n'.join(f'- {item.name}: {item.description}' for item in self.skills.values())
        return f'Load a matching workflow before using it. Available workflows:\n{listing}'

    def get_toolset(self) -> FunctionToolset[object]:
        tools = FunctionToolset[object](id='project-skill-loader')
        skills = self.skills

        @tools.tool_plain(metadata={'code_mode': True})
        def load_skill(name: str) -> str:
            """Load one approved workflow by exact name."""
            try:
                return skills[name].body
            except KeyError:
                available = ', '.join(sorted(skills)) or '(none)'
                raise ModelRetry(f'Unknown skill {name!r}. Available: {available}') from None

        return tools

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return None


class TaskQueue(Protocol):
    async def start(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
        operation_key: str,
        parent_run_id: str,
        agent_name: str,
        task: str,
    ) -> str: ...

    async def status(
        self, *, tenant_id: str, conversation_id: str, task_id: str
    ) -> dict[str, object]: ...

    async def list(
        self, *, tenant_id: str, conversation_id: str, status: str | None
    ) -> list[dict[str, object]]: ...

    async def cancel(
        self, *, tenant_id: str, conversation_id: str, task_id: str
    ) -> dict[str, object]: ...

    async def update(
        self, *, tenant_id: str, conversation_id: str, task_id: str, instruction: str
    ) -> dict[str, object]: ...


class OperationLedger(Protocol):
    async def background_key(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
        run_id: str,
        tool_call_id: str,
        agent_name: str,
        task: str,
    ) -> str: ...


@dataclass
class BackgroundDeps:
    tasks: TaskQueue
    operations: OperationLedger
    tenant_id: str
    conversation_id: str


@dataclass
class BackgroundSubagents(AbstractCapability[BackgroundDeps]):
    """Model-facing boundary around an application-owned durable task queue."""

    id: str | None = 'background-subagents'
    description: str | None = 'Start, list, check, update, or cancel durable child work.'
    defer_loading: bool = True

    def get_instructions(self) -> str:
        return 'Keep every task ID. Start background work only when the parent can continue independently.'

    def get_toolset(self) -> FunctionToolset[BackgroundDeps]:
        tools = FunctionToolset[BackgroundDeps](id='background-subagent-tools')

        @tools.tool
        async def start_background_task(
            ctx: RunContext[BackgroundDeps], agent_name: str, task: str
        ) -> str:
            """Start one allowlisted child task and return its durable ID."""
            if ctx.run_id is None or ctx.tool_call_id is None:
                raise RuntimeError('Background start requires run and tool-call identity.')
            key = await ctx.deps.operations.background_key(
                tenant_id=ctx.deps.tenant_id,
                conversation_id=ctx.deps.conversation_id,
                run_id=ctx.run_id,
                tool_call_id=ctx.tool_call_id,
                agent_name=agent_name,
                task=task,
            )
            return await ctx.deps.tasks.start(
                tenant_id=ctx.deps.tenant_id,
                conversation_id=ctx.deps.conversation_id,
                operation_key=key,
                parent_run_id=ctx.run_id,
                agent_name=agent_name,
                task=task,
            )

        @tools.tool
        async def list_background_tasks(
            ctx: RunContext[BackgroundDeps], status: str | None = None
        ) -> list[dict[str, object]]:
            """List this conversation's tasks, optionally filtered by status."""
            return await ctx.deps.tasks.list(
                tenant_id=ctx.deps.tenant_id,
                conversation_id=ctx.deps.conversation_id,
                status=status,
            )

        @tools.tool
        async def check_background_task(
            ctx: RunContext[BackgroundDeps], task_id: str
        ) -> dict[str, object]:
            """Check a task scoped to this tenant and conversation."""
            return await ctx.deps.tasks.status(
                tenant_id=ctx.deps.tenant_id,
                conversation_id=ctx.deps.conversation_id,
                task_id=task_id,
            )

        @tools.tool
        async def update_background_task(
            ctx: RunContext[BackgroundDeps], task_id: str, instruction: str
        ) -> dict[str, object]:
            """Send follow-up instructions to a running task in this scope."""
            return await ctx.deps.tasks.update(
                tenant_id=ctx.deps.tenant_id,
                conversation_id=ctx.deps.conversation_id,
                task_id=task_id,
                instruction=instruction,
            )

        @tools.tool(requires_approval=True, metadata={'code_mode': False})
        async def cancel_background_task(
            ctx: RunContext[BackgroundDeps], task_id: str
        ) -> dict[str, object]:
            """Request cancellation of a task scoped to this tenant and conversation."""
            return await ctx.deps.tasks.cancel(
                tenant_id=ctx.deps.tenant_id,
                conversation_id=ctx.deps.conversation_id,
                task_id=task_id,
            )

        return tools

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return None


class SandboxClient(Protocol):
    async def read(self, *, workspace_id: str, path: str, offset: int, limit: int) -> str: ...
    async def edit(
        self, *, workspace_id: str, path: str, old_text: str, new_text: str
    ) -> str: ...
    async def run(
        self, *, workspace_id: str, command: str, timeout: int
    ) -> dict[str, object]: ...


@dataclass
class SandboxDeps:
    sandbox: SandboxClient
    workspace_id: str


@dataclass
class RemoteSandbox(AbstractCapability[SandboxDeps]):
    """Narrow tools over an externally isolated and reconnectable workspace."""

    id: str | None = 'remote-sandbox'
    description: str | None = 'Read, edit, and test in the isolated task workspace.'
    defer_loading: bool = False

    def get_toolset(self) -> FunctionToolset[SandboxDeps]:
        tools = FunctionToolset[SandboxDeps](id='remote-sandbox-tools')

        @tools.tool(metadata={'code_mode': True})
        async def read_file(
            ctx: RunContext[SandboxDeps], path: str, offset: int = 0, limit: int = 500
        ) -> str:
            """Read bounded text from the isolated workspace."""
            return await ctx.deps.sandbox.read(
                workspace_id=ctx.deps.workspace_id, path=path, offset=offset, limit=limit
            )

        @tools.tool(requires_approval=True, metadata={'code_mode': False})
        async def edit_file(
            ctx: RunContext[SandboxDeps], path: str, old_text: str, new_text: str
        ) -> str:
            """Replace one exact text fragment in the isolated workspace."""
            return await ctx.deps.sandbox.edit(
                workspace_id=ctx.deps.workspace_id,
                path=path,
                old_text=old_text,
                new_text=new_text,
            )

        @tools.tool(timeout=120, requires_approval=True, metadata={'code_mode': False})
        async def run_command(ctx: RunContext[SandboxDeps], command: str) -> dict[str, object]:
            """Run a bounded command inside the isolated workspace."""
            return await ctx.deps.sandbox.run(
                workspace_id=ctx.deps.workspace_id, command=command, timeout=110
            )

        return tools

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return None
