#!/usr/bin/env bash
set -euo pipefail

# Ensure standalone skills/ copies stay in sync with plugin sources.

exit_code=0

check_sync() {
    local plugin_file="$1"
    local standalone_file="$2"

    if [ ! -f "$standalone_file" ]; then
        echo "MISSING: $standalone_file (should mirror $plugin_file)"
        exit_code=1
        return
    fi

    if ! diff -q "$plugin_file" "$standalone_file" > /dev/null 2>&1; then
        echo "OUT OF SYNC: $standalone_file != $plugin_file"
        echo "  Run: cp $plugin_file $standalone_file"
        exit_code=1
    fi
}

check_sync \
    plugins/instrument-with-logfire/skills/logfire-instrumentation/SKILL.md \
    skills/logfire-instrumentation/SKILL.md

check_sync \
    plugins/instrument-with-logfire/skills/logfire-instrumentation/references/logging-patterns.md \
    skills/logfire-instrumentation/references/logging-patterns.md

exit $exit_code
