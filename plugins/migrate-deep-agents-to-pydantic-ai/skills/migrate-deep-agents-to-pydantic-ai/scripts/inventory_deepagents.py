#!/usr/bin/env python3
"""Inventory LangChain Deep Agents migration signals without modifying a project."""

from __future__ import annotations

import argparse
import ast
import json
import os
from collections.abc import Iterator
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_MAX_FILES = 10_000
DEFAULT_MAX_FILE_BYTES = 2_000_000
DEFAULT_MAX_TOTAL_BYTES = 50_000_000
DEFAULT_MAX_ENTRIES = 100_000
DEFAULT_MAX_MATCHES = 20_000


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    "node_modules",
    "site-packages",
}

ASSET_NAMES = {
    "AGENTS.md": "instructions",
    "CLAUDE.md": "instructions",
    "SKILL.md": "skill",
    "deepagents.toml": "deploy_config",
    "agent.json": "deploy_config",
    "mcp.json": "mcp_config",
    "subagents.yaml": "subagent_config",
    "subagents.yml": "subagent_config",
}

SIGNALS: dict[str, tuple[str, ...]] = {
    "planning": ("write_todos", "TodoListMiddleware"),
    "filesystem": (
        "FilesystemBackend",
        "StateBackend",
        "StoreBackend",
        "CompositeBackend",
        "read_file",
        "write_file",
    ),
    "shell_or_sandbox": (
        "SandboxBackend",
        "LangSmithSandbox",
        "execute(",
        '"execute"',
        "'execute'",
    ),
    "subagents": ("subagents=", "SubAgentMiddleware", "AsyncSubAgent", "task("),
    "skills": ("skills=", "SkillsMiddleware", "SKILL.md"),
    "memory": ("memory=", "MemoryMiddleware", "/memories/"),
    "middleware": (
        "middleware=",
        "AgentMiddleware",
        "@before_model",
        "@after_agent",
        "wrap_tool_call",
    ),
    "approvals_or_permissions": (
        "interrupt_on=",
        "permissions=",
        "HumanInTheLoopMiddleware",
    ),
    "persistence": ("checkpointer=", "store=", "thread_id", "conversation_id"),
    "streaming": (".astream(", ".astream_events(", "stream_mode", ".stream("),
    "structured_output": ("response_format=", "ToolStrategy", "ProviderStrategy"),
    "harness_profile": (
        "HarnessProfile",
        "HarnessProfileConfig",
        "register_harness_profile",
        "excluded_tools",
        "excluded_middleware",
        "extra_middleware",
        "general_purpose_subagent",
        "SystemPromptConfig",
        "base_system_prompt",
        "system_prompt_suffix",
        "tool_description_overrides",
    ),
    "mcp": ("mcp.json", "MCP", "mcp_server"),
}


@dataclass(frozen=True)
class Location:
    path: str
    line: int | None = None


@dataclass(frozen=True)
class AgentCall:
    path: str
    line: int
    keywords: list[str]
    literal_model: str | None


class DeepAgentVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.calls: list[AgentCall] = []
        self.imports: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.startswith(("deepagents", "langchain", "langgraph")):
                self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module.startswith(("deepagents", "langchain", "langgraph")):
            self.imports.add(module)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = self._call_name(node.func)
        if name == "create_deep_agent":
            keywords = sorted(keyword.arg for keyword in node.keywords if keyword.arg)
            literal_model = None
            model_node = next(
                (keyword.value for keyword in node.keywords if keyword.arg == "model"),
                None,
            )
            if isinstance(model_node, ast.Constant) and isinstance(
                model_node.value, str
            ):
                literal_model = model_node.value
            self.calls.append(
                AgentCall(
                    path=self.path,
                    line=node.lineno,
                    keywords=keywords,
                    literal_model=literal_model,
                )
            )
        self.generic_visit(node)

    @staticmethod
    def _call_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None


