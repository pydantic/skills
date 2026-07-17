from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, JsonValue
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.toolsets import FunctionToolset


class TodoItem(BaseModel):
    """Source-compatible todo shape used by Deep Agents prompts and UIs."""

    content: str
    status: Literal['pending', 'in_progress', 'completed']
    active_form: str = Field(alias='activeForm', serialization_alias='activeForm')


class StatePatch(BaseModel):
    """Explicit child-to-parent merge contract; absence means no update."""

    todos: list[TodoItem] | None = None
    file_writes: dict[str, str] = Field(default_factory=dict)
    file_deletes: list[str] = Field(default_factory=list)
    custom_set: dict[str, JsonValue] = Field(default_factory=dict)
    custom_delete: list[str] = Field(default_factory=list)


class DelegationEnvelope(BaseModel):
    """Child output that carries a JSON result and an explicit state patch."""

    result: JsonValue
    patch: StatePatch = Field(default_factory=StatePatch)


class CompatibilityState(BaseModel):
    revision: int = 0
    todos: list[TodoItem] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)
    custom: dict[str, JsonValue] = Field(default_factory=dict)


StateMutation = Callable[[CompatibilityState], None]
RESERVED_STATE_KEYS = frozenset({'messages', 'todos', 'files', 'structured_response'})


class StateStore(Protocol):
    async def load(self, key: str) -> CompatibilityState: ...

    async def mutate(self, key: str, mutation: StateMutation) -> CompatibilityState: ...


class InMemoryStateStore:
    """Test/local store with atomic mutation and copy-on-read semantics."""

    def __init__(self) -> None:
        self._states: dict[str, CompatibilityState] = {}
        self._lock = asyncio.Lock()

    async def load(self, key: str) -> CompatibilityState:
        async with self._lock:
            state = self._states.get(key, CompatibilityState())
            return state.model_copy(deep=True)

    async def mutate(self, key: str, mutation: StateMutation) -> CompatibilityState:
        async with self._lock:
            state = self._states.get(key, CompatibilityState()).model_copy(deep=True)
            mutation(state)
            state.revision += 1
            self._states[key] = state.model_copy(deep=True)
            return state.model_copy(deep=True)


