---
name: logfire-ui
description: Open Logfire project pages, live views, and Explore pages in the Codex browser without querying telemetry first. Use this skill when the user asks to "open in Logfire", "show in the live view", "open Explore", "open the UI", "show in Codex", "use the browser", or asks for a Logfire GUI/browser/live-view presentation of a project, time range, service, span, trace, log, or filter.
---

# Open Logfire UI

Use this skill for direct Logfire UI, browser, live-view, and Explore-page requests.

## Core Rule

For project-level or aggregate UI requests, open Logfire directly by URL.

Do not query telemetry first:
- Do not call `query_run`.
- Do not say you will query Logfire or fetch spans first.
- Do not generate a local HTML/SVG report unless the user explicitly asks for a local artifact.

Only query first when the user needs a specific unknown item found before opening the UI, such as "open the slowest trace" or "open the latest error trace".

## URL Workflow

1. If the full project URL is already known, use it directly.
2. If the user gives a project name but not the organization/base URL, call `project_logfire_link(project, "00000000000000000000000000000000")` only to derive the canonical project URL. Strip or replace the dummy `q=trace_id...` parameter. This is a URL discovery helper, not a telemetry query.
3. Add a URL-encoded `q` filter when useful.
4. Add `since` and `until` query parameters when the user gives a concrete time window and you can compute it.
5. If Browser is available, open the URL in the Codex in-app browser. Otherwise, return the URL.

## Common Filters

- Spans: `q=kind%3D%27span%27`
- Logs: `q=kind%3D%27log%27`
- Exceptions: `q=is_exception%3Dtrue`
- Errors: `q=level%3D%27error%27`
- Service: URL-encode a filter such as `service_name='api'`

## Example

For "open the Logfire live view for spans in starter-project for the last hour in Codex":

1. Open the known or derived `starter-project` Logfire URL directly.
2. Add `q=kind%3D%27span%27`.
3. Add `since=<one-hour-ago>` and `until=<now>`.
4. Open the URL in Codex Browser.
5. Do not run SQL first.

## Auth Boundary

Do not try to pass MCP auth tokens into the browser or Logfire UI. MCP/tool authentication and browser web sessions are separate security contexts. If the browser asks for Logfire login, the user must authenticate normally. Subsequent URLs should reuse the browser session cookie.
