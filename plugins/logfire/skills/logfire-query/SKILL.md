---
name: logfire-query
description: Query and visualize Logfire telemetry data — traces, logs, spans, metrics, sparklines, activity cards, and inline charts. Use this skill when the user asks to "query logfire", "search traces", "find logs", "query data", "search spans", "look up errors in logfire", "get metrics from logfire", "analyze telemetry", "show a sparkline", "render an activity card", or wants to add Logfire querying capabilities to their code. Do not use this skill for direct Logfire UI, browser, live-view, or Explore-page opening requests; use the logfire-ui skill instead.
---

# Query Logfire Data

## When to Use This Skill

Invoke this skill when:
- User wants to query traces, logs, spans, or metrics from Logfire
- User wants to search for specific events, errors, or patterns in telemetry data
- User wants to analyze OpenTelemetry data stored in Logfire
- User wants to add programmatic query capabilities to their code
- User asks to "query logfire", "search traces", "find logs", "get metrics"
- User wants to build reports or dashboards from Logfire data

## Critical Routing: GUI and Live View Requests

Before using any query tool, classify the request.

If the user asks to "open", "show in Codex", "show in Logfire", "show in the live view", "open Explore", "open the UI", "use the browser", or asks for a GUI/browser/live-view presentation for a project-level filter, treat it as a URL-opening task, not a data-query task.

For those live-view requests:
- Do **not** say you will query Logfire, use the query workflow, or fetch telemetry first.
- Do **not** call `query_run`.
- Build or derive the Logfire project URL, add URL parameters, and open it in the browser.
- Use `project_logfire_link(project, "00000000000000000000000000000000")` only when the full project URL is unknown. This is a URL discovery helper, not a telemetry query.
- Continue to the MCP query workflow only when the user asks for a computed answer in chat, a local chart/report, or a specific trace/error/span that must be found first.

Example for "open the Logfire live view for spans in starter-project for the last hour in Codex":
- Open the known or derived `starter-project` Logfire URL directly.
- Add `q=kind%3D%27span%27`.
- Add `since` and `until` for the last-hour window if available.
- Do not run SQL first.

## Two Approaches

| Aspect | MCP `query_run` | REST API `/v1/query` |
|--------|-----------------|----------------------|
| **Best for** | Interactive exploration in Claude | Adding query code to a project |
| **Auth** | OAuth via MCP session | Bearer read token |
| **Setup** | Already configured via plugin | Need a read token |
| **Formats** | JSON rows | JSON, CSV, Apache Arrow |
| **Default window** | Last 30 min | Last 24 hours |
| **Max range** | 14 days | 14 days |
| **Row limit** | Must be in SQL | Default 500, max 10,000 |

## Quick Schema Reference

### `records` table (spans and logs)

Key columns for querying:

| Column | Type | Description |
|--------|------|-------------|
| `start_timestamp` | timestamp (UTC) | When span/log was created |
| `end_timestamp` | timestamp (UTC) | When span/log completed |
| `duration` | double (seconds) | Time between start and end; NULL for logs |
| `trace_id` | string (32 hex) | Unique trace identifier |
| `span_id` | string (16 hex) | Unique span identifier |
| `parent_span_id` | string (16 hex) | Parent span; NULL for root spans |
| `span_name` | string | Low-cardinality label for similar records |
| `message` | string | Human-readable description with arguments filled in |
| `level` | integer | Severity (supports `level = 'error'` string comparison) |
| `kind` | string | `span`, `log`, `span_event`, or `pending_span` |
| `service_name` | string | Service identifier |
| `is_exception` | boolean | Whether an exception was recorded |
| `exception_type` | string | Exception class name |
| `exception_message` | string | Exception message |
| `exception_stacktrace` | string | Full traceback |
| `attributes` | JSON | Structured data; query with `->>'key'` |
| `tags` | string[] | Grouping labels; query with `array_has(tags, 'x')` |
| `http_response_status_code` | integer | HTTP status code |
| `http_method` | string | HTTP method |
| `http_route` | string | HTTP route pattern |
| `otel_status_code` | string | Span status |

### `metrics` table

| Column | Type | Description |
|--------|------|-------------|
| `recorded_timestamp` | timestamp (UTC) | When metric was recorded |
| `metric_name` | string | Metric name |
| `metric_type` | string | Type (gauge, counter, histogram) |
| `unit` | string | Unit of measurement |
| `scalar_value` | double | Metric value |
| `service_name` | string | Service identifier |
| `attributes` | JSON | Metric dimensions |

Full schema: [`references/schema.md`](./references/schema.md)

## SQL Syntax

Logfire uses **Apache DataFusion** (Postgres-like). Key patterns:

