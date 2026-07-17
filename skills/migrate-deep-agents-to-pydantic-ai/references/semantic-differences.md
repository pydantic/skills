# Semantic Differences

Read this before settling the target architecture. Similar names do not establish equivalent behavior. Record and test only the contracts the application depends on.

## Keep three independent classifications

| Axis | Values |
|---|---|
| target shape | `direct`, `composed`, `custom`, `application-owned`, `unknown` |
| parity disposition | `exact`, `compatible`, `intentional change`, `unknown` |
| evidence status | `unproved`, `source-inspected`, `probe-observed`, `regression-tested`, `production-observed` |

`Direct` means a nearby primitive exists; it never means drop-in parity. Source inspection is not runtime evidence. An intentional change needs a named owner and approval.

## Use a semantic-difference ledger

Create one row per independently testable invariant. Split broad features such as “subagents,” “files,” and “persistence” into result representation, state handoff, failure, concurrency, lifecycle, and recovery.

| Field | Record |
|---|---|
| source invariant | What a user, caller, child, operator, or external system observes today. |
| target composition | Exact Pydantic AI/Harness public primitive and installed import path, or application service. |
| target shape | One target-shape classification. |
| parity disposition | What must remain exact, what tolerance is compatible, or what change is accepted. |
| plausible difference | Prompt, state, result, error, event, side effect, security, or recovery difference. |
| discriminating probe | Smallest source/target execution that tells the behaviors apart. |
| evidence | Versions, source trace, target trace, fixtures, and assertion results. |
| user impact | Quality, latency, cost, security, UI, durability, and operational effects. |
| decision | Selected owner/composition and rationale. |
| regression test | Deterministic assertion that freezes the chosen contract. |
| rollback | Flag, adapter, or old route if canaries fail. |

## Common differences to verify

These are hypotheses to test against the project's locked versions, not claims of current parity.

| Concern | Deep Agents shape to inspect | Pydantic AI decision to make |
|---|---|---|
| resolved prompt | constructor input plus defaults, profiles, middleware, repository instructions, and cache markers | Compose static/dynamic instructions deliberately and snapshot first and resumed provider requests. |
| mutable context | graph state, reducers, checkpointer, and backend state may be joined | Separate deps, messages, graph state, durable domain state, jobs, and artifacts by lifecycle. |
| invocation result | callers may receive messages, output, todos, files, and custom state together | Define a typed application result and explicit references to separately owned state. |
| structured output | framework-specific result placement and termination | Test invalid/multiple outputs, streaming, and co-emitted tool calls. |
| tool contract | names, descriptions, schemas, hidden arguments, retry, and error shaping | Snapshot the complete model-visible and caller-visible contract. |
| planning | source tool may replace, patch, or checkpoint plan state | Define plan schema, persistence, duplicate-call, visibility, and isolation semantics. |
| synchronous child | source may copy/merge graph state and serialize child output specially | Define history, deps, usage, result type, state patch, failure, and sibling ordering explicitly. |
| fan-out | parent/model may select calls with observable events | Decide whether fixed application orchestration, adaptive child tools, or a graph owns control; test ordering, partial failure, cancellation, and budgets. |
| background child | source runtime may maintain task registry and notifications | Keep queue/worker ownership in the application; test idempotency, authorization, loss, cancellation, and delivery. |
| files | one file API may hide state, local disk, store namespaces, or a sandbox | Choose a store from lifecycle and security needs; test path and persistence behavior. |
| memory | trusted instructions, message history, writable memory, and artifacts can all look file-like | Give each a separate trust level, namespace, retention policy, and injection rule. |
| compaction | thresholds, archive, summary role, pairing repair, and overflow recovery vary | Test provider-valid histories, retrieval, cache effects, and exact continuation inputs. |
| approval | source may pause a graph with pending state | Persist the pending request and authorization context; test approve, deny, edit, crash, replay, and resume. |
| checkpointing | arbitrary graph node/state recovery may be available | Message continuation and step/event snapshots are narrower; retain or add a durable workflow owner when required. |
| sandbox | remote lease and isolation may sit behind file/execute tools | Keep the sandbox service as the hard boundary; local `Shell` is not equivalent. |
| streaming | source stream modes may expose graph, child, or state updates | Map the consumer's event schema, lineage, backpressure, and final-output timing. |

## Probe protocol

For each risky row:

1. Pin and record source and target versions.
2. Write the invariant before running the probe.
3. Use the smallest deterministic source fixture that exposes it.
4. Implement the smallest target composition that could satisfy it.
5. Run both with controlled model responses and fake services where possible.
6. Compare requests, messages, results, events, side effects, and restart behavior.
7. Record the result in the ledger; do not ship the exploratory probe as skill content.
8. Turn accepted behavior into a project regression test and discard the throwaway probe.

Useful minimum probes include:

- resolved prompt on first and resumed requests;
- invalid structured output plus a co-emitted write tool;
- child typed output, failure, state patch, and parallel siblings;
- plan replacement, duplicate update, and restart;
- virtual-file isolation across two conversations and process reconstruction;
- background-task dedupe, authorization, cancellation, lost worker, and delivery;
- approval denial/edit/crash/resume;
- crash before, during, and after an external side effect;
- streaming event lineage and final-output timing;
- remote sandbox traversal, secret isolation, reconnect, and cleanup.

## Decision gate

A row is ready only when:

- its owner and executable target composition are named;
- exact or compatible claims have runtime evidence against the locked target;
- every difference has an adapter, explicit application boundary, or approved product change;
- the chosen contract has a deterministic regression test;
- high-risk rows are not `unknown` or merely `source-inspected`;
- rollback and operational impact are understood.

Use [migration-map.md](migration-map.md) to choose candidate owners, [implementation-recipes.md](implementation-recipes.md) to build the composition, and [validation.md](validation.md) to promote probe results into durable tests.
