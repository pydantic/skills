---
name: logfire-ui
description: Open or return Logfire project pages, live views, trace links, and Explore pages in the Codex browser without querying telemetry first. Use this skill when the user asks to "open in Logfire", "show in the live view", "open Explore", "open the UI", "show in Codex", "use the browser", "give me a link", or asks for a Logfire GUI/browser/live-view presentation of a project, time range, service, span, trace, log, or filter. If "show" or "view" wording is ambiguous, ask whether the user wants a UI view or query analysis.
---

# Open Logfire UI

Use this skill for direct Logfire UI, browser, live-view, link, and Explore-page requests.

## User-Facing Progress

Keep progress updates quiet. Do not narrate why this skill was selected, restate routing rules, quote local instructions, explain token scope, or announce routine helper calls. If an update is needed, use one short sentence focused on the action, such as "Opening Logfire with the error filter."

After opening Logfire, do not run or narrate an extra page-state check unless the browser appears stuck, asks for login, or the user explicitly asked you to verify the page.

## Browser Targeting

In Codex Desktop, use the Browser plugin's Codex in-app browser (`iab`) and the currently selected tab whenever possible.

Browser access is indirect: do not expect a browser-named MCP tool. If the Browser plugin is listed as available, load the `browser:browser` skill and use its Node REPL `js` / `mcp__node_repl__js` bootstrap to bind `agent.browsers.get("iab")`. If `js` is not visible, use tool discovery for `node_repl js` before declaring the in-app browser unavailable.

Do not use `agent-browser`, `chrome-devtools`, `mcp__chrome_devtools__*`, `mcp__playwright__*`, macOS `open`, `xdg-open`, standalone Playwright/Chromium, a shell-launched browser, web preview cards, or a newly created external browser window unless the user explicitly asks for an external browser. Do not create a new in-app tab when a Logfire live view is already selected and can be updated in place.

Only report the in-app browser unavailable after the Browser plugin is not listed or its skill cannot be loaded, the Node REPL `js` execution tool is unavailable after tool discovery, or the Browser skill bootstrap fails before navigation starts. Then return the clean Logfire URL and explain that the in-app browser could not be controlled. Treat `chrome-devtools`, Playwright MCP, standalone Playwright, and web preview cards as "Browser unavailable", not as fallbacks. Do not silently fall back to any external or dedicated browser window.

## Core Rule

For project-level or aggregate UI requests, open or return Logfire directly by URL.

Do not query telemetry first:
- Do not call `query_run`.
- Do not say you will query Logfire or fetch spans first.

Only query first when the user asks to open a specific unknown item that must be found first, such as "open the slowest trace" or "open the latest error trace".

If the request is ambiguous, such as "show recent errors" or "view logs", ask whether the user wants Logfire opened in the UI or a query analysis in chat. Do not do both unless the user explicitly asks for both.

## Project Discovery

For UI requests without an explicit organization/project, first try to resolve the canonical project URL through Logfire MCP auth/current-project metadata. Use a project-link or current-project helper if the available MCP server exposes one. This is project discovery, not telemetry querying.

If the MCP can resolve exactly one current project, use that project URL. If it cannot resolve a project, resolves multiple candidates, or returns an auth/error state, ask the user for the organization/project or full Logfire project URL.

Do not infer the project URL from `LOGFIRE_BASE_URL`, `LOGFIRE_URL`, exporter config, repository names, or localhost reachability. Env/config values can identify the Logfire platform/API base, but they do not by themselves identify the target organization/project.

## URL Workflow

1. If the full project URL is already known, use it directly.
2. If the user omits the project, resolve the current project through MCP as described above.
3. If the user gives a project name but not the organization/base URL, call `project_logfire_ui_link(project=project)` with the default clean-link behavior to derive the canonical project URL. This is a URL discovery helper, not a telemetry query.
4. For project live-view/filter URLs, call `project_logfire_ui_link(project=project, query=query, since=since, until=until, handoff=True)` when opening the link immediately in Codex Browser. Use the default clean-link behavior when returning a durable or shareable URL. If the user provides an existing clean Logfire project URL and asks for handoff, parse its project, `q`, `since`, and `until` values and pass them through this tool.
5. If the user gives or the query workflow has already found a real `trace_id`, call `project_logfire_link(trace_id=trace_id, project=project, handoff=True)` when opening the link immediately in Codex Browser. Use the default clean-link behavior when returning a durable or shareable URL.
6. Add `query`, `since`, and `until` through `project_logfire_ui_link` when useful. If manually assembling a clean URL, URL-encode `q`, `since`, and `until`.
7. If the user asked to open the URL and Browser is available, open it in the Codex in-app browser. Otherwise, return the URL rather than launching an external browser.

## Already-Open Live View Control

If a Logfire project live view is already open in Codex Browser, use the JSON command bridge. This is the only supported in-app interaction model because it updates the view without a full document reload and shows the user that the agent is actively changing the page.

Do not try to use page-global JavaScript APIs from Codex Browser. The only supported agent control surface is the JSON command input.

