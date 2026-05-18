# Logfire Schema Reference

Logfire stores OpenTelemetry data in two tables: `records` (spans and logs) and `metrics`. SQL dialect is Apache DataFusion (Postgres-like).

## `records` Table

All spans, logs, and span events are stored in the `records` table.

### Timestamps

| Column | Type | Description |
|--------|------|-------------|
| `start_timestamp` | timestamp (UTC) | When span/log was created |
| `end_timestamp` | timestamp (UTC) | When span/log completed |
| `duration` | double (seconds) | Time between start and end; NULL for logs |

### Span Tree Structure

| Column | Type | Description |
|--------|------|-------------|
| `trace_id` | string (32 hex chars) | Unique identifier for the trace |
| `span_id` | string (16 hex chars) | Unique identifier within a trace |
| `parent_span_id` | string (16 hex chars) | Parent span ID; NULL for root spans |

### Core Fields

| Column | Type | Description |
|--------|------|-------------|
| `span_name` | string | Low-cardinality label for similar records |
| `message` | string | Human-readable description with arguments filled in |
| `level` | integer | Severity level; supports string comparison (`level = 'error'`) |
| `kind` | string | Record type: `span`, `log`, `span_event`, or `pending_span` |
| `attributes` | JSON | Arbitrary structured data |
| `tags` | string[] | Optional grouping labels |

### Exception Fields

| Column | Type | Description |
|--------|------|-------------|
| `is_exception` | boolean | Whether an exception was recorded |
| `exception_type` | string | Fully qualified exception class name |
| `exception_message` | string | Exception message text |
| `exception_stacktrace` | string | Full traceback |

### Service / Resource Fields

| Column | Type | Description |
|--------|------|-------------|
| `service_name` | string | Service type identifier |
| `service_version` | string | Service version |
| `service_instance_id` | string | Unique instance identifier |
| `service_namespace` | string | Service namespace |
| `deployment_environment` | string | Environment (production/staging/development) |
| `process_pid` | integer | Process ID |
| `otel_resource_attributes` | JSON | Full OpenTelemetry resource metadata |

### HTTP / URL Fields

| Column | Type | Description |
|--------|------|-------------|
| `http_response_status_code` | integer | HTTP response status code |
| `http_method` | string | HTTP method (GET, POST, etc.) |
| `http_route` | string | HTTP route pattern |
| `url_full` | string | Complete URL |
| `url_path` | string | URL path component |
| `url_query` | string | URL query string |

### OpenTelemetry Fields

| Column | Type | Description |
|--------|------|-------------|
| `otel_status_code` | string | Span status (OK, ERROR, UNSET) |
| `otel_status_message` | string | Status description on error |
| `otel_events` | JSON array | Span events attached to the span |
| `otel_links` | JSON array | Span links to other traces |
| `otel_scope_name` | string | Instrumenting library name |
| `otel_scope_version` | string | Instrumenting library version |
| `otel_scope_attributes` | JSON | Additional scope metadata |

### Telemetry SDK Fields

| Column | Type | Description |
|--------|------|-------------|
| `telemetry_sdk_name` | string | SDK name |
| `telemetry_sdk_language` | string | SDK language |
| `telemetry_sdk_version` | string | SDK version |

### Other

| Column | Type | Description |
|--------|------|-------------|
| `log_body` | string/JSON | Body for OpenTelemetry logs (non-span records) |

---

## `metrics` Table

| Column | Type | Description |
|--------|------|-------------|
| `recorded_timestamp` | timestamp (UTC) | When metric was recorded |
| `metric_name` | string | Metric name |
| `metric_type` | string | Type (gauge, sum, histogram, exponential_histogram) |
| `unit` | string | Unit of measurement |
| `metric_description` | string | Metric description |
| `scalar_value` | double | Scalar metric value (gauge/sum) |
| `start_timestamp` | timestamp (UTC) | Start of aggregation window |
| `aggregation_temporality` | enum | Cumulative or delta |
| `is_monotonic` | boolean | Whether the metric is monotonic |
| `histogram_min` | double | Histogram minimum |
| `histogram_max` | double | Histogram maximum |
| `histogram_count` | integer | Histogram count |
| `histogram_sum` | double | Histogram sum |
| `histogram_bucket_counts` | integer[] | Histogram bucket counts |
| `histogram_explicit_bounds` | double[] | Histogram bucket boundaries |
| `exp_histogram_scale` | integer | Exponential histogram scale |
| `exp_histogram_zero_count` | integer | Exponential histogram zero count |
| `exp_histogram_zero_threshold` | double | Exponential histogram zero threshold |
| `exp_histogram_positive_bucket_counts` | integer[] | Positive bucket counts |
| `exp_histogram_positive_bucket_counts_offset` | integer | Positive bucket offset |
| `exp_histogram_negative_bucket_counts` | integer[] | Negative bucket counts |
| `exp_histogram_negative_bucket_counts_offset` | integer | Negative bucket offset |
| `attributes` | JSON | Metric dimensions/labels |
| `service_name` | string | Service identifier |
| `service_version` | string | Service version |
| `service_instance_id` | string | Unique instance identifier |
| `service_namespace` | string | Service namespace |
| `process_pid` | integer | Process ID |
| `otel_scope_name` | string | Instrumenting library name |
| `otel_scope_version` | string | Instrumenting library version |
| `otel_scope_attributes` | JSON | Additional scope metadata |

---

## JSON Attribute Access

The `attributes` column stores arbitrary structured data as JSON. Use `->>` to extract text values, `->` to extract nested objects.

```sql
-- Extract a text value
SELECT attributes->>'user_id' as user_id FROM records

-- Nested access
SELECT attributes->'request'->>'method' as method FROM records

-- Filter by attribute
WHERE attributes->>'http.url' LIKE '%/api/%'

-- Cast extracted values
WHERE CAST(attributes->>'response.status' AS INTEGER) >= 500
```

## Common Filter Patterns

```sql
-- Recent errors with details
SELECT start_timestamp, service_name, exception_type, exception_message
FROM records
WHERE is_exception AND start_timestamp > now() - interval '1 hour'
ORDER BY start_timestamp DESC LIMIT 20

-- HTTP errors by route
SELECT http_route, http_response_status_code, count(*) as count
FROM records
WHERE http_response_status_code >= 400
GROUP BY http_route, http_response_status_code
ORDER BY count DESC LIMIT 20

-- Slow endpoints (p95 duration)
SELECT http_route,
       approx_percentile_cont(duration, 0.95) as p95_duration,
       count(*) as count
FROM records
WHERE kind = 'span' AND http_route IS NOT NULL
GROUP BY http_route ORDER BY p95_duration DESC LIMIT 20

-- Trace waterfall
SELECT span_name, message, duration, start_timestamp, span_id, parent_span_id
FROM records WHERE trace_id = '<trace_id>'
ORDER BY start_timestamp

-- Tag filtering
SELECT * FROM records WHERE array_has(tags, 'critical') LIMIT 20

-- Time-bucketed error rate
SELECT time_bucket(interval '5 minutes', start_timestamp) as bucket,
       count(*) FILTER (WHERE is_exception) as errors,
       count(*) as total
FROM records
GROUP BY bucket ORDER BY bucket DESC LIMIT 50

-- Metrics query
SELECT recorded_timestamp, scalar_value, attributes
FROM metrics
WHERE metric_name = 'http.server.request.duration'
ORDER BY recorded_timestamp DESC LIMIT 20
```
