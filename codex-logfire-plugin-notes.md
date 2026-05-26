# Codex Logfire Plugin Notes

Date: 2026-05-12

Update: 2026-05-14 - this repository now includes a local Codex marketplace at `.agents/plugins/marketplace.json`
with `logfire` and `logfire-exporter` entries.

## Context

We discussed whether the existing Pydantic agent-skills/plugin work can support a Codex app plugin for Logfire, and what value such a plugin could add beyond a plain MCP server.

## Value Beyond Regular MCP

A Logfire Codex plugin should not just expose MCP tools. The higher-value layer is opinionated observability workflows:

- Investigate a trace or production error from a user prompt.
- Explain latency or error-rate spikes.
- Compare behavior before and after a deploy.
- Find slow endpoints, top exceptions, or problematic services.
- Summarize telemetry into an incident/debugging report.
- Connect trace data back to local source files and suggest fixes.
- Add or improve Logfire instrumentation in the current repo.

Codex can also render inline charts if the plugin or skill generates image files locally and the assistant references them with absolute Markdown image paths. Useful chart targets include latency over time, error-rate trends, endpoint breakdowns, trace waterfalls, and before/after comparisons.

## Publishing And Distribution

Current public Codex plugin distribution appears to go through the OpenAI Apps SDK submission/review flow. After an approved app is published, OpenAI can create the Codex plugin for Codex distribution. Self-serve Codex plugin publishing was described in the docs as coming soon.

For private or developer testing, Codex supports plugin marketplaces from local or Git-backed sources. A repo marketplace uses:

```text
.agents/plugins/marketplace.json
```

A plugin uses:

```text
plugins/<plugin-name>/.codex-plugin/plugin.json
```

## Local Testing

Local testing does not require a GitHub marketplace repo. It does require a local marketplace root that Codex can add:

```bash
codex plugin marketplace add /absolute/path/to/marketplace-root
```

The local marketplace file should include entries with Codex's source/policy/category shape, for example:

```json
{
  "name": "local-logfire",
  "interface": {
    "displayName": "Local Logfire"
  },
  "plugins": [
    {
      "name": "logfire",
      "source": {
        "source": "local",
        "path": "./plugins/logfire"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

## Current Pydantic Repo State

The relevant repo is this one:

- `pydantic/skills`

It includes Claude Code marketplace metadata:

```text
.claude-plugin/marketplace.json
plugins/logfire/.claude-plugin/plugin.json
plugins/ai/.claude-plugin/plugin.json
```

It also includes local Codex marketplace metadata:

```text
.agents/plugins/marketplace.json
plugins/logfire/.codex-plugin/plugin.json
plugins/logfire-exporter/.codex-plugin/plugin.json
plugins/logfire-exporter/hooks/hooks.json
```

The Logfire plugin content is shared across hosts:

```text
plugins/logfire/skills/logfire-instrumentation/SKILL.md
plugins/logfire/skills/logfire-query/SKILL.md
plugins/logfire/skills/logfire-ui/SKILL.md
plugins/logfire/.mcp.json
plugins/logfire/commands/*.md
```

Codex local installation uses:

```bash
codex plugin marketplace add /absolute/path/to/pydantic/skills
```

Then enable `logfire` or `logfire-exporter` from the Codex plugin UI. After changing local plugin files, refresh
the cache with `./scripts/reload-codex-plugin.sh logfire` or
`./scripts/reload-codex-plugin.sh logfire-exporter`.

The separate `pydantic/claude-code-logfire-plugin` repo is more Claude-specific. It uses `.claude-plugin/plugin.json`, Claude hook events, and Claude environment assumptions such as `CLAUDE_PROJECT_DIR`. It may be a useful reference for session capture, but it is not directly portable to Codex.

## Compatibility Matrix

| Feature | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| `SKILL.md` skills | Yes | Yes | Yes |
| `.claude-plugin/marketplace.json` | Yes | No | No |
| `.codex-plugin/plugin.json` | No | Yes | No |
| `.agents/plugins/marketplace.json` | No | Yes | No |
| OpenCode JS/TS plugins | No | No | Yes |

OpenCode has a similar skills concept and can discover skills under `.opencode/skills`, `.claude/skills`, and `.agents/skills`. It also has its own JS/TS plugin mechanism, but that is separate from Claude or Codex marketplace manifests.

## Repo Naming

The name `pydantic/skills` is reasonable if the repo's core purpose is reusable `SKILL.md` content across agents. It becomes less precise if the repo grows into a broader distribution hub with Codex manifests, Claude plugins, OpenCode plugins, MCP config, hooks, and commands.

Possible alternatives if the scope broadens:

- `pydantic-agent-skills`
- `pydantic-agent-extensions`
- `pydantic-agent-tooling`

For now, keeping `pydantic/skills` is defensible because skills are the common denominator across Claude Code, Codex, OpenCode, and other agents.

## Implemented Metadata Layout

Codex metadata now lives in parallel with the existing Claude metadata:

```text
.claude-plugin/marketplace.json
.agents/plugins/marketplace.json
plugins/logfire/.claude-plugin/plugin.json
plugins/logfire/.codex-plugin/plugin.json
plugins/logfire/skills/
plugins/logfire/.mcp.json
```

This keeps Claude Code working while making the same Logfire skill content discoverable and installable by Codex.
The Codex-only exporter plugin adds lifecycle hooks that export Codex turn and tool telemetry to Logfire.
