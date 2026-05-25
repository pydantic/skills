---
name: debug
description: Use Logfire traces to investigate errors and debug production issues
---

# /debug

Use the Logfire MCP server to investigate errors and debug issues using real trace data.

If the user only asks to open, view in browser, use the live view, open Explore, or get a Logfire link, use `logfire-ui` instead of this query-first debugging workflow. For ambiguous prompts such as "show recent errors", ask whether they want UI or query analysis first.

## Prerequisites

The Logfire MCP server must be connected (this plugin configures it automatically). The user must have run `logfire auth` or set `LOGFIRE_TOKEN` for their project.

## Workflow

### When the user reports an error in a specific file

1. Call the `find_exceptions_in_file` MCP tool with the file path to get the 10 most recent exceptions from that file.
2. Show the user the exceptions found - include the exception type, message, and when it occurred.
3. If a specific exception is relevant, use `arbitrary_query` to dig deeper into the surrounding trace context.
4. Suggest a fix based on the exception details and trace data.

### When the user asks about general issues or wants debugging analysis

1. Call `get_logfire_records_schema` to understand the available columns and tables.
2. Use `arbitrary_query` to run SQL queries against the OpenTelemetry data. Common queries:
   - Recent errors: `SELECT start_timestamp, message, attributes FROM records WHERE level = 'error' ORDER BY start_timestamp DESC LIMIT 20`
   - Slow operations: `SELECT span_name, duration, start_timestamp FROM records WHERE duration > interval '1 second' ORDER BY duration DESC LIMIT 20`
   - Specific endpoint issues: `SELECT * FROM records WHERE attributes->>'http.route' = '/api/users' AND level = 'error' ORDER BY start_timestamp DESC LIMIT 10`
3. Present findings and suggest fixes.

### When analysis identifies a trace the user wants to share

1. Use the configured Logfire link tool, such as `project_logfire_link(trace_id=trace_id, project=project)`, to generate a shareable URL for that specific trace.
2. Share the link with the user.

## Output format

When presenting debug findings:
- Lead with the most likely root cause
- Include relevant trace/span data as evidence
- Suggest concrete code changes to fix the issue
- Provide a Logfire UI link only when the user asks for one or when linking a specific trace used as evidence
