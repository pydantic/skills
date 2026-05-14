#!/usr/bin/env python3
"""Render a small, self-contained Logfire activity report as HTML."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from render_activity_card import _load_payload, _normalize_series, _normalize_services, _payload_from_values


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__PAGE_TITLE__</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f4ef;
      --surface: #fffdf9;
      --panel: #ffffff;
      --line: #e7ddd5;
      --text: #151312;
      --muted: #706862;
      --purple: #e520e9;
      --orange: #f15b2a;
      --green: #16866f;
      --shadow: 0 24px 80px rgba(42, 31, 23, 0.12);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 8% 0%, rgba(229, 32, 233, 0.12), transparent 30%),
        linear-gradient(135deg, #fffdf9 0%, var(--bg) 54%, #f8eef5 100%);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    button {
      font: inherit;
    }

    .shell {
      width: min(1180px, calc(100vw - 32px));
      margin: 28px auto;
      display: grid;
      gap: 18px;
    }

    .hero,
    .panel {
      background: rgba(255, 253, 249, 0.92);
      border: 1px solid rgba(231, 221, 213, 0.95);
      border-radius: 18px;
      box-shadow: var(--shadow);
    }

    .hero {
      padding: 22px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 18px;
      align-items: start;
    }

    .brand {
      display: flex;
      gap: 14px;
      align-items: center;
    }

    .mark {
      width: 48px;
      height: 48px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: #fff6f0;
      border: 1px solid #ecded5;
    }

    h1 {
      margin: 0;
      font-size: clamp(26px, 3vw, 42px);
      line-height: 1.04;
      letter-spacing: 0;
    }

    .subtitle {
      margin: 7px 0 0;
      color: var(--muted);
      font-size: 15px;
    }

    .meta {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #ffffff;
      color: #4d4641;
      padding: 7px 10px;
      font-size: 13px;
      font-weight: 650;
      white-space: nowrap;
    }

    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .metric {
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 15px;
      min-height: 106px;
    }

    .metric .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      text-transform: uppercase;
      letter-spacing: 0;
    }

    .metric .value {
      margin-top: 8px;
      font-size: 32px;
      font-weight: 780;
      line-height: 1;
    }

    .metric .hint {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
    }

    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(320px, 0.9fr);
      gap: 18px;
    }

    .panel {
      padding: 18px;
      min-width: 0;
    }

    .panel-header {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
      margin-bottom: 14px;
    }

    h2 {
      margin: 0;
      font-size: 17px;
      letter-spacing: 0;
    }

    .segmented {
      display: inline-flex;
      gap: 4px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #f8f2ee;
    }

    .segmented button {
      border: 0;
      border-radius: 9px;
      padding: 7px 10px;
      background: transparent;
      color: #5e5650;
      cursor: pointer;
      font-size: 13px;
      font-weight: 700;
    }

    .segmented button[aria-pressed="true"] {
      background: #ffffff;
      color: var(--text);
      box-shadow: 0 2px 10px rgba(42, 31, 23, 0.1);
    }

    .chart-wrap {
      position: relative;
      height: 342px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #fffaf6 0%, #ffffff 100%);
      overflow: hidden;
    }

    svg.chart {
      display: block;
      width: 100%;
      height: 100%;
    }

    .tooltip {
      position: absolute;
      min-width: 136px;
      pointer-events: none;
      background: rgba(22, 19, 18, 0.92);
      color: #ffffff;
      border-radius: 10px;
      padding: 8px 10px;
      font-size: 12px;
      line-height: 1.35;
      opacity: 0;
      transform: translate(-50%, -12px);
      transition: opacity 120ms ease;
    }

    .tooltip strong {
      display: block;
      font-size: 13px;
    }

    .chart-note {
      margin: 12px 2px 0;
      color: var(--muted);
      font-size: 13px;
    }

    .services {
      display: grid;
      gap: 9px;
    }

    .service-row {
      width: 100%;
      text-align: left;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #ffffff;
      padding: 12px;
      cursor: pointer;
      display: grid;
      gap: 9px;
    }

    .service-row[aria-pressed="true"] {
      border-color: rgba(229, 32, 233, 0.48);
      box-shadow: 0 0 0 3px rgba(229, 32, 233, 0.11);
    }

    .service-topline {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .service-name {
      font-weight: 760;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .service-meta {
      color: var(--muted);
      font-size: 12px;
      font-weight: 690;
      white-space: nowrap;
    }

    .bar {
      height: 8px;
      border-radius: 999px;
      background: #f3ece7;
      overflow: hidden;
    }

    .bar span {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--purple), var(--orange));
    }

    .callout {
      margin-top: 14px;
      border-radius: 14px;
      background: #fff8f3;
      border: 1px solid #eadbd1;
      padding: 13px;
      color: #4d4641;
      font-size: 13px;
      line-height: 1.45;
    }

    .bottom-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 18px;
    }

    .list {
      margin: 0;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 10px;
    }

    .list li {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 11px 12px;
      background: #ffffff;
      color: #433c37;
      font-size: 14px;
    }

    code {
      padding: 2px 5px;
      border-radius: 7px;
      background: #f3ece7;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.94em;
    }

    @media (max-width: 820px) {
      .hero,
      .grid,
      .bottom-grid {
        grid-template-columns: 1fr;
      }

      .metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .meta {
        justify-content: flex-start;
      }

      .panel-header {
        align-items: flex-start;
        flex-direction: column;
      }
    }

    @media (max-width: 520px) {
      .shell {
        width: min(100vw - 20px, 1180px);
        margin: 10px auto;
      }

      .metrics {
        grid-template-columns: 1fr;
      }

      .chart-wrap {
        height: 292px;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <div class="brand">
          <div class="mark" aria-hidden="true">
            <svg viewBox="0 0 120 112" width="30" height="30">
              <path fill="#E520E9" d="M119.18 86.64 98.02 57.3 63.77 9.8c-1.74-2.4-5.76-2.4-7.49 0L22.04 57.29.87 86.64c-.86 1.2-1.1 2.73-.65 4.13.46 1.4 1.55 2.5 2.95 2.96l55.41 18.14h.01c.46.15.94.23 1.43.23s.97-.08 1.43-.23h.01l55.41-18.14c1.4-.46 2.5-1.55 2.95-2.96.46-1.4.22-2.93-.65-4.13zM60.03 20.39l22.21 30.8-20.77-6.8c-.16-.05-.33-.04-.49-.08-.16-.04-.32-.06-.48-.08-.16-.02-.31-.08-.47-.08-.16 0-.31.06-.47.08-.17.02-.32.04-.48.08-.16.03-.33.03-.48.08l-20.64 6.76-.13.04 22.21-30.8zM28.65 63.91l24.18-7.92 2.58-.84v45.97l-43.35-14.2Zm36 37.2V55.15l26.76 8.76 16.59 23z"></path>
            </svg>
          </div>
          <div>
            <h1>__REPORT_TITLE__</h1>
            <p class="subtitle">__SUBTITLE__</p>
          </div>
        </div>
      </div>
      <div class="meta" aria-label="Report metadata">
        <span class="pill">Window __WINDOW__</span>
        <span class="pill">Bucket __BUCKET__</span>
        <span class="pill">Generated __GENERATED__</span>
      </div>
    </section>

    <section class="metrics" aria-label="Summary metrics">
      <div class="metric">
        <div class="label">Traces</div>
        <div class="value">__TOTAL_TRACES__</div>
        <div class="hint">Across __BUCKET_COUNT__ buckets</div>
      </div>
      <div class="metric">
        <div class="label">Errors</div>
        <div class="value">__TOTAL_ERRORS__</div>
        <div class="hint">__ERROR_RATE__ error rate</div>
      </div>
      <div class="metric">
        <div class="label">Peak p95</div>
        <div class="value">__PEAK_P95__</div>
        <div class="hint">Highest latency bucket</div>
      </div>
      <div class="metric">
        <div class="label">Top service</div>
        <div class="value">__TOP_SERVICE__</div>
        <div class="hint">By trace volume</div>
      </div>
    </section>

    <section class="grid">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 id="chartTitle">Trace volume</h2>
          </div>
          <div class="segmented" aria-label="Metric selector">
            <button type="button" data-metric="trace_count" aria-pressed="true">Traces</button>
            <button type="button" data-metric="error_count" aria-pressed="false">Errors</button>
            <button type="button" data-metric="p95_ms" aria-pressed="false">P95</button>
          </div>
        </div>
        <div class="chart-wrap">
          <svg class="chart" viewBox="0 0 820 330" role="img" aria-labelledby="chartTitle"></svg>
          <div class="tooltip" id="tooltip" role="status"></div>
        </div>
        <p class="chart-note">Hover points to inspect buckets. Use the metric control to switch the chart without rerunning a query.</p>
      </div>

      <aside class="panel">
        <div class="panel-header">
          <h2>Top services</h2>
        </div>
        <div class="services">
          __SERVICE_ROWS__
        </div>
        <div class="callout" id="serviceCallout">Select a service to turn it into the next Logfire filter.</div>
      </aside>
    </section>

    <section class="bottom-grid">
      <div class="panel">
        <div class="panel-header">
          <h2>Quick read</h2>
        </div>
        <ul class="list">
          __FINDINGS__
        </ul>
      </div>
      <div class="panel">
        <div class="panel-header">
          <h2>Sample traces</h2>
        </div>
        <ul class="list">
          __TRACE_ROWS__
        </ul>
      </div>
    </section>
  </main>

  <script>
    const report = __DATA_JSON__;
    const svg = document.querySelector("svg.chart");
    const tooltip = document.getElementById("tooltip");
    const chartTitle = document.getElementById("chartTitle");
    const metrics = {
      trace_count: { label: "Trace volume", color: "#e520e9", unit: "" },
      error_count: { label: "Errors", color: "#f15b2a", unit: "" },
      p95_ms: { label: "P95 latency", color: "#16866f", unit: "ms" }
    };
    let selectedMetric = "trace_count";

    function svgEl(name, attrs = {}) {
      const node = document.createElementNS("http://www.w3.org/2000/svg", name);
      for (const [key, value] of Object.entries(attrs)) {
        node.setAttribute(key, value);
      }
      return node;
    }

    function formatValue(value, metric) {
      const rounded = Math.round(Number(value) || 0);
      return `${rounded}${metrics[metric].unit}`;
    }

    function pointFor(row, index, rows, metric, bounds, low, span) {
      const value = Number(row[metric]) || 0;
      const x = bounds.left + (index / Math.max(1, rows.length - 1)) * bounds.width;
      const y = bounds.top + bounds.height - ((value - low) / span) * bounds.height;
      return { x, y, value };
    }

    function drawChart() {
      const rows = report.series || [];
      const metric = selectedMetric;
      const config = metrics[metric];
      const bounds = { left: 48, top: 28, width: 728, height: 226 };
      const values = rows.map((row) => Number(row[metric]) || 0);
      const high = Math.max(...values, 1);
      const low = Math.min(0, ...values);
      const span = high - low || 1;
      svg.innerHTML = "";
      chartTitle.textContent = config.label;

      for (let i = 0; i <= 4; i += 1) {
        const y = bounds.top + (i / 4) * bounds.height;
        svg.appendChild(svgEl("line", {
          x1: bounds.left,
          x2: bounds.left + bounds.width,
          y1: y,
          y2: y,
          stroke: "#eadfd8",
          "stroke-width": 1
        }));
      }

      if (!rows.length) {
        const empty = svgEl("text", {
          x: 410,
          y: 165,
          "text-anchor": "middle",
          fill: "#706862",
          "font-size": 14
        });
        empty.textContent = "No activity rows in this report.";
        svg.appendChild(empty);
        return;
      }

      const points = rows.map((row, index) => pointFor(row, index, rows, metric, bounds, low, span));
      const pointList = points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
      const areaPath = [
        `M ${bounds.left},${bounds.top + bounds.height}`,
        `L ${pointList}`,
        `L ${bounds.left + bounds.width},${bounds.top + bounds.height}`,
        "Z"
      ].join(" ");

      svg.appendChild(svgEl("path", {
        d: areaPath,
        fill: config.color,
        opacity: 0.12
      }));
      svg.appendChild(svgEl("polyline", {
        points: pointList,
        fill: "none",
        stroke: config.color,
        "stroke-width": 4,
        "stroke-linecap": "round",
        "stroke-linejoin": "round"
      }));

      const labels = [rows[0], rows[Math.floor(rows.length / 2)], rows[rows.length - 1]];
      labels.forEach((row, index) => {
        const x = index === 0 ? bounds.left : index === 1 ? bounds.left + bounds.width / 2 : bounds.left + bounds.width;
        const label = svgEl("text", {
          x,
          y: 292,
          "text-anchor": index === 0 ? "start" : index === 1 ? "middle" : "end",
          fill: "#817771",
          "font-size": 12,
          "font-weight": 650
        });
        label.textContent = row.label || "";
        svg.appendChild(label);
      });

      points.forEach((point, index) => {
        const row = rows[index];
        const dot = svgEl("circle", {
          cx: point.x,
          cy: point.y,
          r: 6,
          fill: "#ffffff",
          stroke: config.color,
          "stroke-width": 3,
          tabindex: 0
        });
        const show = () => {
          tooltip.innerHTML = `<strong>${row.label || `Bucket ${index + 1}`}</strong>${config.label}: ${formatValue(point.value, metric)}<br>Errors: ${formatValue(row.error_count, "error_count")}<br>P95: ${formatValue(row.p95_ms, "p95_ms")}`;
          tooltip.style.left = `${(point.x / 820) * 100}%`;
          tooltip.style.top = `${point.y}px`;
          tooltip.style.opacity = 1;
        };
        dot.addEventListener("mouseenter", show);
        dot.addEventListener("focus", show);
        dot.addEventListener("mouseleave", () => { tooltip.style.opacity = 0; });
        dot.addEventListener("blur", () => { tooltip.style.opacity = 0; });
        svg.appendChild(dot);
      });
    }

    document.querySelectorAll("[data-metric]").forEach((button) => {
      button.addEventListener("click", () => {
        selectedMetric = button.dataset.metric;
        document.querySelectorAll("[data-metric]").forEach((candidate) => {
          candidate.setAttribute("aria-pressed", String(candidate === button));
        });
        tooltip.style.opacity = 0;
        drawChart();
      });
    });

    document.querySelectorAll(".service-row").forEach((row) => {
      row.addEventListener("click", () => {
        document.querySelectorAll(".service-row").forEach((candidate) => {
          candidate.setAttribute("aria-pressed", String(candidate === row));
        });
        const service = row.dataset.service || "unknown";
        document.getElementById("serviceCallout").innerHTML =
          `Next query filter: <code>service_name = '${service.replace(/'/g, "''")}'</code>`;
      });
    });

    drawChart();
  </script>
</body>
</html>
"""


