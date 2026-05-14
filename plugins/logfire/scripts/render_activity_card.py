#!/usr/bin/env python3
"""Render a Logfire activity summary as a standalone SVG.

The input is intentionally simple so it can be produced by either Logfire MCP
queries or the REST query API. See examples/activity-card/sample.json.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


DEFAULT_SAMPLE = {
    "window": "24h",
    "bucket": "15m",
    "series": [
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
    ],
    "top_services": [
        {"service_name": "api", "trace_count": 482, "error_count": 19, "p95_ms": 730},
        {"service_name": "worker", "trace_count": 219, "error_count": 8, "p95_ms": 520},
        {"service_name": "gateway", "trace_count": 174, "error_count": 3, "p95_ms": 310},
    ],
    "sample_trace_ids": [
        "019e2b04a0d67c61a4f8bd2e6fb80b31",
        "019e2b04c98e7280ad1d140c77bb91f0",
    ],
}


def _load_payload(path: Path | None) -> dict[str, Any]:
    if path is None:
        return DEFAULT_SAMPLE
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return {"series": data}
    if isinstance(data, dict):
        # Accept the Logfire REST API's common column-oriented shape:
        # {"columns": [...], "rows": [[...], ...]}.
        if "columns" in data and "rows" in data and isinstance(data["rows"], list):
            columns = data["columns"]
            rows = [dict(zip(columns, row)) for row in data["rows"]]
            return {"series": rows}
        return data
    raise TypeError("Input JSON must be an object or a list of row objects")


def _payload_from_values(values: str, title: str, window: str, bucket: str) -> dict[str, Any]:
    series = []
    for index, raw_value in enumerate(values.split(",")):
        raw_value = raw_value.strip()
        if not raw_value:
            continue
        series.append(
            {
                "bucket": str(index + 1),
                "trace_count": _number(raw_value),
                "error_count": 0,
                "p95_ms": 0,
            }
        )
    if not series:
        raise ValueError("--values must contain at least one numeric value")
    return {
        "title": title,
        "window": window,
        "bucket": bucket,
        "series": series,
        "top_services": [],
    }


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if isinstance(value, str) and not value.strip():
            return default
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def _field(row: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return default


def _label(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if "T" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%H:%M")
        except ValueError:
            pass
    return text[-5:] if len(text) > 5 and text[-3:-2] == ":" else text


def _normalize_series(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_series = payload.get("series") or payload.get("rows") or []
    series: list[dict[str, Any]] = []
    for row in raw_series:
        if not isinstance(row, dict):
            continue
        series.append(
            {
                "label": _label(_field(row, "bucket", "time", "timestamp", "start_timestamp")),
                "trace_count": _number(_field(row, "trace_count", "traces", "total", "count")),
                "error_count": _number(_field(row, "error_count", "errors", "exceptions")),
                "p95_ms": _number(_field(row, "p95_ms", "p95_duration_ms", "p95_duration", "p95")),
            }
        )
    return series


def _normalize_services(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_services = payload.get("top_services") or payload.get("services") or []
    services: list[dict[str, Any]] = []
    for row in raw_services[:5]:
        if not isinstance(row, dict):
            continue
        services.append(
            {
                "name": str(_field(row, "service_name", "service", default="unknown") or "unknown"),
                "trace_count": int(_number(_field(row, "trace_count", "traces", "total", "count"))),
                "error_count": int(_number(_field(row, "error_count", "errors", "exceptions"))),
                "p95_ms": int(_number(_field(row, "p95_ms", "p95_duration_ms", "p95_duration", "p95"))),
            }
        )
    return services


def _polyline(values: list[float], x: float, y: float, width: float, height: float) -> str:
    if not values:
        return ""
    high = max(values) or 1
    low = min(values)
    span = high - low or high or 1
    points: list[str] = []
    for index, value in enumerate(values):
        px = x + (index / max(1, len(values) - 1)) * width
        py = y + height - ((value - low) / span) * height
        points.append(f"{px:.1f},{py:.1f}")
    return " ".join(points)


def _area_path(values: list[float], x: float, y: float, width: float, height: float) -> str:
    line = _polyline(values, x, y, width, height)
    if not line:
        return ""
    first_x = x
    last_x = x + width
    base_y = y + height
    return f"M {first_x:.1f},{base_y:.1f} L {line} L {last_x:.1f},{base_y:.1f} Z"


def render_svg(payload: dict[str, Any]) -> str:
    series = _normalize_series(payload)
    services = _normalize_services(payload)
    trace_values = [row["trace_count"] for row in series]
    p95_values = [row["p95_ms"] for row in series]
    error_values = [row["error_count"] for row in series]
    total_traces = int(sum(trace_values))
    total_errors = int(sum(error_values))
    max_p95 = int(max(p95_values or [0]))
    error_rate = (total_errors / total_traces * 100) if total_traces else 0
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    chart_x, chart_y, chart_w, chart_h = 46, 156, 548, 142
    p95_y = 318
    service_x = 650
    title = escape(str(payload.get("title") or "Logfire activity"))
    window = escape(str(payload.get("window") or "24h"))
    bucket = escape(str(payload.get("bucket") or "15m"))

    labels = []
    if series:
        labels = [series[0]["label"], series[len(series) // 2]["label"], series[-1]["label"]]

    service_rows = []
    max_service_traces = max([service["trace_count"] for service in services] or [1])
    for index, service in enumerate(services[:4]):
        y = 176 + index * 46
        bar_w = max(4, service["trace_count"] / max_service_traces * 150)
        service_rows.append(
            f'''
            <text x="{service_x}" y="{y}" class="service-name">{escape(service["name"])}</text>
            <text x="820" y="{y}" class="service-meta">{service["trace_count"]} traces</text>
            <text x="820" y="{y + 18}" class="service-error">{service["error_count"]} errors</text>
            <rect x="{service_x}" y="{y + 10}" width="{bar_w:.1f}" height="6" rx="3" fill="#E520E9" opacity="0.68"/>
            '''
        )

    error_dots = []
    max_errors = max(error_values or [0])
    if max_errors:
        for index, value in enumerate(error_values):
            if value <= 0:
                continue
            cx = chart_x + (index / max(1, len(error_values) - 1)) * chart_w
            radius = 3 + (value / max_errors) * 5
            error_dots.append(
                f'<circle cx="{cx:.1f}" cy="{chart_y + chart_h + 18:.1f}" r="{radius:.1f}" fill="#E85D2A" opacity="0.76"/>'
            )

    label_markup = ""
    if labels:
        label_markup = f'''
        <text x="{chart_x}" y="322" class="axis">{escape(labels[0])}</text>
        <text x="{chart_x + chart_w / 2 - 18}" y="322" class="axis">{escape(labels[1])}</text>
        <text x="{chart_x + chart_w - 34}" y="322" class="axis">{escape(labels[2])}</text>
        '''

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 420" role="img" aria-label="{title}">
  <style>
    .bg {{ fill: #fffdfb; }}
    .card {{ fill: #ffffff; stroke: #eadfd8; stroke-width: 1; }}
    .title {{ font: 700 24px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #161616; }}
    .subtle {{ font: 500 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #716a66; }}
    .metric {{ font: 700 26px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #161616; }}
    .metric-label {{ font: 600 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #716a66; text-transform: uppercase; }}
    .axis {{ font: 500 11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #8a817b; }}
    .service-title {{ font: 700 15px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #161616; }}
    .service-name {{ font: 650 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #27211e; }}
    .service-meta {{ font: 600 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #625a55; }}
    .service-error {{ font: 600 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #E85D2A; }}
  </style>
  <rect width="960" height="420" class="bg"/>
  <rect x="16" y="16" width="928" height="388" rx="22" class="card"/>
  <path fill="#E520E9" d="M64.18 71.64 53.02 56.3 35.77 32.8c-1.74-2.4-5.76-2.4-7.49 0L11.04 56.29.87 71.64c-.86 1.2-1.1 2.73-.65 4.13.46 1.4 1.55 2.5 2.95 2.96l27.41 9.14h.01c.46.15.94.23 1.43.23s.97-.08 1.43-.23h.01l27.41-9.14c1.4-.46 2.5-1.55 2.95-2.96.46-1.4.22-2.93-.65-4.13zM32.03 43.39l8.21 11.8-8.77-2.8c-.16-.05-.33-.04-.49-.08-.16-.04-.32-.06-.48-.08-.16-.02-.31-.08-.47-.08-.16 0-.31.06-.47.08-.17.02-.32.04-.48.08-.16.03-.33.03-.48.08l-8.64 2.76-.13.04 8.21-11.8zM17.65 62.91l9.18-2.92 2.58-.84v20.97l-17.35-6.2Zm18 17.2V59.15l10.76 3.76 6.59 10z" transform="translate(30 19) scale(.72)"/>
  <text x="94" y="54" class="title">{title}</text>
  <text x="94" y="76" class="subtle">Window {window} · bucket {bucket} · generated {generated}</text>

  <text x="46" y="124" class="metric">{total_traces}</text>
  <text x="46" y="144" class="metric-label">traces</text>
  <text x="190" y="124" class="metric">{total_errors}</text>
  <text x="190" y="144" class="metric-label">errors</text>
  <text x="320" y="124" class="metric">{error_rate:.1f}%</text>
  <text x="320" y="144" class="metric-label">error rate</text>
  <text x="462" y="124" class="metric">{max_p95}ms</text>
  <text x="462" y="144" class="metric-label">max p95 latency</text>

  <rect x="{chart_x}" y="{chart_y}" width="{chart_w}" height="{chart_h}" rx="12" fill="#fff7f1"/>
  <path d="{_area_path(trace_values, chart_x, chart_y + 14, chart_w, chart_h - 28)}" fill="#E520E9" opacity="0.12"/>
  <polyline points="{_polyline(trace_values, chart_x, chart_y + 14, chart_w, chart_h - 28)}" fill="none" stroke="#E520E9" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <polyline points="{_polyline(p95_values, chart_x, p95_y, chart_w, 46)}" fill="none" stroke="#E85D2A" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" opacity="0.72"/>
  {''.join(error_dots)}
  {label_markup}
  <text x="{chart_x}" y="364" class="subtle">Purple: trace volume · orange: p95 latency and error buckets</text>

  <text x="{service_x}" y="124" class="service-title">Top services</text>
  {''.join(service_rows) if service_rows else f'<text x="{service_x}" y="176" class="subtle">No service breakdown in input.</text>'}
</svg>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Logfire activity SVG from JSON data.")
    parser.add_argument("--input", type=Path, help="JSON input file. Omit to render bundled sample data.")
    parser.add_argument("--values", help="Comma-separated trace counts for a quick sparkline smoke test.")
    parser.add_argument("--output", type=Path, required=True, help="SVG output path.")
    parser.add_argument("--title", default="Logfire activity", help="Title used with --values.")
    parser.add_argument("--window", default="ad hoc", help="Window label used with --values.")
    parser.add_argument("--bucket", default="bucket", help="Bucket label used with --values.")
    parser.add_argument("--print-markdown", action="store_true", help="Print a Markdown image tag for the output.")
    args = parser.parse_args()

    if args.values and args.input:
        parser.error("Use either --input or --values, not both.")

    payload = _payload_from_values(args.values, args.title, args.window, args.bucket) if args.values else _load_payload(args.input)
    svg = render_svg(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg)
    print(args.output)
    if args.print_markdown:
        print(f"![Logfire activity]({args.output.resolve()})")


if __name__ == "__main__":
    main()
