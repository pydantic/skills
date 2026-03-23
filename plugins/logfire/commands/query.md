---
name: query
description: Query Logfire telemetry data interactively or add query capabilities to code
---

# /query

Help users query traces, logs, and metrics from Logfire. Supports two approaches: interactive querying via the MCP server, or adding programmatic query capabilities to code.

## Prerequisites

One of the following:
- **MCP**: Logfire MCP server connected (this plugin configures it automatically). User must have run `logfire auth` or set `LOGFIRE_TOKEN`.
- **REST API**: A Logfire read token (created via the Logfire UI or `logfire read-tokens create`).

## Workflow

### Determine the approach

Ask the user what they need:
1. **Explore data interactively** — they want to search traces, investigate issues, or understand their telemetry. Use MCP.
2. **Add querying to code** — they want their application to query Logfire programmatically. Use the REST API / Python client.

If unclear, default to interactive (MCP) since it requires no extra setup.

---

### Interactive querying (MCP)

1. **Understand what the user is looking for.** Ask clarifying questions if needed: time range, service name, error type, endpoint, trace ID, etc.

2. **Formulate the SQL query.** Use Apache DataFusion SQL (Postgres-like). Always follow these rules:
   - Always include `LIMIT` (start with 20, increase if needed)
   - Filter by `start_timestamp` for time ranges: `start_timestamp > now() - interval '1 hour'`
   - Filter by `service_name`, `span_name`, or `trace_id` when possible for efficiency
   - Use `min_timestamp` / `max_timestamp` params instead of SQL `WHERE` for time filtering when the window is simple
   - Access JSON attributes with `->>'key'` operator

3. **Call `query_run`** with the SQL query. Optional params:
   - `project`: target a specific project (default: user's current project)
   - `min_timestamp` / `max_timestamp`: ISO timestamps for time window (default: last 30 min, max range: 14 days)

4. **Present results clearly.** Format as a table or summary. Highlight key findings.

5. **Iterate.** Offer to refine the query — add filters, change time range, join with related spans, drill into a specific trace.

#### Common query patterns

```sql
-- Recent errors
SELECT start_timestamp, message, exception_type, exception_message
FROM records WHERE is_exception LIMIT 20

-- Slow operations
SELECT span_name, duration, start_timestamp, message
FROM records WHERE duration > 1.0 ORDER BY duration DESC LIMIT 20

-- Specific endpoint errors
SELECT start_timestamp, message, exception_message, http_response_status_code
FROM records WHERE http_route = '/api/users' AND level = 'error' LIMIT 20

-- Trace context for a specific trace
SELECT span_name, message, duration, start_timestamp, parent_span_id
FROM records WHERE trace_id = '<trace_id>' ORDER BY start_timestamp

-- Errors by service
SELECT service_name, count(*) as error_count
FROM records WHERE is_exception AND start_timestamp > now() - interval '1 hour'
GROUP BY service_name ORDER BY error_count DESC LIMIT 20

-- Attribute filtering
SELECT start_timestamp, message, attributes->>'user_id' as user_id
FROM records WHERE attributes->>'user_id' = '123' LIMIT 20

-- Metrics
SELECT recorded_timestamp, metric_name, scalar_value
FROM metrics WHERE metric_name = 'http.server.request.duration' LIMIT 20
```

---

### Adding query capabilities to code

1. **Help the user create a read token** if they don't have one:
   - Via UI: logfire.pydantic.dev → Project → Settings → Read tokens → Create
   - Via CLI: `logfire read-tokens --project <org>/<project> create`

2. **Choose the right client** based on their needs:
   - **Python `LogfireQueryClient`** — sync, simple, returns JSON/CSV/Arrow
   - **Python `AsyncLogfireQueryClient`** — async version
   - **Python `logfire.db_api`** — PEP 249, works with pandas and Jupyter
   - **Direct REST API** — any language, `GET /v1/query`

3. **Write the code.** Use the reference docs for detailed examples:
   - Schema: `${CLAUDE_PLUGIN_ROOT}/skills/query/references/schema.md`
   - Client usage: `${CLAUDE_PLUGIN_ROOT}/skills/query/references/client-usage.md`

4. **Store the read token securely.** Use environment variables (`LOGFIRE_READ_TOKEN`), never hardcode tokens. Add to `.env` and ensure `.env` is in `.gitignore`.

## Output format

When presenting query results:
- Use tables for tabular data
- Summarize patterns (e.g., "80% of errors are TimeoutError from the /api/orders endpoint")
- Offer to refine, drill down, or expand the query
- For programmatic usage, show working code the user can copy directly
