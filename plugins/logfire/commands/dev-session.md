---
name: dev-session
description: Start a local Logfire dev session to send traces from your running app for debugging
---

# /dev-session

Start a local Logfire dev session that creates temporary credentials and injects them into your app so you can view traces in the Logfire UI.

## Prerequisites

The Logfire MCP server must be connected (this plugin configures it automatically).

## Workflow

### Step 1: Create the dev session

Call the `mcp__logfire__local_dev_session` MCP tool to provision a temporary dev project and get credentials. This returns:
- Logfire SDK env vars (`LOGFIRE_TOKEN`, `LOGFIRE_BASE_URL`)
- Plain OTEL env vars (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, etc.)
- `OTEL_RESOURCE_ATTRIBUTES` with a session tag for filtering traces
- A Logfire UI link to view traces

Save all returned values — you will need them in the injection step.

### Step 2: Analyze the codebase

Determine how the app is run and configured by scanning for:

- **Env files**: `.env`, `.env.local`, `.env.development`
- **Container orchestration**: `docker-compose.yml` / `docker-compose.yaml`, Kubernetes manifests (`k8s/`, `deploy/`, `*.yaml` with `kind: Deployment`)
- **Dev tools**: `Tiltfile` (Tilt), `skaffold.yaml` (Skaffold), `devcontainer.json` / `.devcontainer/`
- **Process managers**: `Procfile` (foreman/honcho)
- **Build/run targets**: `Makefile`, `justfile` with dev/run targets
- **Deployment config**: `fly.toml`, `helmfile.yaml`, Helm `values.yaml`
- **Framework conventions**: Next.js uses `.env.local`, Python apps typically use `.env`

Also check whether Logfire or OpenTelemetry is already instrumented:
- Look for `logfire` in Python dependencies, `@pydantic/logfire-node` or `logfire` in `package.json`, `logfire` in `Cargo.toml`
- Look for OpenTelemetry SDK imports without Logfire
- **If the app is not instrumented at all, tell the user and suggest running `/instrument` first.** The dev session credentials will still work once instrumentation is added, so continue with injection.

### Step 3: Inject credentials

Choose the best injection method based on what you found. **Prefer methods that support hot reload** so the user doesn't have to restart manually.

#### Choosing between Logfire SDK vars and OTEL vars

- If the app uses the **Logfire SDK** (`logfire` package): inject only `LOGFIRE_TOKEN` and `LOGFIRE_BASE_URL` (2 vars). Also include `OTEL_RESOURCE_ATTRIBUTES` for the session tag.
- If the app uses **plain OpenTelemetry** (no Logfire SDK): inject the full OTEL variable set (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_RESOURCE_ATTRIBUTES`, etc.).
- If unsure, prefer the Logfire SDK vars — they are simpler and the SDK reads them automatically.

#### Local app (no containers)

- **`.env` file (preferred)**: Write or append the env vars to the appropriate `.env` file for the framework. If the file already contains `LOGFIRE_TOKEN` or `OTEL_EXPORTER_OTLP_ENDPOINT`, **replace the existing values** rather than appending duplicates.
- **Shell export (fallback)**: If no `.env` file pattern is used, print `export` commands for the user to paste into their terminal.

#### Docker Compose

- Add vars to the `environment:` section of the relevant service(s), or add/update an `env_file:` reference pointing to a shared `.env` file.
- Tell the user to run `docker compose restart <service>` to pick up changes.

#### Tilt

- Prefer adding a `.env` file and referencing it from the Tiltfile or Kubernetes manifest, since Tilt live-updates automatically.
- For `local_resource()`: add to the command's env or use a shared `.env` file.
- For `docker_build()`: add env vars to the corresponding Kubernetes manifest.
- Suggest `tilt trigger <resource>` if manual reload is needed.

#### Skaffold

- Add env vars to the relevant Kubernetes manifest (`envFrom` with a ConfigMap, or inline `env:` entries).
- Skaffold's `dev` mode auto-syncs and redeploys on changes.

#### Dev Containers / Codespaces

- Add to `remoteEnv` in `devcontainer.json`, or to a `.env` file referenced by `runArgs: ["--env-file", ".env"]`.

#### Kubernetes (direct manifests)

- Add env vars to the Deployment/Pod spec, or create a ConfigMap and reference it via `envFrom`.
- Remind the user to `kubectl apply` after changes.

#### Procfile / foreman / honcho

- Add vars to `.env` file — foreman and honcho auto-load `.env` by default.

#### Makefile / justfile

- Add vars to `.env` and ensure the run target sources it, or add `export` lines to the target.

### Step 4: Ensure the app can pick up credentials

Verify the app will actually read the injected env vars:

- **Python**: The Logfire SDK auto-reads `LOGFIRE_TOKEN` from the environment. If using `.env`, check that `python-dotenv` is loaded or the framework handles it (Django does via `django-environ`, FastAPI often uses `pydantic-settings`).
- **Node.js**: Check if `dotenv` is loaded or if the framework handles it (Next.js loads `.env.local` automatically).
- **Rust**: The Logfire SDK reads `LOGFIRE_TOKEN` from the environment automatically.
- **Containers**: Env vars are injected at container start; a restart or redeploy is needed to pick up changes.

If the `.env` file won't be auto-loaded, tell the user what they need to do (e.g., add `dotenv` loading, or source the file manually).

### Step 5: Report to the user

Tell the user:
1. What credentials were injected and where
2. How to restart or reload the app if needed
3. The **Logfire UI link** where they can view traces from this session
4. That the session is temporary — credentials expire after 7 days

## Important rules

- **Never commit tokens to git.** If you create or modify a `.env` file, check that `.env` is in `.gitignore`. If it's not, add it.
- **Replace, don't duplicate.** If a `.env` file already has `LOGFIRE_TOKEN` or OTEL exporter vars, replace the existing lines instead of appending duplicates.
- **Don't touch instrumentation.** This command only handles credential injection. If the app isn't instrumented, suggest `/instrument` but don't add instrumentation code yourself.
- **Include the session resource attribute.** Always include `OTEL_RESOURCE_ATTRIBUTES` so traces from this session can be filtered in the Logfire UI.
