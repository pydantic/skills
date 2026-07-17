# Spike Evidence Manifest

This manifest records the research baseline behind `SEMANTIC-DELTAS.md`. It is version-specific evidence, not a promise about the application's locked dependencies.

## Baseline

| Project | Revision |
|---|---|
| Deep Agents 0.6.12 | `e821d3d` |
| Pydantic AI | `2a4d7c2` |
| Pydantic AI Harness | `73513a6` |

All probes were offline with fake/test models and disposable files. No provider calls or external side effects were used.

## Deep Agents checks

The focused upstream tests were run from the Deep Agents checkout in an isolated editable environment:

```bash
python -m pytest -q \
  libs/deepagents/tests/unit_tests/test_graph.py::TestSystemPromptAssembly::test_triple_combo_all_three_inputs \
  libs/deepagents/tests/unit_tests/test_graph.py::TestSystemPromptAssembly::test_empty_string_base_system_prompt_replaces_with_empty \
  libs/deepagents/tests/unit_tests/test_subagents.py::TestSubAgents::test_structured_response_serialized_as_tool_message \
  libs/deepagents/tests/unit_tests/test_subagents.py::TestSubAgents::test_structured_response_pydantic_serialized_as_tool_message
```

Observed result: `4 passed`. The prompt assertion was caller prefix → selected base → profile suffix; an empty profile base replaced the SDK base. The child assertions confirmed JSON tool-message serialization for dictionaries and Pydantic models.

The planning contrast used these focused tests:

```bash
# Deep Agents: both competing writes are rejected and no todos are stored.
python -m pytest -q \
  libs/deepagents/tests/unit_tests/test_todo_middleware.py::TestTodoMiddleware::test_todo_middleware_rejects_multiple_write_todos_in_same_message

# Harness: a write replaces plan state; multiple in-progress items produce a note.
python -m pytest -q \
  tests/planning/test_planning.py::TestPlanningToolset::test_write_plan_replaces_state \
  tests/planning/test_planning.py::TestPlanningToolset::test_write_plan_warns_on_multiple_in_progress
```

Observed results: `1 passed` in Deep Agents and `2 passed` in Harness.

Direct in-memory probes called the real task tool and state backends with fake child runnables. Preserve these assertions when turning the spike into application tests:

| Probe | Observed assertion |
|---|---|
| Child file write | `/new.txt` appeared in parent files. |
| Child file delete | Deleting `/a.txt` in the child did not remove it from parent files. |
| Additive reducer | Parent `['parent']` plus child full value `['parent', 'child']` became `['parent', 'parent', 'child']`. |
| Shallow state copy | In-place child mutation changed the parent list without returning the field. |
| Structured dictionary/dataclass/Pydantic | Parent tool content was JSON. |
| Structured string | Parent tool content was the JSON string `"raw"`, not raw text. |
| Non-JSON-native dictionary | A `datetime` value raised `TypeError`. |
| StateBackend without checkpoint | The next invocation could not read `/p.txt`. |
| StateBackend with same checkpoint thread | The next invocation read `persist`. |

These direct probes are `spike-observed`, not `regression-locked`: discard the research probe and rewrite only the lasting assertion in the migrated project's test suite.

## Harness checks

The following upstream tests were run against the pinned Harness checkout:

```bash
python -m pytest -q \
  tests/dynamic_workflow/test_dynamic_workflow.py::test_structured_output_arrives_as_dict \
  tests/dynamic_workflow/test_dynamic_workflow.py::test_print_only_returns_output_dict \
  tests/dynamic_workflow/test_dynamic_workflow.py::test_print_with_result_returns_both \
  tests/filesystem/test_filesystem.py::TestPathSecurity::test_symlink_escape \
  tests/step_persistence/test_step_persistence.py::TestContinueAndForkRun::test_continue_run_returns_snapshot_messages
```

Observed result: `6 passed` because one selected test was parametrized. Direct offline probes added these distinguishing assertions:

Model routing contrast: `test_inherit_model_runs_sub_agents_on_parent_run_model`, `test_inherit_model_off_keeps_sub_agent_bound_model`, and `TestModelInheritance::test_disk_agent_inherits_parent_model` all passed (`3 passed`), confirming that inheritance is explicit and differs by child construction path.

| Probe | Observed assertion |
|---|---|
| `SubAgents` Pydantic child | Parent received `answer=7 note='seven'` from `str(result.output)`, not JSON or the model instance. Source path: `pydantic_ai_harness/subagents/_toolset.py`. |
| DynamicWorkflow expression only | Returned the expression value directly. |
| DynamicWorkflow print only | Returned `{'output': 'hello\n'}`. |
| DynamicWorkflow print + expression | Returned both `output` and `result`. |
| DynamicWorkflow neither | Returned `{}`. Source path: `pydantic_ai_harness/dynamic_workflow/_toolset.py::_workflow_result`. |
| FileSystem lifecycle | A new FileSystem instance over the same root read the host-persisted file. |
| FileSystem containment | Traversal, absolute escape, and an in-root symlink to outside were rejected. |
| StepPersistence mid-tool interruption | The effect ledger retained `tool_call_started`; continuation returned the previous provider-valid message snapshot, not arbitrary run state. |
| Static approval flag inside Code Mode | The wrapped tool body ran and the external denial handler was not called. |
| Explicit `ApprovalRequired` inside Code Mode | The handler ran and denial surfaced through `run_code` as `ModelRetry`. Source coverage: `tests/code_mode/test_code_mode.py::TestCodeMode::test_handler_denial_surfaces_as_model_retry`. |

The Code Mode static-flag result is deliberately documented as a pinned probe rather than a public contract. Re-run it on the installed version before placing any guarded tool behind Code Mode.

Minimal discriminating input: construct an agent with `CodeMode` and a `HandleDeferredToolCalls` handler that always denies; register a counter-incrementing `@agent.tool_plain(requires_approval=True)`; have a `FunctionModel` call `run_code` with `await guarded()`; assert `tool_calls == 1` and `handler_calls == 0`. Repeat with the tool body raising `ApprovalRequired`; assert `tool_calls == 1`, `handler_calls == 1`, and the `run_code` result is a denial `ModelRetry`.

## Evidence limits

- Upstream tests confirm their own contracts, not source-to-target parity.
- Direct probes without a checked-in fixture are only `spike-observed`.
- Source inspection is only `source-inspected`.
- A migration reaches `regression-locked` only after its own deterministic tests freeze the chosen behavior.
- Provider/model routing, streaming, cache markers, and production concurrency still require application-specific traces.
