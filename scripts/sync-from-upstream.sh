#!/usr/bin/env bash
set -euo pipefail

# Sync skill content from upstream source repositories into this aggregator.
#
# Each entry below maps:
#   <upstream repo> : <upstream subpath>
#     -> <plugin destination>
#     -> <standalone destination>
#
# Paths are hardcoded on purpose. If upstream layout changes, this script must
# be updated explicitly so the change goes through review.

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

SUMMARY_FILE="${SUMMARY_FILE:-/tmp/sync-summary.md}"
: > "$SUMMARY_FILE"

sync_skill() {
    local upstream_repo="$1"
    local upstream_subpath="$2"
    local plugin_dest="$3"
    local standalone_dest="$4"
    local skill_name="$5"

    local clone_dir="$WORKDIR/$(echo "$upstream_repo" | tr '/' '_')"

    if [ ! -d "$clone_dir" ]; then
        echo "Cloning $upstream_repo..."
        git clone --depth=1 "https://github.com/$upstream_repo.git" "$clone_dir"
    fi

    local upstream_sha
    upstream_sha="$(git -C "$clone_dir" rev-parse HEAD)"

    local source_dir="$clone_dir/$upstream_subpath"
    if [ ! -d "$source_dir" ]; then
        echo "ERROR: $upstream_repo:$upstream_subpath not found at HEAD ($upstream_sha)" >&2
        exit 1
    fi

    echo "Syncing $skill_name from $upstream_repo@${upstream_sha:0:7}"
    mkdir -p "$plugin_dest" "$standalone_dest"
    rsync -a --delete "$source_dir/" "$plugin_dest/"
    rsync -a --delete "$source_dir/" "$standalone_dest/"

    printf -- '- **%s**: `%s@%s` (`%s`)\n' \
        "$skill_name" "$upstream_repo" "${upstream_sha:0:7}" "$upstream_subpath" \
        >> "$SUMMARY_FILE"
}

sync_skill \
    "pydantic/logfire" \
    "logfire/.agents/skills/logfire-instrumentation" \
    "plugins/logfire/skills/logfire-instrumentation" \
    "skills/logfire-instrumentation" \
    "logfire-instrumentation"

sync_skill \
    "pydantic/pydantic-ai" \
    "pydantic_ai_slim/pydantic_ai/.agents/skills/building-pydantic-ai-agents" \
    "plugins/ai/skills/building-pydantic-ai-agents" \
    "skills/building-pydantic-ai-agents" \
    "building-pydantic-ai-agents"

echo
echo "Sync complete. Summary:"
cat "$SUMMARY_FILE"
