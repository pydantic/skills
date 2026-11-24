"""Opt-in recovery checks against the published CLI, with isolated local APIs only."""

import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CLI = os.environ.get("LOGFIRE_CONNECTION_TEST_CLI") or os.environ.get(
    "LOGFIRE_CLAUDE_TEST_CLI"
)
PROJECT_ID = "11111111-1111-1111-1111-111111111111"
MANAGEMENT_KEY = "synthetic-management-api-key"


class LocalApiFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.calls = []
        self.identity_tools = []
        calls = self.calls
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def reply(self, status, value):
                body = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                calls.append(("GET", self.path))
                if self.path == "/api/v1/projects/":
                    self.reply(
                        200,
                        [
                            {
                                "id": PROJECT_ID,
                                "organization_name": "smoke-org",
                                "project_name": "smoke-project",
                                "created_at": "2026-01-01T00:00:00Z",
                                "updated_at": "2026-01-01T00:00:00Z",
                                "description": None,
                                "visibility": "private",
                            }
                        ],
                    )
                elif (
                    self.path == f"/api/v1/projects/{PROJECT_ID}/write-tokens/"
                    and getattr(fixture, "allow_write_tokens", False)
                ):
                    self.reply(
                        200,
                        [
                            {
                                "id": "22222222-2222-2222-2222-222222222222",
                                "project_id": PROJECT_ID,
                                "active": True,
                                "created_at": "2026-01-01T00:00:00Z",
                                "created_by_name": None,
                                "description": None,
                                "expires_at": None,
                                "frontend_application_deleted": False,
                                "frontend_application_id": None,
                                "frontend_application_name": None,
                                "project_name": "smoke-project",
                                "token_prefix": "synthetic",
                            }
                        ],
                    )
                else:
                    self.reply(404, {})

            def do_POST(self):
                calls.append(("POST", self.path))
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                if self.path == "/mcp":
                    self.identity(json.loads(body))
                    return
                if (
                    self.path == f"/api/v1/projects/{PROJECT_ID}/write-tokens/"
                    and getattr(fixture, "allow_write_tokens", False)
                ):
                    self.reply(
                        200,
                        {
                            "id": "22222222-2222-2222-2222-222222222222",
                            "project_id": PROJECT_ID,
                            "token": "synthetic-exporter-token",
                            "created_at": "2026-01-01T00:00:00Z",
                            "description": None,
                            "expires_at": None,
                        },
                    )
                else:
                    self.reply(500, {"detail": "Unexpected mutation"})

            def identity(self, request):
                if self.headers.get("Authorization") != f"Bearer {MANAGEMENT_KEY}":
                    self.reply(401, {})
                    return
                method = request["method"]
                if method == "initialize":
                    result = {
                        "protocolVersion": request["params"]["protocolVersion"],
                        "serverInfo": {"name": "fixture", "version": "1"},
                        "capabilities": {"tools": {}},
                    }
                elif method == "notifications/initialized":
                    self.send_response(202)
                    self.end_headers()
                    return
                elif method == "tools/list":
                    result = {"tools": [{
                        "name": "token_info",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {"readOnlyHint": True},
                    }]}
                elif method == "tools/call":
                    name = request["params"]["name"]
                    fixture.identity_tools.append(name)
                    if name != "token_info":
                        self.reply(400, {})
                        return
                    result = {
                        "content": [{"type": "text", "text": "fixture identity"}],
                        "structuredContent": {"organization_name": "smoke-org"},
                    }
                else:
                    self.reply(400, {})
                    return
                self.reply(200, {"jsonrpc": "2.0", "id": request["id"], "result": result})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.config = self.root / "claude"
        self.data = self.root / "project"
        self.data.mkdir()
        self.credential = self.data / "logfire_credentials.json"
        self.credential.write_text(
            json.dumps(
                {
                    "token": "synthetic-sdk-token",
                    "project_name": "smoke-project",
                    "project_url": f"{self.base}/smoke-org/smoke-project",
                    "logfire_api_url": self.base,
                }
            )
        )
        self.env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.root),
            "USERPROFILE": str(self.root),
            "CLAUDE_CONFIG_DIR": str(self.config),
            "LOGFIRE_API_KEY": MANAGEMENT_KEY,
        }

    def run_cli(self, *arguments, base=None):
        return subprocess.run(
            [
                CLI,
                "--base-url",
                base or self.base,
                "--beta",
                "--no-input",
                "--output",
                "json",
                *arguments,
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    def telemetry(self, *arguments, base=None):
        return self.run_cli(
            "agent", "claude", "--data-dir", str(self.data), *arguments, base=base
        )


@unittest.skipUnless(CLI, "Set LOGFIRE_CLAUDE_TEST_CLI to the published CLI")
class PublishedCliTests(LocalApiFixture):
    def test_reconnect_and_disconnect_preserve_credentials_and_unrelated_settings(self):
        original_credential = self.credential.read_bytes()
        self.config.mkdir()
        settings = self.config / "settings.json"
        unrelated = {"permissions": {"allow": []}, "apiKeyHelper": "unrelated-helper"}
        settings.write_text(json.dumps(unrelated))
        for _ in range(2):
            current = self.run_cli("project", "--data-dir", str(self.data), "current")
            self.assertEqual(current.returncode, 0, current.stderr)
            configured = self.telemetry("configure", "--capture", "metadata-only")
            self.assertEqual(configured.returncode, 0, configured.stderr)
            self.assertNotIn("synthetic-sdk-token", settings.read_text())
        before_preview = settings.read_bytes()
        preview = self.telemetry("remove", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(settings.read_bytes(), before_preview)
        removed = self.telemetry("remove", "--yes")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertEqual(json.loads(settings.read_text()), unrelated)
        self.assertEqual(self.credential.read_bytes(), original_credential)
        self.assertFalse(any(method == "POST" for method, _ in self.calls))

    def test_independent_exporter_is_not_overwritten(self):
        self.config.mkdir()
        settings = self.config / "settings.json"
        original = json.dumps({"otelHeadersHelper": "independent-exporter"}).encode()
        settings.write_bytes(original)
        configured = self.telemetry("configure", "--capture", "metadata-only")
        self.assertNotEqual(configured.returncode, 0)
        self.assertIn("another OTLP header helper", configured.stderr)
        self.assertEqual(settings.read_bytes(), original)
        self.assertFalse(any(method == "POST" for method, _ in self.calls))

    def test_wrong_instance_cannot_retarget_the_saved_credential(self):
        original = self.credential.read_bytes()
        configured = self.telemetry(
            "configure", "--capture", "metadata-only", base="http://127.0.0.1:1"
        )
        self.assertNotEqual(configured.returncode, 0)
        self.assertEqual(self.credential.read_bytes(), original)
        self.assertFalse((self.config / "settings.json").exists())
        self.assertEqual(self.calls, [])

    def test_missing_project_does_not_create_a_token_or_pick_another_project(self):
        missing = self.root / "missing-project"
        result = self.run_cli(
            "init",
            "use",
            "--name",
            "not-a-project",
            "--data-dir",
            str(missing),
        )
        self.assertNotEqual(result.returncode, 0)
        error = json.loads(result.stderr)["error"]
        self.assertEqual(error["code"], "initialization_failed")
        self.assertIn('no project named "not-a-project"', error["message"])
        self.assertEqual(self.identity_tools, ["token_info"])
        self.assertEqual(
            [call for call in self.calls if call[1] != "/mcp"],
            [("GET", "/api/v1/projects/")],
        )
        self.assertFalse((missing / "logfire_credentials.json").exists())


if __name__ == "__main__":
    unittest.main()
