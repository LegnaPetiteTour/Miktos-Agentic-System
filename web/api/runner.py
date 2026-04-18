"""
web/api/runner.py — /api/session/start, /api/session/stop, /api/session/runner

Owns the run_session.py subprocess lifecycle.

Module-level singleton: safe because uvicorn runs a single worker
process in local mode.

Endpoints (all registered under /api/session in server.py):
  POST /api/session/start  → launch run_session.py
  POST /api/session/stop   → send SIGINT to run_session.py
  GET  /api/session/runner → {running, pid, state, exit_code}

Stop MUST send SIGINT, not SIGTERM.  SIGINT is what Ctrl+C sends,
which triggers the clean shutdown path in run_session.py (monitor
stops → pipeline finishes → session folder written).  SIGTERM skips
that and leaves an empty session folder.
"""

import signal
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level subprocess singleton
# ---------------------------------------------------------------------------

_proc: subprocess.Popen | None = None

_SCRIPT = Path("scripts/run_session.py")


def _poll_proc() -> subprocess.Popen | None:
    """Return the live process, or None if it has exited."""
    global _proc
    if _proc is not None and _proc.poll() is not None:
        _proc = None
    return _proc


def get_runner_state() -> dict:
    """Return the current runner state dict (also used by status.py SSE)."""
    proc = _poll_proc()
    if proc is None:
        return {"running": False, "pid": None, "state": "idle", "exit_code": None}
    rc = proc.poll()
    if rc is None:
        return {"running": True, "pid": proc.pid, "state": "running", "exit_code": None}
    return {"running": False, "pid": None, "state": "idle", "exit_code": rc}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/start")
async def start_session() -> JSONResponse:
    global _proc
    proc = _poll_proc()
    if proc is not None:
        return JSONResponse(
            {"success": False, "error": "Session already running", "pid": proc.pid},
            status_code=409,
        )

    _proc = subprocess.Popen(
        [sys.executable, str(_SCRIPT)],
        cwd=str(Path(_SCRIPT).parent.parent),
    )
    return JSONResponse({"success": True, "pid": _proc.pid})


@router.post("/stop")
async def stop_session() -> JSONResponse:
    proc = _poll_proc()
    if proc is None:
        return JSONResponse(
            {"success": False, "error": "No session is running"},
            status_code=400,
        )
    proc.send_signal(signal.SIGINT)
    return JSONResponse({"success": True})


@router.get("/runner")
async def runner_state() -> JSONResponse:
    return JSONResponse(get_runner_state())
