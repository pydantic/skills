# Validation Guide

Validate observable contracts, not architectural resemblance. Exploratory probes are throwaway evidence; promote every accepted behavior into the migrated project's deterministic test suite.

## Contents

- [Build a contract matrix first](#build-a-contract-matrix-first)
- [Test layers](#test-layers)
- [High-risk contract suites](#high-risk-contract-suites)
- [Cutover gate](#cutover-gate)

## Build a contract matrix first

For each source invariant, record:

| Field | Example |
|---|---|
| observer | caller, model, child, user, operator, external service |
| source behavior | exact result, event, state transition, side effect, or recovery behavior |
| target owner | agent, deps, toolset, capability, graph, Harness capability, or application service |
| parity | exact, compatible with a stated tolerance, or approved intentional change |
| evidence | source fixture, target fixture, versions, and assertion |
| regression | permanent project test that freezes the decision |

For every composed, custom, or application-owned row, name the executable composition and run the same core assertion against source and target. A conceptual mapping is incomplete.

## Test layers

### Import and construction

- import every selected API from a public module;
- construct the agent against locked versions;
- assert deferred capability IDs, names, and descriptions;
- fail on duplicate tools, capabilities, or child names;
- treat warnings from `pydantic_ai_harness.experimental.*` as an explicit pinning decision.

### Pure domain and service tests

Keep path normalization, SQL policy, authorization, plan updates, state merges, output formatting, workflow transitions, and idempotency in pure functions or services where possible. Test them without a model.

### Tool and capability tests

Call tools with fake typed deps and assert:

- argument and return validation;
- model-visible name, description, and JSON schema;
- tenant, path, credential, and resource boundaries;
- timeout, cancellation, retry, and fatal-error behavior;
- bounded reads and results;
- approval and idempotency policy;
- instructions, toolsets, hooks, and `for_run()` isolation for custom capabilities.

Use `ModelRetry` only for model-correctable inputs. Keep unexpected infrastructure errors loud.

### Agent protocol tests

Use `TestModel` for construction/schema checks and `FunctionModel` when exact tool calls, retries, structured output, deferred approvals, or event order matter.

```python
from pydantic_ai import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel


def call_lookup(messages, info):
    received_result = any(
        isinstance(message, ModelRequest)
        and any(isinstance(part, ToolReturnPart) for part in message.parts)
        for message in messages
    )
    if received_result:
        return ModelResponse(parts=[TextPart('Customer found')])
    return ModelResponse(
        parts=[ToolCallPart('lookup_customer', {'customer_id': 'c-1'})]
    )


with agent.override(model=FunctionModel(call_lookup)):
    result = agent.run_sync('Find the customer', deps=fake_deps)
```

Capture run messages when the exact provider request/response sequence matters.

### Integration tests and evals

Keep a small provider integration suite for schema compatibility, provider-native tools, streaming, structured output, and usage. Use `pydantic_evals` or the project's eval harness for representative success, ambiguity, malicious input, tool failure, and budget-pressure cases. Score quality, safety, cost, latency, tool count, and artifact correctness.

## High-risk contract suites

### Prompt and output

- snapshot complete first and resumed provider requests;
- test instruction precedence and untrusted repository text;
- test invalid and multiple structured outputs;
- test output emitted alongside a side-effecting tool;
- compare new/all messages and application result fields.

### Delegation and orchestration

- child isolation from parent history;
- exact typed or serialized parent-visible result;
- deps and usage forwarding;
- per-child call/token/time limits;
- failure, retry, timeout, and cancellation;
- explicit state patch and reducer/conflict behavior;
- parallel result association and partial failure;
- graph transition and resume behavior when a graph is used.

For background children, additionally test idempotent start, scoped list/check, task-ID authorization, update/cancel races, duplicate delivery, lost workers, retry ceilings, and parent notification.

### Context, plans, memory, and files

- trusted instructions load in the intended precedence;
- writable memory stays in its tenant namespace and trust level;
- concurrent memory/plan writes and stale revisions;
- plan replace/patch/duplicate-call semantics;
- path traversal, absolute paths, symlinks, hidden/protected files, and cross-tenant access;
- process reconstruction and retention for promised persistent state;
- artifact URLs, integrity, and cleanup;
- compaction preserves valid tool-call/result pairs and promised retrieval.

### Approval, side effects, and recovery

- approve, deny, edited arguments, stale decisions, and resume;
- crash before, during, and after the tool body;
- duplicate delivery and replayed writes;
- continuable message snapshots only at provider-valid boundaries;
- unresolved tool-effect ledger after a mid-call crash;
- separate conversation, run, parent-run, task, and operation identities;
- explicit documentation of state that is not restored.

If arbitrary graph nodes, reducers, pending jobs, workspace state, or timers must recover, test the durable workflow/application runtime that owns them; message continuation or step persistence alone is insufficient.

### Streaming and traces

Compare representative source and target runs for:

- model requests and usage;
- tool calls, results, retries, and latency;
- child/run lineage;
- compaction or offload events;
- approval/defer/resume sequence;
- filesystem, database, queue, and external side effects;
- event ordering, backpressure, and final-output timing.

Expected traces need not be step-identical, but every material difference needs a contract disposition.

### Security boundaries

Adversarially test command-shell bypasses, secret leakage, SQL mutation and expensive queries, cross-tenant IDs, prompt injection in retrieved content, network redirects, approval replay, and children with wider tools or credentials. Enforce the hard boundary in the backend, sandbox, database role, credential, or worker—not only in prompts.

## Cutover gate

Do not remove the source path until:

- all exact rows pass and compatible tolerances are asserted;
- every non-direct row has an executable target composition and regression test;
- no high-risk row remains `unknown`, `unproved`, or merely `source-inspected`;
- intentional changes are approved and documented;
- import, unit, protocol, integration, eval, and safety suites pass;
- budgets, authorization, and timeouts are host-enforced;
- recovery claims match what the implementation restores;
- tracing, alerts, canaries, and rollback routing are ready.
