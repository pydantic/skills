from __future__ import annotations

import json
import unittest
from collections.abc import Iterator
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HOOKS_PATH = ROOT / "hooks" / "hooks.json"
WINDOWS_LAUNCHER_PATH = ROOT / "scripts" / "run_codex_logfire_hook.cmd"


class HooksConfigTests(unittest.TestCase):
    def command_hooks(self) -> Iterator[tuple[str, dict[str, Any]]]:
        config = json.loads(HOOKS_PATH.read_text(encoding="utf-8"))
        for event_name, groups in config["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    if hook["type"] == "command":
                        yield event_name, hook

    def test_all_commands_have_platform_launchers_and_expected_timeouts(self) -> None:
        expected_timeouts = {
            "SessionStart": 10,
            "UserPromptSubmit": 10,
            "PostToolUse": 10,
            "Stop": 30,
        }
        hooks = list(self.command_hooks())

        self.assertEqual({event_name for event_name, _ in hooks}, set(expected_timeouts))
        for event_name, hook in hooks:
            self.assertIn("${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}", hook["command"])
            windows_command = hook["commandWindows"]
            self.assertIn("%PLUGIN_ROOT%", windows_command)
            self.assertIn("run_codex_logfire_hook.cmd", windows_command)
            self.assertNotIn(" sh ", f" {windows_command.lower()} ")
            self.assertEqual(hook["timeout"], expected_timeouts[event_name])

    def test_windows_launcher_runs_real_hook_and_fails_open(self) -> None:
        launcher = WINDOWS_LAUNCHER_PATH.read_text(encoding="utf-8")

        self.assertIn("codex_logfire_hook.py", launcher)
        self.assertIn("CODEX_LOGFIRE_PYTHON", launcher)
        self.assertIn("exit /b 0", launcher.lower())

    def test_windows_launcher_falls_back_after_failed_candidates(self) -> None:
        launcher = WINDOWS_LAUNCHER_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'python3 "%~dp0codex_logfire_hook.py"\n    if not errorlevel 1 exit /b 0',
            launcher,
        )
        self.assertIn(
            'py -3 "%~dp0codex_logfire_hook.py"\n    if not errorlevel 1 exit /b 0',
            launcher,
        )


if __name__ == "__main__":
    unittest.main()
