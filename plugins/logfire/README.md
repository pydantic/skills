# logfire

Add [Logfire](https://logfire.pydantic.dev/) observability to Python applications.

## Features

- `/instrument` - detect frameworks and add Logfire instrumentation
- `/debug` - investigate errors using Logfire traces via MCP
- `/query` - query traces, logs, and metrics interactively or add query capabilities to code
- `logfire-ui` skill - open Logfire project pages, live views, traces, and Explore filters directly in Codex
- Activity report POC - render trace volume, error buckets, p95 latency, and top services as a local HTML GUI, Codex inline widget, or SVG report
- SKILL.md with core Logfire patterns (configure, instrument, structured logging, AI/LLM instrumentation)
- MCP servers for querying Logfire data and rendering local activity widgets

## Install In Claude Code

```bash
claude plugin marketplace add pydantic/skills
claude plugin install logfire@pydantic-skills
```

The Claude plugin provides `/instrument`, `/debug`, `/query`, and the Logfire MCP server.

## Install In Codex

From the repository root, add the local Pydantic marketplace:

```bash
codex plugin marketplace add /absolute/path/to/pydantic/skills
```

Then enable **Logfire** from the Codex plugin UI. The Codex plugin metadata lives in `.codex-plugin/plugin.json` and configures:

- display name **Logfire**
- category **Coding**
- capabilities **Interactive** and **Write**
- Logfire icon and pink brand color
- Logfire skills for instrumentation, querying, and UI-opening workflows
- MCP servers from `.mcp.json`

For local development after changing this plugin, refresh the Codex plugin cache:

```bash
./scripts/reload-codex-plugin.sh logfire
```

A new Codex conversation may be required for updated skills, MCP servers, icons, or metadata to load.

## MCP

The Logfire MCP server is configured automatically when you install the plugin (US region). EU users can switch by running:

```
claude mcp add logfire --transport http https://logfire-eu.pydantic.dev/mcp
```

In Codex, `.mcp.json` configures:

- `logfire` - hosted HTTP MCP server at `https://logfire-us.pydantic.dev/mcp`
- `logfire-activity-render` - local stdio MCP server for inline widgets and HTML reports

The Logfire MCP server requires normal Logfire authentication, such as `logfire auth` or a suitable `LOGFIRE_TOKEN`.

## Codex Render Tool POC

The Codex plugin includes a local stdio MCP server that exposes:

- `logfire_render_sparkline` - render a quick inline widget from plain trace-count values
- `logfire_render_activity_card` - render a widget from bucketed Logfire query rows plus optional top services
- `logfire_render_activity_report` - write a self-contained HTML report and return a localhost URL

The widget resource is `ui://logfire/activity-card.html` and is served with the MCP Apps MIME type `text/html;profile=mcp-app`.

Smoke-test the local MCP server:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"logfire_render_sparkline","arguments":{"values":[0,0,0,14,14],"title":"Span count","window":"30m","bucket":"5m"}}}' \
  | python3 plugins/logfire/scripts/logfire_activity_mcp.py
```

After changing `.mcp.json`, reload the plugin in Codex before testing from chat.

Smoke-test the HTML report tool:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"logfire_render_activity_report","arguments":{"values":[0,0,0,14,14],"title":"Starter project trace activity","window":"30m","bucket":"6m","filename":"starter-project-trace-activity.html","serve":false}}}' \
  | python3 plugins/logfire/scripts/logfire_activity_mcp.py
```

When Codex runs the MCP server, the server process stays alive for the session, so the tool can also return a localhost URL while that MCP server is running.

## SVG Activity Card Fallback

Render a sample activity card locally:

```bash
python3 plugins/logfire/scripts/render_activity_card.py \
  --input plugins/logfire/examples/activity-card/sample.json \
  --output /tmp/logfire-activity.svg \
  --print-markdown
```

Use the printed Markdown image path in Codex to preview the SVG.

Render an ad hoc sparkline from known bucket counts:

```bash
plugins/logfire/scripts/render_activity_card.py \
  --values "0,0,0,0,14,14" \
  --title "Logfire span-count sparkline" \
  --window "30m" \
  --bucket "5m" \
  --output /tmp/logfire-sparkline.svg \
  --print-markdown
```

## HTML Activity Report POC

Render a small local GUI report from the sample payload:

```bash
python3 plugins/logfire/scripts/render_activity_report.py \
  --input plugins/logfire/examples/activity-card/sample.json \
  --output /tmp/logfire-activity-report.html \
  --print-path
```

Open the printed HTML file in a browser. The report is self-contained and includes metric toggles, hoverable chart points, service rows, quick findings, and sample trace IDs.

For the Codex in-app browser, serve the output over localhost:

```bash
python3 -m http.server 8123 --directory /tmp
```

Then open `http://127.0.0.1:8123/logfire-activity-report.html`.
