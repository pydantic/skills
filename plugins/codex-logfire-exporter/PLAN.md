# Codex Logfire Exporter Plan

## Goal

Build a Codex hook plugin that captures a Codex conversation as Logfire traces without depending on a reliable session-end event.

The plugin should export completed work as bounded OpenTelemetry spans directly to Logfire's OTLP endpoint. It should not use the Logfire SDK or the OpenTelemetry SDK for span creation.

## Design Decisions

### Prior Art

The Grafana Sigil Codex plugin takes the same basic lifecycle stance:

- it registers `SessionStart`, `UserPromptSubmit`, `PostToolUse`, and `Stop`
- it stores lightweight local fragments before `Stop`
- it exports one completed generation on `Stop`
- it treats interrupted turns without `Stop` as non-exported and cleans stale state later

It does not solve session-end root-span closure; it avoids needing a session root span. See:

- <https://github.com/grafana/sigil-sdk/blob/main/plugins/codex/hooks/hooks.json>
- <https://github.com/grafana/sigil-sdk/blob/main/plugins/codex/internal/hook/handlers.go>
- <https://github.com/grafana/sigil-sdk/blob/main/plugins/codex/README.md>

This plugin follows the same lifecycle boundary, but differs in trace identity: completed turns for one Codex
conversation/thread share a deterministic trace ID. The hook `session_id` remains an important correlation attribute, but
it is not always the right identity for the whole visible conversation.

### Conversation Trace Identity

Use a Codex conversation identity to derive a stable OpenTelemetry trace ID:

```text
trace_id = sha256("codex-logfire-exporter:trace:v1\0" + conversation_id)[:16]
```

The resulting 16 bytes are encoded as 32 lowercase hex characters. If the result is all zeroes, replace it with a fixed non-zero fallback derived from the same input plus `":nonzero"`.

The trace identity is selected in this order:

```text
payload.root_thread_id
payload.root_session_id
payload.conversation_id
payload.thread_id
env.CODEX_THREAD_ID
payload.session_id
```

This means every exported span for the same Codex thread/conversation lands in the same trace when Codex exposes that
identity. If only hook `session_id` is available, the plugin falls back to the older one-session/one-trace behavior. The
selected value is stored as `codex.conversation_id`, `codex.trace_source` records where it came from, and the raw hook
session ID is still stored as `codex.session_id` for querying.

### No Session Root Span

Do not emit a session/root span.

Codex hooks do not provide a reliable session-end event, and `Stop` is a completed-turn event, not a conversation-close event. Emitting a root span at `SessionStart` would create a misleading closed span with startup-only duration, while keeping a pending span would require an end event we do not have.

Instead, each completed turn is a root-level span inside the deterministic conversation trace. Logfire can display rootless/multi-root traces by promoting the first visible span for the trace. The trace represents the conversation; the spans represent completed work inside it.

### Direct OTLP Export

Do not use `logfire`, the OpenTelemetry SDK, or span processors.

Emit OTLP HTTP/protobuf or OTLP HTTP/JSON directly to Logfire. The first implementation should prefer OTLP HTTP/JSON for simpler implementation and easier debugging, unless payload size or compatibility pushes us to protobuf.

Configuration:

```text
LOGFIRE_TOKEN=<write token>
LOGFIRE_URL=https://logfire-api.pydantic.dev
```

The trace export endpoint is:

```text
{LOGFIRE_URL}/v1/traces
```

Use `Authorization: <LOGFIRE_TOKEN>` by default, matching Logfire's direct OTLP client configuration. Allow `CODEX_LOGFIRE_AUTH_SCHEME=Bearer` for collector-style setups that need a scheme-prefixed header.

Resource attributes should be emitted in the OTLP `resourceSpans.resource.attributes` block. Span-specific attributes stay on each span.

### Transcript Parsing

Codex transcript parsing is not required for the basic trace structure:

- `session_id`, `turn_id`, `cwd`, `model`, and `transcript_path` come from common hook fields
- `prompt` comes from `UserPromptSubmit`
- supported tool calls come from `PostToolUse`
- the final assistant text comes from `Stop.last_assistant_message`

However, transcript parsing is still needed for higher-fidelity telemetry that hook payloads do not currently expose:

- token usage, because Codex hook payloads do not include token counts
- subagent parent/child linkage, because current hook payloads do not expose stable parent session or parent turn metadata
- recovery from missed/interleaved hook payload details, when the rollout file has a more complete record than the hooks
- future richer reconstruction of multiple model sampling calls inside one completed turn

Keep this parser smaller than the Claude plugin parser. Parse the Codex rollout JSONL only at `Stop`, only for the current `turn_id`, and fail open if the file is missing, oversized, malformed, or has an unknown shape. A failed transcript parse should never block exporting the turn span.

## Hook Model

Register these Codex hooks:

```text
SessionStart
UserPromptSubmit
PostToolUse
Stop
```

`SessionStart` stores session-scoped metadata only:

- `session_id`
- selected conversation/thread identity
- `cwd`
- `model`
- `source`
- `transcript_path`
- first-seen timestamp

`UserPromptSubmit` creates or updates a per-turn fragment:

- `session_id`
- `turn_id`
- prompt text if content capture is enabled
- inherited session metadata
- started timestamp

`PostToolUse` appends tool records to the turn fragment:

