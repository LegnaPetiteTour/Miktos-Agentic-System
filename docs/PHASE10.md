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

This is not “build a website.” It is:

> The first operator-facing control surface — a browser cockpit
> that reads what Miktos already knows and triggers what Miktos
> already knows how to do.

The terminal remains as a fallback. The browser becomes the
operator’s standing production surface.

---

## Architecture Decisions (confirmed)

| Decision | Choice |
|---|---|
| Session launcher | `run_session.py` stays (Option A) |
| Web server lifecycle | Separate process, Option B |
| Session history | Named sessions only, last 20 |
| Backend | FastAPI + uvicorn + jinja2 |
| Frontend | HTMX + minimal CSS, no build step |

---

## Phase 10a — Local Operations Dashboard ✅ COMPLETE

**Completed:** 2026-04-17
**Commit:** `6f5230e`
**Tests:** 116 passed, 1 permanent skip

### What was built

**`web/` directory:**

```
web/
  __init__.py
  server.py              ← FastAPI app, mounts static+templates, 4 HTML views
  api/
    __init__.py
    session.py           ← GET/POST /api/session/config, GET /api/sessions, GET /api/sessions/{name}/report
    status.py            ← GET /api/status/stream — SSE 1-second push
    pearl.py             ← GET /api/pearl/layouts/{cid}, POST /api/pearl/switch
  templates/
    base.html, index.html, setup.html, sessions.html, report.html
  static/
    style.css            ← dark terminal palette matching Phase 9
tests/
  test_phase_10a_web.py  ← 8 tests → 116 total passed, 1 skipped
```

**SSE stream payload (1-second push):**
```json
{
  "hardware": "epiphan",
  "stream_state": "stopped",
  "tick": 42,
  "alerts": [],
  "pearl_layouts": [{"channel": "2", "layout_name": "Speaker View"}],
  "pipeline_slots": ["..._EN", "...mp3", "...report.html"],
  "elapsed": "00:08"
}
```

**State sources (read-only):**

| Data | Source |
|---|---|
| Hardware, channels | `session_config.yaml` |
| Stream state, ticks | `data/messages/message.log` |
| Pearl layout state | `data/logs/layout_log.jsonl` |
| Pipeline / session history | `data/sessions/` |

**Fix applied:** Starlette 1.0.0 changed `TemplateResponse` to pass
context as Jinja2 globals (LRU cache key unhashable in Python 3.14).
Updated all calls to `request=` keyword style.

**Launch:**
```bash
cd "/Users/atorrella/Desktop/Miktos Agentic System"
.venv/bin/python web/server.py
# Open: http://localhost:8000
```

**Architecture invariant confirmed:** `web/` contains no orchestration
logic. Can be removed without affecting `run_session.py`.

---

## Phase 10b — Session Launch from GUI

Pending Phase 10a stable in production.
- “Start Session” button in the cockpit
- Web server manages `run_session.py` subprocess
- Clean state transitions: idle → pre-flight → live → post-stream → done
- Fallback terminal path preserved

---

## Phase 10c — Remote / Admin Expansion

Pending specific operational need.
- Authentication, remote operator view, optional deployment model.

---

*Phase 10a sealed 2026-04-17 at 6f5230e, 116 passed.*
