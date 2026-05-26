# Logfire Exporter

Codex hook plugin that exports completed Codex turns and tool calls to Logfire using direct OTLP HTTP/JSON.

This plugin is separate from the main Logfire plugin:

- `logfire` lets Codex query Logfire data and help instrument applications.
- `logfire-exporter` sends Codex's own activity telemetry to Logfire.

The exporter deliberately does not emit a long-lived session root span. Each completed `Stop` hook exports one
root-level turn span in a deterministic trace derived from the Codex conversation/thread identity; tool spans are
children of that turn span.

## Capabilities

The Codex plugin metadata lives in `.codex-plugin/plugin.json` and configures:

- display name **Logfire Exporter**
- category **Coding**
- capabilities **Read** and **Write**
- transparent SVG icon and Logfire pink brand color
- default prompts for checking hook installation and explaining the trace design
- hook configuration from `hooks/hooks.json`

The installed hooks capture Codex lifecycle events:

| Hook | Purpose |
|------|---------|
| `SessionStart` | Initialize local telemetry state for startup, resume, and clear events |
| `UserPromptSubmit` | Store the submitted prompt and turn metadata |
| `PostToolUse` | Store tool-call results so they can be exported as child spans |
| `Stop` | Export the completed turn and its tool spans to Logfire |

## Install Locally

From the repository root:

```bash
codex plugin marketplace add /absolute/path/to/pydantic/skills
```

Then enable **Logfire Exporter** from the **Pydantic** marketplace in the Codex plugin UI.

After enabling the plugin:

1. Configure `LOGFIRE_TOKEN` in your shell environment or in `${XDG_CONFIG_HOME:-~/.config}/logfire-exporter/config.env`.
2. Restart Codex so hook configuration is loaded.
3. Run `/hooks` if Codex asks you to review or trust the plugin hooks.
4. Complete a new Codex turn; the exporter sends telemetry on the `Stop` hook.

For local development after changing the plugin:

```bash
./scripts/reload-codex-plugin.sh logfire-exporter
```

A new Codex conversation may be required for updated hooks, icons, or metadata to load.

## Configuration

Configure credentials in:

```text
${XDG_CONFIG_HOME:-~/.config}/logfire-exporter/config.env
```

The minimal config is:

```dotenv
LOGFIRE_TOKEN=<your Logfire write token>
```

`LOGFIRE_BASE_URL` defaults to `https://logfire-api.pydantic.dev`. Set it only for another Logfire region or a local
Logfire instance. `LOGFIRE_URL` is still accepted as a compatibility alias, but `LOGFIRE_BASE_URL` takes precedence.

For a local Logfire instance:

```dotenv
LOGFIRE_BASE_URL=http://localhost:3000/
LOGFIRE_TOKEN=pylf_v1_local_zHhcVLNlKY921fl9jkN7vZ6P4gkL9w7h8HVG609xK5ym
CODEX_LOGFIRE_DEBUG=true
```

For compatibility with local pre-release testing, the exporter will also read old config paths when the new config
file does not exist.

The plugin sends `Authorization: <LOGFIRE_TOKEN>`, matching Logfire's direct OTLP client configuration. If you need a
scheme-prefixed header, set `CODEX_LOGFIRE_AUTH_SCHEME=Bearer`.

The exporter writes directly to Logfire's OTLP HTTP endpoint. It does not use the Logfire SDK or the OpenTelemetry SDK,
which lets it control deterministic trace IDs and span IDs derived from Codex conversation metadata.

## Trace Identity

Trace IDs are deterministic. The exporter chooses the trace identity in this order:

- hook payload root/thread fields, if Codex exposes them
- `CODEX_THREAD_ID`, when present in the hook environment
- hook `session_id` as the fallback

The selected value is exported as `codex.conversation_id`, while the hook `session_id` is exported separately as
`codex.session_id`.

## Content Capture

By default the plugin uses `CODEX_LOGFIRE_CONTENT_CAPTURE_MODE=full`, so it exports redacted prompt text, final
assistant text, tool inputs, tool outputs, and tool errors.

To suppress captured content, set a narrower mode:

```dotenv
CODEX_LOGFIRE_CONTENT_CAPTURE_MODE=metadata_only
```

Capture modes:

- `full`: default; includes redacted user prompt, final assistant message, tool input/output, and tool errors.
- `no_tool_content`: includes redacted user prompt and final assistant message, but not tool input/output.
- `metadata_only`: no prompt, assistant, tool input, or tool output content.

The current plugin emits standard Logfire/OTel spans plus `pydantic_ai.all_messages` when content capture is enabled,
which lets Logfire show Codex turns in the generic LLM conversation/details panel.

## Relationship To The Logfire Plugin

Install `logfire-exporter` when you want telemetry about Codex itself. Install `logfire` when you want Codex to
help instrument applications, query existing Logfire data, or open Logfire UI views.
The two plugins can be enabled together.

## Troubleshooting

Debug logs are written under:

```text
${XDG_STATE_HOME:-~/.local/state}/logfire-exporter/logs/
```

If no spans or plugin logs appear after a completed Codex turn, check the Codex TUI log:

```bash
rg -n "logfire-exporter|failed to load plugin" ~/.codex/log/codex-tui.log
```

## Test

From the repository root:

```bash
python3 -m unittest discover -s plugins/logfire-exporter/tests
```
