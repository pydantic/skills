# Deep Agents to Pydantic AI Migration Map

Use this reference after inventorying the source. Its target-shape column is a starting hypothesis, not the migrated project's result. A **direct** target is only the nearest primitive; it does not establish semantic parity. Record parity separately as **exact**, **compatible**, **intentional change**, or **unknown**, and evidence as **unproved**, **source-inspected**, **spike-observed**, **regression-locked**, or **production-observed**. For every non-direct row, select and test an executable route from [the Pydantic AI patterns guide](PYDANTIC-AI-PATTERNS.md).

## Contents

- [Agent construction and execution](#agent-construction-and-execution)
- [Harness behavior](#harness-behavior)
- [Backends and persistence](#backends-and-persistence)
- [Middleware and policy](#middleware-and-policy)
- [Design choices without direct mappings](#design-choices-without-direct-mappings)
- [Version and API discipline](#version-and-api-discipline)

## Agent construction and execution

| Deep Agents / LangGraph | Pydantic AI target | Candidate target shape | Migration note |
|---|---|---:|---|
| `create_deep_agent(model=...)` | `Agent('provider:model', ...)` | `direct` | This is only the constructor primitive. Deep Agents adds middleware, tools, a base prompt, and often a general-purpose child implicitly; build the target roster explicitly and preserve provider settings. |
| effective system prompt / `AGENTS.md` | `instructions=...`, dynamic `@agent.instructions`, or gated `RepoContext` | `composed` | Deep Agents may assemble caller prefix, selected base, caller suffix, profile suffix, middleware fragments, and cache markers. Capture first-run and resumed provider requests. Trust repository instruction files before injecting them as system instructions. |
| `tools=[...]` | `tools=[Tool(...)]`, decorators, or `toolsets=[...]` | `direct` | Snapshot names, descriptions, JSON schemas, hidden context, retry/error behavior, and concurrency before claiming compatibility. |
| `response_format` | `output_type=MyModel` and an explicit output mode/end strategy | `direct` | Result location, co-emitted tool calls, retries, and `run_stream` behavior can differ. Test invalid and multiple outputs plus a co-emitted side-effecting tool. |
| `context_schema` | `deps_type=Deps` + `RunContext[Deps]` | `direct` | Use only for clients, tenant identity, configuration, and stores. Deps are not reduced or checkpointed graph state. |
| custom `state_schema` | deps, durable application state, or `pydantic_graph` state | `composed` | Classify every field and reducer separately. Agent message history is not a general graph-state dictionary. |
| `.invoke({'messages': ...})` | `await agent.run(...)` plus `assets/migration_patterns/deepagents_compat.py::invoke_compat` | `composed` | The tested facade rejoins messages, output, todos, files, and custom state. Add project fields and test raw messages/no-new-prompt continuation. |
| `.astream(..., stream_mode=...)` | `run(event_stream_handler=...)`, `run_stream_events()`, or `iter()` | `composed` | Map the UI's actual event contract and lineage; `run_stream()` can alter final-output/side-effect timing. |
| LangChain/LangGraph model fallback middleware | `FallbackModel` or application fallback | `composed` | Failure predicates, per-model preparation/settings, mid-stream failures, native tools, structured output, usage, and suspended continuations can differ. Spike before-first-byte and mid-stream failures. |
| LangSmith tracing | Logfire / OpenTelemetry plus correlation/event adapters | `composed` | Preserve conversation/run/parent/task/tool-call lineage, graph/subagent events, content redaction, and usage attribution explicitly. |

## Harness behavior

| Deep Agents behavior | Pydantic AI / Harness | Candidate target shape | Important differences |
|---|---|---:|---|
| `write_todos` | checked-in `DeepAgentsCompatibility` or Harness `Planning` for an accepted redesign | `composed` | The compatibility capability preserves source fields, durable replacement, and rejects duplicate calls before execution. Harness Planning remains a deliberate contract change. |
| filesystem tools with `FilesystemBackend` | `pydantic_ai_harness.FileSystem` | `composed` | Both can target local files, but names, schemas, policies, dotfiles, edit/delete/media support, outputs, and environment lifecycle differ. Run the path/tool matrix before selecting aliases or an adapter. |
| `execute` on a sandbox backend | external sandbox adapter; Harness `Shell` only for deliberate local execution | `retain externally` | `Shell` inherits a local process boundary and its command controls are best-effort. Preserve remote isolation, lease, workspace, credentials, and reconnect semantics outside the agent. |
| synchronous `task` subagents | checked-in typed `delegate_task` + `DelegationEnvelope`, or `SubAgents` for text-only work | `composed` | The tested adapter forwards deps/usage, applies explicit state patches after success, reproduces source JSON serialization, and makes delegation approval-required when writes require approval. Define reducer/sibling order per project. |
| many parallel/chained `task` calls | `DynamicWorkflow` | `direct` | This replaces observable parent-selected calls with one blocking model-written program. It changes ordering, approval, failure/retry, streaming, and result-channel semantics; keep parity `unknown` until it can be marked compatible or an intentional change. |
| async/background remote subagents | checked-in `BackgroundSubagents` capability plus application worker/queue | `custom` | The tested capability carries tenant, conversation, run, tool-call, and operation identity and supports scoped start/list/check/update/cancel. The queue still owns durability, dedupe, and restart. |
| Deep Agents summarization middleware | `TieredCompaction` / `SummarizingCompaction` or custom compaction | `composed` | Threshold accounting, overflow recovery, summary role, history archive, manual compaction, tool-argument handling, and media recovery differ. |
| filesystem offload for large tool results | `OverflowingToolOutput(Spill(...))` plus a namespaced store | `composed` | Threshold units, covered result types, read-back tools, tenant isolation, retention, restart behavior, and large user inputs need separate decisions. |
| always-loaded memory files | `RepoContext`, static instructions, or a custom file-memory adapter | `composed` | Static developer instructions and model-written cross-run memory differ in trust, freshness, path, and injection role. |
| writable long-term memory | `pydantic_ai_harness.memory.Memory` | `composed` | Choose a bounded tenant namespace and test reread timing, concurrent writes, injection role, and cache effects. |
| skills progressive disclosure | checked-in host-validated `SkillCatalog` or deferred capability per trusted skill | `custom` | The tested catalog loads only supplied records. Preserve source precedence/validation and enforce tool authorization separately from skill metadata. |
| prompt caching middleware | provider/core cache behavior plus cache-aware capabilities | `composed` | Preserve stable prefixes and exact cache markers. Planning, memory, and history rewrites can alter costs and behavior. |
| `PatchToolCallsMiddleware` | interrupted-message capture, UI history sanitization, provider-valid snapshots, and optional compatibility preprocessing | `composed` | These mechanisms have different scopes. Test valid/malformed live tails, interrupted tails, orphan returns, interior gaps, and client-supplied history before accepting target repair behavior. |
| default general-purpose subagent | explicit `SubAgent` | `direct` | Decide whether to add it. Omitting it changes parity and requires an `intentional change` disposition. Also disable or audit Harness disk-agent discovery so the target roster is explicit. |
| custom harness/provider profiles | an agent factory that composes model settings and capabilities | `composed` | Resolve the active profile first. Preserve prompt additions, tool descriptions/exclusions, middleware ordering/exclusions, and GP child behavior with golden construction tests. |

## Backends and persistence

| Deep Agents / LangGraph | Pydantic AI target | Candidate target shape | Migration note |
|---|---|---:|---|
| `StateBackend` virtual files | checked-in virtual-file tools over `StateStore` | `custom` | The tested SQLite path survives agent/store reconstruction without host workspace files. Add source edit/search/media behavior only when inventoried. |
| `FilesystemBackend(root_dir=...)` | `FileSystem(root_dir=...)` plus schema/policy adapters | `composed` | Reproduce path, allow/deny/protected, dotfile, read/edit/delete, media, line, and result behavior explicitly. |
| `StoreBackend` and namespaces | `Memory` stores or an application-specific store in deps | `composed` | Choose based on whether the data is model memory, artifacts, workflow state, or business data. |
| `CompositeBackend` path routing | multiple focused capabilities/toolsets or a custom router | `custom` | Test prefix collisions and cross-store operations; prefer semantic APIs when one namespace is unnecessary. |
| sandbox backend | checked-in `RemoteSandbox` capability over the existing execution service | `retain externally` | The tested boundary routes model tools to the external client; the host retains isolation, lease/reconnect, credentials, egress, timeouts, and cleanup. |
| LangGraph `checkpointer` | `StepPersistence` for audit and valid message snapshots; durable state elsewhere | `composed` | It does not restore graph nodes, arbitrary state/reducers, capability state, retry counters, plans, workspace snapshots, or pending application work. |
| durable graph execution | `pydantic_graph` plus a durable application workflow, or the existing orchestrator | `retain externally` | Use durable execution when crash/redeploy recovery is required, not merely conversation continuation. |
| `thread_id` | `conversation_id`, per-run `run_id`, and application task IDs | `composed` | Keep dialogue identity, one run invocation, parent lineage, and external job identity separate. |
| files holding artifacts | `FileSystem`, object storage, or an artifact service | `composed` | Artifacts are not message history or memory. Define tenancy, retention, integrity, and URLs explicitly. |

## Middleware and policy

| LangChain middleware purpose | Pydantic AI target | Rule |
|---|---|---|
| Add tools plus instructions and hooks | custom `AbstractCapability` | Use the primary extension point. Keep it focused and reusable. |
| Observe or lightly modify lifecycle | `Hooks` decorators | Use for logging, metrics, queue checks, request shaping, and audits. |
| Group or wrap tools | `FunctionToolset`, `WrapperToolset`, `.filtered()`, `.prepared()`, `.approval_required()` | Apply policy at the toolset boundary. |
| Validate arguments | tool `args_validator` or validation hook | Raise `ModelRetry` for correctable model mistakes; raise application errors for broken invariants. |
| Retry tools | tool `retries` + `ModelRetry` | Do not convert every infrastructure exception into a model retry. |
| Require approval | `requires_approval=True`, conditional `ApprovalRequired`, or approval-required toolset | Include `DeferredToolRequests` in output and resume with `DeferredToolResults`. |
| Inject mid-run user input | `RunContext.enqueue()` or `AgentRun.enqueue()` | Application queues remain external; enqueue only after authenticating and ordering messages. |
| Limit model calls/tokens | `UsageLimits`, subagent budgets, and application deadlines | Bound the parent and every child/fan-out path. |
| Enforce input/output policy | Harness `InputGuard` / `OutputGuard` or custom hooks | Do not stream unscreened output when the policy must block before exposure. |
| Catch tool errors | typed tool errors, `ModelRetry`, or a narrow `on_tool_execute_error` hook | Preserve loud failures by default. Contain only known recoverable classes. |

## Design choices without direct mappings

### Skills

Do not inline every `SKILL.md` into the system prompt. For a small stable set, migrate each skill to a deferred capability with a stable ID, routing description, instructions, and optional toolset. For a large or user-editable corpus, build a bounded catalog plus `load_skill` tool and keep path resolution in host code.

### Background subagents

Model a background delegation as an external job:

1. `start_background_task(agent_name, task)` returns a durable ID.
2. A worker runs the child agent with its own budgets and credentials.
3. `check`, `update`, and `cancel` operate on the task store.
4. Completion can be enqueued into a live parent run or consumed on the next run.
5. Store task lineage separately from conversation and run IDs.

### Remote sandboxes

Keep the provider client and sandbox lease in deps. Expose narrow filesystem and command tools through a capability. Handle reconnect/recreate in the host, keep secrets out of the sandbox, annotate side effects for replay, and apply OS/container isolation. Harness `Shell` alone is not that boundary.

### Full graph-state resume

If the old system resumes arbitrary graph nodes with custom state, use `pydantic_graph` plus a durable workflow runtime or retain the existing orchestrator. `message_history=` resumes a conversation; it does not reconstruct arbitrary application state.

### Rubric-driven revision loops

Do not map Deep Agents `RubricMiddleware` directly to a final `OutputGuard`. A persisted grade-revise loop has grader prompts/models, bounded transcript selection, retry/iteration state, revision messages, terminal statuses, and grader-failure policy. Rebuild it as an explicit application or `pydantic_graph` state machine, or a custom capability backed by durable state. Spike fail-then-revise-then-pass, maximum iterations, grader exception, resume, and event/usage telemetry.

## Version and API discipline

- Read the lockfile before choosing an import path.
- Inspect the installed `pydantic_ai_harness/<capability>/README.md` and public `__init__.py`.
- Treat submodule-only imports as deliberate; do not guess top-level re-exports.
- Treat Harness APIs as version-sensitive: pin compatible versions and add an import smoke test.
- Prefer official Pydantic AI docs and source for core behavior and the official Harness repository for capability behavior.
- Link decisions to the exact capability contract rather than a release-number comparison table that will age quickly.

Primary sources: [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview), [Deep Agents repository](https://github.com/langchain-ai/deepagents), [Pydantic AI docs](https://ai.pydantic.dev/), and [Pydantic AI Harness](https://github.com/pydantic/pydantic-ai-harness).
