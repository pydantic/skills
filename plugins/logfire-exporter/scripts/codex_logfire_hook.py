#!/usr/bin/env python3
"""Codex hook entrypoint that exports completed turns to Logfire via OTLP JSON.

This intentionally avoids the Logfire SDK and the OpenTelemetry SDK so the
plugin can control trace/span IDs from Codex conversation identities.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


FALLBACK_PLUGIN_VERSION = "unknown"


def plugin_version() -> str:
    manifest_path = Path(__file__).resolve().parents[1] / ".codex-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return FALLBACK_PLUGIN_VERSION

    if not isinstance(manifest, dict):
        return FALLBACK_PLUGIN_VERSION

    version = manifest.get("version")
    if isinstance(version, str) and version:
        return version
    return FALLBACK_PLUGIN_VERSION


PLUGIN_VERSION = plugin_version()
SERVICE_NAME = "logfire-exporter"
STATE_DIR_NAME = "logfire-exporter"
LEGACY_STATE_DIR_NAMES = ("codex-logfire-exporter", "codex-logfire-plugin")
DEFAULT_LOGFIRE_URL = "https://logfire-api.pydantic.dev"
MAX_TRANSCRIPT_BYTES = 20 * 1024 * 1024
STALE_AFTER_SECONDS = 24 * 60 * 60
LOCK_TIMEOUT_SECONDS = 2.0
SPAN_KIND_INTERNAL = 1
STATUS_CODE_OK = 1
STATUS_CODE_ERROR = 2
LOGFIRE_LEVEL_INFO = 9
LOGFIRE_LEVEL_ERROR = 17
PREVIEW_CHARS = 120
TRACE_IDENTITY_PAYLOAD_KEYS = (
    "root_thread_id",
    "root_session_id",
    "conversation_id",
    "thread_id",
)

USAGE_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)([\"'\s:=]+)([^\"'\s,}]+)"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\b(glc_[A-Za-z0-9_-]{20,})\b"),
]


def main() -> int:
    load_config_env()
    raw = sys.stdin.read()
    if not raw.strip():
        debug("empty hook input")
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        debug(f"invalid hook JSON: {exc}")
        return 0

    try:
        dispatch(payload)
    except Exception as exc:  # noqa: BLE001 - hooks must fail open.
        debug(f"hook failed open: {type(exc).__name__}: {exc}")
    finally:
        cleanup_stale(payload.get("session_id"), payload.get("turn_id"))

    return 0


def dispatch(payload: dict[str, Any]) -> None:
    event = payload.get("hook_event_name")
    debug(f"dispatch event={event!r} session={payload.get('session_id')!r} turn={payload.get('turn_id')!r}")
    if event == "SessionStart":
        handle_session_start(payload)
    elif event == "UserPromptSubmit":
        handle_user_prompt_submit(payload)
    elif event == "PostToolUse":
        handle_post_tool_use(payload)
    elif event == "Stop":
        handle_stop(payload)
    else:
        debug(f"unknown event: {event!r}")


def handle_session_start(payload: dict[str, Any]) -> None:
    session_id = payload.get("session_id")
    if not session_id:
        return

    def mutate(session: dict[str, Any]) -> None:
        session["session_id"] = session_id
        copy_present(payload, session, "cwd", "model", "source", "transcript_path")
        apply_conversation_identity(payload, session)
        touch(session, event_time_ns(payload))

    update_json(session_path(session_id), mutate)

    turn_id = payload.get("turn_id")
    if turn_id:
        update_turn_common(payload)


def handle_user_prompt_submit(payload: dict[str, Any]) -> None:
    if not payload.get("session_id") or not payload.get("turn_id"):
        debug("UserPromptSubmit missing session_id or turn_id")
        return

    mode = content_capture_mode()

    def mutate(turn: dict[str, Any]) -> None:
        apply_turn_common(payload, turn)
        if payload.get("prompt"):
            prompt = str(payload["prompt"])
            turn["prompt_length"] = len(prompt)
            if mode != "metadata_only":
                turn["prompt"] = redact_text(prompt)

    update_json(turn_path(payload["session_id"], payload["turn_id"]), mutate)


def handle_post_tool_use(payload: dict[str, Any]) -> None:
    if not payload.get("session_id") or not payload.get("turn_id"):
        debug("PostToolUse missing session_id or turn_id")
        return

    mode = content_capture_mode()

    def mutate(turn: dict[str, Any]) -> None:
        apply_turn_common(payload, turn)
        response = payload.get("tool_response")
        if response is None:
            response = payload.get("tool_output")
        tool: dict[str, Any] = {
            "tool_name": payload.get("tool_name") or payload.get("name") or "unknown",
            "tool_use_id": payload.get("tool_use_id") or payload.get("tool_call_id"),
            "status": normalize_status(payload, response),
            "completed_at_ns": event_time_ns(payload),
        }
        duration_ms = payload.get("tool_duration_ms")
        if duration_ms is None:
            duration_ms = payload.get("duration_ms")
        if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
            tool["duration_ms"] = duration_ms
        if mode == "full":
            if payload.get("tool_input") is not None:
                tool["tool_input"] = redact_json_value(payload["tool_input"])
            if response is not None:
                tool["tool_response"] = redact_json_value(response)
            if payload.get("error") is not None:
                tool["error"] = redact_json_value(payload["error"])
        turn.setdefault("tools", []).append(tool)

    update_json(turn_path(payload["session_id"], payload["turn_id"]), mutate)


def handle_stop(payload: dict[str, Any]) -> None:
    session_id = payload.get("session_id")
    turn_id = payload.get("turn_id")
    if not session_id or not turn_id:
        debug("Stop missing session_id or turn_id")
        return

    mode = content_capture_mode()
    completed_at_ns = event_time_ns(payload)

    def mutate(turn: dict[str, Any]) -> None:
        apply_turn_common(payload, turn)
        turn["completed_at_ns"] = completed_at_ns
        turn["stop_hook_active"] = bool(payload.get("stop_hook_active"))
        if payload.get("last_assistant_message"):
            last_assistant_message = str(payload["last_assistant_message"])
            turn["last_assistant_message_length"] = len(last_assistant_message)
            if mode != "metadata_only":
                turn["last_assistant_message"] = redact_text(last_assistant_message)

    path = turn_path(session_id, turn_id)
    update_json(path, mutate)
    turn = load_json(path)
    if not turn:
        debug("Stop has no turn fragment")
        return

    if not logfire_token():
        debug("LOGFIRE_TOKEN not set; deleting completed fragment without export")
        delete_file(path)
        return

    usage = read_token_usage_for_turn(turn.get("transcript_path"), turn_id)
    request = build_otlp_request(turn, usage)
    export_otlp(request)
    delete_file(path)
    debug(f"exported session={session_id} turn={turn_id} spans={count_spans(request)}")


def update_turn_common(payload: dict[str, Any]) -> None:
    update_json(
        turn_path(payload["session_id"], payload["turn_id"]),
        lambda turn: apply_turn_common(payload, turn),
    )


def apply_turn_common(payload: dict[str, Any], turn: dict[str, Any]) -> None:
    session_id = payload.get("session_id")
    turn_id = payload.get("turn_id")
    if session_id:
        turn["session_id"] = session_id
    if turn_id:
        turn["turn_id"] = turn_id
    if session_id:
        session = load_json(session_path(session_id))
        for key in ("cwd", "model", "source", "transcript_path", "conversation_id", "trace_source"):
            if turn.get(key) in (None, "") and session.get(key):
                turn[key] = session[key]
    copy_present(payload, turn, "cwd", "model", "source", "transcript_path")
    apply_conversation_identity(payload, turn)
    touch(turn, event_time_ns(payload))


def touch(record: dict[str, Any], timestamp_ns: int) -> None:
    if not record.get("started_at_ns"):
        record["started_at_ns"] = timestamp_ns
    record["last_event_at_ns"] = timestamp_ns


def copy_present(source: dict[str, Any], target: dict[str, Any], *keys: str) -> None:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            target[key] = value


def apply_conversation_identity(payload: dict[str, Any], target: dict[str, Any]) -> None:
    identity, source = conversation_identity(payload, target)
    if identity:
        target["conversation_id"] = identity
        target["trace_source"] = source


def conversation_identity(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> tuple[str | None, str | None]:
    for key in TRACE_IDENTITY_PAYLOAD_KEYS:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value), f"payload.{key}"

    env_value = os.getenv("CODEX_THREAD_ID", "").strip()
    if env_value:
        return env_value, "env.CODEX_THREAD_ID"

    if existing:
        value = existing.get("conversation_id")
        if value not in (None, ""):
            return str(value), str(existing.get("trace_source") or "state.conversation_id")

    value = payload.get("session_id")
    if value not in (None, ""):
        return str(value), "payload.session_id"

    return None, None


def trace_identity(turn: dict[str, Any]) -> str:
    return str(turn.get("conversation_id") or turn["session_id"])


def build_otlp_request(turn: dict[str, Any], usage: dict[str, Any] | None) -> dict[str, Any]:
    trace_id = deterministic_hex_id("trace:v1", 16, trace_identity(turn))
    turn_span_id = deterministic_hex_id("turn-span:v1", 8, turn["session_id"], turn["turn_id"])
    started_at_ns = int(turn.get("started_at_ns") or turn.get("last_event_at_ns") or now_ns())
    completed_at_ns = int(turn.get("completed_at_ns") or turn.get("last_event_at_ns") or now_ns())
    if completed_at_ns < started_at_ns:
        completed_at_ns = started_at_ns

    spans = [build_turn_span(turn, usage, trace_id, turn_span_id, started_at_ns, completed_at_ns)]
    for index, tool in enumerate(turn.get("tools") or []):
        spans.append(build_tool_span(turn, tool, index, trace_id, turn_span_id, completed_at_ns))

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": otlp_attributes(
                        {
                            "service.name": os.getenv("CODEX_LOGFIRE_SERVICE_NAME", SERVICE_NAME),
                            "telemetry.sdk.name": SERVICE_NAME,
                            "telemetry.sdk.language": "python",
                            "telemetry.sdk.version": PLUGIN_VERSION,
                        }
                    )
                },
                "scopeSpans": [
                    {
                        "scope": {"name": SERVICE_NAME, "version": PLUGIN_VERSION},
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def build_turn_span(
    turn: dict[str, Any],
    usage: dict[str, Any] | None,
    trace_id: str,
    span_id: str,
    started_at_ns: int,
    completed_at_ns: int,
) -> dict[str, Any]:
    mode = content_capture_mode()
    messages = pydantic_ai_messages(turn, mode) if mode != "metadata_only" else []
    attrs: dict[str, Any] = {
        "logfire.msg": turn_message(turn),
        "logfire.span_type": "span",
        "logfire.level_num": LOGFIRE_LEVEL_INFO,
        "logfire.tags": ["Codex", *(["LLM"] if messages else [])],
        "codex.conversation_id": turn.get("conversation_id") or turn.get("session_id"),
        "codex.trace_source": turn.get("trace_source") or "payload.session_id",
        "codex.session_id": turn.get("session_id"),
        "codex.turn_id": turn.get("turn_id"),
        "codex.cwd": turn.get("cwd"),
        "codex.source": turn.get("source"),
        "codex.model": turn.get("model"),
        "codex.transcript_path": turn.get("transcript_path"),
        "codex.logfire_project": os.getenv("CODEX_LOGFIRE_PROJECT"),
        "codex.stop_hook_active": bool(turn.get("stop_hook_active")),
        "codex.prompt.length": turn.get("prompt_length"),
        "codex.response.length": turn.get("last_assistant_message_length"),
        "gen_ai.system": "codex",
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": turn.get("model"),
        "gen_ai.response.model": turn.get("model"),
        "gen_ai.response.finish_reasons": ["stop"],
        "gen_ai.tool.call.count": len(turn.get("tools") or []),
        "agent_name": "codex",
        "model_name": turn.get("model"),
    }
    if usage:
        attrs.update(usage_attributes(usage))
    if mode != "metadata_only":
        attrs["codex.prompt"] = turn.get("prompt")
        attrs["codex.last_assistant_message"] = turn.get("last_assistant_message")
        if messages:
            attrs["pydantic_ai.all_messages"] = json_dumps_or_none(messages)
            attrs["logfire.json_schema"] = json_dumps_or_none(
                {
                    "type": "object",
                    "properties": {
                        "pydantic_ai.all_messages": {"type": "array"},
                        "final_result": {"type": "string"},
                    },
                }
            )
        if turn.get("last_assistant_message"):
            attrs["final_result"] = turn.get("last_assistant_message")

    return {
        "traceId": trace_id,
        "spanId": span_id,
        "name": "codex turn",
        "kind": SPAN_KIND_INTERNAL,
        "startTimeUnixNano": str(started_at_ns),
        "endTimeUnixNano": str(completed_at_ns),
        "attributes": otlp_attributes(attrs),
        "status": {"code": STATUS_CODE_OK},
    }


def build_tool_span(
    turn: dict[str, Any],
    tool: dict[str, Any],
    index: int,
    trace_id: str,
    parent_span_id: str,
    fallback_completed_at_ns: int,
) -> dict[str, Any]:
    tool_key = str(tool.get("tool_use_id") or f"{index}:{tool.get('tool_name')}:{tool.get('completed_at_ns')}")
    span_id = deterministic_hex_id("tool-span:v1", 8, turn["session_id"], turn["turn_id"], tool_key)
    completed_at_ns = int(tool.get("completed_at_ns") or fallback_completed_at_ns)
    duration_ms = tool.get("duration_ms")
    if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
        started_at_ns = completed_at_ns - int(duration_ms * 1_000_000)
    else:
        started_at_ns = completed_at_ns
    if completed_at_ns < started_at_ns:
        completed_at_ns = started_at_ns

    status_is_error = tool.get("status") == "error"
    attrs: dict[str, Any] = {
        "logfire.msg": tool_message(tool),
        "logfire.span_type": "span",
        "logfire.level_num": LOGFIRE_LEVEL_ERROR if status_is_error else LOGFIRE_LEVEL_INFO,
        "logfire.tags": ["Codex"],
        "codex.conversation_id": turn.get("conversation_id") or turn.get("session_id"),
        "codex.trace_source": turn.get("trace_source") or "payload.session_id",
        "codex.session_id": turn.get("session_id"),
        "codex.turn_id": turn.get("turn_id"),
        "codex.tool.status": tool.get("status"),
        "codex.tool.success": not status_is_error,
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": tool.get("tool_name"),
        "gen_ai.tool.call.id": tool.get("tool_use_id"),
        "gen_ai.tool.type": "function",
    }
    if duration_ms is not None:
        attrs["codex.tool.duration_ms"] = duration_ms
    if status_is_error:
        attrs["error.type"] = "tool_execution_error"
    if content_capture_mode() == "full":
        attrs["gen_ai.tool.call.arguments"] = json_dumps_or_none(tool.get("tool_input"))
        attrs["gen_ai.tool.call.result"] = json_dumps_or_none(tool.get("tool_response"))
        attrs["codex.tool.error"] = json_dumps_or_none(tool.get("error"))

    span = {
        "traceId": trace_id,
        "spanId": span_id,
        "parentSpanId": parent_span_id,
        "name": f"codex tool {tool.get('tool_name') or 'unknown'}",
        "kind": SPAN_KIND_INTERNAL,
        "startTimeUnixNano": str(started_at_ns),
        "endTimeUnixNano": str(completed_at_ns),
        "attributes": otlp_attributes(attrs),
        "status": {"code": STATUS_CODE_ERROR if status_is_error else STATUS_CODE_OK},
    }
    if status_is_error:
        span["status"]["message"] = "tool returned error"
    return span


def turn_message(turn: dict[str, Any]) -> str:
    model = turn.get("model") or "unknown model"
    if turn.get("prompt"):
        return f"Codex turn: {preview_text(str(turn['prompt']))}"
    if turn.get("last_assistant_message"):
        return f"Codex turn: {preview_text(str(turn['last_assistant_message']))}"
    prompt_length = turn.get("prompt_length")
    if isinstance(prompt_length, int) and prompt_length > 0:
        return f"Codex turn ({model}, {prompt_length} prompt chars)"
    return f"Codex turn ({model})"


def tool_message(tool: dict[str, Any]) -> str:
    name = tool.get("tool_name") or "unknown"
    status = tool.get("status") or "completed"
    return f"Codex tool {name} {status}"


def preview_text(value: str) -> str:
    compact = " ".join(value.split())
    if len(compact) <= PREVIEW_CHARS:
        return compact
    return compact[: PREVIEW_CHARS - 1].rstrip() + "..."


def pydantic_ai_messages(turn: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    prompt = turn.get("prompt")
    if prompt:
        messages.append({"role": "user", "parts": [{"type": "text", "content": prompt}]})

    if mode == "full":
        for index, tool in enumerate(turn.get("tools") or []):
            tool_id = str(tool.get("tool_use_id") or f"tool-{index + 1}")
            tool_name = str(tool.get("tool_name") or "unknown")
            if tool.get("tool_input") is not None:
                messages.append(
                    {
                        "role": "assistant",
                        "parts": [
                            {
                                "type": "tool_call",
                                "id": tool_id,
                                "name": tool_name,
                                "arguments": tool.get("tool_input"),
                            }
                        ],
                    }
                )
            if tool.get("tool_response") is not None or tool.get("error") is not None:
                messages.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "type": "tool_call_response",
                                "id": tool_id,
                                "name": tool_name,
                                "result": (
                                    tool.get("tool_response")
                                    if tool.get("tool_response") is not None
                                    else tool.get("error")
                                ),
                            }
                        ],
                    }
                )

    last_assistant_message = turn.get("last_assistant_message")
    if last_assistant_message:
        messages.append({"role": "assistant", "parts": [{"type": "text", "content": last_assistant_message}]})
    return messages


def usage_attributes(usage: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    mapping = {
        "input_tokens": "gen_ai.usage.input_tokens",
        "cached_input_tokens": "gen_ai.usage.cache_read_input_tokens",
        "output_tokens": "gen_ai.usage.output_tokens",
        "reasoning_output_tokens": "gen_ai.usage.reasoning_tokens",
        "total_tokens": "gen_ai.usage.total_tokens",
    }
    for source_key, attr_key in mapping.items():
        value = usage.get(source_key)
        if isinstance(value, int) and value > 0:
            attrs[attr_key] = value
    if usage.get("model_context_window"):
        attrs["codex.token_usage.context_window"] = usage["model_context_window"]
    if usage.get("source"):
        attrs["codex.token_usage.source"] = usage["source"]
    return attrs


def export_otlp(request: dict[str, Any]) -> None:
    body = json.dumps(request, separators=(",", ":")).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"{SERVICE_NAME}/{PLUGIN_VERSION}",
    }
    token = logfire_token()
    if token:
        headers["Authorization"] = authorization_header(token)
    headers.update(extra_otlp_headers())

    req = urllib.request.Request(otlp_traces_endpoint(), data=body, headers=headers, method="POST")
    timeout = float(os.getenv("CODEX_LOGFIRE_EXPORT_TIMEOUT", "10"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"OTLP export returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read(512).decode(errors="replace")
        raise RuntimeError(f"OTLP export returned HTTP {exc.code}: {detail}") from exc


def otlp_traces_endpoint() -> str:
    raw = (
        os.getenv("CODEX_LOGFIRE_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("LOGFIRE_BASE_URL")
        or os.getenv("LOGFIRE_URL")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or DEFAULT_LOGFIRE_URL
    ).strip()
    base = raw.rstrip("/")
    if base.endswith("/v1/traces"):
        return base
    if base.endswith("/v1"):
        return base + "/traces"
    if base.endswith("/otlp"):
        return base + "/v1/traces"
    return base + "/v1/traces"


def logfire_token() -> str:
    return (os.getenv("LOGFIRE_TOKEN") or os.getenv("CODEX_LOGFIRE_TOKEN") or "").strip()


def authorization_header(token: str) -> str:
    scheme = os.getenv("CODEX_LOGFIRE_AUTH_SCHEME", "").strip()
    if scheme:
        if scheme.lower() in {"none", "raw"}:
            return token
        scheme_prefix = f"{scheme} "
        if token.lower().startswith(scheme_prefix.lower()):
            return token
        return f"{scheme} {token}"
    if re.match(r"^[A-Za-z]+\s+\S+", token):
        return token
    return token


def extra_otlp_headers() -> dict[str, str]:
    raw = os.getenv("CODEX_LOGFIRE_OTLP_HEADERS") or os.getenv("OTEL_EXPORTER_OTLP_HEADERS") or ""
    headers: dict[str, str] = {}
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers


def otlp_attributes(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key, value in attrs.items():
        if value is None or value == "":
            continue
        out.append({"key": key, "value": otlp_value(value)})
    return out


def otlp_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, (list, tuple)):
        return {"arrayValue": {"values": [otlp_value(item) for item in value if item is not None]}}
    if isinstance(value, dict):
        return {"stringValue": json.dumps(value, sort_keys=True, separators=(",", ":"))}
    return {"stringValue": str(value)}


def deterministic_hex_id(kind: str, byte_count: int, *parts: str) -> str:
    h = hashlib.sha256()
    h.update(f"{SERVICE_NAME}:{kind}".encode())
    for part in parts:
        h.update(b"\0")
        h.update(str(part).encode())
    digest = h.digest()[:byte_count]
    if not any(digest):
        h = hashlib.sha256()
        h.update(f"{SERVICE_NAME}:{kind}:nonzero".encode())
        for part in parts:
            h.update(b"\0")
            h.update(str(part).encode())
        digest = h.digest()[:byte_count]
    return digest.hex()


def read_token_usage_for_turn(transcript_path: str | None, turn_id: str) -> dict[str, Any] | None:
    if not transcript_path:
        return None
    path = Path(transcript_path).expanduser()
    try:
        if not path.is_file() or path.stat().st_size > MAX_TRANSCRIPT_BYTES:
            return None
    except OSError:
        return None

    current_turn: str | None = None
    seen_target = False
    baseline: dict[str, int] | None = None
    last_before: dict[str, int] | None = None
    last_current_total: dict[str, int] | None = None
    last_current_delta: dict[str, int] | None = None
    model_context_window: int | None = None

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                record_type = record.get("type")
                payload = record.get("payload") or {}
                if record_type == "turn_context":
                    current_turn = str((payload or {}).get("turn_id") or "")
                    continue
                if record_type != "event_msg" or payload.get("type") != "token_count":
                    continue
                info = payload.get("info") or {}
                total = normalize_usage(info.get("total_token_usage"))
                delta = normalize_usage(info.get("last_token_usage"))
                if not total:
                    continue
                if isinstance(info.get("model_context_window"), int):
                    model_context_window = info["model_context_window"]
                if current_turn == turn_id:
                    if not seen_target:
                        baseline = last_before
                        seen_target = True
                    last_current_total = total
                    if delta:
                        last_current_delta = delta
                elif not seen_target:
                    last_before = total
    except OSError as exc:
        debug(f"token usage read failed path={path}: {exc}")
        return None

    if not last_current_total:
        return None

    usage = subtract_usage(last_current_total, baseline or {})
    if not has_positive_usage(usage) and last_current_delta:
        usage = last_current_delta
    if not has_positive_usage(usage):
        return None
    if model_context_window:
        usage["model_context_window"] = model_context_window
    usage["source"] = "codex_rollout_token_count"
    return usage


def normalize_usage(raw: Any) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    usage: dict[str, int] = {}
    for key in USAGE_KEYS:
        value = raw.get(key)
        if isinstance(value, int):
            usage[key] = max(value, 0)
    return usage or None


def subtract_usage(total: dict[str, int], baseline: dict[str, int]) -> dict[str, int]:
    return {key: max(int(total.get(key, 0)) - int(baseline.get(key, 0)), 0) for key in USAGE_KEYS}


def has_positive_usage(usage: dict[str, int]) -> bool:
    return any(int(usage.get(key, 0)) > 0 for key in USAGE_KEYS)


def normalize_status(payload: dict[str, Any], response: Any) -> str:
    raw_status = str(payload.get("status") or "").strip().lower()
    if raw_status in {"error", "failed", "failure"}:
        return "error"
    if raw_status in {"completed", "complete", "success", "succeeded", "ok"}:
        return "completed"
    if payload.get("error") not in (None, "", {}, []):
        return "error"
    inferred = infer_status_from_value(response)
    return inferred or ""


def infer_status_from_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("status", "state"):
            status = str(value.get(key) or "").strip().lower()
            if status in {"error", "failed", "failure"}:
                return "error"
            if status in {"completed", "complete", "success", "succeeded", "ok"}:
                return "completed"
        for key in ("is_error", "isError"):
            if isinstance(value.get(key), bool):
                return "error" if value[key] else "completed"
        if isinstance(value.get("success"), bool):
            return "completed" if value["success"] else "error"
        for key in ("exit_code", "exitCode"):
            if isinstance(value.get(key), int):
                return "completed" if value[key] == 0 else "error"
        if value.get("error") not in (None, "", {}, []):
            return "error"
    return ""


def event_time_ns(payload: dict[str, Any]) -> int:
    for key in ("timestamp", "time", "created_at"):
        if payload.get(key):
            parsed = parse_time_ns(payload[key])
            if parsed:
                return parsed
    return now_ns()


def parse_time_ns(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        if value > 10_000_000_000_000:
            return int(value)
        if value > 10_000_000_000:
            return int(value * 1_000_000)
        return int(value * 1_000_000_000)
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1_000_000_000)


def now_ns() -> int:
    return time.time_ns()


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def update_json(path: Path, mutate: Any) -> None:
    with file_lock(path):
        data = load_json(path)
        mutate(data)
        atomic_write_json(path, data)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True, separators=(",", ":"))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


@contextlib.contextmanager
def file_lock(path: Path) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if is_stale_lock(lock_path):
                delete_file(lock_path)
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"lock timeout: {lock_path}")
            time.sleep(0.01)
    try:
        os.write(fd, f"pid={os.getpid()}\ncreated={dt.datetime.now(dt.timezone.utc).isoformat()}\n".encode())
        yield
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)
        delete_file(lock_path)


def is_stale_lock(path: Path) -> bool:
    try:
        return time.time() - path.stat().st_mtime > 120
    except OSError:
        return False


def delete_file(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


def state_root() -> Path:
    override = os.getenv("CODEX_LOGFIRE_STATE_DIR")
    if override:
        return Path(override).expanduser()
    base = os.getenv("XDG_STATE_HOME")
    if base:
        return Path(base).expanduser() / STATE_DIR_NAME
    return Path.home() / ".local" / "state" / STATE_DIR_NAME


def session_path(session_id: str) -> Path:
    return state_root() / "sessions" / f"{hashed_filename(session_id)}.json"


def turn_path(session_id: str, turn_id: str) -> Path:
    return state_root() / "turns" / f"{hashed_filename(session_id + chr(0) + turn_id)}.json"


def hashed_filename(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def cleanup_stale(current_session_id: str | None = None, current_turn_id: str | None = None) -> None:
    root = state_root()
    cutoff = time.time() - STALE_AFTER_SECONDS
    skip = set()
    if current_session_id:
        skip.add(session_path(current_session_id))
    if current_session_id and current_turn_id:
        skip.add(turn_path(current_session_id, current_turn_id))
    for subdir in ("sessions", "turns"):
        directory = root / subdir
        if not directory.is_dir():
            continue
        for path in directory.glob("*.json"):
            if path in skip:
                continue
            with contextlib.suppress(OSError):
                if path.stat().st_mtime < cutoff:
                    path.unlink()


def content_capture_mode() -> str:
    raw = os.getenv("CODEX_LOGFIRE_CONTENT_CAPTURE_MODE", "full").strip().lower()
    if raw in {"full", "no_tool_content", "metadata_only"}:
        return raw
    return "full"


def redact_json_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_json_value(item) for item in value]
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if re.search(r"(?i)(api[_-]?key|token|secret|password)", str(key)):
                out[key] = "[REDACTED]"
            else:
                out[key] = redact_json_value(item)
        return out
    return value


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]" if len(m.groups()) >= 3 else "[REDACTED]", redacted)
    return redacted


def json_dumps_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def count_spans(request: dict[str, Any]) -> int:
    total = 0
    for resource_span in request.get("resourceSpans") or []:
        for scope_span in resource_span.get("scopeSpans") or []:
            total += len(scope_span.get("spans") or [])
    return total


def load_config_env() -> None:
    path = config_env_path()
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not (key.startswith("LOGFIRE_") or key.startswith("CODEX_LOGFIRE_") or key.startswith("OTEL_EXPORTER_OTLP")):
            continue
        if key in os.environ:
            continue
        os.environ[key] = unquote_env_value(value.strip())


def config_env_path() -> Path:
    override = os.getenv("CODEX_LOGFIRE_CONFIG_FILE")
    if override:
        return Path(override).expanduser()
    base = os.getenv("XDG_CONFIG_HOME")
    if base:
        config_home = Path(base).expanduser()
    else:
        config_home = Path.home() / ".config"
    path = config_home / STATE_DIR_NAME / "config.env"
    if path.is_file():
        return path
    for legacy_state_dir_name in LEGACY_STATE_DIR_NAMES:
        legacy_path = config_home / legacy_state_dir_name / "config.env"
        if legacy_path.is_file():
            return legacy_path
    return path


def unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def debug_enabled() -> bool:
    return os.getenv("CODEX_LOGFIRE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def debug(message: str) -> None:
    if not debug_enabled():
        return
    try:
        log_dir = state_root() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "logfire-exporter.log").open("a", encoding="utf-8") as f:
            timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
            f.write(f"{timestamp} {message}\n")
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
