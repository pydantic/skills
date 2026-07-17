---
name: migrate-deep-agents-to-pydantic-ai
description: Converts and audits Python LangChain Deep Agents applications, create_deep_agent projects, and Deep Agents Code or deploy layouts using Pydantic AI, with optional pydantic-ai-harness capabilities where they preserve the required behavior. Use when migrating, reviewing, or validating a Deep Agents project, or a LangGraph harness that specifically uses Deep Agents-style middleware, backends, HarnessProfile behavior, AGENTS.md or skills, subagents, sandboxes, planning, memory, streaming, approvals, or persistence.
---

# Migrate Deep Agents to Pydantic AI

Translate behavior and operational guarantees, not constructor arguments. Keep application orchestration outside the agent where it already owns queues, sandboxes, tenancy, deployment, or external side effects.

## Verify Semantic Differences

- Treat every mapping, including `direct`, as a hypothesis rather than a claim of identical behavior.
- Read [the semantic delta and spike guide](references/SEMANTIC-DELTAS.md) before choosing the target architecture.
- Show users every known or plausible change in prompts, tools, state, files, child results, errors, events, approvals, persistence, budgets, and side effects.
- Spike each high-risk or uncertain mapping on the installed source and target versions. Retire the experimental probe after use; promote lasting application contracts into project regression tests.
- Keep target shape, parity disposition, and evidence status separate. A `direct` target can still have `unknown` parity and `unproved` evidence. Retain the old path or add an adapter instead of implying parity.

## Workflow

1. **Freeze the contract.** Record entry points, outputs, tools, filesystem and shell boundaries, subagent topology/state handoff, context policy, persistence, approvals, streaming, budgets, deployment surfaces, the resolved HarnessProfile, and the fully assembled effective prompt. Do not remove Deep Agents yet.
2. **Inventory the project.** Resolve `SKILL_DIR` to the absolute directory containing this `SKILL.md`, run the bundled scanner from any working directory, and verify its findings manually. Read [the migration map](references/MIGRATION-MAP.md) for every detected feature.

   ```bash
   SKILL_DIR="<absolute path to this skill>"
   python3 "$SKILL_DIR/scripts/inventory_deepagents.py" <project-root>
   ```
3. **Inspect installed APIs.** Check the project's locked versions and importable symbols. Treat Harness APIs as version-sensitive; prefer the installed package, its bundled README files, and official docs over remembered imports.
4. **Build the delta ledger.** Create one row per independently testable invariant; split broad features such as subagents or persistence into state, result, routing, failure, concurrency, and recovery rows. Record target candidate, plausible delta, spike evidence, user impact, and rollback. Keep three fields independent: target shape (`direct`, `composed`, `custom`, `retain externally`, or `unknown`), parity disposition (`exact`, `compatible`, `intentional change`, or `unknown`), and evidence status (`unproved`, `source-inspected`, `spike-observed`, `regression-locked`, or `production-observed`).
5. **Choose the target shape.** Use a plain `Agent` for one agent loop, `SubAgents` for occasional delegation, `DynamicWorkflow` for scripted fan-out/chaining, `pydantic_graph` for an application state machine, and a durable runtime for crash-safe orchestration.
6. **Build one vertical slice.** Port typed deps, one tool family, output type, and one representative request. Keep adapters around existing LangChain tools only as a temporary seam.
7. **Add harness behavior deliberately.** Compose only the capabilities the contract needs. Read only the matching recipe sections routed below.
8. **Implement the Pydantic AI shape.** Read [the validated Pydantic AI patterns](references/PYDANTIC-AI-PATTERNS.md) for every `composed`, `custom`, or `retain externally` target shape. Copy or adapt the bundled capability, toolset, facade, or application-boundary assets; run the same source-contract assertion against the target. Do not stop at naming the nearest primitive.
9. **Migrate by risk.** Port read-only tools before writes, local runs before persistence, synchronous delegation before background work, and deterministic hooks before deployment integrations.
10. **Verify parity.** Follow [the validation guide](references/VALIDATION.md). Compare outputs, tool traces, budgets, failure modes, approval pauses, resume behavior, and side effects—not just whether the new agent answers.
11. **Cut over reversibly.** Keep the old path behind a flag until representative evals pass; then remove framework-specific adapters and dependencies.

