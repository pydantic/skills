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

check_dir_sync \
    plugins/logfire/skills/logfire-setup \
    skills/logfire-setup

check_dir_sync \
    plugins/logfire/skills/logfire-instrumentation \
    skills/logfire-instrumentation

check_dir_sync \
    plugins/logfire/skills/logfire-infrastructure \
    skills/logfire-infrastructure

check_dir_sync \
    plugins/logfire/skills/logfire-evals \
    skills/logfire-evals

check_dir_sync \
    plugins/logfire/skills/logfire-query \
    skills/logfire-query

check_dir_sync \
    plugins/logfire/skills/logfire-ui \
    skills/logfire-ui

check_dir_sync \
    plugins/ai/skills/building-pydantic-ai-agents \
    skills/building-pydantic-ai-agents

check_dir_sync \
    plugins/ai/skills/migrating-agno-to-pydantic-ai \
    skills/migrating-agno-to-pydantic-ai

check_dir_sync \
    plugins/ai/skills/migrating-claude-agent-sdk-to-pydantic-ai \
    skills/migrating-claude-agent-sdk-to-pydantic-ai

check_dir_sync \
    plugins/ai/skills/migrating-google-adk-to-pydantic-ai \
    skills/migrating-google-adk-to-pydantic-ai

check_dir_sync \
    plugins/ai/skills/migrating-langchain-to-pydantic-ai \
    skills/migrating-langchain-to-pydantic-ai

check_dir_sync \
    plugins/ai/skills/migrating-mastra-to-pydantic-ai \
    skills/migrating-mastra-to-pydantic-ai

check_dir_sync \
    plugins/ai/skills/migrating-openai-agents-sdk-to-pydantic-ai \
    skills/migrating-openai-agents-sdk-to-pydantic-ai

check_dir_sync \
    plugins/ai/skills/migrating-pi-to-pydantic-ai \
    skills/migrating-pi-to-pydantic-ai

check_dir_sync \
    plugins/ai/skills/migrating-vercel-ai-sdk-and-eve-to-pydantic-ai \
    skills/migrating-vercel-ai-sdk-and-eve-to-pydantic-ai

check_dir_sync \
    plugins/pydantic-ai-harness/skills/pydantic-ai-harness \
    skills/pydantic-ai-harness

check_dir_sync \
    plugins/pydantic/skills/pydantic \
    skills/pydantic

exit $exit_code
