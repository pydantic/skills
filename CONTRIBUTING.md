# Contributing

## How this repo works

Synced skills are owned by the library they document. Libraries host those skills at `<package-dir>/.agents/skills/<skill-name>/`; this repo is a thin aggregator that mirrors them to two destinations:

- `plugins/<plugin>/skills/<skill>/` — for the Claude Code plugin marketplace.
- `skills/<skill>/` — the standalone copy for [agentskills.io](https://agentskills.io).

| Skill | Upstream |
|-------|----------|
| `logfire-instrumentation` | [`pydantic/logfire`](https://github.com/pydantic/logfire) — `logfire/.agents/skills/logfire-instrumentation/` |
| `building-pydantic-ai-agents` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/building-pydantic-ai-agents/` |
| `pydantic-ai-harness` | [`pydantic/pydantic-ai-harness`](https://github.com/pydantic/pydantic-ai-harness) — `pydantic_ai_harness/.agents/skills/pydantic-ai-harness/` |

A daily workflow (`.github/workflows/sync-from-upstream.yml`) clones each upstream listed above, runs `rsync -a --delete` into both destinations, and opens a PR. CI (`scripts/check-skill-sync.sh`) enforces that plugin and standalone skill copies stay byte-identical.

**Anything you add directly inside a synced skill directory will be wiped on the next sync.** To change synced skill content, send a PR upstream. Everything else in this repo (plugin metadata, repo-root files, `.github/`, `scripts/`) is fine to edit here.

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

The Cursor and Codex marketplaces currently list `logfire`; Codex also lists `logfire-exporter`. The `ai` plugin remains Claude-only plus a standalone cross-agent skill.
