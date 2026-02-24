---
name: instrument
description: Detect frameworks in the current project and add Logfire instrumentation
---

# /instrument

Add Logfire observability to the current project.

## Workflow

1. **Detect frameworks**: Read `pyproject.toml` or `requirements.txt` to identify instrumentable libraries (FastAPI, httpx, asyncpg, SQLAlchemy, PydanticAI, OpenAI, Django, Flask, etc.)

2. **Install logfire with extras**: Run `uv add 'logfire[<detected-extras>]'` with all matching extras. If unsure about the package manager, check for `uv.lock` (uv), `poetry.lock` (poetry), or `Pipfile.lock` (pipenv) and use the appropriate tool.

3. **Add configuration and instrumentation**: Find the application entry point and add:
   - `import logfire` at the top
   - `logfire.configure()` - must come before any `instrument_*()` calls
   - `logfire.instrument_<library>()` calls for each detected framework
   - Web framework instrumentors (`instrument_fastapi`, `instrument_django`, `instrument_flask`) need the app instance as an argument
   - HTTP client and database instrumentors (`instrument_httpx`, `instrument_asyncpg`) are global and take no arguments

4. **Report**: Show the user what was added and suggest running `logfire auth` if they haven't already.

## Output format

After making changes, summarize:
- Which frameworks were detected
- Which extras were installed
- Where `logfire.configure()` and `instrument_*()` calls were placed
- Any manual steps remaining (e.g., `logfire auth`, setting `LOGFIRE_TOKEN`)
