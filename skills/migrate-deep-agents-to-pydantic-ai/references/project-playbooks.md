# Project Migration Playbooks

These are architecture studies of substantial official LangChain Deep Agents projects. Use the matching playbook to find hidden behavior; do not reproduce model names, prompts, or deployment assumptions blindly.

## Contents

- [Open SWE](#open-swe)
- [Deep Research](#deep-research)
- [Content Builder](#content-builder)
- [Text-to-SQL](#text-to-sql)
- [Deploy Coding Agent](#deploy-coding-agent)
- [Deploy GTM Agent](#deploy-gtm-agent)
- [Cross-project lessons](#cross-project-lessons)

## Open SWE

Source: [langchain-ai/open-swe](https://github.com/langchain-ai/open-swe)

### How it works

Open SWE is an application, not merely an agent constructor. It creates a fresh Deep Agent per task/thread and keeps operational state in a persistent remote sandbox plus thread metadata. The agent has a curated tool set, an explicit general-purpose child, and a long ordered middleware stack. Slack, Linear, and GitHub triggers live outside the agent. Follow-up messages enter a queue and middleware injects them before a later model request. The host owns sandbox provisioning/reconnection, GitHub credential proxying, source-context assembly, status notifications, review workflows, and PR side effects.

Its key architectural boundaries are:

- one isolated cloud sandbox per task/thread;
- curated tools, with sensitive service credentials kept server-side;
- repository instructions plus issue/thread context;
- subagents for isolated investigation;
- deterministic middleware for message queues, retries, limits, artifacts, approvals, status, and provider-specific sanitation;
- prompt-driven local validation plus external PR/CI workflows.

### Migration shape

Keep the application shell. Replace only the Deep Agent runtime initially:

1. Build a Pydantic AI `Agent` factory from authenticated typed deps.
2. Wrap the existing sandbox provider as a focused filesystem/command capability. Do not replace remote isolation with local Harness `Shell`.
3. Use static/dynamic instructions or a repository-context capability only when it can see the sandbox filesystem and repository instruction files are trusted at system priority; otherwise expose them as lower-trust context or inject only host-approved instructions.
4. Map an explicit child to a typed child `Agent`; an installed Harness experimental delegation capability is optional when its contract fits. Preserve model, tool boundary, budgets, and retry policy. If the child reads or mutates shared graph state, add a deps-backed store and a typed handoff/merge contract.
5. Convert middleware in order:
   - preparation and identity → deps plus dynamic instructions;
   - message queue → host-driven `AgentRun.enqueue` or a narrow request hook;
   - model-call limits → `UsageLimits` plus application deadline;
   - tool retry → `ModelRetry` only for recognized recoverable failures;
   - tool artifacts/diffs → `ToolReturn` metadata or an `after_tool_execute` capability;
   - push/release guards → deferred approval plus server-side authorization;
   - status/notifications → event handler and after-run hook;
   - provider sanitation/fallback → provider model configuration and `FallbackModel`.
6. Add an installed step/event persistence capability for lineage if useful, but retain thread metadata, sandbox lease, task queue, and side-effect ledger in the application.
7. Re-run end-to-end tests for sandbox recreation, duplicate trigger delivery, mid-run messages, permissions, draft PR creation, and review follow-ups.

### Do not flatten

- Do not turn Slack/Linear/GitHub delivery into model tools unless the agent genuinely chooses when to use them.
- Do not put sandbox credentials in deps that are exposed to model-written shell commands.
- Do not replace deterministic approval or PR policy with prompt text.
- Do not collapse the reviewer/analyzer/background jobs into one large agent. They are separate application workflows with different tool and trust boundaries.

## Deep Research

Source: [Deep Agents deep_research example](https://github.com/langchain-ai/deepagents/tree/main/examples/deep_research)

### How it works

The orchestrator writes a plan and report files, delegates focused research to isolated children, and synthesizes citations. A research child uses Tavily for URL discovery, fetches full pages, and calls a no-op reflection tool after searches. Prompts enforce concurrency and iteration guidance, but the code shown does not enforce every numerical limit at the host boundary.

### Migration shape

- `write_todos` → a typed plan repository and tools; optionally installed Harness experimental `Planning` after verifying its contract.
- `task` → typed child agents for adaptive rounds, or bounded application fan-out for known independent facets and comparisons.
- Tavily/search/fetch → native tools or provider-adaptive `WebSearch`/`WebFetch`; keep full-content fetch bounded.
- `think_tool` → `Thinking` plus explicit stop criteria; do not preserve a no-op tool unless its trace event is an actual product requirement.
- Deep Agents `StateBackend` report files → typed intermediate outputs or a custom per-run virtual artifact adapter. Use `FileSystem` only when real, isolated workspace artifacts are part of the target contract; never silently turn ephemeral state files into shared host files.
- child return → a Pydantic model containing claims, source URLs, and confidence. Let the parent deduplicate and format citations.
- large page returns → bounded results/artifact offload, optionally the installed experimental overflow capability; long runs → a `ProcessHistory` composition, optionally an installed experimental compaction capability.
- prompt-only concurrency/iteration limits → an application semaphore/call counter, `UsageLimits`, child timeouts, and an application deadline.

Test simple fact lookup, multi-entity comparison, conflicting sources, empty search, duplicate URLs, citation renumbering, and budget exhaustion.

Create a fresh artifact namespace or workspace per run. Verify that one run cannot read or overwrite another run's reports, and define retention separately from conversation history.

## Content Builder

Source: [Deep Agents content-builder-agent example](https://github.com/langchain-ai/deepagents/tree/main/examples/content-builder-agent)

### How it works

`AGENTS.md` holds always-on brand instructions. `skills/*/SKILL.md` provides on-demand blog and social workflows. YAML defines a research child. Custom tools generate images and write them into a local content tree. The CLI streams Deep Agents messages and recognizes tool names to render user-facing status.

### Migration shape

- brand `AGENTS.md` → trusted static/dynamic instructions or a repository-context capability, not writable model memory by default;
- each writing skill → a deferred custom capability with its own description and instructions, or a bounded skill catalog;
- researcher YAML → an explicit typed child `Agent`, or installed Harness experimental subagent definitions after checking format and tool resolution;
- generated content/artifacts → `FileSystem` plus image-generation tools that return typed path/metadata;
- CLI event mapping → `event_stream_handler` over Pydantic AI event types rather than string matching arbitrary messages;
- quality checklist → output model or deterministic artifact validation, not prompt text alone.

Keep the image client in deps and validate the requested output path beneath the workspace. Test missing provider keys, no-image responses, file conflicts, research failure, and both content layouts.

## Text-to-SQL

Source: [Deep Agents text-to-sql-agent example](https://github.com/langchain-ai/deepagents/tree/main/examples/text-to-sql-agent)

### How it works

The project combines `SQLDatabaseToolkit`, always-loaded database instructions, on-demand schema/query skills, planning, and a persistent local filesystem. It declares SQL safety in prompt text and passes no custom subagents, although Deep Agents may still add a default general-purpose child depending on its profile.

### Migration shape

1. Keep `SQLDatabaseToolkit` behind `LangChainToolset` for the first vertical slice, or replace it with a small native read-only toolset.
2. Enforce read-only behavior in the database connection/tool implementation. Parse or prepare SQL and reject multiple statements and mutating operations. Prompt instructions are secondary.
3. Map `AGENTS.md` to static instructions and the two skills to deferred capabilities.
4. Add typed plan tools—or an installed experimental planning capability—only for genuinely multi-table analytical work; simple count/lookups do not need a plan.
5. Use a typed output such as `QueryAnswer(sql, columns, rows, explanation, limitations)`.
6. Use Code Mode only around explicitly read-only schema/query tools when batching and local aggregation reduce model turns.
7. Remove the implicit general-purpose child unless a tested query class benefits from delegation.

Test SQL injection attempts, DDL/DML, multiple statements, nulls, empty results, schema errors, query timeouts, maximum-row limits, and exact numeric formatting.

## Deploy Coding Agent

Source: [Deep Agents deploy-coding-agent example](https://github.com/langchain-ai/deepagents/tree/main/examples/deploy-coding-agent)

### How it works

The deployed agent follows Plan → Implement → Review → Deliver inside a LangSmith sandbox. Its skills add planning, code review, helper scripts, and persistent user coding preferences. The prompt instructs the agent to test, lint, commit, and delegate research or independent work.

### Migration shape

- planning → typed plan state and tools, optionally the installed experimental planning capability;
- file access and commands → a real sandbox adapter, or `FileSystem` + `Shell` only inside an already isolated host;
- code-review workflow → deferred capability with its helper scripts mounted into the sandbox;
- coding preferences → a tenant-scoped application store with bounded tools, preferably on-demand when trust requires it;
- subagents → explicit typed child agents with narrow tools;
- test/lint loop → keep prompt guidance, then add deterministic post-edit verification in the host when completion must guarantee it;
- commit/push → separate tools and require approval for external writes according to product policy.

Test dirty worktrees, failing tests, long-running commands, command truncation, generated diffs, user preference conflicts, sandbox loss, and approval/resume.

## Deploy GTM Agent

Source: [Deep Agents deploy-gtm-agent example](https://github.com/langchain-ai/deepagents/tree/main/examples/deploy-gtm-agent)

### How it works

The supervisor performs synchronous market research before strategy work and describes a background content-writer workstream whose result is monitored and integrated later. Project and child skills encode competitor and market-analysis workflows. The research child writes a full report to a shared memory/artifact path and returns concise structured extracts.

### Migration shape

- blocking market research → a typed child agent returning `MarketReport`; if an installed Harness delegation capability is selected, test its exact parent-visible serialization;
- independent batch research → bounded application fan-out when all work should finish in the request, or an explicit graph when transitions are domain state;
- background content writing → an external worker and a custom background-task capability with start/list/check/update/cancel tools;
- shared report path → artifact store or FileSystem, not automatically model memory;
- skills → deferred capabilities;
- task IDs and status → durable application store, correlated to conversation/run IDs;
- final integration → host or parent agent consumes completed artifacts and typed summaries.

Test a background task finishing before/after the parent, cancellation, duplicate completion delivery, unavailable workers, stale task IDs, partial market evidence, and final-plan generation without optional content.

## Cross-project lessons

- A Deep Agent project usually mixes agent reasoning with application orchestration. Migrate those layers separately.
- Files are used for at least four roles: trusted instructions, model memory, scratch context, and durable artifacts. Give each a distinct store and trust policy.
- Prompts often state limits that the runtime does not enforce. Convert critical limits into host-enforced budgets.
- Subagents are primarily context isolation, not automatically better reasoning. Keep only delegations that win in evals.
- Implicit Deep Agents defaults must be inventoried: planning, filesystem, summarization, patching, prompt caching, and the general-purpose child may exist even when application code does not mention them.
- Large production projects depend more on sandbox lifecycle, queues, identity, idempotency, and external delivery than on the agent constructor. Preserve those application contracts first.
