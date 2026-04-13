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
    plugins/ai/skills/building-pydantic-ai-agents/SKILL.md \
    skills/building-pydantic-ai-agents/SKILL.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/COMMON-TASKS.md \
    skills/building-pydantic-ai-agents/references/COMMON-TASKS.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/ARCHITECTURE.md \
    skills/building-pydantic-ai-agents/references/ARCHITECTURE.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/AGENTS-CORE.md \
    skills/building-pydantic-ai-agents/references/AGENTS-CORE.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/CAPABILITIES-AND-HOOKS.md \
    skills/building-pydantic-ai-agents/references/CAPABILITIES-AND-HOOKS.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/TOOLS-CORE.md \
    skills/building-pydantic-ai-agents/references/TOOLS-CORE.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/BUILTIN-TOOLS.md \
    skills/building-pydantic-ai-agents/references/BUILTIN-TOOLS.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/TOOLS-ADVANCED.md \
    skills/building-pydantic-ai-agents/references/TOOLS-ADVANCED.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/INPUT-AND-HISTORY.md \
    skills/building-pydantic-ai-agents/references/INPUT-AND-HISTORY.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/TESTING-AND-DEBUGGING.md \
    skills/building-pydantic-ai-agents/references/TESTING-AND-DEBUGGING.md

check_sync \
    plugins/ai/skills/building-pydantic-ai-agents/references/ORCHESTRATION-AND-INTEGRATIONS.md \
    skills/building-pydantic-ai-agents/references/ORCHESTRATION-AND-INTEGRATIONS.md

exit $exit_code
