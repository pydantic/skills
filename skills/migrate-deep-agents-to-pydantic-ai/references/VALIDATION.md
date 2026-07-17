# Migration Validation Guide

Verify behavioral parity and operational guarantees before removing the Deep Agents path.

## Contents

- [Build the contract matrix](#build-the-contract-matrix)
- [Test layers](#test-layers)
- [Tools and capabilities](#tools-and-capabilities)
- [Subagents and workflows](#subagents-and-workflows)
- [Context, persistence, and recovery](#context-persistence-and-recovery)
- [Safety and side effects](#safety-and-side-effects)
- [Trace comparison](#trace-comparison)
- [Cutover gate](#cutover-gate)

## Build the contract matrix

Before implementation, capture representative requests and expected invariants:

| Surface | Record |
|---|---|
| Inputs | prompt shapes, files/media, identity, configuration, follow-up messages |
| Outputs | type/schema, text/artifacts, ordering, citations, error/refusal forms |
| Tools | names, schemas, authorization, retries, timeouts, side effects, maximum output |
| Planning | when a plan appears, status rules, completion reconciliation |
| Subagents | roster, tools, context isolation, concurrency, budgets, error policy |
| Context | assembled prompt/profile, trust level of repository instructions, skills, scratch files, compaction thresholds |
| Memory | namespace, injection, write policy, retention, concurrency |
| Persistence | conversation/run/job identity, snapshot boundary, resume/fork guarantees |
| Streaming | event types, ordering, subagent visibility, terminal events |
| Deployment | sandbox lifecycle, queues, credentials, notifications, idempotency |

Add a delta-ledger row for each surface: source invariant, target candidate, target shape, parity disposition, evidence status, known or plausible delta, spike evidence, user-visible impact, decision, regression test, and rollback. `direct` with parity `unknown` and evidence `unproved` means only “nearest API,” not parity; keep the three axes in separate fields.

For every `composed`, `custom`, or `retain externally` row, name the executable capability, adapter, facade, or service boundary and run a target test containing the same core assertion as the source fixture. A mapping without a working route is incomplete; use [the validated Pydantic AI patterns](PYDANTIC-AI-PATTERNS.md).

For each row, label whether parity must be exact, compatible, or intentionally changed. Get approval for intentional changes before cutover.

## Test layers

### 1. Import and construction smoke tests

- import every chosen capability from the documented public module;
- construct the agent with the project's locked versions;
- assert deferred capabilities have stable IDs;
- assert agent/subagent names and descriptions are present;
- fail on duplicate tool, capability, or subagent names.

### 2. Pure domain tests

Keep SQL policy, path normalization, task authorization, output formatting, citation merging, and workflow decisions in pure functions where possible. Test these without a model.

### 3. Tool tests

Call tool functions or toolsets with fake typed deps. Assert:

- validated arguments and return types;
- tenant and path boundaries;
- timeout and cancellation cleanup;
- retryable versus fatal errors;
- idempotency behavior;
- bounded reads/results;
- no secret leakage in command environments, traces, or errors.

### 4. Agent protocol tests

Use `TestModel` for fast construction and schema tests. Use `FunctionModel` when exact tool calls, retries, deferred approvals, structured outputs, or event order matter.

```python
from pydantic_ai import Agent, ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel


def call_lookup(messages, info):
    return ModelResponse(parts=[ToolCallPart('lookup_customer', {'email': 'a@example.com'})])


with agent.override(model=FunctionModel(call_lookup)):
    result = agent.run_sync('Find the customer', deps=fake_deps)
```

Use `capture_run_messages()` when a failure needs an exact request/response history.

### 5. Recorded integration tests

Run a small set against real providers or recorded cassettes. Keep the test focused on framework integration: tool schema compatibility, streaming events, structured output, provider-native capabilities, and usage accounting.

### 6. Evals

Use `pydantic_evals` for a representative dataset. Include ordinary tasks, difficult decompositions, ambiguous requests, malicious inputs, tool failures, and budget pressure. Score task success, safety, cost, latency, tool count, and artifact correctness.

## Tools and capabilities

For every migrated tool family, test:

- the model-visible name and docstring match new prompts;
- old Deep Agents names (`ls`, `glob`, `grep`, `execute`, `task`, `write_todos`) do not remain accidentally unless compatibility aliases are intentional;
- `@agent.tool` functions accept `RunContext` first and `tool_plain` functions do not;
- toolsets receive the intended metadata, filters, approval, and deferred-loading policy;
- `ModelRetry` is raised only for model-correctable inputs;
- infrastructure exceptions remain loud unless a documented containment policy applies;
- rich `ToolReturn` content and metadata survive as expected;
- Code Mode wraps only the intended safe tools;
- externally approved/deferred tools stay outside Code Mode unless a test proves the tool body does not run before the decision and preserves approve, deny, edit, crash, and resume semantics;
- large tool returns spill/truncate/summarize at the correct thresholds and remain readable when promised.

For each custom capability, test its contributions independently:

- instructions and descriptions;
- toolset schemas and calls;
- hook order and return values;
- `for_run()` state isolation under concurrent runs;
- serialization opt-in or opt-out;
- deferred activation and history replay.

## Subagents and workflows

Test `SubAgents` for:

- child isolation from parent history;
- self-contained task text;
- any Deep Agents graph-state handoff/merge is intentionally omitted or reproduced by an explicit typed adapter;
- the exact parent-visible representation of text and structured child outputs;
- deletion tombstones, additive reducers, and mutable child inputs do not disappear, double-apply, or leak by shallow-copy aliasing;
- deps forwarding and tool non-inheritance by default;
- shared versus isolated usage accounting;
- per-child request/token budget, timeout, and max calls;
- soft timeout/budget outcome;
- model failure retry;
- unexpected crash propagation and optional containment;
- parallel calls and stable result association.

Test `DynamicWorkflow` for:

- valid Python identifiers and clear descriptions;
- structured child output arriving as a dictionary;
- exact `max_agent_calls` under concurrent fan-out;
- per-child/token usage settings;
- resource limit on pure CPU loops;
- failed script retry without re-paying completed child work when supported;
- rejection of nested workflows;
- final-expression return shape;
- captured `print()` output shape when printing is intentionally used;
- the exact expression-only, print-only, expression-plus-print, and empty result envelopes;
- no accidental loss of intermediate evidence needed by the parent.

For background subagents, add worker/application tests for idempotent start, scoped listing and task-ID recovery after compaction, authorization by task ID, status transitions, update/cancel races, duplicate delivery, lost workers, retry ceilings, and parent notification.

## Context, persistence, and recovery

### Context and memory

- verify trusted instructions load once and in the intended precedence order;
- ensure model-written memory does not enter the system-instruction trust level;
- test memory namespaces with two users and two agents;
- test concurrent writes and stale revisions;
- verify prompt and read/search limits;
- test skill name precedence, file containment, maximum size, and activation;
- force compaction and confirm tool-call/result pairing remains provider-valid;
- verify cache-sensitive mutable reminders do not accumulate in durable history.

### Conversation continuation

- distinguish `new_messages()` from `all_messages()`;
- resume with `message_history=` and the same conversation identity;
- verify the system instructions are not duplicated or silently lost;
- test multimodal parts and tool returns in replay.

### Step persistence

- crash before a tool, during a tool, and after a tool;
- assert continuable snapshots exist only at provider-valid boundaries;
- inspect unresolved tool effects after a mid-call crash;
- test `conversation_id`, per-call `run_id`, and `parent_run_id` lineage separately;
- verify media externalization and store retention if used;
- document that capability state, workspace state, and arbitrary graph nodes are not restored.
- compare the continuation snapshot with the old checkpointer's exact node, custom state, reducers, pending approval, plan, files, and side-effect ledger; retain a durable boundary for every missing field.

For a stronger durable runtime, test replay determinism, non-deterministic I/O isolation, timers, signals, cancellation, and idempotent external writes using that runtime's own test harness.

## Safety and side effects

Adversarially test:

- `..`, absolute paths, symlinks, hidden files, and protected patterns;
- shell interpreters that can bypass a command allowlist;
- environment-variable and credential exfiltration;
- SQL comments, multiple statements, DDL/DML, pragmas, and expensive queries;
- cross-tenant memory/task identifiers;
- prompt injection inside web pages, logs, memory, skills, and repository files;
- approval denial, edited arguments, stale approvals, and resume;
- duplicate queue events and replayed side effects;
- network destinations and redirect chains;
- streaming output that would bypass an output guard;
- child agents with wider tools or credentials than intended.

Verify the hard boundary in the backend, sandbox, database role, API credential, or worker—not only in model instructions.

## Trace comparison

Instrument both paths and compare representative runs:

- model requests and token usage;
- tool names, arguments, results, retries, and latency;
- child run tree and usage;
- compaction/spill events;
- approval/defer/resume sequence;
- filesystem, database, and external side effects;
- final output and artifacts.

Expected traces need not be step-identical. Explain every material difference and confirm it preserves or improves the contract.

## Cutover gate

Do not remove the old path until:

- all exact-parity rows pass;
- every non-`direct` row has an executable Pydantic AI implementation or an explicitly retained source boundary, with a target contract test;
- no high-risk row has target shape or parity disposition `unknown`, or evidence status `unproved`/`source-inspected`, and every claimed exact or compatible behavior has spike or trace evidence;
- intentional changes are approved and documented;
- import, unit, protocol, integration, and eval suites pass;
- safety tests exercise every write boundary;
- budgets and timeouts are host-enforced;
- production tracing and alerts are ready;
- a rollback flag or routing mechanism exists;
- canary traffic shows acceptable quality, cost, latency, and error rates;
- persistence/recovery claims match what the implementation actually restores.
