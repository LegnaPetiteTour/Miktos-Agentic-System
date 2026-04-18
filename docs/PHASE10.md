# Phase 10 Spec — Web Cockpit (Local Operator Surface)

**Branch:** `phase-10/web-cockpit`
**Core principle:** The web layer is a surface over the existing system.
It reads existing state. It triggers existing capabilities.
It does not duplicate orchestration logic.

---

## What Phase 10 Is

Phase 10 replaces the `rich` terminal cockpit with a browser tab.
The underlying system — engine, coordinator, workers, message bus,
Pearl client, OBS monitor — is unchanged.

This is not "build a website." It is:

> The first operator-facing control surface — a browser cockpit
> that reads what Miktos already knows and triggers what Miktos
> already knows how to do.

The terminal remains as a fallback. The browser becomes the
operator's standing production surface.

---

## What It Is Not (first pass)

- Not remote access
- Not authentication
- Not multi-user
- Not cloud deployment
- Not subprocess control from the browser
- Not a replacement for OBS, Zoom, or Pearl Admin entirely
- Not a React/Vue/Svelte SPA with a build pipeline

Those belong to Phase 10b, 10c, or later.

---

## Architecture Decisions (confirmed)

### Q1 — Session launcher

**`run_session.py` stays as the session launcher (Option A).**

The browser is the monitoring and control surface.
The terminal remains the bootstrapping layer.
This preserves the current working path and reduces risk
while the web layer is new. A "Start Session" button
belongs to Phase 10b, after the dashboard is stable.

### Q2 — Web server lifecycle

**Operator runs `python web/server.py` separately (Option B).**

The web server is a separate process, started independently.
It stays open across sessions. It can be restarted without
affecting a running session. Cleaner failure isolation.
An optional `run_session.py --with-web` convenience flag
belong to Phase 10b.

### Q3 — Session history

**Named sessions only, most recent 20 by default.**

Filters out hex-UUID test/dev sessions automatically.
Fast and readable. Search and date filtering are later.

### Stack

**Backend: FastAPI (Python)**
Fits the existing Python stack. Serves both API and frontend.
No new runtime.

**Frontend: HTMX + minimal CSS**
No build pipeline. No JavaScript framework.
Server pushes state; HTMX updates the DOM.
Ideal for a local real-time monitoring dashboard.
Evolvable to React later if needed without touching the backend.

---

## Phase 10a — Local Operations Dashboard

### Objective

Three things done well:
1. Session setup — form-based `session_config.yaml` editor
2. Live cockpit — real-time health, alerts, Pearl layouts, pipeline
3. Session review — recent session history, inline report viewer

### File Structure

```
web/
  __init__.py
  server.py              ← FastAPI app entry point
  api/
    __init__.py
    session.py           ← /api/session/* endpoints
    status.py            ← /api/status/* endpoints (SSE stream)
    pearl.py             ← /api/pearl/* endpoints
  templates/
    base.html            ← shared layout, nav, CSS vars
    index.html           ← live cockpit (main view)
    setup.html           ← session config form
    sessions.html        ← session history list
    report.html          ← inline session report viewer
  static/
    style.css            ← minimal CSS, design tokens from Phase 9

tests/
  test_phase_10a_web.py  ← ~8 tests
```

---

### `web/server.py` — entry point

```bash
# Start the web cockpit (separate terminal, before or after run_session.py)
cd "/Users/atorrella/Desktop/Miktos Agentic System"
.venv/bin/python web/server.py

# Then open: http://localhost:8000
```

FastAPI mounts the HTMX templates and the REST API.
Dependency: `fastapi`, `uvicorn`, `jinja2` (already in Python ecosystem,
none specific to the frontend).

---

### API Endpoints

**Session config**
```
GET  /api/session/config
     → Returns parsed session_config.yaml as JSON

POST /api/session/config
     Body: updated config fields
     → Validates required fields, writes session_config.yaml
     → Returns {success, errors[]}
```

**Live status (Server-Sent Events)**
```
GET  /api/status/stream
     → SSE stream, pushes updates every second
     → Reads: message.log (last event), data/sessions/ (latest named),
             layout_log.jsonl (Pearl layouts)
     → Payload: {hardware, stream_state, tick, alerts,
                 pearl_layouts, pipeline_slots, elapsed}
```

SSE is the right choice over polling: the server pushes updates,
no repeated HTTP requests from the browser, low overhead,
works natively with HTMX's `hx-ext="sse"`.

**Pearl control**
```
GET  /api/pearl/layouts/{channel_id}
     → Returns layout list for a channel (wraps PearlClient.get_layouts)

POST /api/pearl/switch
     Body: {channel_id, layout_id}
     → Calls PearlClient.switch_layout
     → Appends to layout_log.jsonl (same as pearl_control.py)
     → Returns {success, layout_name}
```

**Session history**
```
GET  /api/sessions
     Query: ?limit=20&named_only=true
     → Returns list of named session folders, most recent first
     → Each entry: {name, date, hardware, exit_reason, has_report}

GET  /api/sessions/{session_name}/report
     → Returns the _report.html content for inline display
```

---

### Views