def _format_int(value: float | int) -> str:
    return f"{int(round(float(value))):,}"


def _format_percent(value: float) -> str:
    return f"{value:.1f}%"


def _format_ms(value: float | int) -> str:
    return f"{int(round(float(value))):,}ms"


def _json_for_script(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")


def _normalize_trace_ids(payload: dict[str, Any]) -> list[str]:
    raw_trace_ids = payload.get("sample_trace_ids") or payload.get("trace_ids") or []
    if not isinstance(raw_trace_ids, list):
        return []
    return [str(trace_id) for trace_id in raw_trace_ids[:8] if trace_id]


def _max_row(series: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    if not series:
        return None
    return max(series, key=lambda row: float(row.get(key) or 0))


def _service_rows(services: list[dict[str, Any]]) -> str:
    if not services:
        return '<div class="callout">No service breakdown was included in the input.</div>'
    max_traces = max((service["trace_count"] for service in services), default=1) or 1
    rows: list[str] = []
    for service in services:
        name = escape(str(service["name"]), quote=True)
        width = max(4, min(100, (service["trace_count"] / max_traces) * 100))
        rows.append(
            f"""<button class="service-row" type="button" data-service="{name}" aria-pressed="false">
            <span class="service-topline">
              <span class="service-name">{name}</span>
              <span class="service-meta">{_format_int(service["trace_count"])} traces</span>
            </span>
            <span class="bar" aria-hidden="true"><span style="width: {width:.1f}%"></span></span>
            <span class="service-meta">{_format_int(service["error_count"])} errors - p95 {_format_ms(service["p95_ms"])}</span>
          </button>"""
        )
    return "\n".join(rows)


def _findings(series: list[dict[str, Any]], services: list[dict[str, Any]]) -> str:
    if not series:
        return "<li>No activity rows were included in this report.</li>"

    peak_traces = _max_row(series, "trace_count")
    peak_errors = _max_row(series, "error_count")
    peak_p95 = _max_row(series, "p95_ms")
    rows = [
        (
            f"Highest trace volume was <strong>{_format_int(peak_traces['trace_count'])}</strong> "
            f"at <code>{escape(str(peak_traces['label']))}</code>."
        )
        if peak_traces
        else "No trace volume buckets were found.",
        (
            f"Most errors were <strong>{_format_int(peak_errors['error_count'])}</strong> "
            f"at <code>{escape(str(peak_errors['label']))}</code>."
        )
        if peak_errors
        else "No error buckets were found.",
        (
            f"Peak p95 latency was <strong>{_format_ms(peak_p95['p95_ms'])}</strong> "
            f"at <code>{escape(str(peak_p95['label']))}</code>."
        )
        if peak_p95
        else "No latency buckets were found.",
    ]
    if services:
        service = services[0]
        rows.append(
            f"Top service by volume was <code>{escape(str(service['name']))}</code> "
            f"with <strong>{_format_int(service['trace_count'])}</strong> traces."
        )
    return "\n".join(f"<li>{row}</li>" for row in rows)


def _trace_rows(trace_ids: list[str]) -> str:
    if not trace_ids:
        return "<li>No sample trace IDs were included. Add <code>sample_trace_ids</code> to the input to show examples.</li>"
    return "\n".join(f"<li><code>{escape(trace_id)}</code></li>" for trace_id in trace_ids)


def render_html(payload: dict[str, Any]) -> str:
    series = _normalize_series(payload)
    services = sorted(_normalize_services(payload), key=lambda row: row["trace_count"], reverse=True)
    trace_ids = _normalize_trace_ids(payload)
    total_traces = sum(row["trace_count"] for row in series)
    total_errors = sum(row["error_count"] for row in series)
    error_rate = (total_errors / total_traces * 100) if total_traces else 0
    peak_p95 = max((row["p95_ms"] for row in series), default=0)
    top_service = services[0]["name"] if services else "none"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = str(payload.get("title") or "Logfire activity report")
    window = str(payload.get("window") or "ad hoc")
    bucket = str(payload.get("bucket") or "bucket")

    report_data = {
        "series": series,
        "services": services,
        "trace_ids": trace_ids,
    }
    replacements = {
        "__PAGE_TITLE__": escape(title, quote=True),
        "__REPORT_TITLE__": escape(title),
        "__SUBTITLE__": "A lightweight local GUI report generated from Logfire query rows.",
        "__WINDOW__": escape(window),
        "__BUCKET__": escape(bucket),
        "__GENERATED__": escape(generated),
        "__TOTAL_TRACES__": _format_int(total_traces),
        "__TOTAL_ERRORS__": _format_int(total_errors),
        "__ERROR_RATE__": _format_percent(error_rate),
        "__PEAK_P95__": _format_ms(peak_p95),
        "__TOP_SERVICE__": escape(str(top_service)),
        "__BUCKET_COUNT__": _format_int(len(series)),
        "__SERVICE_ROWS__": _service_rows(services),
        "__FINDINGS__": _findings(series, services),
        "__TRACE_ROWS__": _trace_rows(trace_ids),
        "__DATA_JSON__": _json_for_script(report_data),
    }
    html = HTML_TEMPLATE
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a local Logfire activity HTML report.")
    parser.add_argument("--input", type=Path, help="JSON input file. Omit to render bundled sample data.")
    parser.add_argument("--values", help="Comma-separated trace counts for a quick chart smoke test.")
    parser.add_argument("--output", type=Path, required=True, help="HTML output path.")
    parser.add_argument("--title", default="Logfire activity report", help="Title used with --values.")
    parser.add_argument("--window", default="ad hoc", help="Window label used with --values.")
    parser.add_argument("--bucket", default="bucket", help="Bucket label used with --values.")
    parser.add_argument("--print-path", action="store_true", help="Print the absolute report path.")
    args = parser.parse_args()

    if args.values and args.input:
        parser.error("Use either --input or --values, not both.")

    payload = _payload_from_values(args.values, args.title, args.window, args.bucket) if args.values else _load_payload(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(payload))
    if args.print_path:
        print(args.output.resolve())


if __name__ == "__main__":
    main()