def iter_files(
    root: Path,
    *,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
    max_entries: int,
) -> tuple[list[Path], list[dict[str, Any]]]:
    files: list[Path] = []
    warnings: list[dict[str, Any]] = []
    candidate_count = 0
    entry_count = 0
    total_bytes = 0

    def on_walk_error(exc: OSError) -> None:
        error_path = Path(exc.filename) if exc.filename else root
        try:
            display_path = error_path.resolve().relative_to(root).as_posix() or "."
        except (OSError, ValueError):
            display_path = str(error_path)
        warnings.append(
            {
                "path": display_path,
                "warning": f"directory walk failed: {type(exc).__name__}: {exc}",
            }
        )

    for current, dirs, names in os.walk(root, onerror=on_walk_error):
        entry_count += len(dirs) + len(names)
        if entry_count > max_entries:
            warnings.append(
                {
                    "path": Path(current).relative_to(root).as_posix() or ".",
                    "warning": f"stopped after more than {max_entries} directory entries",
                }
            )
            return files, warnings
        base = Path(current)
        safe_dirs: list[str] = []
        for directory in sorted(dirs):
            path = base / directory
            if directory in IGNORED_DIRS:
                continue
            if path.is_symlink():
                warnings.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "warning": "skipped symlinked directory",
                    }
                )
                continue
            safe_dirs.append(directory)
        dirs[:] = safe_dirs

        for name in sorted(names):
            path = base / name
            if path.suffix.lower() not in {
                ".py",
                ".md",
                ".toml",
                ".json",
                ".yaml",
                ".yml",
            }:
                continue
            if candidate_count >= max_files:
                warnings.append(
                    {
                        "path": ".",
                        "warning": f"stopped after {max_files} candidate files",
                    }
                )
                return files, warnings
            candidate_count += 1
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                warnings.append({"path": relative, "warning": "skipped symlinked file"})
                continue
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(root)
                size = resolved.stat().st_size
            except (OSError, ValueError) as exc:
                warnings.append(
                    {
                        "path": relative,
                        "warning": f"skipped unsafe file: {type(exc).__name__}: {exc}",
                    }
                )
                continue
            if size > max_file_bytes:
                warnings.append(
                    {
                        "path": relative,
                        "warning": f"skipped oversized file ({size} bytes; limit {max_file_bytes})",
                    }
                )
                continue
            if total_bytes + size > max_total_bytes:
                warnings.append(
                    {
                        "path": relative,
                        "warning": f"stopped before exceeding {max_total_bytes} total bytes",
                    }
                )
                return files, warnings
            total_bytes += size
            files.append(resolved)
    return files, warnings


def matching_lines(text: str, needles: tuple[str, ...]) -> Iterator[int]:
    for line_number, line in enumerate(text.splitlines(), 1):
        if any(needle in line for needle in needles):
            yield line_number


def inventory(
    root: Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_matches: int = DEFAULT_MAX_MATCHES,
) -> dict[str, Any]:
    agent_calls: list[AgentCall] = []
    imports: dict[str, set[str]] = defaultdict(set)
    assets: dict[str, list[Location]] = defaultdict(list)
    signals: dict[str, list[Location]] = defaultdict(list)
    parse_errors: list[dict[str, Any]] = []

    paths, inspection_warnings = iter_files(
        root,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
        max_entries=max_entries,
    )
    total_matches = 0
    match_limit_reported = False
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            parse_errors.append(
                {"path": relative, "error": f"read: {type(exc).__name__}: {exc}"}
            )
            continue

        asset_kind = ASSET_NAMES.get(path.name)
        if asset_kind is not None:
            assets[asset_kind].append(Location(relative))
        if "subagents" in Path(relative).parts and path.name in {
            "AGENTS.md",
            "agent.json",
            "deepagents.toml",
        }:
            assets["subagent_definition"].append(Location(relative))

        for signal, needles in SIGNALS.items():
            for line in matching_lines(text, needles):
                if total_matches >= max_matches:
                    if not match_limit_reported:
                        inspection_warnings.append(
                            {
                                "path": relative,
                                "warning": f"stopped recording behavior matches after {max_matches}",
                            }
                        )
                        match_limit_reported = True
                    break
                signals[signal].append(Location(relative, line))
                total_matches += 1

        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(text, filename=relative)
        except SyntaxError as exc:
            parse_errors.append(
                {"path": relative, "line": exc.lineno, "error": f"syntax: {exc.msg}"}
            )
            continue
        visitor = DeepAgentVisitor(relative)
        visitor.visit(tree)
        agent_calls.extend(visitor.calls)
        for call in visitor.calls:
            if total_matches < max_matches:
                signals["harness_profile_resolution"].append(
                    Location(call.path, call.line)
                )
                total_matches += 1
            elif not match_limit_reported:
                inspection_warnings.append(
                    {
                        "path": relative,
                        "warning": f"stopped recording behavior matches after {max_matches}",
                    }
                )
                match_limit_reported = True
        for module in visitor.imports:
            imports[module].add(relative)

    return {
        "root": str(root),
        "create_deep_agent_calls": [asdict(call) for call in agent_calls],
        "framework_imports": {
            module: sorted(paths) for module, paths in sorted(imports.items())
        },
        "assets": {
            kind: [asdict(item) for item in items]
            for kind, items in sorted(assets.items())
        },
        "signals": {
            name: [asdict(item) for item in items]
            for name, items in sorted(signals.items())
        },
        "parse_errors": parse_errors,
        "inspection_warnings": inspection_warnings,
    }


