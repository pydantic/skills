# Contributing

## How this repo works

Each skill is owned by the library it documents. Libraries host their skills at `<package-dir>/.agents/skills/<skill-name>/`; this repo is a thin aggregator that mirrors them to two destinations:

- `plugins/<plugin>/skills/<skill>/` — for the Claude Code plugin marketplace.
- `skills/<skill>/` — the standalone copy for [agentskills.io](https://agentskills.io).

| Skill | Upstream |
|-------|----------|
| `logfire-instrumentation` | [`pydantic/logfire`](https://github.com/pydantic/logfire) — `logfire/.agents/skills/logfire-instrumentation/` |
| `building-pydantic-ai-agents` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/building-pydantic-ai-agents/` |

A daily workflow (`.github/workflows/sync-from-upstream.yml`) clones each upstream, runs `rsync -a --delete` into both destinations, and opens a PR. CI (`scripts/check-skill-sync.sh`) enforces that the two destinations stay byte-identical.

**Anything you add directly inside `plugins/*/skills/*/` or `skills/*/` will be wiped on the next sync.** To change skill content, send a PR upstream. Everything else in this repo (plugin metadata, repo-root files, `.github/`, `scripts/`) is fine to edit here.

## Adding a new skill

1. Ensure the skill exists in the library at `<package-dir>/.agents/skills/<skill-name>/`.
2. Add a `sync_skill` entry to `scripts/sync-from-upstream.sh`.

## Manually triggering a sync

Actions → **Sync skills from upstream** → Run workflow.
