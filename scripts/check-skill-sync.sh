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

require_dir() {
    local dir="$1"
    local label="$2"
    if [ ! -d "$dir" ]; then
        echo "MISSING $label: $dir"
        exit_code=1
        return
    fi
}

# Print plugin_dest<TAB>standalone_dest for each sync_skill call in the
# upstream sync script. Those destinations are the authoritative registry
# for synced skills; filesystem discovery cannot see a skill deleted from
# both mirrors.
parse_synced_destinations() {
    local in_call=0
    local -a args=()
    local line

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ ^sync_skill[[:space:]]+\\ ]]; then
            in_call=1
            args=()
            continue
        fi
        if (( in_call )); then
            if [[ "$line" =~ \"([^\"]+)\" ]]; then
                args+=("${BASH_REMATCH[1]}")
            fi
            if (( ${#args[@]} == 5 )); then
                printf '%s\t%s\n' "${args[2]}" "${args[3]}"
                in_call=0
            fi
        fi
    done < scripts/sync-from-upstream.sh
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

expected_sync_calls="$(grep -c '^sync_skill \\' scripts/sync-from-upstream.sh || true)"
parsed_sync_calls=0
synced_skill_names="|"
while IFS=$'\t' read -r plugin_dir standalone_dir; do
    parsed_sync_calls=$((parsed_sync_calls + 1))
    synced_skill_names+="${plugin_dir##*/}|"
    require_dir "$plugin_dir" "synced plugin skill"
    require_dir "$standalone_dir" "synced standalone skill"
done < <(parse_synced_destinations)

if [ "$parsed_sync_calls" -eq 0 ] || [ "$parsed_sync_calls" -ne "$expected_sync_calls" ]; then
    echo "ERROR: parsed $parsed_sync_calls sync_skill destinations, expected $expected_sync_calls"
    exit_code=1
fi

# Repo-local skills are not in the sync script, so deletion cannot be
# derived from it. Keep this list in sync with skills that live only here.
local_skills=(logfire-query logfire-ui)
local_skill_names="|"
if [ "${#local_skills[@]}" -gt 0 ]; then
    for skill_name in "${local_skills[@]}"; do
        local_skill_names+="$skill_name|"
        if [[ "$synced_skill_names" == *"|$skill_name|"* ]]; then
            echo "INVALID local skill also synced: $skill_name"
            exit_code=1
        fi
        plugin_dirs=(plugins/*/skills/"$skill_name")
        if [ "${#plugin_dirs[@]}" -ne 1 ]; then
            echo "MISSING local skill plugin dir: $skill_name (expected 1, found ${#plugin_dirs[@]})"
            exit_code=1
            continue
        fi
        require_dir "${plugin_dirs[0]}" "local plugin skill"
        require_dir "skills/$skill_name" "local standalone skill"
    done
fi

# Every plugin skill on disk must be in the sync registry or local_skills.
# Otherwise a forgotten local skill can be deleted later with no CI failure.
for plugin_dir in plugins/*/skills/*; do
    [ -d "$plugin_dir" ] || continue
    skill_name="${plugin_dir##*/}"
    if [[ "$synced_skill_names" == *"|$skill_name|"* || "$local_skill_names" == *"|$skill_name|"* ]]; then
        continue
    fi
    echo "UNREGISTERED skill: $plugin_dir (add a sync_skill entry or local_skills)"
    exit_code=1
done

# Discover mirrored skills so equality checks cover every plugin skill
# without a second hardcoded path list.
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
