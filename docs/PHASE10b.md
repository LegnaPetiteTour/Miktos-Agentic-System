# Phase 10b Spec — Session Launch from GUI

**Branch:** `phase-10b/session-launch`
**Depends on:** Phase 10a sealed (`0e4c392`)
**Core principle:** The web layer remains a surface. It starts the same
`run_session.py` the operator has always run. No new orchestration logic.

---

## Objective

Add a Start/Stop Session control to the web cockpit. The operator can
launch and stop a session entirely from the browser. The terminal path
(`python scripts/run_session.py`) is preserved as a fallback and
continues to work unchanged.

---

## Process Architecture

```
web server (FastAPI/uvicorn)
  └─ run_session.py         ← started by POST /api/session/start
       ├─ main_post_stream.py  (start_new_session=True, independent)
       └─ main_epiphan.py      (subprocess.run, blocks until Ctrl+C)
            or main_streamlab.py
```

When the operator clicks Stop, the web server sends SIGINT to
`run_session.py`. This triggers the exact same shutdown path as
pressing Ctrl+C in the terminal: the monitor stops, the pipeline
finishes, the session folder is written. Clean exit.

**Note:** `start_new_session=True` is NOT used here. The web server
needs to own the `run_session.py` lifecycle. `main_post_stream.py`
still uses it (as before) because it must survive a Ctrl+C.

---

## State Machine

```
idle  ── Start clicked ──►  running
                              │
              recording_stopped event ▼
                           pipeline
                              │
              process exits ▼
                            idle
```

Four states:
- `idle` — no session running, Start button active
- `running` — `run_session.py` process alive, Stop button active
- `pipeline` — monitor stopped, pipeline finishing (Stop disabled)
- `done` — process exited cleanly, transitions to `idle` after 3s

State is derived from the live process object, not from files.
The SSE stream already handles showing what’s happening inside
the session (ticks, alerts, pipeline slots).

---

## New Files

### `web/api/runner.py`

The only new module. Owns the subprocess lifecycle.

```python
# Responsibilities:
# - Store the Popen object in a module-level singleton
# - POST /api/session/start  → launch run_session.py
# - POST /api/session/stop   → send SIGINT to run_session.py
# - GET  /api/session/runner → {running, pid, state, exit_code}
```

Rules:
- If a process is already running, `start` returns 409 Conflict
- `stop` sends `signal.SIGINT` (not SIGTERM — SIGINT triggers
  the clean shutdown path in run_session.py)
- Process exit is detected by `proc.poll()` on every `runner` poll
- Module-level singleton is safe here — uvicorn runs a single
  worker process in local mode

### Modified: `web/api/status.py`

Extend the SSE payload with `session_running: bool` and `session_pid:
int | null`. The cockpit JS uses this to show/hide the Start/Stop
button without a separate API call.

### Modified: `web/templates/index.html`

Add a control row below the Hardware panel:

```
[ Start Session ]     ← shown when idle
[ Stop Session  ]     ← shown when running
[ Finishing…    ]     ← shown when pipeline running (disabled)
```

Button clicks POST to `/api/session/start` or `/api/session/stop`
via plain `fetch()`. No full page reload.

---

## API Endpoints

```
POST /api/session/start
  → Launches run_session.py as subprocess
  → Returns {success, pid} or {error} with 409 if already running

POST /api/session/stop
  → Sends SIGINT to run_session.py
  → Returns {success} or {error} if not running

GET  /api/session/runner
  → Returns {running: bool, pid: int|null, state: str, exit_code: int|null}
```

The existing `GET /api/session/config` and `POST /api/session/config`
are unchanged. `runner.py` is included in `server.py` alongside the
existing routers.

---

## Safety Rules

1. **Cannot start if already running** — 409 returned, button disabled
2. **Stop sends SIGINT, not SIGTERM** — preserves the clean shutdown
   path that lets the pipeline finish
3. **Terminal path unchanged** — `run_session.py` can still be started
   from the terminal. The web cockpit will not have a process reference
   in that case, but the SSE stream still reflects session state from
   `message.log`. The Start button is the web-native path.
4. **Reload mode caveat** — uvicorn `reload=True` restarts the server
   process on file changes, which would orphan a running session subprocess.
   In production use (during a live event), the operator should not be
   editing files. This is acceptable for the local-first use case.

---

## Modified: `web/server.py`

Add `runner` router:
```python
from web.api import pearl, runner, session, status
app.include_router(runner.router, prefix="/api/session")
```

`runner.router` adds `/start`, `/stop`, `/runner` under `/api/session/`.
Existing `/api/session/config` endpoints are unchanged.

---

## Tests (`tests/test_phase_10b_runner.py`)

~6 tests, FastAPI TestClient, mock subprocess:

1. `test_start_launches_process` — POST /start → Popen called, pid returned
2. `test_start_conflict` — POST /start when running → 409 returned
3. `test_stop_sends_sigint` — POST /stop → SIGINT sent to process
4. `test_stop_not_running` — POST /stop when idle → error returned
5. `test_runner_state_idle` — GET /runner when no process → {running: false}
6. `test_runner_state_running` — GET /runner with live process → {running: true, pid}

**Prior tests unmodified. Target: 116 + ~6 = ~122 passed, 1 skip.**

---

## Seal Criteria

- All tests pass, 116 prior tests unmodified
- `POST /api/session/start` launches `run_session.py` visibly in the terminal
- Start button in cockpit triggers a real session (pre-flight runs, monitor starts)
- Stop button sends SIGINT, session closes cleanly, pipeline finishes
- Terminal path (`python scripts/run_session.py`) still works independently
- Browser reflects session state changes via existing SSE stream

---

## What Does Not Change

- `run_session.py` — not modified
- `main_post_stream.py` — not modified
- `main_epiphan.py` / `main_streamlab.py` — not modified
- Engine, coordinator, workers — not modified
- All Phase 10a endpoints — not modified
- Architecture invariant — web layer adds no orchestration logic

---

*Spec written 2026-04-18.*
*Branch: `phase-10b/session-launch` from `main` at `0e4c392`.*
