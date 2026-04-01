---
name: instrument-logfire
description: Detect languages and frameworks in the current project and add Logfire instrumentation
---

# Instrument with Logfire

Add Logfire observability to the current project. Supports Python, JavaScript/TypeScript, and Rust — including polyglot projects.

## Workflow

1. **Detect languages and frameworks**: Scan the project root for language indicators and dependency files:
   - `pyproject.toml`, `requirements.txt` — Python
   - `package.json` — JavaScript/TypeScript
   - `Cargo.toml` — Rust
   - A project may use multiple languages. Instrument each.

2. **For each detected language, follow the appropriate setup:**

### Python

- Identify instrumentable libraries from dependencies (FastAPI, httpx, asyncpg, SQLAlchemy, PydanticAI, OpenAI, Django, Flask, etc.)
- Install logfire with matching extras: `uv add 'logfire[<detected-extras>]'`. Check for `uv.lock` (uv), `poetry.lock` (poetry), or `Pipfile.lock` (pipenv) to pick the right package manager.
- Find the application entry point and add:
  - `import logfire` at the top
  - `logfire.configure()` — must come before any `instrument_*()` calls
  - `logfire.instrument_<library>()` calls for each detected framework
  - Web framework instrumentors (`instrument_fastapi`, `instrument_django`, `instrument_flask`) need the app instance. HTTP client and database instrumentors are global.

### JavaScript / TypeScript

- Check `package.json` for framework (Express, Next.js, Fastify) and runtime (Node.js, Cloudflare Workers, Deno).
- Install the appropriate package:
  - Node.js: `npm install @pydantic/logfire-node`
  - Cloudflare Workers: `npm install @pydantic/logfire-cf-workers logfire`
  - Next.js / generic: `npm install logfire`
- Add instrumentation based on runtime:
  - **Node.js**: Create `instrumentation.ts` with `import * as logfire from '@pydantic/logfire-node'` and `logfire.configure()`. Add `--require ./instrumentation.js` to the start script.
  - **Cloudflare Workers**: Wrap the handler with `instrument()` from `@pydantic/logfire-cf-workers`.
  - **Next.js**: Set `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` in `.env.local`.

### Rust

- Add `logfire = "0.6"` to `Cargo.toml` dependencies.
- In `main()`, add `logfire::configure().install_panic_handler().finish()?` and `shutdown_handler.shutdown()?` before exit.

3. **Report**: Show the user what was added per language and suggest running `logfire auth` or setting `LOGFIRE_TOKEN`.

## Output format

After making changes, summarize:
- Which languages and frameworks were detected
- What packages/extras were installed per language
- Where instrumentation was placed
- Any manual steps remaining (e.g., `logfire auth`, setting `LOGFIRE_TOKEN`, adding `--require` to start script)
