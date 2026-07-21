---
name: migrate-deep-agents-to-pydantic-ai
description: Converts and audits Python LangChain Deep Agents applications, create_deep_agent projects, and Deep Agents Code or deploy layouts using idiomatic Pydantic AI, with optional pydantic-ai-harness capabilities. Use when migrating, reviewing, or validating projects that rely on Deep Agents prompts, middleware, backends, HarnessProfile behavior, AGENTS.md or skills, subagents, sandboxes, planning, memory, streaming, approvals, persistence, or deployment orchestration.
---

# Migrate Deep Agents to Pydantic AI

Translate observable behavior and operational guarantees, not constructor arguments. Build from Pydantic AI's typed primitives; use Harness capabilities where their contracts fit, and keep durable application concerns in application services.

## Workflow

1. **Freeze the source contract.** Record the effective prompt, model/profile routing, tools, output, state, files, subagent topology, approvals, streaming, budgets, persistence, deployment boundaries, and representative traces.
2. **Inventory the project.** Read manifests and lockfiles, then search the full repository for Deep Agents/LangGraph imports, `create_deep_agent` factories and call sites, middleware/profile construction, tools, backends, state schemas, checkpointers, subagent definitions, instructions/skills, streaming consumers, deployment entry points, and external services. Follow indirection instead of relying on a fixed token list; record unreadable or uninspected paths and read [the migration map](references/migration-map.md) for every detected surface.
3. **Choose the owner.** Read [the Pydantic AI architecture guide](references/pydantic-ai-architecture.md). Place each concern in the smallest correct primitive: agent configuration, typed deps, output type, tool/toolset, capability, hook, `ProcessHistory`, graph, Harness capability, or application service.
4. **Record semantic differences.** Follow [the semantic-differences guide](references/semantic-differences.md). Treat a similarly named API as a candidate until its prompt, state, result, failure, event, side-effect, and recovery behavior are verified.
5. **Build one vertical slice.** Port typed deps, one tool family, the output contract, and one representative request. Keep temporary LangChain adapters only at explicit seams.
6. **Implement with public abstractions.** Use [the implementation recipes](references/implementation-recipes.md). Extend Pydantic AI through toolsets, capabilities, hooks, typed child agents, graphs, and services instead of recreating a monolithic harness.
7. **Validate by risk.** Follow [the validation guide](references/validation.md). Port read-only behavior before writes, synchronous work before background work, and local execution before durable or remote execution.
8. **Compare traces and recovery.** Verify outputs, tool schemas, child results, budgets, approvals, events, side effects, crash boundaries, and continuation—not only whether both agents answer.
9. **Cut over reversibly.** Keep the source path behind a flag until representative tests and evals pass, then remove framework-specific adapters.

## Pydantic AI design rules

- Use `deps_type` and `RunContext` for resources, identity, configuration, and stores; do not treat deps as checkpointed graph state.
- Use Pydantic output models for validated results.
- Use toolsets for related actions, capabilities for reusable tools plus instructions/hooks/settings, and `Hooks` for focused lifecycle interception.
- Use deferred tools for approvals and external execution; persist pending decisions and application state in the host.
- Use typed child agents for delegation, application code for explicit orchestration, and `pydantic_graph` for state machines.
- Keep queues, remote sandboxes, tenancy, artifacts, durable business state, and deployment orchestration application-owned.
- Treat static instructions, model-written memory, message history, workflow state, and artifacts as different lifecycles.
- Enforce authorization and isolation at the backend/service boundary; prompts and shell filters are not security boundaries.
- Bound every parent, child, workflow, and external side-effect path with appropriate usage, call, timeout, and retry limits.
- Inspect locked Pydantic AI and Harness versions before selecting imports; prefer public APIs and installed documentation.

## Reference routing

- Read [pydantic-ai-architecture.md](references/pydantic-ai-architecture.md) to understand core primitives, Harness's role, extension points, state ownership, background jobs, sandboxes, and approvals.
- Read [migration-map.md](references/migration-map.md) after inventorying features.
- Read [implementation-recipes.md](references/implementation-recipes.md) only for the selected implementation shapes.
- Read [project-playbooks.md](references/project-playbooks.md) only for a matching large-project pattern such as Open SWE, Deep Research, Content Builder, Text-to-SQL, coding, or GTM agents.
- Read [semantic-differences.md](references/semantic-differences.md) for uncertain or high-risk mappings.
- Read [validation.md](references/validation.md) before implementation and cutover.

## Deliverables

Produce an inventory, source behavior contract, semantic-difference ledger, feature mapping with implementation owners, staged migration plan, migrated code and project-specific tests when requested, explicit risk register, and trace/eval evidence for cutover.
