# Contributing

## How this repo works

Synced skills are owned by the library they document. Libraries host those skills at `<package-dir>/.agents/skills/<skill-name>/`; this repo is a thin aggregator that mirrors them to two destinations:

- `plugins/<plugin>/skills/<skill>/` — for the Claude Code plugin marketplace.
- `skills/<skill>/` — the standalone copy for [agentskills.io](https://agentskills.io).

| Skill | Upstream |
|-------|----------|
| `logfire-setup` | [`pydantic/logfire`](https://github.com/pydantic/logfire) — `logfire-sdk/logfire/.agents/skills/logfire-setup/` |
| `logfire-instrumentation` | [`pydantic/logfire`](https://github.com/pydantic/logfire) — `logfire-sdk/logfire/.agents/skills/logfire-instrumentation/` |
| `logfire-infrastructure` | [`pydantic/logfire`](https://github.com/pydantic/logfire) — `logfire-sdk/logfire/.agents/skills/logfire-infrastructure/` |
| `logfire-evals` | [`pydantic/logfire`](https://github.com/pydantic/logfire) — `logfire-sdk/logfire/.agents/skills/logfire-evals/` |
| `logfire-coding-agents` | [`pydantic/logfire-cli`](https://github.com/pydantic/logfire-cli) — `skills/logfire-coding-agents/` |
| `logfire-frontend` | [`pydantic/logfire-js`](https://github.com/pydantic/logfire-js) — `packages/logfire-browser/.agents/skills/logfire-frontend/` |
| `logfire-gateway` | [`pydantic/logfire`](https://github.com/pydantic/logfire) — `logfire-sdk/logfire/.agents/skills/logfire-gateway/` |
| `logfire-query` | This repository — `plugins/logfire/skills/logfire-query/` (native MCP workflow) |
| `logfire-ui` | This repository — `plugins/logfire/skills/logfire-ui/` (native MCP/browser workflow) |
| `logfire-datasets` | This repository — `plugins/logfire/skills/logfire-datasets/` (datasets API workflow; the MCP server has no dataset tools) |
| `building-pydantic-ai-agents` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/building-pydantic-ai-agents/` |
| `migrating-agno-to-pydantic-ai` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/migrating-agno-to-pydantic-ai/` |
| `migrating-claude-agent-sdk-to-pydantic-ai` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/migrating-claude-agent-sdk-to-pydantic-ai/` |
| `migrating-google-adk-to-pydantic-ai` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/migrating-google-adk-to-pydantic-ai/` |
| `migrating-langchain-to-pydantic-ai` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/migrating-langchain-to-pydantic-ai/` |
| `migrating-mastra-to-pydantic-ai` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/migrating-mastra-to-pydantic-ai/` |
| `migrating-openai-agents-sdk-to-pydantic-ai` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/migrating-openai-agents-sdk-to-pydantic-ai/` |
| `migrating-pi-to-pydantic-ai` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/migrating-pi-to-pydantic-ai/` |
| `migrating-vercel-ai-sdk-and-eve-to-pydantic-ai` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/migrating-vercel-ai-sdk-and-eve-to-pydantic-ai/` |
| `pydantic-ai-harness` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `src/pydantic_ai_harness/pydantic_ai_harness/.agents/skills/pydantic-ai-harness/` |
| `migrating-deep-agents-to-pydantic-ai-harness` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `src/pydantic_ai_harness/pydantic_ai_harness/.agents/skills/migrating-deep-agents-to-pydantic-ai-harness/` |
| `pydantic` | [`pydantic/pydantic`](https://github.com/pydantic/pydantic) — `.agents/skills/pydantic/` |

A daily workflow (`.github/workflows/sync-from-upstream.yml`) clones each upstream listed above, runs `rsync -a --delete` into both destinations, and opens a PR. CI (`scripts/check-skill-sync.sh`) enforces that plugin and standalone skill copies stay byte-identical.

`scripts/logfire-skill-sources.json` is the executable ownership map for the
Logfire catalog. Both upstream sync and mirror validation use it. CI also
checks that every published Logfire skill has an owner and that relative
references resolve inside the assembled catalog.

**Anything you add directly inside a synced skill directory will be wiped on the next sync.** To change synced skill content, send a PR upstream. Everything else in this repo (plugin metadata, repo-root files, `.github/`, `scripts/`) is fine to edit here.

The three locally owned Logfire skills are not upstream sync targets. Edit their
plugin sources here, then mirror them to `skills/`. `logfire-query` and
`logfire-ui` use native MCP authentication; do not replace it with the CLI's
independently authenticated MCP client. `logfire-datasets` uses a Logfire API
key for the datasets API and a read token for script-side queries, because the
MCP server has no dataset tools.

The CLI also ships release-bound SDK/query/UI adaptations. Those are not public
sync sources: do not import them over the SDK owner's files or the native MCP
entrypoints. Migrate shared improvements upstream deliberately; the CLI's
prepared-project and embedded-reference behavior must survive that migration.

For this ownership migration, merge the frontend owner in logfire-js and the
CLI connection references and the SDK's separate Gateway owner first. Publish
the specialists here and verify their public URLs before merging the SDK's
browser delegation. The ownership-map change must not merge before its
upstream directories exist on their default branches.
`plugins/logfire/skills/logfire-codex-connection` is plugin-owned onboarding,
not a mirrored library specialist. Its runtime and native-host instructions are
maintained here and are not part of the standalone skill catalog or upstream sync.

## Adding a new skill

1. Ensure the skill exists in the library at `<package-dir>/.agents/skills/<skill-name>/`.
2. Add a `sync_skill` entry to `scripts/sync-from-upstream.sh`.

## Manually triggering a sync

Actions → **Sync skills from upstream** → Run workflow.

## Plugin development

Test a Claude Code plugin locally:

```bash
claude --plugin-dir ./plugins/logfire
```

After editing a Codex plugin, reload the plugin cache:

```bash
./scripts/reload-codex-plugin.sh logfire
./scripts/reload-codex-plugin.sh logfire-exporter
```

A new Codex conversation may be required for plugin metadata, skills, MCP servers, icons, or hooks to refresh.

While developing the Cursor plugin, symlink the checkout instead of copying it:

```bash
ln -s /absolute/path/to/pydantic/skills/plugins/logfire ~/.cursor/plugins/local/logfire
```

Host-specific metadata lives alongside the shared plugin content:

```text
.claude-plugin/marketplace.json
.cursor-plugin/marketplace.json
.agents/plugins/marketplace.json
plugins/logfire/.claude-plugin/plugin.json
plugins/logfire/.cursor-plugin/plugin.json
plugins/logfire/.codex-plugin/plugin.json
plugins/logfire-exporter/.codex-plugin/plugin.json
```

The Cursor and Codex marketplaces currently list `logfire`; Codex also lists `logfire-exporter`. The `ai` and `pydantic` plugins remain Claude-only plus a standalone cross-agent skill each.