- tool name
- tool call/use ID when available
- input/output only if content capture is enabled
- status/error evidence
- completion timestamp
- duration when available

`Stop` is the export boundary:

- stamp the turn completion timestamp
- capture `last_assistant_message` if content capture is enabled
- read token usage from Codex rollout JSONL when `transcript_path` is available
- emit one turn span and any child tool spans
- flush the direct OTLP request
- delete the completed turn fragment on success

Interrupted turns that never receive `Stop` are not exported. Stale local fragments are cleaned up later.

## Span Shape

### Turn Span

Each completed Codex turn exports one root-level span in the session trace.

```text
trace_id: deterministic from selected conversation_id
span_id: sha256("codex-logfire-exporter:turn-span:v1\0" + session_id + "\0" + turn_id)[:8]
parent_span_id: omitted
name: "codex turn"
start_time_unix_nano: first timestamp for the turn
end_time_unix_nano: Stop timestamp
kind: internal
status: ok unless export/mapping detects a turn-level error
```

Important attributes:

```text
codex.conversation_id = <selected conversation/thread identity>
codex.trace_source = <payload/env/fallback source>
codex.session_id = <session_id>
codex.turn_id = <turn_id>
codex.cwd = <cwd>
codex.source = <source>
codex.model = <model>
gen_ai.system = "codex"
gen_ai.operation.name = "chat"
gen_ai.request.model = <model>
gen_ai.response.model = <model>
gen_ai.response.finish_reasons = ["stop"]
gen_ai.usage.input_tokens = <input tokens, when known>
gen_ai.usage.output_tokens = <output tokens, when known>
gen_ai.usage.total_tokens = <total tokens, when known>
logfire.msg = <human-readable Codex turn summary>
logfire.span_type = "span"
logfire.level_num = 9
logfire.tags = ["Codex"] plus ["LLM"] when conversation content is present
codex.prompt.length = <prompt character count, when known>
codex.response.length = <assistant character count, when known>
```

Important resource attributes:

```text
service.name = "codex-logfire-exporter"
telemetry.sdk.name = "codex-logfire-exporter"
telemetry.sdk.language = "python"
```

Prompt, assistant text, and tool content are enabled by default because the product requirement is full conversation
capture for analytics and improvement. Content is redacted before export. `CODEX_LOGFIRE_CONTENT_CAPTURE_MODE` is an
optional suppression switch:

```text
full            default; prompt, final assistant message, tool inputs, tool outputs, and tool errors
no_tool_content prompt and final assistant message only
metadata_only   no prompt, assistant, tool input, or tool output content
```

With `CODEX_LOGFIRE_CONTENT_CAPTURE_MODE=no_tool_content` or `full`, turn spans also include
`pydantic_ai.all_messages`, `final_result`, and `logfire.json_schema` so Logfire can render the standard LLM
conversation/details panel. The dedicated Claude Code session panel is Logfire UI-specific and keyed to Claude Code
records, so Codex should use the generic LLM panel unless/until Logfire adds a Codex-specific session view.

### Tool Spans

Each captured tool call exports a child span under the turn span.

```text
trace_id: same deterministic conversation trace ID
span_id: sha256("codex-logfire-exporter:tool-span:v1\0" + session_id + "\0" + turn_id + "\0" + tool_key)[:8]
parent_span_id: turn span ID
name: "codex tool <tool_name>"
start_time_unix_nano: completed_at - duration, when duration is available; otherwise completed_at
end_time_unix_nano: completed_at
kind: internal
status: error when tool status/error evidence indicates failure, otherwise ok
```

Important attributes:

```text
codex.session_id = <session_id>
codex.turn_id = <turn_id>
gen_ai.operation.name = "execute_tool"
gen_ai.tool.name = <tool_name>
gen_ai.tool.call.id = <tool call/use ID, when available>
logfire.msg = <human-readable tool summary>
logfire.span_type = "span"
logfire.level_num = 9 or 17
logfire.tags = ["Codex"]
codex.tool.status = <normalized status>
codex.tool.success = <bool>
error.type = <tool error type, when known>
```

## Local State

Store hook state under:

```text
${XDG_STATE_HOME:-~/.local/state}/codex-logfire-exporter
```

Use separate directories for:

```text
sessions/
turns/
logs/
```

State files must be written atomically with `0600` permissions. Use file locks around per-session and per-turn updates because Codex may run matching hooks concurrently.

Turn files should be deleted after successful export. Stale session and turn files older than 24 hours should be removed opportunistically on later hook invocations.

## Relationship To Native Codex OTel

Native Codex OTel can be enabled independently, but this plugin should not try to merge with native Codex spans unless Codex starts passing W3C trace context to hooks.

For now, native Codex OTel and this plugin's direct OTLP export are correlated by attributes such as `codex.session_id`, `codex.turn_id`, model, and cwd. They are not expected to share trace parentage.

Avoid duplicating the same semantic events in both systems. The plugin owns conversation/turn/tool spans intended for Logfire's agent view; native Codex OTel can remain useful for Codex internal operational telemetry.

## Open Questions

- Whether to export OTLP JSON first or use generated protobuf messages from the start.
- Exact Logfire endpoint defaults for local development versus production.
- Final content-capture modes and redaction rules.
- Whether to emit OTel events on the turn span for prompt/assistant summaries instead of span attributes.
- How much of Codex rollout JSONL should be parsed beyond token counts.