For Codex Browser / `iab`, fill the `Logfire live view agent command` input with a JSON patch such as `{"q":"level='error'","last":"1h","since":null,"until":null}` and press Enter. The hidden submit button is only a form target; do not skip this path just because the button is not visibly clickable.

Use direct URL/search-param updates only when the bridge form input is not present or cannot be submitted. Do not update the URL directly when the bridge form is available.

When using the direct URL fallback and the browser control surface permits page-script URL updates, update `window.history` and dispatch a `popstate` event. Use `pushState` for meaningful user-visible navigation and `replaceState` for cleanup or retries. If in-page URL updates are unavailable, fall back to opening the clean URL.

Do not mutate an `/api/auth/handoff?ticket=...` URL. Handoff URLs are single-use entry points only; after the redirect, control the final clean project URL.

Live view search parameters:

- `q`: SQL-like Logfire filter expression, for example `level='error'`, `kind='span'`, or `service_name='api'`. URL-encode this when constructing a URL string.
- `last`: rolling live window, such as `5m`, `1h`, `14d`, or a millisecond number. Use this for live mode and remove `since`/`until`.
- `since` and `until`: fixed historical window as ISO 8601 timestamps. Use these for a bounded time range and remove `last`.
- `env`: deployment environment filter. Use repeated `env` parameters for multiple environments. Omit it for all environments.
- `traceId` and `spanId`: focus a specific trace/span when known. Clear stale focus parameters such as `traceId`, `spanId`, `focusTraceId`, and `focusTraceTimestamp` when changing the main query or time range unless the user asked to preserve the focused record.

## Browser Handoff URLs

When the MCP link tools support `handoff: bool = False`, use `handoff=True` only for a URL that will be opened immediately in the browser. A handoff URL is short-lived, single-use, and bound to the destination minted by the platform.

- If the handoff result is a string, open that exact URL promptly. It may be an `/api/auth/handoff?ticket=...` URL. Do not add query params to it, rewrite it, persist it, quote it in docs, or treat it as shareable.
- If the handoff result is an object with `handoff: false`, use its `url` value as the clean fallback URL. Mention `reason` only when it helps the user understand why the browser may still ask for login, such as API-key auth or a need to re-authenticate.
- If the reason says to re-authenticate the Logfire MCP connection, explain that the MCP OAuth refresh token is missing the metadata needed to mint a UI session. Do not describe this as a browser-session refresh; the user needs to reconnect/re-authenticate the Logfire MCP auth flow.
- If the available MCP server does not expose `handoff`, call the link tool normally and use the clean URL.
- Do not manually append filters or time params to a handoff URL. Put the final project filter destination into `project_logfire_ui_link` and let the platform mint the ticket for that destination.

## Codex Browser Open Stability

When opening a Logfire handoff URL in Codex Browser, keep the durable clean URL for the same destination as a fallback. If needed, call the same link tool with `handoff=False` before reporting a browser-open failure.

Use the Browser skill's in-app browser workflow and bound the navigation attempt. Do not wait for `networkidle`, websocket completion, or a fully quiet live-view page. If waiting after navigation, wait only for URL commit, the final clean project URL, or a visible Logfire page signal.

If the browser remains on a grey `about:blank` screen or the browser navigation call times out, stop waiting and return the clean URL. Describe this as the browser open stalling before navigation, not as a Logfire auth failure. Do not expose the consumed or expired handoff URL.

Do not recover from Codex Browser stalls by launching a separate browser window. Return the clean URL unless the user explicitly asks you to try an external browser.

## Common Filters

- Spans: `q=kind%3D%27span%27`
- Logs: `q=kind%3D%27log%27`
- Exceptions: `q=is_exception%3Dtrue`
- Errors: `q=level%3D%27error%27`
- Service: URL-encode a filter such as `service_name='api'`

## Example

For "open the Logfire live view for spans in starter-project for the last hour in Codex":

1. Open the known or derived `starter-project` Logfire URL directly.
2. Add `q=kind%3D%27span%27`.
3. Add `since=<one-hour-ago>` and `until=<now>`.
4. Open the URL in Codex Browser.
5. Do not run SQL first.

For "find the slowest trace and open it", use the query workflow only to identify the trace, then use `project_logfire_link(trace_id=trace_id, project=project, handoff=True)` and open that link.

For "change the open live view to the last hour of errors", submit `{"q":"level='error'","last":"1h","since":null,"until":null}` through the `Logfire live view agent command` input; do not mint a new handoff URL.

## Auth Boundary

Do not try to pass MCP auth tokens into the browser or Logfire UI. Never put bearer, API, read, or write tokens in URL query parameters, fragments, pasted browser instructions, logs, or notes. MCP/tool authentication and browser web sessions are separate security contexts.

For immediately opened UI links, prefer the platform handoff described above. If handoff is unavailable, fall back to the clean URL and explain the specific fallback reason when useful. A missing browser cookie may require normal browser login; a stale MCP OAuth connection requires MCP re-authentication instead.
