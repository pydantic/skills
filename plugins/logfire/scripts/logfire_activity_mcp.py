#!/usr/bin/env python3
"""Local MCP render-tool POC for Logfire activity widgets.

This is intentionally dependency-free so the Codex plugin can prove the render
tool wiring locally before adopting the full Apps SDK server package.
"""

from __future__ import annotations

import json
import sys
import tempfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from re import sub
from threading import Lock, Thread
from typing import Any

from render_activity_report import render_html


WIDGET_URI = "ui://logfire/activity-card.html"
WIDGET_MIME_TYPE = "text/html;profile=mcp-app"
REPORT_ROOT = Path(tempfile.gettempdir()) / "logfire-activity-reports"

_REPORT_SERVER: ThreadingHTTPServer | None = None
_REPORT_SERVER_THREAD: Thread | None = None
_REPORT_SERVER_LOCK = Lock()

DEFAULT_SERIES = [
    {"bucket": "00:00", "trace_count": 42, "error_count": 0, "p95_ms": 180},
    {"bucket": "02:00", "trace_count": 51, "error_count": 1, "p95_ms": 220},
    {"bucket": "04:00", "trace_count": 37, "error_count": 0, "p95_ms": 190},
    {"bucket": "06:00", "trace_count": 64, "error_count": 2, "p95_ms": 340},
    {"bucket": "08:00", "trace_count": 128, "error_count": 7, "p95_ms": 910},
    {"bucket": "10:00", "trace_count": 96, "error_count": 3, "p95_ms": 480},
    {"bucket": "12:00", "trace_count": 110, "error_count": 2, "p95_ms": 360},
    {"bucket": "14:00", "trace_count": 118, "error_count": 4, "p95_ms": 420},
    {"bucket": "16:00", "trace_count": 89, "error_count": 1, "p95_ms": 290},
    {"bucket": "18:00", "trace_count": 132, "error_count": 9, "p95_ms": 1040},
    {"bucket": "20:00", "trace_count": 101, "error_count": 5, "p95_ms": 610},
    {"bucket": "22:00", "trace_count": 77, "error_count": 1, "p95_ms": 300},
]

DEFAULT_SERVICES = [
    {"service_name": "api", "trace_count": 482, "error_count": 19, "p95_ms": 730},
    {"service_name": "worker", "trace_count": 219, "error_count": 8, "p95_ms": 520},
    {"service_name": "gateway", "trace_count": 174, "error_count": 3, "p95_ms": 310},
]


