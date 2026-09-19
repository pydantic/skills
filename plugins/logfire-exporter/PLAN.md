# Native Codex Telemetry and Logfire Enrichment

## Goal

Send Codex activity to Logfire using Codex's supported OpenTelemetry exporters.
Use hooks only for conversation fields that native telemetry does not expose.

## Verified Native Surface

Codex 0.151.0 was exercised against a local OTLP/HTTP JSON receiver. Native
telemetry provides:

- `conversation.id`, model, provider, source, and Codex version
- API timing, retries, status, token usage, and time-to-first-token
- tool name, arguments, bounded result previews, duration, and outcome
- permission decisions, sandbox outcomes, hook activity, and startup timing
- logs, traces, and metrics through separate exporters

Native traces carry trace-safe metadata. Native logs additionally include the
authenticated account email, host name, tool arguments, and a tool-result
preview. Raw prompts remain redacted unless `otel.log_user_prompt` is enabled.

## Ownership

### Native Codex OpenTelemetry

Native telemetry owns:

- conversation and trace identity
- lifecycle and API spans
- model and provider metadata
- token accounting
- tool calls, timing, and outcomes
- permission and sandbox events

Do not recreate these records in plugin hooks.

### Logfire Enrichment Hook

The plugin should retain only the smallest hook surface required for fields
missing from native telemetry:

- the final assistant response from `Stop.last_assistant_message`
- optional prompt text when conversation capture is enabled without native log
  export
- Logfire-specific rendering attributes such as `final_result`

Correlate enrichment records with native telemetry using `conversation.id` and
`codex.turn_id`. Do not manufacture a parallel conversation trace or attach a
parent span unless Codex supplies an active W3C trace context to hooks.

## Capture Modes

### Metadata only

- enable the native trace exporter
- keep the native log exporter disabled
- do not install or run enrichment hooks

This is the default. It avoids prompt, assistant, tool, account-email, and host
content while retaining timing, usage, and operational structure.

### Conversation

- enable the native trace exporter
- keep the native log exporter disabled
- use `UserPromptSubmit` and `Stop` only for bounded prompt/final-response
  enrichment
- never capture tool input or output
- redact before applying a 60 KiB UTF-8 limit to each captured prompt or
  response, and enforce a 512 KiB request ceiling with metadata-only fallback

### Full debugging

- enable native traces and logs explicitly
- set `otel.log_user_prompt = true`
- use `Stop` only for the final assistant response
- retain Codex's bounded tool-result preview instead of exporting full results

Full debugging must be an explicit choice. The CLI must explain that native
logs include account email, host name, tool arguments, and tool-result previews.

Metrics remain disabled initially. Their high-cardinality operational series
are useful for fleet monitoring but are not required for the Logfire agent-run
experience and can materially increase ingest volume.

## Configuration Safety

`logfire codex configure` should own the generated Codex OTLP configuration.
It must:

- preserve unrelated `config.toml` content and comments
- refuse to replace an existing non-Logfire OTLP destination without an
  explicit replacement choice
- write atomically with user-only permissions
- never print or pass the project token in subprocess arguments
- report native telemetry and optional enrichment status separately
- remove only settings it owns

Codex currently supports static OTLP headers but no documented keychain or
header-helper command. Until it does, configuration must clearly disclose where
the project write token is stored and avoid claiming keychain-backed storage.

## Migration Sequence

1. Teach `logfire-cli` to configure native traces and validate conflicts.
2. Add Platform fixtures for native `codex.*` logs and traces.
3. Make native events render as Codex conversations and runs.
4. Reduce this plugin to the capture-mode-specific enrichment hooks above.
5. Remove transcript token parsing, tool-span synthesis, deterministic trace
   IDs, and duplicate lifecycle state.

Keep the existing exporter behavior until steps 1-3 are deployable together;
otherwise users would lose the current Codex run view during migration.