```sql
-- Time filtering
WHERE start_timestamp > now() - interval '1 hour'

-- JSON attribute access
WHERE attributes->>'user_id' = '123'
SELECT attributes->>'http.url' as url FROM records

-- Nested JSON
attributes->'request'->>'method'

-- Array filtering
WHERE array_has(tags, 'production')

-- Level filtering (string comparison works)
WHERE level = 'error'

-- Case-insensitive matching
WHERE message ILIKE '%timeout%'

-- Time bucketing for aggregation
SELECT time_bucket(interval '5 minutes', start_timestamp) as bucket,
       count(*) FROM records GROUP BY bucket ORDER BY bucket
```

## MCP Approach (Interactive)

Call the `query_run` MCP tool:
- `query` (required): SQL query string
- `project` (optional): target project (default: user's current project)
- `min_timestamp` / `max_timestamp` (optional): ISO timestamps for time window

Default window is last 30 min. Max range is 14 days. Always include `LIMIT` in SQL.

### Common queries

```sql
-- Recent errors
SELECT start_timestamp, message, exception_type, exception_message
FROM records WHERE is_exception LIMIT 20

-- Slow spans
SELECT span_name, duration, start_timestamp
FROM records WHERE duration > 1.0 ORDER BY duration DESC LIMIT 20

-- Endpoint errors
SELECT start_timestamp, message, http_response_status_code
FROM records WHERE http_route = '/api/users' AND level = 'error' LIMIT 20

-- Full trace
SELECT span_name, message, duration, parent_span_id
FROM records WHERE trace_id = '<id>' ORDER BY start_timestamp

-- Error breakdown by service
SELECT service_name, count(*) as errors
FROM records WHERE is_exception GROUP BY service_name ORDER BY errors DESC
```

## Logfire UI Live View

Use this workflow when the user asks for a GUI, browser view, live view, Logfire UI, Explore page, or asks to "show" telemetry visually in Codex. Prefer the real Logfire UI over generated local reports.

1. For project-level or aggregate requests, do **not** query Logfire just to build a UI link. Go straight to a Logfire URL.
2. If the full project URL is already known, construct the Logfire URL directly from it without using any tool.
3. If the user gives a project but not an organization/base URL, call `project_logfire_link(project, "00000000000000000000000000000000")` only to derive the canonical project URL. Strip or replace the dummy `q=trace_id...` parameter; do not present it as a real trace. This is a link helper call, not a telemetry query.
4. Open the project live view with a URL-encoded `q` filter when useful, for example `q=kind%3D%27span%27`. Add `since`/`until` when the time window is concrete and available. These parameters are accepted by Logfire UI links generated by `project_logfire_link`.
5. If the request is about a specific trace, error, exception, endpoint example, slow span, or a row already known to have a `trace_id`, call `project_logfire_link(project, trace_id)` to generate the exact Logfire UI link.
6. If the user asked to render/open it in Codex and Browser is available, open the Logfire UI link in the Codex in-app browser. Otherwise, return the link.
7. Only use `query_run` before opening the UI when the user asked for a computed answer in chat, a specific trace must be found, or the direct project/filter URL is insufficient.
8. Do not try to pass MCP auth tokens into the browser or Logfire UI. MCP/tool authentication and browser web sessions are separate security contexts; if the browser asks for Logfire login, the user must authenticate normally. Subsequent URLs should reuse the browser session cookie.
9. Only fall back to `logfire_render_activity_report`, local HTML, or SVG when the user explicitly asks for a local artifact, no relevant Logfire UI link can be produced, or the browser cannot open Logfire.

For the previous span-count activity prompt, open the project live view directly with a filter like `kind='span'`. Also provide this SQL only if the user wants an aggregate query to paste into Explore:

```sql
SELECT
  time_bucket(interval '5 minutes', start_timestamp) AS bucket,
  count(*) AS span_count
FROM records
WHERE kind = 'span'
GROUP BY bucket
ORDER BY bucket
LIMIT 200
```

## Activity Card and Report POC

Use this workflow when the user asks for an inline chart, sparkline, visual report, activity summary, trace-count chart, error-count chart, or a graphical Logfire POC.

First consider the Logfire UI Live View workflow above. Use generated activity cards or reports only when the user asks for a local artifact or when opening Logfire UI is not practical.

1. Query Logfire for bucketed activity.
2. Save or shape the result as JSON.
3. If the user asks for a GUI, dashboard, browser report, or richer visual report, prefer the `logfire_render_activity_report` MCP tool when available. It writes a local HTML report and returns a localhost URL.
4. If the `logfire_render_activity_card` or `logfire_render_sparkline` MCP tool is available, call that tool to render the inline widget.
5. If the render MCP tool is unavailable or the host does not display widgets, render an SVG fallback with `plugins/logfire/scripts/render_activity_card.py`.
6. If the report MCP tool is unavailable, render an HTML report with `plugins/logfire/scripts/render_activity_report.py`.
7. For SVG fallback output, show the resulting SVG with an absolute Markdown image path. For HTML report output, provide the absolute report path. If previewing in the Codex in-app browser, serve the output over localhost because direct `file://` navigation may be blocked.

Do not answer sparkline or activity-card requests with prose only. If there is already a list of bucket counts, call `logfire_render_sparkline` with those values, or render it directly with `--values` as a fallback. If Logfire query data is available, call `logfire_render_activity_card`, or render the JSON payload with `--input` as a fallback.

### Bucketed activity query

```sql
SELECT
  time_bucket(interval '15 minutes', start_timestamp) AS bucket,
  count(DISTINCT trace_id) AS trace_count,
  sum(
    CASE
      WHEN is_exception OR level = 'error' OR otel_status_code = 'ERROR'
      THEN 1
      ELSE 0
    END
  ) AS error_count,
  approx_percentile_cont(duration, 0.95) * 1000 AS p95_ms
FROM records
WHERE kind = 'span'
GROUP BY bucket
ORDER BY bucket
LIMIT 200
```

Use the MCP or REST query time-window parameters for the actual window, for example the last 24 hours. If the query engine rejects `approx_percentile_cont`, fall back to `max(duration) * 1000 AS p95_ms` for the POC.

### Top services query

```sql
SELECT
  service_name,
  count(DISTINCT trace_id) AS trace_count,
  sum(
    CASE
      WHEN is_exception OR level = 'error' OR otel_status_code = 'ERROR'
      THEN 1
      ELSE 0
    END
  ) AS error_count,
  approx_percentile_cont(duration, 0.95) * 1000 AS p95_ms
FROM records
WHERE kind = 'span'
GROUP BY service_name
ORDER BY error_count DESC, trace_count DESC
LIMIT 5
```

### Expected renderer input

The MCP render tool and SVG renderer both accept a JSON object with `series` and optional `top_services`:

```json
{
  "title": "Logfire activity",
  "window": "24h",
  "bucket": "15m",
  "series": [
    { "bucket": "2026-05-12T10:00:00Z", "trace_count": 42, "error_count": 1, "p95_ms": 180 }
  ],
  "top_services": [
    { "service_name": "api", "trace_count": 482, "error_count": 19, "p95_ms": 730 }
  ]
}
```

Render locally:

```bash
python3 plugins/logfire/scripts/render_activity_card.py \
  --input /tmp/logfire-activity.json \
  --output /tmp/logfire-activity.svg \
  --print-markdown
```

Render a local HTML report:

```bash
python3 plugins/logfire/scripts/render_activity_report.py \
  --input /tmp/logfire-activity.json \
  --output /tmp/logfire-activity-report.html \
  --print-path
```

Render through the local MCP report tool:

```json
{
  "name": "logfire_render_activity_report",
  "arguments": {
    "title": "Logfire activity",
    "window": "24h",
    "bucket": "15m",
    "series": [
      { "bucket": "2026-05-12T10:00:00Z", "trace_count": 42, "error_count": 1, "p95_ms": 180 }
    ],
    "top_services": [
      { "service_name": "api", "trace_count": 482, "error_count": 19, "p95_ms": 730 }
    ]
  }
}
```

For a smoke test without live Logfire data, omit `--input` or use `plugins/logfire/examples/activity-card/sample.json`.

For an ad hoc sparkline from counts already in the conversation:

```bash
plugins/logfire/scripts/render_activity_card.py \
  --values "0,0,0,0,14,14" \
  --title "Logfire span-count sparkline" \
  --window "30m" \
  --bucket "5m" \
  --output /tmp/logfire-sparkline.svg \
  --print-markdown
```

## REST API Approach (Programmatic)

**Endpoint**: `GET https://logfire-api.pydantic.dev/v1/query`

Region variants:
- US: `https://logfire-us.pydantic.dev/v1/query`
- EU: `https://logfire-eu.pydantic.dev/v1/query`

**Auth**: `Authorization: Bearer <read_token>`

**Parameters**:
- `sql` (required): SQL query
- `min_timestamp` / `max_timestamp` (optional): ISO timestamps
- `limit` (optional): row limit (default 500, max 10,000)

**Response formats** (via `Accept` header):
- `application/json` — column-oriented JSON (default)
- `application/json` with `row_oriented=true` param — row-oriented JSON
- `text/csv` — CSV
- `application/vnd.apache.arrow.stream` — Apache Arrow

**Python clients**: `LogfireQueryClient` (sync), `AsyncLogfireQueryClient` (async), `logfire.db_api` (PEP 249 / pandas).

Detailed examples: [`references/client-usage.md`](./references/client-usage.md)

## Query Best Practices

1. **Always LIMIT** — start with 20, increase as needed
2. **Use `min_timestamp`/`max_timestamp` params** for simple time windows instead of SQL `WHERE`
3. **Filter efficiently** — `service_name`, `span_name`, `trace_id`, `is_exception` are fast filters
4. **Use `->>'key'`** for JSON attribute access (returns text); use `->` for nested JSON objects
5. **Avoid `SELECT *`** — select only the columns you need
6. **Max 14-day range** — queries cannot span more than 14 days
