#!/usr/bin/env bash
set -euo pipefail

plugin="${1:-logfire}"
marketplace="${2:-pydantic-skills}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$repo_root/plugins/$plugin"
manifest="$source_dir/.codex-plugin/plugin.json"
cache_root="${CODEX_HOME:-$HOME/.codex}/plugins/cache/$marketplace/$plugin"

if [ ! -d "$source_dir" ]; then
    echo "Missing plugin source: $source_dir" >&2
    exit 1
fi

if [ ! -f "$manifest" ]; then
    echo "Missing Codex plugin manifest: $manifest" >&2
    exit 1
fi

version="$(
    python3 - "$manifest" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text())
print(manifest["version"])
PY
)"
target_dir="$cache_root/$version"

mkdir -p "$target_dir"
python3 - "$source_dir" "$target_dir" <<'PY'
import shutil
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
target_resolved = target.resolve()

if ".codex/plugins/cache" not in target_resolved.as_posix():
    raise SystemExit(f"Refusing to replace unexpected target: {target_resolved}")

if target.exists():
    shutil.rmtree(target)
target.mkdir(parents=True)

def ignore(dir_path: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name == "__pycache__" or name.endswith(".pyc")
    }

shutil.copytree(source, target, dirs_exist_ok=True, ignore=ignore)
PY

echo "Reloaded $plugin@$marketplace $version"
echo "Source: $source_dir"
echo "Cache:  $target_dir"

if [ "$plugin" = "logfire" ]; then
    query_marker="$target_dir/skills/logfire-query/SKILL.md"
    ui_marker="$target_dir/skills/logfire-ui/SKILL.md"
    if rg -q "Critical Routing: One Workflow Per Request" "$query_marker" && rg -q "Do not query telemetry first" "$ui_marker"; then
        echo "Verified: Logfire query/UI routing contract is present."
    else
        echo "Warning: Logfire query/UI routing marker not found in $query_marker or $ui_marker" >&2
        exit 1
    fi
fi

echo
echo "Start a new Codex conversation to reload skill context."
