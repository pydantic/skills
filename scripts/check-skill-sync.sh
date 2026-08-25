#!/usr/bin/env bash
set -euo pipefail

# Ensure standalone skills/ copies stay byte-identical to plugin sources.
#
# A recursive diff enforces the "plugin dir == standalone dir" invariant for
# each skill without depending on a hand-curated file list, which would go stale
# the moment a skill adds a new file.

exit_code=0

check_dir_sync() {
    local plugin_dir="$1"
    local standalone_dir="$2"

    if [ ! -d "$plugin_dir" ]; then
        echo "MISSING plugin dir: $plugin_dir"
        exit_code=1
        return
    fi

    if [ ! -d "$standalone_dir" ]; then
        echo "MISSING standalone dir: $standalone_dir (should mirror $plugin_dir)"
        exit_code=1
        return
    fi

    if ! diff -rq "$plugin_dir" "$standalone_dir"; then
        echo "OUT OF SYNC: $standalone_dir does not match $plugin_dir"
        echo "  Run: rsync -a --delete '$plugin_dir/' '$standalone_dir/'"
        exit_code=1
    fi
}

shopt -s nullglob

# Claude Code resolves these Git-hosted plugins by commit SHA. An explicit
# version would pin installed users to stale skill content between bumps.
for manifest in .claude-plugin/marketplace.json plugins/*/.claude-plugin/plugin.json; do
    if grep -q '"version"[[:space:]]*:' "$manifest"; then
        echo "PINNED Claude plugin version: $manifest (omit version to use the Git commit SHA)"
        exit_code=1
    fi
done

# Discover mirrored skills so adding a sync_skill entry does not also require
# maintaining a second hardcoded registry in this script.
for plugin_dir in plugins/*/skills/*; do
    [ -d "$plugin_dir" ] || continue
    skill_name="${plugin_dir##*/}"
    check_dir_sync "$plugin_dir" "skills/$skill_name"
done

# A standalone skill must belong to exactly one plugin. This also catches
# orphaned copies and ambiguous duplicate skill names across plugins.
for standalone_dir in skills/*; do
    [ -d "$standalone_dir" ] || continue
    skill_name="${standalone_dir##*/}"
    plugin_dirs=(plugins/*/skills/"$skill_name")

    if [ "${#plugin_dirs[@]}" -ne 1 ]; then
        echo "INVALID mirror ownership: $standalone_dir has ${#plugin_dirs[@]} plugin mirrors (expected 1)"
        exit_code=1
    fi
done

exit $exit_code
