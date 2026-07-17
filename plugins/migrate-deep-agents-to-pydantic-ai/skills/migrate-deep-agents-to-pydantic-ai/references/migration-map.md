# Deep Agents to Pydantic AI Migration Map

Use this map after inventorying the source. A similar primitive is only a starting point: verify the prompt, state, result, failure, event, side-effect, and recovery contracts that the application actually depends on. Read [pydantic-ai-architecture.md](pydantic-ai-architecture.md) before choosing an owner.

Classify each row independently:

- **target shape:** `direct`, `composed`, `custom`, `application-owned`, or `unknown`;
- **parity:** `exact`, `compatible`, `intentional change`, or `unknown`;
- **evidence:** `unproved`, `source-inspected`, `probe-observed`, `regression-tested`, or `production-observed`.

## Agent and execution

| Deep Agents / LangGraph | Idiomatic Pydantic AI shape | What to verify |
|---|---|---|
| `create_deep_agent(model=...)` | `Agent(...)` plus explicit instructions, tools/toolsets, capabilities, output type, and model settings | Deep Agents adds defaults and middleware; snapshot the resolved source agent rather than translating only constructor arguments. |
| effective prompt / `AGENTS.md` | static or dynamic `instructions`; optionally a validated repository-context capability | Preserve ordering, trust level, cache markers, and resumed-run behavior. Never promote untrusted repository text to system priority accidentally. |
| `tools=[...]` | decorated tools, `Tool`, or toolsets | Compare names, descriptions, JSON schemas, hidden context, retries, errors, timeouts, concurrency, and approval. |
| `response_format` | Pydantic `output_type` with an explicit output mode and end strategy | Test invalid output, multiple outputs, streaming, and a final result emitted with a side-effecting tool call. |
| `context_schema` | `deps_type` + `RunContext` | Dependencies hold resources, identity, configuration, and stores; they are not checkpointed graph state. |
| custom `state_schema` | messages, typed deps, durable repositories, or `pydantic_graph` state according to lifecycle | Classify every field and reducer. Do not replace a state dictionary with another undifferentiated container. |
| `.invoke({'messages': ...})` | a small application facade around `agent.run(...)` | Define the target return contract explicitly: final output, new/all messages, state references, and artifacts. |
| `.astream(..., stream_mode=...)` | event stream handler, `run_stream_events()`, or `iter()` | Translate the UI event contract and lineage, not method names. Check when final output and side effects become observable. |
| model fallback middleware | `FallbackModel` or application routing | Test eligibility, provider settings, structured output, native tools, usage, pre-first-byte failure, and mid-stream failure. |
| LangSmith tracing | OpenTelemetry/Logfire plus application correlation | Preserve conversation, run, parent, child, tool-call, and external-job identities separately. |

## Tools, delegation, and context management

| Deep Agents behavior | Idiomatic Pydantic AI shape | What to verify |
|---|---|---|
| `write_todos` | a typed plan model plus a focused tool/capability; optionally Harness experimental `Planning` when its installed contract fits | Replacement vs patch semantics, duplicate calls, persistence, visibility, and isolation. |
| filesystem tools | Harness `FileSystem` for deliberate host-workspace files, or a domain/state/artifact store exposed through tools | Paths, dotfiles, edit/delete/media behavior, tenancy, retention, outputs, and containment. |
| `execute` on a remote sandbox | sandbox client in deps plus narrow tools | Keep isolation, leases, credentials, egress, reconnect, timeout, and cleanup in the sandbox service. Harness `Shell` is local process plumbing. |
| synchronous `task` | a parent tool that invokes a typed child `Agent`; optionally Harness experimental `SubAgents` for its supported contract | Child history isolation, deps and budget forwarding, result serialization, failure, approval, and explicit state merge. |
| parallel or chained children | ordinary application `asyncio` for fixed fan-out; `pydantic_graph` for a typed state machine; model-selected child tools for adaptive delegation | Ordering, cancellation, partial failure, budgets, retry, streaming, and stable result association. |
| background children | durable application queue/worker plus start/list/check/update/cancel tools | Tenancy, authorization, idempotency, delivery, cancellation races, lost workers, retry ceilings, and parent notification. |
| summarization middleware | Pydantic AI `ProcessHistory`; optionally an installed Harness experimental compaction capability | Thresholds, summary role, tool-pair validity, archives, media, overflow recovery, and cache behavior. |
| large tool-result offload | bounded tool results or an artifact store; optionally Harness experimental overflow capability | Units and thresholds, read-back, retention, restart, tenancy, and large inputs as well as outputs. |
| always-loaded memory files | trusted instructions, bounded contextual retrieval, or repository context | Trust, freshness, precedence, size, and injection role. |
| writable long-term memory | a tenant-scoped application store in deps with narrow read/write tools | Namespace, write policy, reread timing, concurrency, retention, deletion, and prompt injection. |
| skills | deferred capabilities for a small trusted set, or a host-validated catalog plus bounded `load_skill` tool | Precedence, path containment, size, trust, activation, mutable history, and tool authorization. |
| prompt caching middleware | provider/core cache controls plus stable capability composition | Exact cache markers and the effect of changing plans, memories, or `ProcessHistory`. |
| interrupted-tool repair | provider-valid history capture and an explicit continuation policy | Malformed tails, orphan results, pending approvals, client-supplied history, and whether repair hides a real side effect. |
| implicit general-purpose child | an explicitly registered child agent, or no child as an intentional change | Roster, tools, model, budgets, and any disk-based discovery must be explicit. |