def render_markdown(data: dict[str, Any]) -> str:
    lines = ["# Deep Agents migration inventory", "", f"Root: `{data['root']}`", ""]
    calls = data["create_deep_agent_calls"]
    lines.extend(["## Agent constructors", ""])
    if calls:
        for call in calls:
            keywords = ", ".join(call["keywords"]) or "none"
            model = (
                f"; model `{call['literal_model']}`" if call["literal_model"] else ""
            )
            lines.append(
                f"- `{call['path']}:{call['line']}` — keywords: {keywords}{model}"
            )
    else:
        lines.append(
            "- No `create_deep_agent(...)` call found; inspect factories, aliases, and generated configs manually."
        )

    lines.extend(["", "## Behavior signals", ""])
    for name, locations in data["signals"].items():
        examples = ", ".join(
            f"`{item['path']}:{item['line']}`"
            if item.get("line")
            else f"`{item['path']}`"
            for item in locations[:5]
        )
        suffix = f" — {examples}" if examples else ""
        lines.append(f"- **{name}**: {len(locations)} match(es){suffix}")

    lines.extend(["", "## Agent assets", ""])
    if data["assets"]:
        for kind, locations in data["assets"].items():
            examples = ", ".join(f"`{item['path']}`" for item in locations[:8])
            lines.append(f"- **{kind}**: {len(locations)} — {examples}")
    else:
        lines.append("- No conventional assets found.")

    lines.extend(["", "## Framework imports", ""])
    if data["framework_imports"]:
        for module, paths in data["framework_imports"].items():
            shown = ", ".join(f"`{path}`" for path in paths[:6])
            omitted = len(paths) - 6
            suffix = f", … (+{omitted} more)" if omitted > 0 else ""
            lines.append(f"- `{module}` — {len(paths)} file(s): {shown}{suffix}")
    else:
        lines.append("- No direct Deep Agents, LangChain, or LangGraph imports found.")

    if data["parse_errors"]:
        lines.extend(["", "## Inspection warnings", ""])
        for error in data["parse_errors"]:
            line = f":{error['line']}" if error.get("line") else ""
            lines.append(f"- `{error['path']}{line}` — {error['error']}")

    if data["inspection_warnings"]:
        lines.extend(["", "## Scanner warnings", ""])
        for warning in data["inspection_warnings"]:
            lines.append(f"- `{warning['path']}` — {warning['warning']}")

    lines.extend(
        [
            "",
            "## Next step",
            "",
            "Verify every signal against runtime wiring, then classify it as direct, composed, custom, or retained externally.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Deep Agents project root")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES)
    parser.add_argument("--max-matches", type=int, default=DEFAULT_MAX_MATCHES)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    limits = (
        args.max_files,
        args.max_file_bytes,
        args.max_total_bytes,
        args.max_entries,
        args.max_matches,
    )
    if any(limit < 1 for limit in limits):
        parser.error("all --max-* limits must be positive")
    data = inventory(
        root,
        max_files=args.max_files,
        max_file_bytes=args.max_file_bytes,
        max_total_bytes=args.max_total_bytes,
        max_entries=args.max_entries,
        max_matches=args.max_matches,
    )
    if args.format == "json":
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(render_markdown(data), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