class SqliteStateStore:
    """Small durable store; replace with the application's transactional store at scale."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.execute('PRAGMA journal_mode=WAL')
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                'CREATE TABLE IF NOT EXISTS compatibility_state ('
                'state_key TEXT PRIMARY KEY, payload TEXT NOT NULL)'
            )

    async def load(self, key: str) -> CompatibilityState:
        return await asyncio.to_thread(self._load_sync, key)

    def _load_sync(self, key: str) -> CompatibilityState:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT payload FROM compatibility_state WHERE state_key = ?', (key,)
            ).fetchone()
        return CompatibilityState.model_validate_json(row[0]) if row else CompatibilityState()

    async def mutate(self, key: str, mutation: StateMutation) -> CompatibilityState:
        return await asyncio.to_thread(self._mutate_sync, key, mutation)

    def _mutate_sync(self, key: str, mutation: StateMutation) -> CompatibilityState:
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute(
                'SELECT payload FROM compatibility_state WHERE state_key = ?', (key,)
            ).fetchone()
            state = CompatibilityState.model_validate_json(row[0]) if row else CompatibilityState()
            mutation(state)
            state.revision += 1
            connection.execute(
                'INSERT INTO compatibility_state(state_key, payload) VALUES (?, ?) '
                'ON CONFLICT(state_key) DO UPDATE SET payload = excluded.payload',
                (key, state.model_dump_json(by_alias=True)),
            )
            connection.commit()
            return state.model_copy(deep=True)
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


@dataclass
class CompatibilityDeps:
    state_store: StateStore
    state_key: str
    subagents: Mapping[str, Agent[Any, Any]] = field(default_factory=dict)


async def invoke_compat(
    agent: Agent[CompatibilityDeps, Any],
    prompt: str | None,
    *,
    deps: CompatibilityDeps,
    message_history: list[Any] | None = None,
) -> dict[str, Any]:
    """Return a Deep Agents-shaped state facade around one Pydantic AI run."""
    result = await agent.run(prompt, deps=deps, message_history=message_history)
    state = await deps.state_store.load(deps.state_key)
    return {
        **state.custom,
        'messages': result.all_messages(),
        'todos': [todo.model_dump(by_alias=True) for todo in state.todos],
        'files': dict(state.files),
        'structured_response': result.output,
    }


def _normalize_path(path: str) -> str:
    candidate = PurePosixPath(path if path.startswith('/') else f'/{path}')
    if '..' in candidate.parts:
        raise ModelRetry('Path traversal with `..` is not allowed.')
    parts = [part for part in candidate.parts if part not in {'/', '.', ''}]
    if not parts:
        raise ModelRetry('A file path is required.')
    return '/' + '/'.join(parts)


def serialize_deepagents_output(value: Any) -> str:
    """Match Deep Agents child structured-response serialization."""
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    if is_dataclass(value) and not isinstance(value, type):
        return json.dumps(asdict(value))
    return json.dumps(value)


def _apply_patch(state: CompatibilityState, patch: StatePatch) -> None:
    reserved = RESERVED_STATE_KEYS.intersection(patch.custom_set) | RESERVED_STATE_KEYS.intersection(
        patch.custom_delete
    )
    if reserved:
        raise ModelRetry(f'Custom state cannot modify reserved keys: {", ".join(sorted(reserved))}')
    if patch.todos is not None:
        state.todos = [item.model_copy(deep=True) for item in patch.todos]
    for path, content in patch.file_writes.items():
        state.files[_normalize_path(path)] = content
    for path in patch.file_deletes:
        state.files.pop(_normalize_path(path), None)
    state.custom.update(patch.custom_set)
    for key in patch.custom_delete:
        state.custom.pop(key, None)


@dataclass
class DeepAgentsCompatibility(AbstractCapability[CompatibilityDeps]):
    """Opt-in compatibility surface for the source behaviors an application needs."""

    id: str | None = 'deep-agents-compatibility'
    description: str | None = 'Source-shaped planning, virtual files, and typed child delegation.'
    defer_loading: bool = False
    require_write_approval: bool = False

    def get_instructions(self) -> str:
        return (
            'Use write_todos once per model response. Treat virtual files as conversation state. '
            'Delegate only self-contained tasks and preserve the JSON result.'
        )

    async def after_model_request(
        self,
        ctx: RunContext[CompatibilityDeps],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        del ctx, request_context
        duplicate_writes = sum(
            isinstance(part, ToolCallPart) and part.tool_name == 'write_todos'
            for part in response.parts
        )
        if duplicate_writes > 1:
            raise ModelRetry(
                'Error: The `write_todos` tool should never be called multiple times in parallel. '
                'Please call it only once per model invocation to update the todo list.'
            )
        return response

    def get_toolset(self) -> FunctionToolset[CompatibilityDeps]:
        tools = FunctionToolset[CompatibilityDeps](id='deep-agents-compatibility-tools', sequential=True)
        approval = self.require_write_approval

        @tools.tool(requires_approval=approval, metadata={'code_mode': False})
        async def write_todos(ctx: RunContext[CompatibilityDeps], todos: list[TodoItem]) -> str:
            """Replace the todo list; never call this tool twice in one model response."""
            def replace(state: CompatibilityState) -> None:
                state.todos = [item.model_copy(deep=True) for item in todos]

            await ctx.deps.state_store.mutate(ctx.deps.state_key, replace)
            return f'Updated todo list with {len(todos)} item(s).'

        @tools.tool(requires_approval=approval, metadata={'code_mode': False})
        async def write_file(ctx: RunContext[CompatibilityDeps], file_path: str, content: str) -> str:
            """Write one UTF-8 virtual file in conversation state."""
            normalized = _normalize_path(file_path)

            def write(state: CompatibilityState) -> None:
                state.files[normalized] = content

            await ctx.deps.state_store.mutate(ctx.deps.state_key, write)
            return f'Wrote {normalized}'

        @tools.tool(metadata={'code_mode': True})
        async def read_file(
            ctx: RunContext[CompatibilityDeps], file_path: str, offset: int = 0, limit: int = 2000
        ) -> str:
            """Read bounded lines from one virtual file."""
            if offset < 0 or limit < 1:
                raise ModelRetry('`offset` must be non-negative and `limit` must be positive.')
            normalized = _normalize_path(file_path)
            state = await ctx.deps.state_store.load(ctx.deps.state_key)
            try:
                content = state.files[normalized]
            except KeyError:
                raise ModelRetry(f"File '{normalized}' not found") from None
            lines = content.splitlines(keepends=True)
            if offset > len(lines):
                raise ModelRetry(f'Line offset {offset} exceeds file length ({len(lines)} lines)')
            return ''.join(lines[offset : offset + limit])

        @tools.tool(metadata={'code_mode': True})
        async def list_files(ctx: RunContext[CompatibilityDeps]) -> list[str]:
            """List all virtual file paths for this conversation."""
            state = await ctx.deps.state_store.load(ctx.deps.state_key)
            return sorted(state.files)

        @tools.tool(requires_approval=approval, metadata={'code_mode': False})
        async def delete_file(ctx: RunContext[CompatibilityDeps], file_path: str) -> str:
            """Delete one virtual file from conversation state."""
            normalized = _normalize_path(file_path)

            def delete(state: CompatibilityState) -> None:
                if normalized not in state.files:
                    raise ModelRetry(f"Error: File '{normalized}' not found")
                del state.files[normalized]

            await ctx.deps.state_store.mutate(ctx.deps.state_key, delete)
            return f'Deleted {normalized}'

        @tools.tool(requires_approval=approval, metadata={'code_mode': False})
        async def delegate_task(ctx: RunContext[CompatibilityDeps], agent_name: str, task: str) -> str:
            """Run a child and return JSON; an explicit child patch may update parent state."""
            try:
                child = ctx.deps.subagents[agent_name]
            except KeyError:
                available = ', '.join(sorted(ctx.deps.subagents)) or '(none)'
                raise ModelRetry(f'Unknown subagent {agent_name!r}. Available: {available}') from None
            result = await child.run(task, deps=ctx.deps, usage=ctx.usage)
            output = result.output
            if isinstance(output, DelegationEnvelope):
                await ctx.deps.state_store.mutate(
                    ctx.deps.state_key, lambda state: _apply_patch(state, output.patch)
                )
                return serialize_deepagents_output(output.result)
            return serialize_deepagents_output(output)

        return tools

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return None