## Persistence and application boundaries

| Deep Agents / LangGraph | Idiomatic Pydantic AI shape | What to verify |
|---|---|---|
| `StateBackend` virtual files | a conversation/run-scoped state or artifact repository with model-facing tools | Persistence, path semantics, reconstruction, isolation, and whether edit/search/media behavior is required. |
| `StoreBackend` namespaces | domain repository, memory service, artifact store, or workflow store in deps | Choose by lifecycle rather than preserving a file-shaped API automatically. |
| `CompositeBackend` routing | focused toolsets/capabilities or a small explicit router | Prefix collisions, cross-store operations, authorization, and transactional boundaries. |
| sandbox backend | existing sandbox service behind typed deps and narrow tools | The application retains isolation, leases, credentials, networking, reconnect, and cleanup. |
| LangGraph checkpointer | message continuation plus durable application state; optionally Harness experimental step persistence for event/message snapshots | Message history is not arbitrary node, reducer, plan, workspace, approval, or side-effect recovery. |
| durable graph execution | `pydantic_graph` plus an appropriate durable workflow runtime, or retain the existing orchestrator | Crash/redeploy recovery, replay, timers, signals, idempotency, and pending external work. |
| `thread_id` | distinct conversation, run, parent-run, and external-task IDs | Do not overload one identifier across lifecycles. |
| files holding artifacts | artifact/object storage or an isolated workspace | Tenancy, integrity, retention, URLs, and cleanup are application contracts. |

## Middleware and policy

| Middleware purpose | Pydantic AI owner |
|---|---|
| add reusable tools plus instructions/hooks/settings | built-in or custom capability |
| observe or lightly transform lifecycle | `Hooks` |
| group, filter, prepare, or approve tools | toolset wrappers |
| validate model-correctable arguments | validator that raises `ModelRetry` |
| handle infrastructure failures | narrow application policy; keep unknown failures loud |
| require external approval | deferred tools plus a durable host decision |
| inject authenticated mid-run input | application queue followed by `enqueue()` |
| enforce call/token/time budgets | `UsageLimits`, child budgets, and application deadlines |
| authorize side effects | backend/service boundary, with model-facing policy as defense in depth |

## Version discipline

- Read the target lockfile before choosing an import path.
- Inspect public `__init__.py` exports and installed documentation; do not guess top-level re-exports.
- Treat `pydantic_ai_harness.experimental.*` as version-sensitive and pin it deliberately.
- Add an import-and-construction smoke test for every selected capability.
- Prefer Pydantic AI public primitives when a small composition expresses the contract clearly.

Primary sources: [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview), [Deep Agents repository](https://github.com/langchain-ai/deepagents), [Pydantic AI docs](https://ai.pydantic.dev/), and [Pydantic AI Harness](https://github.com/pydantic/pydantic-ai-harness).