def _number(value: Any, default: float = 0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _series_from_values(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    values = arguments.get("values") or []
    errors = arguments.get("errors") or []
    p95_values = arguments.get("p95_ms") or []
    series = []
    for index, value in enumerate(values):
        series.append(
            {
                "bucket": str(index + 1),
                "trace_count": _number(value),
                "error_count": _number(errors[index] if index < len(errors) else 0),
                "p95_ms": _number(p95_values[index] if index < len(p95_values) else 0),
            }
        )
    return series


def _normalize_payload(arguments: dict[str, Any]) -> dict[str, Any]:
    series = arguments.get("series")
    if not isinstance(series, list):
        series = _series_from_values(arguments)
    if not series:
        series = DEFAULT_SERIES

    top_services = arguments.get("top_services")
    if not isinstance(top_services, list):
        top_services = arguments.get("services")
    if not isinstance(top_services, list):
        top_services = DEFAULT_SERVICES

    payload = {
        "title": arguments.get("title") or "Logfire activity",
        "window": arguments.get("window") or "24h",
        "bucket": arguments.get("bucket") or "15m",
        "series": series,
        "top_services": top_services,
    }
    sample_trace_ids = arguments.get("sample_trace_ids") or arguments.get("trace_ids")
    if isinstance(sample_trace_ids, list):
        payload["sample_trace_ids"] = sample_trace_ids
    return payload


def _slug(value: str) -> str:
    slug = sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or "logfire-activity-report"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - matches stdlib signature.
        return


def _ensure_report_server(port: int | None = None) -> str:
    global _REPORT_SERVER
    global _REPORT_SERVER_THREAD
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    with _REPORT_SERVER_LOCK:
        if _REPORT_SERVER is not None:
            host, active_port = _REPORT_SERVER.server_address[:2]
            return f"http://{host}:{active_port}"

        handler = partial(_QuietHandler, directory=str(REPORT_ROOT))
        server = ThreadingHTTPServer(("127.0.0.1", int(port or 0)), handler)
        thread = Thread(target=server.serve_forever, name="logfire-activity-report-http", daemon=True)
        thread.start()
        _REPORT_SERVER = server
        _REPORT_SERVER_THREAD = thread
        host, active_port = server.server_address[:2]
        return f"http://{host}:{active_port}"


def _report_output_path(arguments: dict[str, Any], payload: dict[str, Any]) -> Path:
    output_path = arguments.get("output_path")
    if isinstance(output_path, str) and output_path.strip():
        path = Path(output_path).expanduser()
        if path.suffix.lower() != ".html":
            path = path.with_suffix(".html")
        return path

    filename = arguments.get("filename")
    if isinstance(filename, str) and filename.strip():
        safe_filename = _slug(filename)
    else:
        safe_filename = _slug(str(payload.get("title") or "logfire-activity-report"))
    if not safe_filename.endswith(".html"):
        safe_filename = f"{safe_filename}.html"
    return REPORT_ROOT / safe_filename


def _path_to_report_url(base_url: str, path: Path) -> str:
    resolved_root = REPORT_ROOT.resolve()
    resolved_path = path.resolve()
    try:
        relative = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            f"Cannot serve report outside {resolved_root}. "
            "Omit output_path or write inside the default report directory."
        ) from exc
    return f"{base_url}/{relative.as_posix()}"


def _widget_html() -> str:
    # Keep the widget single-file and inline so resource reads work over stdio.
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Logfire activity</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #fffdfb;
      --panel: #ffffff;
      --ink: #171514;
      --muted: #6f6761;
      --line: #eadfd8;
      --magenta: #E520E9;
      --orange: #E85D2A;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #171514;
        --panel: #211e1c;
        --ink: #f8f4f1;
        --muted: #c5b8af;
        --line: #403833;
      }
    }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
    }
    .wrap {
      box-sizing: border-box;
      width: min(100%, 900px);
      padding: 14px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--panel);
      padding: 18px;
    }
    .head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;
    }
    h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
      letter-spacing: 0;
    }
    .sub {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .metric {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
    }
    .value {
      font-size: 22px;
      line-height: 1.1;
      font-weight: 750;
    }
    .label {
      margin-top: 4px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 650;
      text-transform: uppercase;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 240px;
      gap: 16px;
      align-items: stretch;
    }
    .chart {
      width: 100%;
      height: 210px;
      display: block;
      border-radius: 10px;
      background: color-mix(in srgb, var(--orange) 8%, transparent);
    }
    .services h2 {
      margin: 0 0 10px;
      font-size: 14px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    .service {
      margin-bottom: 12px;
    }
    .service-row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 13px;
      font-weight: 650;
    }
    .service-meta {
      color: var(--muted);
      font-size: 12px;
      margin-top: 2px;
    }
    .bar {
      height: 6px;
      margin-top: 6px;
      border-radius: 999px;
      background: color-mix(in srgb, var(--magenta) var(--bar-width, 0%), var(--line));
    }
    @media (max-width: 720px) {
      .metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="card" aria-label="Logfire activity">
      <div class="head">
        <div>
          <h1 id="title">Logfire activity</h1>
          <div class="sub" id="subtitle">Waiting for tool output</div>
        </div>
      </div>
      <div class="metrics" id="metrics"></div>
      <div class="grid">
        <svg class="chart" id="chart" viewBox="0 0 620 210" role="img" aria-label="Trace count sparkline"></svg>
        <aside class="services">
          <h2>Top services</h2>
          <div id="services"></div>
        </aside>
      </div>
    </section>
  </main>
  <script>
    const fallback = {
      title: "Logfire activity",
      window: "24h",
      bucket: "15m",
      series: [
        {bucket: "00:00", trace_count: 42, error_count: 0, p95_ms: 180},
        {bucket: "02:00", trace_count: 51, error_count: 1, p95_ms: 220},
        {bucket: "04:00", trace_count: 37, error_count: 0, p95_ms: 190},
        {bucket: "06:00", trace_count: 64, error_count: 2, p95_ms: 340},
        {bucket: "08:00", trace_count: 128, error_count: 7, p95_ms: 910},
        {bucket: "10:00", trace_count: 96, error_count: 3, p95_ms: 480},
        {bucket: "12:00", trace_count: 110, error_count: 2, p95_ms: 360},
        {bucket: "14:00", trace_count: 118, error_count: 4, p95_ms: 420},
        {bucket: "16:00", trace_count: 89, error_count: 1, p95_ms: 290},
        {bucket: "18:00", trace_count: 132, error_count: 9, p95_ms: 1040},
        {bucket: "20:00", trace_count: 101, error_count: 5, p95_ms: 610},
        {bucket: "22:00", trace_count: 77, error_count: 1, p95_ms: 300}
      ],
      top_services: [
        {service_name: "api", trace_count: 482, error_count: 19, p95_ms: 730},
        {service_name: "worker", trace_count: 219, error_count: 8, p95_ms: 520},
        {service_name: "gateway", trace_count: 174, error_count: 3, p95_ms: 310}
      ]
    };

    function n(value) {
      const result = Number(value);
      return Number.isFinite(result) ? result : 0;
    }

    function pointList(values, x, y, w, h) {
      if (!values.length) return "";
      const high = Math.max(...values, 1);
      const low = Math.min(...values);
      const span = high - low || high || 1;
      return values.map((value, index) => {
        const px = x + (index / Math.max(1, values.length - 1)) * w;
        const py = y + h - ((value - low) / span) * h;
        return `${px.toFixed(1)},${py.toFixed(1)}`;
      }).join(" ");
    }

    function areaPath(values, x, y, w, h) {
      const points = pointList(values, x, y, w, h);
      return points ? `M ${x},${y + h} L ${points} L ${x + w},${y + h} Z` : "";
    }

    function render(payload) {
      const series = Array.isArray(payload?.series) ? payload.series : fallback.series;
      const services = Array.isArray(payload?.top_services) ? payload.top_services : [];
      const traces = series.map(row => n(row.trace_count ?? row.traces ?? row.count));
      const errors = series.map(row => n(row.error_count ?? row.errors));
      const p95 = series.map(row => n(row.p95_ms ?? row.p95_duration_ms ?? row.p95));
      const totalTraces = traces.reduce((a, b) => a + b, 0);
      const totalErrors = errors.reduce((a, b) => a + b, 0);
      const errorRate = totalTraces ? (totalErrors / totalTraces) * 100 : 0;
      const maxP95 = Math.max(...p95, 0);

      document.getElementById("title").textContent = payload?.title || "Logfire activity";
      document.getElementById("subtitle").textContent = `Window ${payload?.window || "n/a"} · bucket ${payload?.bucket || "n/a"}`;
      document.getElementById("metrics").innerHTML = [
        [Math.round(totalTraces), "traces"],
        [Math.round(totalErrors), "errors"],
        [`${errorRate.toFixed(1)}%`, "error rate"],
        [`${Math.round(maxP95)}ms`, "max p95 latency"]
      ].map(([value, label]) => `<div class="metric"><div class="value">${value}</div><div class="label">${label}</div></div>`).join("");

      const chart = document.getElementById("chart");
      const x = 32, y = 26, w = 560, h = 118;
      const p95Points = pointList(p95, x, 150, w, 38);
      const maxErrors = Math.max(...errors, 0);
      const dots = maxErrors ? errors.map((value, index) => {
        if (!value) return "";
        const cx = x + (index / Math.max(1, errors.length - 1)) * w;
        const r = 3 + (value / maxErrors) * 5;
        return `<circle cx="${cx.toFixed(1)}" cy="165" r="${r.toFixed(1)}" fill="var(--orange)" opacity=".72"></circle>`;
      }).join("") : "";
      chart.innerHTML = `
        <path d="${areaPath(traces, x, y, w, h)}" fill="var(--magenta)" opacity=".13"></path>
        <polyline points="${pointList(traces, x, y, w, h)}" fill="none" stroke="var(--magenta)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></polyline>
        <polyline points="${p95Points}" fill="none" stroke="var(--orange)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" opacity=".76"></polyline>
        ${dots}
        <text x="32" y="200" fill="var(--muted)" font-size="11">trace volume</text>
        <text x="500" y="200" fill="var(--muted)" font-size="11">latency/errors</text>
      `;

      const maxServiceTraces = Math.max(...services.map(row => n(row.trace_count)), 1);
      document.getElementById("services").innerHTML = services.length ? services.slice(0, 5).map(row => {
        const name = row.service_name || row.service || "unknown";
        const count = Math.round(n(row.trace_count));
        const width = Math.max(4, (count / maxServiceTraces) * 100);
        return `<div class="service">
          <div class="service-row"><span>${name}</span><span>${count}</span></div>
          <div class="service-meta">${Math.round(n(row.error_count))} errors · p95 ${Math.round(n(row.p95_ms))}ms</div>
          <div class="bar" style="--bar-width:${width}%"></div>
        </div>`;
      }).join("") : `<div class="sub">No service breakdown in input.</div>`;

      window.openai?.notifyIntrinsicHeight?.();
    }

    function readHostOutput() {
      return window.openai?.toolOutput || fallback;
    }

    window.addEventListener("message", event => {
      const message = event.data;
      if (message?.method === "ui/notifications/tool-result") {
        render(message.params?.structuredContent || message.params?._meta?.payload || fallback);
      }
    });

    render(readHostOutput());
  </script>
</body>
</html>
"""


def _tools() -> list[dict[str, Any]]:
    tool_meta = {
        "ui": {"resourceUri": WIDGET_URI},
        "openai/outputTemplate": WIDGET_URI,
        "openai/toolInvocation/invoking": "Rendering Logfire activity",
        "openai/toolInvocation/invoked": "Logfire activity ready",
    }
    return [
        {
            "name": "logfire_render_activity_card",
            "title": "Render Logfire Activity Card",
            "description": (
                "Render an inline Logfire activity widget from bucketed telemetry rows. "
                "Use this when the user asks to show a sparkline, chart, activity card, "
                "trace-count trend, error trend, or latency summary."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "window": {"type": "string"},
                    "bucket": {"type": "string"},
                    "series": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "bucket": {"type": "string"},
                                "trace_count": {"type": "number"},
                                "error_count": {"type": "number"},
                                "p95_ms": {"type": "number"},
                            },
                        },
                    },
                    "top_services": {"type": "array", "items": {"type": "object"}},
                },
            },
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            "_meta": tool_meta,
        },
        {
            "name": "logfire_render_sparkline",
            "title": "Render Logfire Sparkline",
            "description": (
                "Render an inline Logfire sparkline from plain trace-count values. "
                "Use this for quick visual checks like values 0, 0, 0, 14, 14."
            ),
            "inputSchema": {
                "type": "object",
                "required": ["values"],
                "properties": {
                    "values": {"type": "array", "items": {"type": "number"}},
                    "errors": {"type": "array", "items": {"type": "number"}},
                    "p95_ms": {"type": "array", "items": {"type": "number"}},
                    "title": {"type": "string"},
                    "window": {"type": "string"},
                    "bucket": {"type": "string"},
                },
            },
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            "_meta": tool_meta,
        },
        {
            "name": "logfire_render_activity_report",
            "title": "Render Logfire Activity Report",
            "description": (
                "Write a self-contained local HTML Logfire activity report and return "
                "a localhost URL. Use this when the user asks for a GUI, dashboard, "
                "browser report, visual activity report, or interactive telemetry view."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "window": {"type": "string"},
                    "bucket": {"type": "string"},
                    "filename": {
                        "type": "string",
                        "description": "Optional report filename under the MCP report directory.",
                    },
                    "output_path": {
                        "type": "string",
                        "description": (
                            "Optional HTML path. Must be inside the default report directory "
                            "if serve is true."
                        ),
                    },
                    "serve": {
                        "type": "boolean",
                        "description": "Start/reuse a localhost server and return url. Defaults to true.",
                    },
                    "port": {
                        "type": "integer",
                        "description": "Optional localhost port. Omit to use an available ephemeral port.",
                    },
                    "series": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "bucket": {"type": "string"},
                                "trace_count": {"type": "number"},
                                "error_count": {"type": "number"},
                                "p95_ms": {"type": "number"},
                            },
                        },
                    },
                    "values": {"type": "array", "items": {"type": "number"}},
                    "errors": {"type": "array", "items": {"type": "number"}},
                    "p95_ms": {"type": "array", "items": {"type": "number"}},
                    "top_services": {"type": "array", "items": {"type": "object"}},
                    "sample_trace_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
            "annotations": {
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            },
        },
    ]


def _tool_result(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_payload(arguments)
    trace_total = sum(_number(row.get("trace_count")) for row in payload["series"] if isinstance(row, dict))
    error_total = sum(_number(row.get("error_count")) for row in payload["series"] if isinstance(row, dict))
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    "Rendered a Logfire activity widget "
                    f"({int(trace_total)} traces, {int(error_total)} errors)."
                ),
            }
        ],
        "structuredContent": payload,
        "_meta": {
            "openai/outputTemplate": WIDGET_URI,
            "ui": {"resourceUri": WIDGET_URI},
        },
    }


def _report_tool_result(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_payload(arguments)
    output_path = _report_output_path(arguments, payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(payload))

    serve = arguments.get("serve")
    should_serve = True if serve is None else bool(serve)
    url = None
    if should_serve:
        base_url = _ensure_report_server(arguments.get("port"))
        url = _path_to_report_url(base_url, output_path)

    trace_total = sum(_number(row.get("trace_count")) for row in payload["series"] if isinstance(row, dict))
    error_total = sum(_number(row.get("error_count")) for row in payload["series"] if isinstance(row, dict))
    structured_content: dict[str, Any] = {
        "path": str(output_path.resolve()),
        "url": url,
        "title": payload["title"],
        "window": payload["window"],
        "bucket": payload["bucket"],
        "trace_count": int(trace_total),
        "error_count": int(error_total),
        "served": should_serve,
    }
    text = (
        "Wrote a Logfire activity report "
        f"({int(trace_total)} traces, {int(error_total)} errors) to {structured_content['path']}."
    )
    if url:
        text += f" Open it at {url}."
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": structured_content,
    }


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method and method.startswith("notifications/"):
        return None

    try:
        if method == "initialize":
            params = request.get("params") or {}
            result = {
                "protocolVersion": params.get("protocolVersion") or "2025-06-18",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "logfire-activity-render", "version": "0.1.0"},
            }
        elif method == "tools/list":
            result = {"tools": _tools()}
        elif method == "tools/call":
            params = request.get("params") or {}
            name = params.get("name")
            if name == "logfire_render_activity_report":
                result = _report_tool_result(params.get("arguments") or {})
            elif name in {"logfire_render_activity_card", "logfire_render_sparkline"}:
                result = _tool_result(params.get("arguments") or {})
            else:
                raise ValueError(f"Unknown tool: {name}")
        elif method == "resources/list":
            result = {
                "resources": [
                    {
                        "uri": WIDGET_URI,
                        "name": "Logfire activity widget",
                        "mimeType": WIDGET_MIME_TYPE,
                        "description": "Inline Logfire sparkline and activity summary widget.",
                    }
                ]
            }
        elif method == "resources/templates/list":
            result = {"resourceTemplates": []}
        elif method == "resources/read":
            params = request.get("params") or {}
            if params.get("uri") != WIDGET_URI:
                raise ValueError(f"Unknown resource: {params.get('uri')}")
            result = {
                "contents": [
                    {
                        "uri": WIDGET_URI,
                        "mimeType": WIDGET_MIME_TYPE,
                        "text": _widget_html(),
                        "_meta": {
                            "ui": {
                                "prefersBorder": True,
                                "csp": {"connectDomains": [], "resourceDomains": []},
                            },
                            "openai/widgetDescription": (
                                "A compact Logfire activity card with trace, error, "
                                "and latency sparklines."
                            ),
                        },
                    }
                ]
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:  # noqa: BLE001 - convert all handler errors to JSON-RPC.
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": str(exc)},
        }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = _handle(request)
        except json.JSONDecodeError as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
