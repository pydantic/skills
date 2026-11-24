# Logfire Query Client Usage

Detailed examples for querying Logfire data programmatically.

## Creating a Read Token

### Via the Logfire UI

1. Go to [logfire.pydantic.dev](https://logfire.pydantic.dev)
2. Select your project
3. Open Settings (gear icon) → Read tokens tab
4. Click "Create read token"
5. Copy the token immediately — it won't be shown again

### Via the Rust CLI

Follow the [shared identity and credential flow](https://pydantic.dev/.well-known/agent-skills/logfire-instrumentation/references/auth.md).
For an already configured local project, `logfire token read` creates a read token.
If a consumer specifically requires a project API key, use
`logfire api-key query --name query-client` instead; do not grant unrelated
permissions.
Capture its stdout programmatically, check exit status zero, and deliver it to the
application's secret mechanism without logging or displaying it. Do not put a token
literal in source or command arguments. Use `LOGFIRE_READ_TOKEN` in the application's
private environment. Interactive analysis through `logfire mcp query run` uses
OAuth and does not need a separately created read token.

---

## Python `LogfireQueryClient` (Sync)

Install `logfire` and `httpx` with the project's existing package manager.
Install `pyarrow` only when using the Arrow examples. Keep the read token in a
private `LOGFIRE_READ_TOKEN` environment variable, never in source.

```python
import os
from datetime import datetime, timedelta, timezone

from logfire.query_client import LogfireQueryClient

min_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

with LogfireQueryClient(read_token=os.environ['LOGFIRE_READ_TOKEN']) as client:
    rows = client.query_json_rows(
        sql='SELECT start_timestamp, message FROM records LIMIT 10',
        min_timestamp=min_timestamp,
    )

    # CSV
    csv_data = client.query_csv(
        sql='SELECT start_timestamp, message FROM records LIMIT 10',
        min_timestamp=min_timestamp,
    )

    # Apache Arrow (requires pyarrow)
    arrow_table = client.query_arrow(
        sql='SELECT start_timestamp, message FROM records LIMIT 10',
        min_timestamp=min_timestamp,
    )

    # Token info
    info = client.info()
```

With time filtering:

```python
import os
from datetime import datetime, timedelta, timezone

from logfire.query_client import LogfireQueryClient

max_timestamp = datetime.now(timezone.utc)
min_timestamp = max_timestamp - timedelta(days=1)

with LogfireQueryClient(read_token=os.environ['LOGFIRE_READ_TOKEN']) as client:
    rows = client.query_json_rows(
        sql='SELECT message, exception_type FROM records WHERE is_exception LIMIT 20',
        min_timestamp=min_timestamp,
        max_timestamp=max_timestamp,
    )
```

---

## Python `AsyncLogfireQueryClient` (Async)

```python
import os
from datetime import datetime, timedelta, timezone

from logfire.query_client import AsyncLogfireQueryClient

min_timestamp = datetime.now(timezone.utc) - timedelta(hours=2)

async with AsyncLogfireQueryClient(read_token=os.environ['LOGFIRE_READ_TOKEN']) as client:
    rows = await client.query_json_rows(
        sql='SELECT start_timestamp, message FROM records LIMIT 10',
        min_timestamp=min_timestamp,
    )
    csv_data = await client.query_csv(
        sql='SELECT start_timestamp, message FROM records LIMIT 10',
        min_timestamp=min_timestamp,
    )
    arrow_table = await client.query_arrow(
        sql='SELECT start_timestamp, message FROM records LIMIT 10',
        min_timestamp=min_timestamp,
    )
```

---

## Python DB API 2.0 (`logfire.db_api`)

PEP 249 compliant interface. Works with pandas, Jupyter, and marimo.

### Basic usage

```python
import os

import logfire.db_api

with logfire.db_api.connect(read_token=os.environ['LOGFIRE_READ_TOKEN']) as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT start_timestamp, message FROM records LIMIT 10')
    rows = cursor.fetchall()
    for row in rows:
        print(row)
```

### Parameterized queries

Use `%(name)s` syntax (pyformat style) to safely pass parameters:

```python
cursor.execute(
    'SELECT message FROM records WHERE service_name = %(service)s LIMIT 10',
    {'service': 'my-app'}
)
```

### Pandas integration

```python
import os

import pandas as pd
import logfire.db_api

with logfire.db_api.connect(read_token=os.environ['LOGFIRE_READ_TOKEN']) as conn:
    df = pd.read_sql('SELECT start_timestamp, message, duration FROM records LIMIT 100', conn)
    print(df.describe())
```

### Configuration options

```python
import os
import logfire.db_api
from datetime import timedelta, datetime, timezone

# Custom row limit
conn = logfire.db_api.connect(read_token=os.environ['LOGFIRE_READ_TOKEN'], limit=1000)

# Query last 7 days (default is 24 hours)
conn = logfire.db_api.connect(read_token=os.environ['LOGFIRE_READ_TOKEN'], min_timestamp=timedelta(days=7))

# Disable default timestamp filter
conn = logfire.db_api.connect(read_token=os.environ['LOGFIRE_READ_TOKEN'], min_timestamp=None)

# Per-cursor overrides
cursor = conn.cursor()
cursor.limit = 500
cursor.min_timestamp = datetime.now(timezone.utc) - timedelta(days=14)
```

---

## Direct REST API

For any language or tool. Works with `curl`, `httpx`, `requests`, `fetch`, etc.

### Endpoint

Send a `POST` request with a JSON body to the endpoint for the project's region:

- US: `https://logfire-us.pydantic.dev/v2/query`
- EU: `https://logfire-eu.pydantic.dev/v2/query`

### Authentication

```http
Authorization: Bearer <read_token>
```

### JSON body

| Parameter | Required | Description |
|-----------|----------|-------------|
| `sql` | Yes | SQL query string |
| `min_timestamp` | Yes | Timezone-aware ISO timestamp lower bound |
| `max_timestamp` | No | ISO timestamp upper bound |
| `limit` | No | Row limit (default 100, max 10,000) |
| `timezone` | No | Query execution timezone, such as `Europe/Paris` |
| `deployment_environment` | No | One or more deployment-environment names |
| `explain` | No | Include query-plan messages when true |

### Response formats

Set the `Accept` header:

- `application/json` — schema plus data rows (default)
- `application/x-ndjson` — streaming schema, data, and completion messages
- `text/csv` — CSV
- `application/vnd.apache.arrow.stream` — Apache Arrow

### curl examples

```bash
# Set this to a recent, timezone-aware lower bound before running the examples.
MIN_TIMESTAMP='<ISO-8601 lower bound>'
MAX_TIMESTAMP='<ISO-8601 upper bound>'

# Basic query (JSON). Pass the secret header over stdin, not argv.
printf 'Authorization: Bearer %s\n' "$LOGFIRE_READ_TOKEN" | curl 'https://logfire-us.pydantic.dev/v2/query' \
  -H @- \
  --json "{\"sql\":\"SELECT start_timestamp, message FROM records LIMIT 5\",\"min_timestamp\":\"$MIN_TIMESTAMP\"}"

# Streaming NDJSON
printf 'Authorization: Bearer %s\n' "$LOGFIRE_READ_TOKEN" | curl 'https://logfire-us.pydantic.dev/v2/query' \
  -H @- \
  -H 'Accept: application/x-ndjson' \
  --json "{\"sql\":\"SELECT start_timestamp, message FROM records LIMIT 5\",\"min_timestamp\":\"$MIN_TIMESTAMP\"}"

# CSV format
printf 'Authorization: Bearer %s\n' "$LOGFIRE_READ_TOKEN" | curl 'https://logfire-us.pydantic.dev/v2/query' \
  -H @- \
  -H "Accept: text/csv" \
  --json "{\"sql\":\"SELECT start_timestamp, message FROM records LIMIT 5\",\"min_timestamp\":\"$MIN_TIMESTAMP\"}"

# With time range
printf 'Authorization: Bearer %s\n' "$LOGFIRE_READ_TOKEN" | curl 'https://logfire-us.pydantic.dev/v2/query' \
  -H @- \
  --json "{\"sql\":\"SELECT message FROM records WHERE is_exception LIMIT 20\",\"min_timestamp\":\"$MIN_TIMESTAMP\",\"max_timestamp\":\"$MAX_TIMESTAMP\"}"
```

### Python (httpx)

```python
import os
from datetime import UTC, datetime, timedelta

import httpx

response = httpx.post(
    'https://logfire-us.pydantic.dev/v2/query',
    json={
        'sql': 'SELECT start_timestamp, message FROM records LIMIT 5',
        'min_timestamp': (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
    },
    headers={'Authorization': f"Bearer {os.environ['LOGFIRE_READ_TOKEN']}"},
)
response.raise_for_status()
data = response.json()
```

### JavaScript (fetch)

Run this only in a trusted server process; never expose a read token to browser code.

```javascript
const readToken = process.env.LOGFIRE_READ_TOKEN;
if (!readToken) throw new Error('LOGFIRE_READ_TOKEN is required');
const minTimestamp = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();

const response = await fetch(
  'https://logfire-us.pydantic.dev/v2/query',
  {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${readToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      sql: 'SELECT start_timestamp, message FROM records LIMIT 5',
      min_timestamp: minTimestamp,
    }),
  },
);
if (!response.ok) throw new Error(`Logfire query failed: ${response.status}`);
const data = await response.json();
```