**`/` — Live Cockpit (index.html)**

The main view. Operator keeps this tab open during a stream.

Sections:
- **Hardware badge** — `Epiphan Pearl 192.168.2.45` or `OBS`,
  read from `session_config.yaml`
- **Stream state** — ARMED / STOPPED / DONE with elapsed timer
- **Health** — tick counter, alert level, last alert description
- **Pearl layouts** (epiphan only) — one row per channel,
  current layout name + **switch buttons** for available layouts
- **Pipeline** — Stages 1–4, per-slot status
  (pending / running / ✅ / ❌ / —)
- **Last session** — link to most recent session report

Updates via SSE — HTMX `hx-ext="sse"` swaps panel sections
as the server pushes state. No page reload.

**`/setup` — Session Setup (setup.html)**

Form fields mirroring `prepare_session.py` prompts:
- Hardware selector (radio: OBS / Epiphan)
- Event name (text, required)
- YouTube EN/FR video IDs (text)
- Pearl host, channel EN, channel FR (shown when Epiphan selected)

Submit writes `session_config.yaml` via `POST /api/session/config`.
Inline validation: required fields highlighted before save.

**`/sessions` — Session History (sessions.html)**

List of last 20 named sessions, most recent first.
Each row: date, event name, hardware icon, exit status badge,
"View Report" link.

**`/sessions/{name}` — Inline Report (report.html)**

The `_report.html` content rendered inside the dashboard layout.
No separate browser tab needed.

---

### State sources (read-only, no new writes)

| Data | Source | Already written by |
|---|---|---|
| Hardware, channels | `session_config.yaml` | `prepare_session.py` |
| Stream state, ticks, alerts | `data/messages/message.log` | `engine/messaging/bus.py` |
| Pearl layout state | `data/logs/layout_log.jsonl` | `pearl_control.py` (Phase 8b) |
| Pipeline slot status | `data/sessions/{latest}/` | `PostStreamCoordinator` |
| Session history | `data/sessions/` (named dirs) | `FileRenameWorker` |
| Session reports | `data/sessions/{name}/*_report.html` | `ReportWorker` |

The web layer reads all of these. It writes only:
- `session_config.yaml` (via setup form)
- `data/logs/layout_log.jsonl` (via Pearl switch API, same as CLI)

---

### Phase 10a Tests (`tests/test_phase_10a_web.py`)

~8 tests, FastAPI `TestClient`, no live Pearl or OBS required:

1. `test_config_read` — GET /api/session/config returns valid JSON
2. `test_config_write_valid` — POST with valid fields writes yaml, returns success
3. `test_config_write_invalid` — POST with missing required field returns error
4. `test_sessions_list` — GET /api/sessions returns named sessions only
5. `test_sessions_named_only` — hex-UUID folders excluded from results
6. `test_pearl_layouts_mock` — mock PearlClient, GET layouts returns list
7. `test_pearl_switch_mock` — mock PearlClient, POST switch returns success + appends log
8. `test_index_renders` — GET / returns 200 with expected panel sections

### Phase 10a Seal Criteria

- All tests pass, prior 108 tests unmodified, 1 permanent skip
- `python web/server.py` starts without error
- `http://localhost:8000` opens the cockpit in a browser
- Session setup form saves correctly to `session_config.yaml`
- Live cockpit updates when `run_session.py` is running alongside
- Pearl layout buttons appear (epiphan sessions) and call the API
- Session history shows named sessions, most recent first
- Session report renders inline

---

## Phase 10b — Session Launch from GUI

**Depends on:** Phase 10a stable in production.

- "Start Session" button in the cockpit
- Web server manages `run_session.py` subprocess
- Clean state transitions: idle → pre-flight → live → post-stream → done
- Fallback: terminal path preserved
- Optional: `run_session.py --with-web` auto-starts web server

---

## Phase 10c — Remote / Admin Expansion

**Depends on:** Phase 10b stable. Triggered by operational need.

- Authentication (operator login)
- Remote operator view (read-only, no controls)
- Optional deployment model (local network, not public internet)
- Stronger security model

Not scoped in detail. Requires a specific use case to justify the complexity.

---

## Dependencies

New packages needed (not currently in `pyproject.toml`):

```
fastapi>=0.111
uvicorn>=0.29
jinja2>=3.1      # template rendering
python-multipart>=0.0.9  # form parsing
```

HTMX is loaded from CDN in the HTML template — no npm, no build step.

---

## Architecture Invariant

The web layer must remain a surface, not a second system.

- Reads state that Miktos already writes
- Triggers capabilities that already exist (PearlClient, config files)
- Contains no orchestration logic
- Contains no domain knowledge
- Can be removed without affecting `run_session.py` or any other component

If any proposed web feature requires adding logic to `web/` that
does not already exist elsewhere in the system, stop and ask whether
the logic belongs in `web/` or in the existing domain layer.

---

*Spec written 2026-04-17.*
*Answers confirmed: Q1=Option A, Q2=Option B, Q3=named sessions last 20.*
*Stack confirmed: FastAPI + HTMX. No build pipeline.*
*10a/10b/10c sequencing confirmed.*
