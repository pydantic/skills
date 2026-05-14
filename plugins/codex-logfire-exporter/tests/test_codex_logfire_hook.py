from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / "scripts" / "codex_logfire_hook.py"
spec = importlib.util.spec_from_file_location("codex_logfire_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(hook)


class CaptureHandler(BaseHTTPRequestHandler):
    body: bytes | None = None
    headers_seen: dict[str, str] = {}

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        type(self).body = self.rfile.read(length)
        type(self).headers_seen = dict(self.headers)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *_args: object) -> None:
        return


class HookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_env = os.environ.copy()
        os.environ.clear()
        os.environ.update(
            {
                "CODEX_LOGFIRE_STATE_DIR": str(Path(self.tmp.name) / "state"),
                "CODEX_LOGFIRE_CONFIG_FILE": str(Path(self.tmp.name) / "missing.env"),
            }
        )
        CaptureHandler.body = None
        CaptureHandler.headers_seen = {}
        self.addCleanup(self.restore_env)

    def restore_env(self) -> None:
        os.environ.clear()
        os.environ.update(self.old_env)

    def test_deterministic_ids_are_stable_and_sized(self) -> None:
        trace_id = hook.deterministic_hex_id("trace:v1", 16, "sess")
        self.assertEqual(trace_id, hook.deterministic_hex_id("trace:v1", 16, "sess"))
        self.assertEqual(len(trace_id), 32)
        self.assertNotEqual(trace_id, "0" * 32)

        span_id = hook.deterministic_hex_id("turn-span:v1", 8, "sess", "turn")
        self.assertEqual(len(span_id), 16)
        self.assertNotEqual(span_id, "0" * 16)

    def test_authorization_header_defaults_to_raw_token(self) -> None:
        self.assertEqual(hook.authorization_header("write-token"), "write-token")
        self.assertEqual(hook.authorization_header("Bearer write-token"), "Bearer write-token")
        os.environ["CODEX_LOGFIRE_AUTH_SCHEME"] = "Bearer"
        self.assertEqual(hook.authorization_header("write-token"), "Bearer write-token")

    def test_content_capture_defaults_to_full(self) -> None:
        self.assertEqual(hook.content_capture_mode(), "full")
        os.environ["CODEX_LOGFIRE_CONTENT_CAPTURE_MODE"] = "metadata_only"
        self.assertEqual(hook.content_capture_mode(), "metadata_only")
        os.environ["CODEX_LOGFIRE_CONTENT_CAPTURE_MODE"] = "invalid"
        self.assertEqual(hook.content_capture_mode(), "full")

    def test_config_env_path_falls_back_to_legacy_poc_path(self) -> None:
        os.environ.pop("CODEX_LOGFIRE_CONFIG_FILE", None)
        config_home = Path(self.tmp.name) / "config"
        os.environ["XDG_CONFIG_HOME"] = str(config_home)
        legacy_path = config_home / "codex-logfire-plugin" / "config.env"
        legacy_path.parent.mkdir(parents=True)
        legacy_path.write_text("LOGFIRE_TOKEN=legacy-token\n", encoding="utf-8")

        self.assertEqual(hook.config_env_path(), legacy_path)

        new_path = config_home / "codex-logfire-exporter" / "config.env"
        new_path.parent.mkdir(parents=True)
        new_path.write_text("LOGFIRE_TOKEN=new-token\n", encoding="utf-8")
        self.assertEqual(hook.config_env_path(), new_path)

    def test_stop_exports_turn_and_tool_spans(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        os.environ["LOGFIRE_TOKEN"] = "test-token"
        os.environ["LOGFIRE_URL"] = f"http://127.0.0.1:{server.server_port}"
        os.environ["CODEX_LOGFIRE_CONTENT_CAPTURE_MODE"] = "no_tool_content"

        transcript = Path(self.tmp.name) / "rollout.jsonl"
        transcript.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "event_msg",
                            "payload": {
                                "type": "token_count",
                                "info": {
                                    "total_token_usage": {
                                        "input_tokens": 10,
                                        "cached_input_tokens": 2,
                                        "output_tokens": 3,
                                        "reasoning_output_tokens": 1,
                                        "total_tokens": 13,
                                    }
                                },
                            },
                        }
                    ),
                    json.dumps({"type": "turn_context", "payload": {"turn_id": "turn-1"}}),
                    json.dumps(
                        {
                            "type": "event_msg",
                            "payload": {
                                "type": "token_count",
                                "info": {
                                    "total_token_usage": {
                                        "input_tokens": 30,
                                        "cached_input_tokens": 4,
                                        "output_tokens": 8,
                                        "reasoning_output_tokens": 2,
                                        "total_tokens": 38,
                                    },
                                    "last_token_usage": {
                                        "input_tokens": 20,
                                        "cached_input_tokens": 2,
                                        "output_tokens": 5,
                                        "reasoning_output_tokens": 1,
                                        "total_tokens": 25,
                                    },
                                    "model_context_window": 128000,
                                },
                            },
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        hook.dispatch(
            {
                "hook_event_name": "SessionStart",
                "session_id": "sess-1",
                "cwd": "/tmp/project",
                "model": "gpt-5.5",
                "source": "startup",
                "transcript_path": str(transcript),
                "timestamp": "2026-05-14T10:00:00Z",
            }
        )
        hook.dispatch(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "sess-1",
                "turn_id": "turn-1",
                "prompt": "hello",
                "timestamp": "2026-05-14T10:00:01Z",
            }
        )
        hook.dispatch(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "sess-1",
                "turn_id": "turn-1",
                "tool_name": "Bash",
                "tool_use_id": "tool-1",
                "tool_response": {"exit_code": 0},
                "duration_ms": 250,
                "timestamp": "2026-05-14T10:00:03Z",
            }
        )
        hook.dispatch(
            {
                "hook_event_name": "Stop",
                "session_id": "sess-1",
                "turn_id": "turn-1",
                "last_assistant_message": "done",
                "timestamp": "2026-05-14T10:00:04Z",
            }
        )

        self.assertIsNotNone(CaptureHandler.body)
        request = json.loads(CaptureHandler.body or b"{}")
        spans = request["resourceSpans"][0]["scopeSpans"][0]["spans"]
        self.assertEqual(len(spans), 2)
        self.assertEqual(spans[0]["name"], "codex turn")
        self.assertEqual(spans[0]["kind"], hook.SPAN_KIND_INTERNAL)
        self.assertEqual(spans[0]["status"]["code"], hook.STATUS_CODE_OK)
        self.assertNotIn("parentSpanId", spans[0])
        self.assertEqual(spans[1]["parentSpanId"], spans[0]["spanId"])
        self.assertEqual(spans[1]["kind"], hook.SPAN_KIND_INTERNAL)
        self.assertEqual(spans[1]["status"]["code"], hook.STATUS_CODE_OK)
        self.assertEqual(spans[0]["traceId"], spans[1]["traceId"])
        self.assertEqual(CaptureHandler.headers_seen["Authorization"], "test-token")

        attrs = flatten_attrs(spans[0]["attributes"])
        self.assertEqual(attrs["logfire.msg"], "Codex turn: hello")
        self.assertEqual(attrs["logfire.span_type"], "span")
        self.assertEqual(attrs["logfire.tags"], ["Codex", "LLM"])
        self.assertEqual(attrs["codex.conversation_id"], "sess-1")
        self.assertEqual(attrs["codex.trace_source"], "payload.session_id")
        self.assertEqual(attrs["codex.session_id"], "sess-1")
        self.assertEqual(attrs["codex.prompt.length"], "5")
        self.assertEqual(attrs["codex.response.length"], "4")
        self.assertEqual(attrs["gen_ai.operation.name"], "chat")
        self.assertEqual(attrs["gen_ai.response.model"], "gpt-5.5")
        self.assertEqual(attrs["gen_ai.usage.input_tokens"], "20")
        self.assertEqual(attrs["gen_ai.usage.output_tokens"], "5")
        self.assertEqual(attrs["final_result"], "done")
        messages = json.loads(str(attrs["pydantic_ai.all_messages"]))
        self.assertEqual(
            messages,
            [
                {"role": "user", "parts": [{"type": "text", "content": "hello"}]},
                {"role": "assistant", "parts": [{"type": "text", "content": "done"}]},
            ],
        )

        tool_attrs = flatten_attrs(spans[1]["attributes"])
        self.assertEqual(tool_attrs["logfire.msg"], "Codex tool Bash completed")
        self.assertEqual(tool_attrs["logfire.tags"], ["Codex"])
        self.assertEqual(tool_attrs["codex.tool.success"], True)

    def test_thread_id_env_groups_multiple_hook_sessions_in_one_trace(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        os.environ["LOGFIRE_TOKEN"] = "test-token"
        os.environ["LOGFIRE_URL"] = f"http://127.0.0.1:{server.server_port}"
        os.environ["CODEX_THREAD_ID"] = "thread-1"

        hook.dispatch(
            {
                "hook_event_name": "SessionStart",
                "session_id": "sess-a",
                "timestamp": "2026-05-14T10:00:00Z",
            }
        )
        hook.dispatch(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "sess-a",
                "turn_id": "turn-a",
                "prompt": "hello",
                "timestamp": "2026-05-14T10:00:01Z",
            }
        )
        hook.dispatch(
            {
                "hook_event_name": "Stop",
                "session_id": "sess-a",
                "turn_id": "turn-a",
                "last_assistant_message": "hi",
                "timestamp": "2026-05-14T10:00:02Z",
            }
        )
        first_request = json.loads(CaptureHandler.body or b"{}")

        hook.dispatch(
            {
                "hook_event_name": "SessionStart",
                "session_id": "sess-b",
                "timestamp": "2026-05-14T10:00:10Z",
            }
        )
        hook.dispatch(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "sess-b",
                "turn_id": "turn-b",
                "prompt": "again",
                "timestamp": "2026-05-14T10:00:11Z",
            }
        )
        hook.dispatch(
            {
                "hook_event_name": "Stop",
                "session_id": "sess-b",
                "turn_id": "turn-b",
                "last_assistant_message": "done",
                "timestamp": "2026-05-14T10:00:12Z",
            }
        )
        second_request = json.loads(CaptureHandler.body or b"{}")

        first_span = first_request["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        second_span = second_request["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(first_span["traceId"], second_span["traceId"])
        self.assertNotEqual(first_span["spanId"], second_span["spanId"])

        first_attrs = flatten_attrs(first_span["attributes"])
        second_attrs = flatten_attrs(second_span["attributes"])
        self.assertEqual(first_attrs["codex.conversation_id"], "thread-1")
        self.assertEqual(first_attrs["codex.trace_source"], "env.CODEX_THREAD_ID")
        self.assertEqual(first_attrs["codex.session_id"], "sess-a")
        self.assertEqual(second_attrs["codex.conversation_id"], "thread-1")
        self.assertEqual(second_attrs["codex.trace_source"], "env.CODEX_THREAD_ID")
        self.assertEqual(second_attrs["codex.session_id"], "sess-b")

    def test_payload_thread_id_overrides_env_trace_identity(self) -> None:
        os.environ["CODEX_THREAD_ID"] = "env-thread"
        identity, source = hook.conversation_identity(
            {"session_id": "sess-1", "thread_id": "payload-thread"},
        )
        self.assertEqual(identity, "payload-thread")
        self.assertEqual(source, "payload.thread_id")

    def test_token_usage_parser_returns_delta_for_turn(self) -> None:
        path = Path(self.tmp.name) / "rollout.jsonl"
        path.write_text(
            "\n".join(
                [
                    json.dumps({"type": "turn_context", "payload": {"turn_id": "old"}}),
                    json.dumps(
                        {
                            "type": "event_msg",
                            "payload": {
                                "type": "token_count",
                                "info": {"total_token_usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}},
                            },
                        }
                    ),
                    json.dumps({"type": "turn_context", "payload": {"turn_id": "new"}}),
                    json.dumps(
                        {
                            "type": "event_msg",
                            "payload": {
                                "type": "token_count",
                                "info": {"total_token_usage": {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13}},
                            },
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        usage = hook.read_token_usage_for_turn(str(path), "new")
        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 4)
        self.assertEqual(usage["output_tokens"], 2)
        self.assertEqual(usage["total_tokens"], 6)


def flatten_attrs(attrs: list[dict[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for attr in attrs:
        value = attr["value"]
        assert isinstance(value, dict)
        if "stringValue" in value:
            out[str(attr["key"])] = value["stringValue"]
        elif "intValue" in value:
            out[str(attr["key"])] = value["intValue"]
        elif "boolValue" in value:
            out[str(attr["key"])] = value["boolValue"]
        elif "arrayValue" in value:
            array = value["arrayValue"]
            assert isinstance(array, dict)
            values = array.get("values", [])
            assert isinstance(values, list)
            out[str(attr["key"])] = [flatten_value(item) for item in values]
    return out


def flatten_value(value: object) -> object:
    assert isinstance(value, dict)
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return value["intValue"]
    if "boolValue" in value:
        return value["boolValue"]
    if "doubleValue" in value:
        return value["doubleValue"]
    return value


if __name__ == "__main__":
    unittest.main()
