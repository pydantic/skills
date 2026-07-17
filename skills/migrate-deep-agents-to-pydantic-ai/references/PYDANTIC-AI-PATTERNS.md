# Validated Pydantic AI Patterns for Non-1:1 Mappings

Choose the Pydantic AI architecture that expresses the required observable contract: a capability, toolset, typed adapter, or application boundary. Then run the same assertion against source and target.

## Contents

- [Required workflow](#required-workflow)
- [Validated compatibility assets](#validated-compatibility-assets)
- [What the assets prove](#what-the-assets-prove)
- [Pattern selection matrix](#pattern-selection-matrix)
- [Validation template](#validation-template)
- [Version discipline](#version-discipline)

## Required workflow

For every `composed`, `custom`, or `retain externally` target shape:

1. Write the smallest source fixture that demonstrates the invariant.
2. Name the target Pydantic AI pattern and its owner.
3. Implement it with public Pydantic AI/Harness APIs or an application service behind typed deps.
4. Execute the same assertion against the target using a disposable offline spike.
5. Record what is exact, compatible, intentionally changed, or still unknown.
6. Keep the source path until the target assertion passes. Retire the experimental probe afterward; if the assertion protects a lasting project contract, promote it into the project's real regression suite.

Do not count prose, import success, or “the agent answered” as validation.

## Validated compatibility assets

Copy only the needed modules from `assets/migration_patterns/` into the migrated project:

| Asset | Closes |
|---|---|
| `deepagents_compat.py` | source-shaped invocation result, durable todos, conversation-scoped virtual files, exact child structured-result serialization, explicit child state patches, native approval before writes |
| `application_boundaries.py` | host-approved skill catalog, durable background-task capability, remote sandbox capability |

The implementations were exercised with disposable offline `FunctionModel` probes covering the behaviors listed below. Those probes are intentionally not bundled or regression evidence: write the smallest fixture for the actual project's source contract and run it against the copied target implementation. Retire the experimental fixture afterward; when the assertion is a lasting application contract, promote it into the migrated project's real regression suite.

Copy only the modules the target needs:

```bash
PATTERNS="$SKILL_DIR/assets/migration_patterns"
cp "$PATTERNS/deepagents_compat.py" <target-package>/
cp "$PATTERNS/application_boundaries.py" <target-package>/
```

### Mandatory approval and Code Mode wiring

Any agent that includes an approval-required asset tool must either include `DeferredToolRequests` in `output_type` and resume with `DeferredToolResults`, or install an explicit deferred-call handler. Without one, Pydantic AI raises a construction/runtime `UserError` when the model calls the guarded tool.

The `code_mode` metadata is a selector tag, not automatic protection. If Code Mode is present, select only tools explicitly marked safe:

```python
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import ToolApproved, ToolDenied
from pydantic_ai_harness import CodeMode

from deepagents_compat import (
    CompatibilityDeps,
    DeepAgentsCompatibility,
    InMemoryStateStore,
)


deps = CompatibilityDeps(state_store=InMemoryStateStore(), state_key='tenant:conversation')
agent = Agent(
    TestModel(call_tools=['write_file']),  # replace with the production model
    deps_type=CompatibilityDeps,
    output_type=[str, DeferredToolRequests],
    capabilities=[
        DeepAgentsCompatibility(require_write_approval=True),
        CodeMode(tools={'code_mode': True}),
    ],
)

first = agent.run_sync('Write one virtual file', deps=deps)
if isinstance(first.output, DeferredToolRequests):
    decisions = {
        call.tool_call_id: ToolApproved()  # or ToolDenied('reason') after host review
        for call in first.output.approvals
    }
    final = agent.run_sync(
        deps=deps,
        message_history=first.all_messages(),
        deferred_tool_results=DeferredToolResults(approvals=decisions),
    )
```

Never use `CodeMode(tools='all')` with these assets. It can fold approval-required tools behind `run_code` and bypass the intended external pause. The safe selector currently admits only `DeepAgentsCompatibility.read_file`, `DeepAgentsCompatibility.list_files`, `SkillCatalog.load_skill`, and `RemoteSandbox.read_file`. Guarded writes and delegation (because a child may return a patch), job operations, edits, commands, and cancellation remain native. Whenever these assets change, use a disposable construction probe to assert that the admitted tool names are exactly this allowlist and that no tool has both `requires_approval=True` and `metadata['code_mode'] is True`.

## What the assets prove

| Source invariant | Pydantic AI implementation | Validated behavior | Remaining decision |
|---|---|---|---|
| `.invoke()` returns messages plus graph-like fields | `invoke_compat()` loads external state after `Agent.run()` | messages, todos, files, custom fields, and structured response are returned in one dictionary | add any project-specific fields and reducers |
| todo schema and whole-list replacement | `DeepAgentsCompatibility.write_todos` | `content`, three source statuses, `activeForm`, durable replacement | project UI/event projection |
| two `write_todos` calls in one response mutate nothing | `after_model_request` rejects the response before tools execute | duplicate response causes zero writes; a corrected response writes once | Pydantic AI emits one retry part rather than two LangChain error ToolMessages |
| StateBackend-style files are not host files | virtual file tools over `StateStore` in deps | same key survives agent/store reconstruction; no Harness `FileSystem` dependency | add source-specific edit/glob/grep/media behavior when inventory requires it |
| child Pydantic/dataclass/dict/string output uses source JSON rules | `serialize_deepagents_output` | exact default `model_dump_json()`/`json.dumps()` behavior, quoted string, source `TypeError` for `datetime`, plus parent deps/shared usage forwarding | none for covered types |
| child state changes reach the parent | approval-aware `delegate_task` + `DelegationEnvelope` + `StatePatch` | writes/deletes/custom updates apply atomically only after child success; reserved facade keys are rejected; `require_write_approval=True` guards delegation because it may patch state | reducer policy is application-specific; patch semantics intentionally remove shallow-copy leakage and deletion loss |
| guarded writes pause before side effects | native `requires_approval=True` plus mandatory deferred-output/handler wiring and safe Code Mode selector | first run produces a request with zero mutations; denial resumes with zero mutations | host must durably persist pending requests and make duplicate decisions idempotent |
| files/todos/custom state survive process reconstruction | `SqliteStateStore` | a fresh store and agent see the prior namespace | production store needs tenant keying, migrations, retention, and operational HA |
| background task operations remain application-owned | `BackgroundSubagents` over queue and operation-ledger protocols | start/list/check/update/cancel are tenant/conversation scoped; listing recovers task IDs after compaction; start carries run, tool-call, and operation identity | queue implements durability, deduplication, worker retry, and update/cancel races |
| sandbox semantics remain remote and workspace-scoped | `RemoteSandbox` over a host client protocol | every model tool passes the explicit workspace ID to the external client | host service enforces binding, containment, isolation, credentials, reconnect, and cleanup |
| skills are progressively available without arbitrary backend reads | `SkillCatalog` built from host-validated records | only supplied names/bodies can be loaded | host performs path containment, precedence, size limits, trust, and tool authorization |

The asset is a starting implementation, not a universal library. Copy it so project types, state fields, policies, and stores become explicit application code.

## Pattern selection matrix

Use this table to select the Pydantic AI implementation shape:

| Non-1:1 surface | Make it doable with | Required target proof |
|---|---|---|
| Prompt/profile assembly | one typed agent factory that resolves base/prefix/suffix, model settings, tool descriptions, exclusions, and child roster | golden first and resumed provider requests for every deployed profile |
| Mutable graph state | typed repository in deps plus `pydantic_graph` when transitions matter | field-by-field restore, reducer/transaction, concurrent update, and namespace tests |
| Full graph/node resume | Pydantic AI durable execution integration or existing workflow runtime; keep state repository separate | kill/restart test restores exact safe boundary and does not duplicate side effects |
| Planning | checked-in compatibility capability | duplicate-write, replacement, persistence, isolation, and UI-shape tests |
| Virtual/composite files | checked-in virtual file capability; add a router over multiple stores when prefixes matter | read/write/delete/list, routing collisions, tenant isolation, and zero host leakage |
| Synchronous child state merge | typed child input plus `DelegationEnvelope` patches | success/failure, delete, reducer policy, sibling ordering, and exact parent-visible JSON |
| Async/background children | checked-in queue capability plus application worker | start/list/check/update/cancel, compaction recovery, dedupe, restart, authorization, and lost-worker tests |
| Approval interrupt | native deferred tools outside Code Mode plus durable pending-request store | guarded/unguarded parallel calls, approve/edit/deny, crash, replay, and once-only effects |
| Remote sandbox | checked-in external-client capability | containment, environment/secret isolation, network, timeout cleanup, reconnect, and lease lifecycle |
| Skills | checked-in host-validated catalog or one deferred capability per trusted skill | duplicate precedence, activation, path containment, mutable history, and authorization tests |
| Middleware/order | one custom capability or ordered toolset wrapper when order is load-bearing | golden hook order for success, retry, deferral, and failure |
| Transcript repair | explicit history processor for the accepted cancellation policy | valid/malformed tail, interrupted tail, orphan return, and interior gap fixtures |
| Compaction | custom history processor/capability plus archive store when loss/recovery matters | boundary counting, provider overflow, tool pairs, media, archive, and recovery tests |
| Streaming/subgraph UI | application event envelope that adds parent/child/task lineage | normalized golden event trace with parallel child success/failure and backpressure |
| Rubric revision | `pydantic_graph` or durable application loop with typed rubric state | fail/revise/pass, max iterations, grader failure, resume, usage, and telemetry |
| Fallback behavior | configured `FallbackModel` when compatible; otherwise an application model-call wrapper | eligible/noneligible errors, pre-byte/mid-stream, tools, structured output, and usage tests |
| Deployment/thread runtime | application API/queue/workflow adapter around `Agent.run` | duplicate delivery, mid-run message, worker loss, restart, idempotency, and identity mapping |

If the target proof cannot be written, leave parity `unknown`; do not call the Pydantic AI pattern validated.

## Validation template

Use one parametrized contract fixture so source and target execute the same assertion:

```python
@pytest.mark.parametrize('implementation', [source_adapter, target_adapter])
async def test_contract(implementation):
    observed = await implementation.run(fixture)
    assert observed.output == expected_output
    assert observed.state == expected_state
    assert observed.effects == expected_effects
    assert observed.resume_point == expected_resume_point
```

When exact parity is neither possible nor desirable, split the assertion:

- shared invariant: must pass on both;
- target improvement: explicit intentional change;
- source-only artifact: UI or transcript adapter if consumers still require it.

## Version discipline

The assets use public Pydantic AI APIs: `Agent`, `RunContext`, `FunctionToolset`, `AbstractCapability`, model request hooks, deferred tools, and typed outputs. They avoid private `_state`, `_toolset`, `_capability`, and `pydantic_ai._*` modules.

Harness capability locations have changed across revisions, including moves under `experimental`. Inspect the installed checkout and pin the version before copying any Harness-specific import. Re-run the asset tests and the project's cross-framework contract tests after every Pydantic AI, Harness, provider, or model upgrade.
