# Contributing

## Principle: skills live in the library they document

Every skill in this marketplace is **owned by the package it documents**, not by this aggregator. Each library hosts its own skill in-tree under the conventional library-skills layout (`<package-dir>/.agents/skills/<skill-name>/`), and we mirror it here. This keeps three things true:

- **One source of truth.** The library team reviews and ships the skill the same way they ship the rest of their code.
- **No duplication or drift.** We do not maintain a parallel copy that can diverge from what the library ships.
- **Two delivery channels from one source.** Users discover the skill via the library directly (agents that read `.agents/skills/`) *and* via this marketplace.

This repo is a thin aggregator: it clones each upstream library, mirrors the skill directory, and republishes it as both a marketplace plugin and a standalone skill.

## Where skill content lives in this repo

Each synced skill is materialized in **two** locations here:

- `plugins/<plugin>/skills/<skill>/` — consumed by the Claude Code plugin marketplace.
- `skills/<skill>/` — the standalone copy distributed via the [agentskills.io](https://agentskills.io) standard.

The two copies must stay byte-identical (they are mirrors of the same upstream). CI runs `scripts/check-skill-sync.sh` on every PR to enforce this.

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

## Adding a new skill

A new skill always lands in its library's repo first, then gets wired up here:

1. **The skill exists in the library** at `<package-dir>/.agents/skills/<skill-name>/`, following the library-skills layout (a `SKILL.md` plus any `references/...` it pulls in). That repo is the source of truth.
2. **A `sync_skill` entry is added to `scripts/sync-from-upstream.sh`** here, pointing at the upstream repo, the upstream subpath, and the plugin + standalone destinations.

## Manually triggering a sync

From the Actions tab, run **Sync skills from upstream** via `workflow_dispatch`. It will open (or update) the `autosync/upstream-skills` branch.
