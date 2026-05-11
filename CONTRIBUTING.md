# Contributing

## Where skill content lives

Each skill exists in **two** places in this repo:

- `plugins/<plugin>/skills/<skill>/` — consumed by the Claude Code plugin marketplace.
- `skills/<skill>/` — the standalone copy distributed via the [agentskills.io](https://agentskills.io) standard.

The two copies must stay byte-identical. CI runs `scripts/check-skill-sync.sh` on every PR to enforce this.

## Upstream is authoritative

Skill content is **owned by the upstream source repository**, not by this aggregator:

| Skill | Upstream |
|-------|----------|
| `logfire-instrumentation` | [`pydantic/logfire`](https://github.com/pydantic/logfire) — `logfire/.agents/skills/logfire-instrumentation/` |
| `building-pydantic-ai-agents` | [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai) — `pydantic_ai_slim/pydantic_ai/.agents/skills/building-pydantic-ai-agents/` |

A daily GitHub Actions job (`.github/workflows/sync-from-upstream.yml`) clones each upstream and runs `rsync -a --delete` from the upstream subpath into both the plugin and standalone destinations, then opens a PR titled `chore: sync skills from upstream`.

### What `--delete` means for you

`rsync --delete` removes any file in the destination that is not present upstream. **Anything you add directly to `plugins/<plugin>/skills/<skill>/` or `skills/<skill>/` will be wiped on the next sync.** If you want to change skill content, send the PR to the upstream repo. The sync job will pick it up and propagate it here.

The only files in this repo that are safe to edit by hand are:

- `plugins/*/` plugin metadata (e.g. `.claude-plugin/plugin.json`, command files outside `skills/`).
- Files at the repo root (`README.md`, `LICENSE`, `prek.toml`, `CONTRIBUTING.md`).
- `.github/` workflows and `scripts/`.

## Manually triggering a sync

From the Actions tab, run **Sync skills from upstream** via `workflow_dispatch`. It will open (or update) the `autosync/upstream-skills` branch.