## Translation Rules

- Prefer typed dependencies (`deps_type` + `RunContext`) over global clients or graph context dictionaries.
- Prefer Pydantic output models over prompt-only response formats.
- Prefer toolsets for related tools, capabilities for reusable tools plus instructions or hooks, and `Hooks` for narrow interception.
- Treat static repository instructions, writable memory, message history, and durable checkpoints as four different concerns.
- Enforce permissions in tools, toolsets, sandboxes, and application credentials. Prompt instructions are not a security boundary.
- Bound every recursive or fan-out path with request, token, call-count, timeout, and external-side-effect limits as appropriate.
- Preserve model-visible tool errors for recoverable mistakes; propagate infrastructure and invariant failures unless the contract explicitly contains them.
- Do not treat Harness `Shell` command filters as isolation. Use an OS/container/remote sandbox when untrusted model-written commands require a hard boundary.
- When an asset tool requires approval, include `DeferredToolRequests` in the agent output or install a tested deferred-call handler; persist messages and pending application state before returning control.
- If Code Mode is present, use an explicit safe-tool selector such as `CodeMode(tools={'code_mode': True})`; never use `tools='all'` with guarded asset tools.
- Do not describe `StepPersistence` as a full LangGraph checkpoint. It records events and provider-valid message snapshots; use durable execution or application state for stronger resume guarantees.

## Project Patterns

Read only the matching project playbook: [Open SWE](references/PROJECT-PATTERNS.md#open-swe), [Deep Research](references/PROJECT-PATTERNS.md#deep-research), [Content Builder](references/PROJECT-PATTERNS.md#content-builder), [Text-to-SQL](references/PROJECT-PATTERNS.md#text-to-sql), [deploy coding](references/PROJECT-PATTERNS.md#deploy-coding-agent), or [deploy GTM](references/PROJECT-PATTERNS.md#deploy-gtm-agent). Use it as a decomposition example, not a copy-paste template.

## Reference Routing

- Always use [the minimal agent](references/RECIPES.md#a-minimal-agent) and [typed dependencies](references/RECIPES.md#typed-tools-and-dependencies) when implementing.
- Read [the composed long-horizon agent](references/RECIPES.md#a-composed-long-horizon-agent) only when inventory justifies planning, repository context, filesystem, shell, overflow, or compaction.
- Read [delegation](references/RECIPES.md#subagents) or [dynamic workflows](references/RECIPES.md#dynamic-workflows) only when inventory finds child agents or fan-out.
- Read [context and memory](references/RECIPES.md#context-memory-and-history) or [filesystem, shell, and Code Mode](references/RECIPES.md#filesystem-shell-and-code-mode) only for those detected surfaces.
- Read [approvals](references/RECIPES.md#approvals-and-policy), [streaming](references/RECIPES.md#streaming-and-mid-run-messages), [persistence](references/RECIPES.md#persistence), or [LangChain adapters](references/RECIPES.md#transitional-langchain-tools) only when required.
- Read [skill capabilities](references/EXTENDING-THE-HARNESS.md#turn-one-skill-into-a-deferred-capability), [skill catalogs](references/EXTENDING-THE-HARNESS.md#load-a-directory-of-existing-skills), [background jobs](references/EXTENDING-THE-HARNESS.md#build-background-subagents), [remote sandboxes](references/EXTENDING-THE-HARNESS.md#wrap-a-remote-sandbox), [middleware](references/EXTENDING-THE-HARNESS.md#translate-middleware), or [ordered policy](references/EXTENDING-THE-HARNESS.md#implement-ordered-policy) only for a matching requirement.
- For planning, virtual state files, source-shaped invocation, child JSON/state merge, native approval, background jobs, remote sandboxes, or skill catalogs, start from the tested modules in `assets/migration_patterns/` rather than rewriting them from memory.

## Deliverables

Produce:

- an inventory and behavior contract;
- a semantic delta ledger with spike evidence for every high-risk or uncertain mapping;
- a mapping with target shape, parity disposition, and evidence status for every feature;
- a staged migration plan;
- migrated code and deterministic tests when implementation is requested;
- a named executable Pydantic AI implementation and target behavior test for every non-`direct` mapping;
- an explicit semantic-difference and risk register;
- evidence from parity tests and traces.
