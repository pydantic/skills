# Logfire Query Client Usage

Detailed examples for querying Logfire data programmatically.

## Creating a Read Token

### Via the Logfire UI

1. Go to [logfire.pydantic.dev](https://logfire.pydantic.dev)
2. Select your project
3. Open Settings (gear icon) → Read tokens tab
4. Click "Create read token"
5. Copy the token immediately — it won't be shown again

### Via the CLI

```bash
logfire read-tokens --project <organization>/<project> create
```

Store the token in an environment variable:

```bash
export LOGFIRE_READ_TOKEN=<your-read-token>
```

---

## Python `LogfireQueryClient` (Sync)

```python
from logfire.query_client import LogfireQueryClient

with LogfireQueryClient(read_token='<token>') as client:
    # Column-oriented JSON (default)
    result = client.query_json(sql='SELECT start_timestamp, message FROM records LIMIT 10')

    # Row-oriented JSON
    rows = client.query_json_rows(sql='SELECT start_timestamp, message FROM records LIMIT 10')

    # CSV
    csv_data = client.query_csv(sql='SELECT start_timestamp, message FROM records LIMIT 10')

    # Apache Arrow (requires pyarrow)
    arrow_table = client.query_arrow(sql='SELECT start_timestamp, message FROM records LIMIT 10')

    # Token info
    info = client.info()
```

With time filtering:

```python
with LogfireQueryClient(read_token='<token>') as client:
    result = client.query_json(
        sql='SELECT message, exception_type FROM records WHERE is_exception LIMIT 20',
        min_timestamp='2025-01-01T00:00:00Z',
        max_timestamp='2025-01-02T00:00:00Z',
    )
```

### Using environment variables

```python
import os
from logfire.query_client import LogfireQueryClient

# Reads from LOGFIRE_READ_TOKEN env var
with LogfireQueryClient(read_token=os.environ['LOGFIRE_READ_TOKEN']) as client:
    result = client.query_json(sql='SELECT message FROM records LIMIT 5')
```

---

## Python `AsyncLogfireQueryClient` (Async)

```python
from logfire.query_client import AsyncLogfireQueryClient

async with AsyncLogfireQueryClient(read_token='<token>') as client:
    result = await client.query_json(
        sql='SELECT start_timestamp, message FROM records LIMIT 10'
    )
    rows = await client.query_json_rows(
        sql='SELECT start_timestamp, message FROM records LIMIT 10'
    )
    csv_data = await client.query_csv(
        sql='SELECT start_timestamp, message FROM records LIMIT 10'
    )
    arrow_table = await client.query_arrow(
        sql='SELECT start_timestamp, message FROM records LIMIT 10'
    )
```

---

## Python DB API 2.0 (`logfire.db_api`)

PEP 249 compliant interface. Works with pandas, Jupyter, and marimo.

### Basic usage

```python
import logfire.db_api

with logfire.db_api.connect(read_token='<token>') as conn:
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
import pandas as pd
import logfire.db_api

with logfire.db_api.connect(read_token='<token>') as conn:
    df = pd.read_sql('SELECT start_timestamp, message, duration FROM records LIMIT 100', conn)
    print(df.describe())
```

### Configuration options

```python
import logfire.db_api
from datetime import timedelta, datetime, timezone

# Custom row limit
conn = logfire.db_api.connect(read_token='<token>', limit=1000)

# Query last 7 days (default is 24 hours)
conn = logfire.db_api.connect(read_token='<token>', min_timestamp=timedelta(days=7))

# Disable default timestamp filter
conn = logfire.db_api.connect(read_token='<token>', min_timestamp=None)

# Per-cursor overrides
cursor = conn.cursor()
cursor.limit = 500
cursor.min_timestamp = datetime.now(timezone.utc) - timedelta(days=14)
```

---

## Direct REST API

For any language or tool. Works with `curl`, `httpx`, `requests`, `fetch`, etc.

### Endpoint

```
GET https://logfire-api.pydantic.dev/v1/query
```

Region variants:
- US: `https://logfire-us.pydantic.dev/v1/query`
- EU: `https://logfire-eu.pydantic.dev/v1/query`

### Authentication

```
Authorization: Bearer <read_token>
```

### Query parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `sql` | Yes | SQL query string |
| `min_timestamp` | No | ISO timestamp lower bound |
| `max_timestamp` | No | ISO timestamp upper bound |
| `limit` | No | Row limit (default 500, max 10,000) |
| `row_oriented` | No | Set `true` for row-oriented JSON |

### Response formats

Set the `Accept` header:
- `application/json` — column-oriented JSON (default)
- `text/csv` — CSV
- `application/vnd.apache.arrow.stream` — Apache Arrow

### curl examples

```bash
# Basic query (column-oriented JSON)
curl -G 'https://logfire-api.pydantic.dev/v1/query' \
  -H "Authorization: Bearer $LOGFIRE_READ_TOKEN" \
  --data-urlencode "sql=SELECT start_timestamp, message FROM records LIMIT 5"

# Row-oriented JSON
curl -G 'https://logfire-api.pydantic.dev/v1/query' \
  -H "Authorization: Bearer $LOGFIRE_READ_TOKEN" \
  --data-urlencode "sql=SELECT start_timestamp, message FROM records LIMIT 5" \
  --data-urlencode "row_oriented=true"

# CSV format
curl -G 'https://logfire-api.pydantic.dev/v1/query' \
  -H "Authorization: Bearer $LOGFIRE_READ_TOKEN" \
  -H "Accept: text/csv" \
  --data-urlencode "sql=SELECT start_timestamp, message FROM records LIMIT 5"

# With time range
curl -G 'https://logfire-api.pydantic.dev/v1/query' \
  -H "Authorization: Bearer $LOGFIRE_READ_TOKEN" \
  --data-urlencode "sql=SELECT message FROM records WHERE is_exception LIMIT 20" \
  --data-urlencode "min_timestamp=2025-01-01T00:00:00Z" \
  --data-urlencode "max_timestamp=2025-01-02T00:00:00Z"
```

### Python (httpx)

```python
import httpx

response = httpx.get(
    'https://logfire-api.pydantic.dev/v1/query',
    params={'sql': 'SELECT start_timestamp, message FROM records LIMIT 5'},
    headers={'Authorization': f'Bearer {read_token}'},
)
data = response.json()
```

### JavaScript (fetch)

```javascript
const params = new URLSearchParams({
  sql: 'SELECT start_timestamp, message FROM records LIMIT 5',
});

const response = await fetch(
  `https://logfire-api.pydantic.dev/v1/query?${params}`,
  { headers: { Authorization: `Bearer ${readToken}` } }
);
const data = await response.json();
```
