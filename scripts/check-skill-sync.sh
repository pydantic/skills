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
    plugins/logfire/skills/instrumentation/SKILL.md \
    skills/logfire-instrumentation/SKILL.md

check_sync \
    plugins/logfire/skills/instrumentation/references/python/logging-patterns.md \
    skills/logfire-instrumentation/references/python/logging-patterns.md

check_sync \
    plugins/logfire/skills/instrumentation/references/python/integrations.md \
    skills/logfire-instrumentation/references/python/integrations.md

check_sync \
    plugins/logfire/skills/instrumentation/references/javascript/patterns.md \
    skills/logfire-instrumentation/references/javascript/patterns.md

check_sync \
    plugins/logfire/skills/instrumentation/references/javascript/frameworks.md \
    skills/logfire-instrumentation/references/javascript/frameworks.md

check_sync \
    plugins/logfire/skills/instrumentation/references/rust/patterns.md \
    skills/logfire-instrumentation/references/rust/patterns.md

check_sync \
    plugins/logfire/skills/query/SKILL.md \
    skills/logfire-query/SKILL.md

check_sync \
    plugins/logfire/skills/query/references/schema.md \
    skills/logfire-query/references/schema.md

check_sync \
    plugins/logfire/skills/query/references/client-usage.md \
    skills/logfire-query/references/client-usage.md

exit $exit_code
