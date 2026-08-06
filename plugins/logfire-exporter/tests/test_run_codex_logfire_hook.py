from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = ROOT / "scripts" / "run_codex_logfire_hook.sh"

# The wrapper itself needs coreutils (dirname, grep, cat, sleep, ...), so the
# sandboxed PATHs used below always keep the system directories; fake
# interpreters shadow real ones by coming first.
SYSTEM_PATH = os.defpath.lstrip(os.pathsep)


@unittest.skipIf(sys.platform == "win32", "the hook wrapper targets POSIX shells")
class WrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.state_dir = self.tmp_path / "state"
        self.bin_dir = self.tmp_path / "bin"
        self.bin_dir.mkdir()

    def base_env(self) -> dict[str, str]:
        # State and config overrides keep the wrapper (and the hook it may
        # launch) away from the developer's real files.
        return {
            "HOME": str(self.tmp_path),
            "PATH": os.pathsep.join([str(self.bin_dir), SYSTEM_PATH]),
            "CODEX_LOGFIRE_STATE_DIR": str(self.state_dir),
            "CODEX_LOGFIRE_CONFIG_FILE": str(self.tmp_path / "config.env"),
        }

    def write_executable(self, path: Path, body: str) -> Path:
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def write_fake_interpreter(self, name: str, marker: Path) -> Path:
        # Answers any invocation (including the probe) and records its argv,
        # standing in for a working python3 without exec-ing the real hook.
        return self.write_executable(
            self.bin_dir / name,
            f'#!/bin/sh\nprintf \'%s\\n\' "$@" > "{marker}"\nexit 0\n',
        )

    def write_hanging_shim(self, name: str) -> Path:
        return self.write_executable(self.bin_dir / name, "#!/bin/sh\nsleep 60\nexit 0\n")

    def run_wrapper(
        self, env: dict[str, str], stdin: str = "", cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(WRAPPER_PATH)],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
            timeout=30.0,
        )

    def cached_interpreter(self) -> str | None:
        cache = self.state_dir / "python_interpreter"
        if not cache.is_file():
            return None
        return cache.read_text(encoding="utf-8").strip()

    def assert_process_exited(self, pid: int) -> None:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)
        self.fail(f"process {pid} is still present")

    def test_healthy_interpreter_runs_hook_and_caches_choice(self) -> None:
        marker = self.tmp_path / "ran"
        self.write_fake_interpreter("python3", marker)
        result = self.run_wrapper(self.base_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("codex_logfire_hook.py", marker.read_text(encoding="utf-8"))
        self.assertEqual(self.cached_interpreter(), str(self.bin_dir / "python3"))

    def test_real_interpreter_end_to_end(self) -> None:
        # With the real Python first on PATH the wrapper must run the real
        # hook, which exits 0 immediately on empty stdin.
        env = self.base_env()
        env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), SYSTEM_PATH])
        result = self.run_wrapper(env)
        self.assertEqual(result.returncode, 0, result.stderr)
        cached = self.cached_interpreter()
        if cached is None:
            self.fail("no interpreter was cached")
        self.assertTrue(Path(cached).exists())

    def test_hanging_shim_never_stalls_the_hook(self) -> None:
        # A pyenv-style shim that hangs shadows python3. The wrapper must kill
        # the probe after ~2s and move on (to a system interpreter when one
        # exists, else fail open); it must never wait on the shim.
        shim = self.write_hanging_shim("python3")
        started = time.monotonic()
        result = self.run_wrapper(self.base_env())
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 8.0)
        cached = self.cached_interpreter()
        if cached is not None:
            self.assertNotEqual(cached, str(shim))

    def test_missing_home_and_state_directory_fails_open(self) -> None:
        marker = self.tmp_path / "ran"
        self.write_fake_interpreter("python3", marker)
        env = self.base_env()
        env.pop("HOME")
        env.pop("CODEX_LOGFIRE_STATE_DIR")

        result = self.run_wrapper(env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())

    def test_normalizes_working_directory_before_running_python(self) -> None:
        marker = self.tmp_path / "working-directories"
        self.write_executable(
            self.bin_dir / "python3",
            f'''#!/bin/sh
printf '%s\t%s\t%s\n' "$1" "$PWD" "$(pwd -P)" >> "{marker}"
exit 0
''',
        )
        invocation_dir = self.tmp_path / "invocation"
        invocation_dir.mkdir()
        env = self.base_env()
        env["PWD"] = "."

        result = self.run_wrapper(
            env,
            stdin='{"hook_event_name": "Stop"}',
            cwd=invocation_dir,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        records = [line.split("\t") for line in marker.read_text().splitlines()]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0][0], "-c")
        self.assertIn("codex_logfire_hook.py", records[1][0])
        expected_cwd = str(WRAPPER_PATH.parent.resolve())
        for _, logical_cwd, physical_cwd in records:
            self.assertEqual(logical_cwd, expected_cwd)
            self.assertEqual(physical_cwd, expected_cwd)

    def test_watchdog_kills_complete_probe_process_tree(self) -> None:
        child_pidfile = self.tmp_path / "child.pid"
        grandchild_pidfile = self.tmp_path / "grandchild.pid"
        self.write_executable(
            self.bin_dir / "python3",
            f'''#!/bin/sh
/bin/sh -c 'sleep 60 & echo $! > "{grandchild_pidfile}"; wait' &
echo $! > "{child_pidfile}"
wait
''',
        )
        result = self.run_wrapper(self.base_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        child_pid = int(child_pidfile.read_text(encoding="utf-8").strip())
        grandchild_pid = int(grandchild_pidfile.read_text(encoding="utf-8").strip())
        self.assert_process_exited(child_pid)
        self.assert_process_exited(grandchild_pid)

    def test_env_override_is_trusted_without_probe(self) -> None:
        marker = self.tmp_path / "ran"
        pinned = self.write_fake_interpreter("pinned-python", marker)
        env = self.base_env()
        env["CODEX_LOGFIRE_PYTHON"] = str(pinned)
        result = self.run_wrapper(env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("codex_logfire_hook.py", marker.read_text(encoding="utf-8"))

    def test_config_file_override_is_used(self) -> None:
        marker = self.tmp_path / "ran"
        pinned = self.write_fake_interpreter("pinned-python", marker)
        (self.tmp_path / "config.env").write_text(
            f'CODEX_LOGFIRE_PYTHON="{pinned}"\n', encoding="utf-8"
        )
        result = self.run_wrapper(self.base_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("codex_logfire_hook.py", marker.read_text(encoding="utf-8"))

    def test_config_file_override_tolerates_whitespace(self) -> None:
        # The hook's own config parser allows whitespace around '=' and the
        # value; the wrapper's one-key parser must accept the same shapes.
        marker = self.tmp_path / "ran"
        pinned = self.write_fake_interpreter("pinned-python", marker)
        (self.tmp_path / "config.env").write_text(
            f"  CODEX_LOGFIRE_PYTHON = '{pinned}'  \n", encoding="utf-8"
        )
        result = self.run_wrapper(self.base_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("codex_logfire_hook.py", marker.read_text(encoding="utf-8"))

    def test_config_file_falls_back_to_legacy_paths(self) -> None:
        legacy_directories = ("codex-logfire-exporter", "codex-logfire-plugin")
        for index, legacy_directory in enumerate(legacy_directories):
            with self.subTest(legacy_directory=legacy_directory):
                marker = self.tmp_path / f"legacy-ran-{index}"
                pinned = self.write_fake_interpreter(f"legacy-python-{index}", marker)
                config_home = self.tmp_path / f"config-{index}"
                legacy_config = config_home / legacy_directory / "config.env"
                legacy_config.parent.mkdir(parents=True)
                legacy_config.write_text(
                    f"CODEX_LOGFIRE_PYTHON={pinned}\n", encoding="utf-8"
                )
                env = self.base_env()
                env.pop("CODEX_LOGFIRE_CONFIG_FILE")
                env["XDG_CONFIG_HOME"] = str(config_home)

                result = self.run_wrapper(env)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    "codex_logfire_hook.py", marker.read_text(encoding="utf-8")
                )

    def test_stale_cache_rescans_instead_of_hanging(self) -> None:
        hanging = self.write_hanging_shim("stale-python")
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "python_interpreter").write_text(f"{hanging}\n", encoding="utf-8")
        marker = self.tmp_path / "ran"
        self.write_fake_interpreter("python3", marker)
        started = time.monotonic()
        result = self.run_wrapper(self.base_env())
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(marker.exists(), "rescan did not reach the healthy interpreter")
        self.assertLess(elapsed, 8.0)
        self.assertEqual(self.cached_interpreter(), str(self.bin_dir / "python3"))

    def test_failed_cached_path_candidate_is_only_probed_once(self) -> None:
        marker = self.tmp_path / "probe-count"
        hanging = self.write_executable(
            self.bin_dir / "python3",
            f'#!/bin/sh\nprintf "probe\\n" >> "{marker}"\nsleep 60\n',
        )
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "python_interpreter").write_text(
            f"{hanging}\n", encoding="utf-8"
        )

        result = self.run_wrapper(self.base_env())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["probe"])

    def test_stdin_reaches_the_hook(self) -> None:
        # The probes must not consume the hook payload: the fake interpreter
        # answers probes (-c) directly and otherwise records stdin.
        capture = self.tmp_path / "stdin"
        self.write_executable(
            self.bin_dir / "python3",
            f'#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\ncat > "{capture}"\nexit 0\n',
        )
        result = self.run_wrapper(self.base_env(), stdin='{"hook_event_name": "Stop"}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(capture.read_text(encoding="utf-8"), '{"hook_event_name": "Stop"}')


if __name__ == "__main__":
    unittest.main()
