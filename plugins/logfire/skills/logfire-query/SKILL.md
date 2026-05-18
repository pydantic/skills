---
name: logfire-query
description: Query Logfire telemetry data — traces, logs, spans, and metrics. Use this skill when the user asks to "query logfire", "search traces", "find logs", "query data", "search spans", "look up errors in logfire", "get metrics from logfire", "analyze telemetry", or wants to add Logfire querying capabilities to their code. Also use when the user wants to explore OpenTelemetry data, investigate production issues by querying, or build dashboards/reports from Logfire data.
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
