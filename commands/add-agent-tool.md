---
name: add-agent-tool
description: Add a new tool to an existing Pydantic AI agent
---

# Add Pydantic AI Tool

Add a new tool to a Pydantic AI agent.

## Workflow

1. **Determine tool type**:
   - Use `@agent.tool` if the tool needs `RunContext` (access to dependencies, retry count, usage stats, or message history)
   - Use `@agent.tool_plain` for pure functions with no agent context

2. **Write the tool function**:
   - Write a clear docstring — it becomes the tool description sent to the LLM
   - Document all parameters in the docstring — they are extracted and added to the JSON parameter schema (Google, NumPy, and Sphinx formats are auto-detected)
   - Return type must be JSON-serializable by Pydantic
   - Use `RunContext[DepsType]` as the first parameter for `@agent.tool` — the generic type must match the agent's `deps_type`

3. **Handle errors**:
   - Raise `ModelRetry("reason")` to ask the model to retry with corrected inputs
   - Pydantic validation errors on tool arguments are automatically fed back to the LLM for retry (default `retries=1`)

4. **Example**:

```python
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry


@agent.tool
def search_database(ctx: RunContext[MyDeps], query: str, limit: int = 10) -> list[dict]:
    """Search the database for records matching the query.

    Args:
        query: The search query string.
        limit: Maximum number of results to return.
    """
    results = ctx.deps.db.search(query, limit=limit)
    if not results:
        raise ModelRetry('No results found. Try a broader search query.')
    return results
```

5. **Add a test** using `TestModel`:

```python
from pydantic_ai.models.test import TestModel


async def test_search_tool():
    with agent.override(model=TestModel()):
        result = await agent.run('Find recent orders', deps=mock_deps)
        assert result.output is not None
```
