# Semantic Deltas and Migration Spikes

Read this before selecting a target architecture. The existence of a similar Pydantic AI or Harness API does not imply the same prompt, state, lifecycle, failure, or persistence semantics.

## Contents

- [Classification](#classification)
- [Delta ledger](#delta-ledger)
- [Research baseline](#research-baseline)
- [Easy-to-miss observed deltas](#easy-to-miss-observed-deltas)
- [High-risk semantic deltas](#high-risk-semantic-deltas)
- [Spike protocol](#spike-protocol)
- [Minimum spike set](#minimum-spike-set)
- [Decision gate](#decision-gate)

## Classification

Keep three independent axes. Do not collapse them into one slash-separated label.

| Target shape | Meaning |
|---|---|
| `direct` | The nearest target primitive exists. Its required observable behavior is still unproved. |
| `composed` | Several core/Harness pieces reproduce the contract. |
| `custom` | A toolset, capability, adapter, or service must be written. |
| `retain externally` | The application/runtime should continue owning the behavior. |
| `unknown` | A responsible target shape cannot yet be chosen. |

| Parity disposition | Meaning |
|---|---|
| `exact` | The recorded observable invariant must remain identical. |
| `compatible` | A specified difference is acceptable to named existing consumers under recorded tolerances. |
| `intentional change` | The user accepts a documented product/operational change. |
| `unknown` | The required parity decision has not been made. |

Track confidence separately with an evidence status: `unproved`, `source-inspected`, `spike-observed`, `regression-locked`, or `production-observed`. Do not use `direct` as shorthand for “drop-in replacement,” write combinations such as `composed/unknown`, or let source inspection masquerade as a runtime spike. Exact parity applies only to the invariants the evidence proves.

## Delta ledger

Create one row per independently testable source invariant. Split broad features such as “subagents,” “files,” or “persistence” into result representation, state handoff, model routing, failure, concurrency, lifecycle, and recovery rows as applicable.

| Field | Record |
|---|---|
| Source invariant | What users, tools, children, or operators can observe today. |
| Target candidate | Exact Pydantic AI/Harness primitive and installed import path. |
| Target shape | One of `direct`, `composed`, `custom`, `retain externally`, or `unknown`. |
| Executable target pattern | Named capability, toolset, facade, durable service boundary, or retained source path. |
| Parity disposition | One of `exact`, `compatible`, `intentional change`, or `unknown`. |
| Plausible delta | How prompt, state, result, error, event, side effect, or recovery could differ. |
| Spike | Smallest source/target experiment that distinguishes the behaviors. |
| Evidence | Source trace, target trace, fixtures, versions, and assertion results. |
| Evidence status | One status from `unproved` through `production-observed`; this is independent of mapping classification. |
| Decision | Adapter/retained boundary plus the owner and rationale for any accepted change. |
| User impact | Quality, latency, cost, security, UI, durability, and operational consequences. |
| Regression test | Deterministic test that freezes the chosen contract. |
| Rollback | Flag, adapter, or old path used if canaries fail. |

## Research baseline

The observations below were reproduced offline against Deep Agents 0.6.12 at `e821d3d`, Pydantic AI at `2a4d7c2`, and Pydantic AI Harness at `73513a6`. Four focused Deep Agents prompt/structured-result tests passed, and direct in-memory probes covered child state merge, StateBackend continuation, and async task registry behavior. Harness probes covered structured delegation, all four DynamicWorkflow result channels, FileSystem persistence/containment, StepPersistence mid-tool interruption, and Code Mode approval routing. See the [spike evidence manifest](SPIKE-EVIDENCE.md) for commands, assertions, and evidence limits.

This baseline does not replace a spike against the application's locked versions. Record new evidence in the delta ledger instead of silently carrying these observations forward.

## Easy-to-miss observed deltas

These observations came from source inspection and offline spikes against pinned checkouts. They are examples of what to verify, not permanent claims about every installed version.

| Apparently similar feature | Observed difference | Migration consequence |
|---|---|---|
| Constructor prompt | Deep Agents assembled caller prefix, selected base, caller suffix, then profile suffix; a bare `system_prompt` was a prefix rather than a replacement. | Reconstruct the resolved prompt deliberately and snapshot the complete first and resumed provider requests. |
| Mutable context | Deep Agents graph state used reducers and checkpoints; Pydantic AI deps were resource references and message history contained messages only. | Classify each field into deps, messages, durable application state, or an explicit `pydantic_graph` state machine. Never move graph state wholesale into deps. |
| Synchronous delegation | Deep Agents copied selected parent state into a child and merged most returned child state; Harness `SubAgents` passed task text plus configured resources and returned text. Source spikes also showed a child deletion failing to delete the parent file, an additive reducer duplicating the parent's old value, and shallow-copy mutation leaking without an explicit return. | Define typed child input/output and a merge policy. Test deletion tombstones, reducers, mutable values, and concurrent siblings; a shared mutable store is not an automatic equivalent. |
| Structured child output | Deep Agents put `model_dump_json()` output in the parent tool message; Harness `SubAgents` produced `str(child_output)` (`answer=7 note='seven'` in the spike). | Return JSON deliberately or write a serialization adapter; do not parse a Python representation as JSON. |
| Planning | Deep Agents todo state can follow graph/checkpoint lifecycle and its guidance permits unrelated simultaneous `in_progress` items; Harness Planning replaces a per-run plan, adds `cancelled`, asks for exactly one `in_progress`, and handles competing writes differently. | Decide plan schema, persistence, UI events, and concurrency explicitly; use a compatibility plan store when these are consumer-facing. |
| Scripted workflow result | Harness `DynamicWorkflow` returned the expression directly, `{'output': ...}` for print-only, `{'output': ..., 'result': ...}` for both, and `{}` for neither. | Freeze the chosen channel and exact return schema; printing is not observationally equivalent to returning. |
| Virtual files | Deep Agents `StateBackend` files lived in graph state and required the same checkpoint thread for cross-invocation persistence; Harness `FileSystem` persisted real host files and rejected traversal, absolute escape, and symlink escape in the spike. | Decide lifecycle, tenancy, storage, binary/media support, and namespace before mapping file tools. Use the source graph's state API rather than assuming raw checkpoint blobs contain reconstructed files. |
| Checkpoint/resume | LangGraph could restore arbitrary graph state and node position; Harness `StepPersistence` retained provider-valid messages/events/effects, and a simulated mid-tool crash continued from the previous safe message snapshot. | Use it for audit and safe message continuation, not as proof of graph, capability, plan, workspace, or side-effect recovery. |
| Approvals inside Code Mode | In the pinned Harness spike, a statically `requires_approval=True` tool folded into Code Mode executed its body without invoking the external denial handler; an explicit `ApprovalRequired` raised by the body did invoke the handler. | Keep approval-required tools outside Code Mode when an external pause is required, unless an installed-version spike proves the full defer/resume path. |
| Transcript repair | Deep Agents `PatchToolCallsMiddleware` cancels dangling calls using source-specific tool messages. Pydantic AI captures interrupted parts, and UI `sanitize_messages` strips unresolved client-supplied tail calls; neither establishes identical global repair behavior. | Test live tail, interrupted tail, malformed arguments, orphan returns, interior gaps, and UI-supplied history. Add a compatibility preprocessor only if exact cancellation semantics matter. |

Store the spike fixture and assertion beside the migrated application. Re-run it whenever Deep Agents, Pydantic AI, Harness, the provider, or the model changes.

## High-risk semantic deltas

| Surface | Deep Agents behavior to verify | Pydantic AI/Harness subtlety | Smallest discriminating spike |
|---|---|---|---|
| Effective prompt | Constructor prompt may be a prefix around an SDK base prompt plus resolved HarnessProfile suffix and cache markers. | `instructions` and capabilities assemble context differently. | Capture the complete first model request in both paths and diff ordered system/instruction blocks. |
| Model/profile routing | Parent and declarative children can resolve different provider profiles/models/settings, including GP-specific prompt behavior. | Explicit children keep their constructed model; workflow/disk children and run-level parent overrides have their own inheritance rules. | Capture the actual model, settings, effort, fallback, prompt, and tool schema for parent default/override plus explicit and disk children. |
| Implicit defaults | Planning, filesystem, summarization, patching, prompt caching, and a general-purpose child can appear without explicit application wiring. | Capabilities are normally explicit. | Compare model-visible tools, descriptions, prompt, and middleware/capability roster for a minimal constructor. |
| Tool surface | Names, schemas, descriptions, hidden runtime args, retry counts, and tool-result shapes are framework-specific. | Native tools/toolsets may validate and expose errors differently. | Snapshot tool definitions and run one success, invalid argument, model-correctable error, and infrastructure failure. |
| Graph state | Custom state fields and reducers can survive nodes and be updated with `Command`. | Dependencies are resources, not a mutable graph-state dictionary and are not checkpointed automatically. | Have parallel steps/children update an additive field, resume from a checkpoint, and inspect exact merge behavior. |
| Planning | Todo schema, active-form text, parallel writes, and checkpoint visibility are source contracts. | Harness plan state is normally per run, full-replacement, includes `cancelled`, and only warns/notes on some invalid progress shapes. | Try two parallel writes, zero/one/many `in_progress` items, all statuses, a second run, message continuation, and process restart. |
| Synchronous subagents | A `task` child can receive selected parent state and merge returned state; messages/todos/private fields have special rules. | `SubAgents` isolates history, forwards configured resources, and returns text. | Let a child write a virtual file, mutate custom state, and return a typed result; inspect the parent's state and tool result exactly. |
| Structured child output | Deep Agents JSON-serializes `structured_response` for the parent. | Harness delegation currently stringifies child output. | Return a nested Pydantic model and assert the exact parent-visible bytes/type. |
| Dynamic workflows | Script output can combine printed output and a final expression. | Return shape changes depending on whether either channel is present. | Run expression-only, print-only, and print-plus-expression workflows. |
| Async children | Task IDs/status live in graph state and may follow graph checkpoint semantics. | Background execution needs an external queue, tenant/conversation scope, and replay-stable side-effect identity. | Start/list/update/cancel across two conversations and a crash/replay; assert isolation and deduplication. |
| Virtual files | Default `StateBackend` files are graph state with reducers; their lifecycle follows invocation, checkpointer, and thread identity. | `FileSystem` writes real files under a host directory. | Write in run A, inspect returned state/disk, then read in run B with the same/different thread and a second tenant. |
| Composite stores | Path prefixes can route state, store, filesystem, or sandbox backends. | Multiple capabilities do not automatically reproduce one virtual namespace. | Exercise every routed prefix, collision, rename, and cross-store operation. |
| Skills and instructions | Skills may be discovered from configured backends with precedence and progressive loading. | Deferred capabilities/catalogs have different activation, trust, serialization, and replay behavior. | Test duplicate names, mutable skill text, activation, history replay, and untrusted repository instructions. |
| Memory and history | Memory files, graph state, store namespaces, and message history are distinct but can look file-like. | Harness `Memory`, `RepoContext`, deps stores, and `message_history` have different trust/lifecycles. | Run two users and two conversations; test injection order, writes, continuation, and leakage. |
| Middleware ordering | Ordered middleware can rewrite state, requests, tools, and responses around graph nodes. | Capability order, hooks, toolset wrappers, and application orchestration have different nesting points. | Instrument before/after events around a model call, retry, tool success, and tool failure; compare exact order. |
| Errors and retries | Middleware may turn failures into messages, commands, interrupts, or graph retries. | `ModelRetry`, tool retries, containment, provider failures, and normal exceptions have distinct control flow. | Force validation, domain, infrastructure, provider, cancellation, and usage-limit failures. |
| Streaming | LangGraph stream modes expose state/messages/custom updates and subgraph paths. | Pydantic AI emits typed model/tool events; final-output streaming is a separate contract. | Record ordered events for text, tool call, child call, approval pause, failure, and completion. |
| Approvals | Interrupt/checkpointer flows can pause graph execution with state and can expose approve/edit/reject/respond decisions. | Deferred tools return requests and resume from messages/results; edited arguments need reauthorization, and Code Mode changes where deferral occurs. | Combine guarded and unguarded parallel calls; approve, deny, edit arguments, crash before resume, and replay the same side effect. |
| Persistence | A LangGraph checkpointer can persist graph state and node position. | `StepPersistence` records events, valid message snapshots, effects, and lineage—not arbitrary graph/capability/workspace state. | Crash before/during/after a tool, continue, and compare restored state, messages, counters, files, and pending effects. |
| Summarization | Trigger thresholds, preserved state, file offload, and history rewrites are middleware-specific. | Compaction strategies may clear, deduplicate, spill, or summarize at different boundaries. | Force threshold crossing and diff provider-visible history, tool pairs, artifacts, and cache prefix. |
| Budgets | Prompt limits, graph recursion, middleware counters, and children may account separately. | `UsageLimits`, forwarded child usage, workflow call limits, and application deadlines compose explicitly. | Exhaust parent, child, parallel, token, request, timeout, and external-side-effect limits independently. |
| Shell/sandbox | A sandbox backend may provide remote isolation, lease/reconnect, credentials, and persistent workspace. | Harness `Shell` is local process plumbing; filters are not isolation. | Probe filesystem, environment, network, child processes, timeout cleanup, reconnect, and secret visibility in a disposable workspace. |
| Deployment | LangGraph server threads, commands, queues, schedules, and UI protocols may surround the agent. | `Agent.run` does not replace an application runtime. | Replay duplicate delivery, mid-run messages, worker loss, deployment restart, and external write idempotency. |

## Spike protocol

1. Pin and record source, Pydantic AI, Harness, provider, and model versions.
2. Pick one representative production trace and reduce it to the smallest fixture that preserves the invariant.
3. Use a recording/fake model in the source and `FunctionModel` or `TestModel` in Pydantic AI when provider behavior is not the subject.
4. Use temporary workspaces and fake clients. Do not perform live writes, notifications, pushes, or billable calls.
5. Capture the full observable contract: prompt, tool definitions, messages, state, files, result types, events, usage, errors, side effects, and recovery point.
6. Change one dimension at a time. Run success and failure cases.
7. Explain every difference. Implement an adapter/capability, retain a tested application boundary, or mark an intentional change. Use [the validated Pydantic AI patterns](PYDANTIC-AI-PATTERNS.md).
8. Retire the experimental probe. If the accepted observation is a lasting application contract, promote that assertion into a deterministic project regression test and attach the result to the ledger.

If dependencies cannot be installed or a source path cannot run, record evidence as `source-inspected` or `unproved`. Set target shape or parity disposition to `unknown` only when the missing evidence prevents that specific decision.

## Minimum spike set

Run these for every migration:

1. **Prompt/tool snapshot:** complete first model request and model-visible tool schemas.
2. **Representative vertical slice:** one real task with output, tool trace, usage, latency, and side effects.
3. **Failure slice:** invalid model arguments, retryable domain failure, and fatal infrastructure failure.
4. **State/lifecycle slice:** two turns or runs showing what persists and what resets.

Add the relevant high-risk spikes from the table whenever the inventory finds planning, model/profile routing, subagents, virtual files, skills/memory, middleware, streaming, approvals, compaction, persistence, shell/sandbox, or deployment orchestration.

## Decision gate

Cut over when every high-risk row has a decided target shape and parity disposition, executable evidence beyond `unproved`/`source-inspected`, and an executable target pattern or retained boundary. Split broad rows into independently testable invariants. Mark `compatible` only after naming the consumer and tolerance, and keep the old path until the same core assertion passes against source and target. State trade-offs in capability, durability, cost, trust, and operational ownership in plain language.
