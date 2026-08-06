#!/bin/sh
# Runs codex_logfire_hook.py with a Python interpreter that is known to work.
#
# Invoking a bare `python3` is not reliable: version-manager shims (notably
# pyenv's) can hang instead of failing when their backing installation is
# broken, and Codex then blocks on every hook until its timeout, grinding the
# chat to a crawl. This wrapper probes interpreter candidates with a short
# watchdog, caches the first one that answers, and fails open (exit 0) when
# none does, so a broken Python setup degrades to "no telemetry" rather than
# "stalled chats".
#
# Configuration:
#   CODEX_LOGFIRE_PYTHON     absolute path to the interpreter to use; trusted
#                            as-is (no probe). May also be set in the exporter
#                            config.env file.
#   CODEX_LOGFIRE_STATE_DIR  overrides where the interpreter choice is cached
#                            (same variable the hook itself uses for state).
#   CODEX_LOGFIRE_DEBUG      when non-empty, selection details are written to
#                            stderr.

set -u

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
HOOK_SCRIPT="$SCRIPT_DIR/codex_logfire_hook.py"

STATE_DIR="${CODEX_LOGFIRE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/logfire-exporter}"
CACHE_FILE="$STATE_DIR/python_interpreter"
PROBE_TIMEOUT_TICKS=20 # x 0.1s = 2 seconds

debug() {
    if [ -n "${CODEX_LOGFIRE_DEBUG:-}" ]; then
        printf 'run_codex_logfire_hook: %s\n' "$1" >&2
    fi
}

# The hook script itself loads config.env, but the interpreter choice is
# needed before any Python runs, so read this one key here too.
load_python_from_config() {
    config_file="${CODEX_LOGFIRE_CONFIG_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/logfire-exporter/config.env}"
    [ -f "$config_file" ] || return 1
    # Accept the same shapes the hook's own config parser does: optional
    # whitespace around the key and '=', and whitespace-padded values.
    line=$(grep -E '^[[:space:]]*CODEX_LOGFIRE_PYTHON[[:space:]]*=' "$config_file" 2>/dev/null | tail -n 1) || return 1
    [ -n "$line" ] || return 1
    value=$(printf '%s' "${line#*=}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
    # Strip one layer of surrounding quotes, matching the hook's env parsing.
    case $value in
        \"*\") value=${value#\"}; value=${value%\"} ;;
        \'*\') value=${value#\'}; value=${value%\'} ;;
    esac
    [ -n "$value" ] || return 1
    CODEX_LOGFIRE_PYTHON=$value
    return 0
}

# probe <interpreter>: true when the interpreter starts, is Python 3, and
# exits within the watchdog window. Stdin is redirected away so a probe can
# never consume the hook payload.
probe() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' </dev/null >/dev/null 2>&1 &
    probe_pid=$!
    (
        ticks=0
        while [ "$ticks" -lt "$PROBE_TIMEOUT_TICKS" ]; do
            kill -0 "$probe_pid" 2>/dev/null || exit 0
            # Fractional sleep is not POSIX; degrade to whole seconds where
            # unsupported, consuming ten ticks per second so the total
            # watchdog window stays ~2s either way.
            sleep 0.1 2>/dev/null || { sleep 1; ticks=$((ticks + 9)); }
            ticks=$((ticks + 1))
        done
        # A hanging shim usually blocks on a child it spawned; sweep that
        # child too so it is not orphaned to run to completion (one leaked
        # process per hook run). Snapshot the children BEFORE killing the
        # parent: killing them first can let the parent finish cleanly and
        # the probe would then count as a success, selecting the hung shim.
        # (setsid + a process-group kill would be more thorough, but setsid
        # does not exist on macOS, where this failure mode is most common.)
        probe_children=$(pgrep -P "$probe_pid" 2>/dev/null)
        kill -9 "$probe_pid" 2>/dev/null
        if [ -n "$probe_children" ]; then
            # shellcheck disable=SC2086 # word-splitting the PID list is intended
            kill -9 $probe_children 2>/dev/null
        fi
    ) &
    watchdog_pid=$!
    wait "$probe_pid" 2>/dev/null
    probe_status=$?
    kill "$watchdog_pid" 2>/dev/null
    wait "$watchdog_pid" 2>/dev/null
    [ "$probe_status" -eq 0 ]
}

run_with() {
    exec "$1" "$HOOK_SCRIPT"
}

if [ -z "${CODEX_LOGFIRE_PYTHON:-}" ]; then
    load_python_from_config || true
fi

if [ -n "${CODEX_LOGFIRE_PYTHON:-}" ]; then
    debug "using CODEX_LOGFIRE_PYTHON=$CODEX_LOGFIRE_PYTHON"
    run_with "$CODEX_LOGFIRE_PYTHON"
fi

# A previously cached interpreter is still probed (cheap when healthy) so a
# cache pointing at a since-broken shim falls through to a fresh scan instead
# of hanging.
if [ -f "$CACHE_FILE" ]; then
    cached=$(cat "$CACHE_FILE" 2>/dev/null || printf '')
    if [ -n "$cached" ] && [ -x "$cached" ] && probe "$cached"; then
        debug "using cached interpreter $cached"
        run_with "$cached"
    fi
    debug "cached interpreter unusable, rescanning"
fi

for candidate in python3 /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python; do
    resolved=$(command -v "$candidate" 2>/dev/null) || continue
    if probe "$resolved"; then
        debug "selected $resolved"
        mkdir -p "$STATE_DIR" 2>/dev/null || true
        printf '%s\n' "$resolved" > "$CACHE_FILE" 2>/dev/null || true
        run_with "$resolved"
    fi
    debug "candidate $resolved failed probe"
done

# Fail open: exporting telemetry is never worth breaking the conversation.
debug "no working Python 3 interpreter found; skipping export"
exit 0
