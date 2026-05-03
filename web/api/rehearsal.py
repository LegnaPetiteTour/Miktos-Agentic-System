"""
web/api/rehearsal.py — /api/rehearsal/* endpoints.

GET  /api/rehearsal/state    → {"active": bool, "ts": str | null}
POST /api/rehearsal/start    → enable rehearsal mode
POST /api/rehearsal/stop     → disable rehearsal mode

When rehearsal mode is active the adapter registry substitutes
``RehearsalAdapter`` for all hardware calls, so every cockpit
panel works without live Pearl or OBS hardware.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import engine.rehearsal as rehearsal_mod
from engine.action_log import write_action

router = APIRouter()


@router.get("/state")
async def get_state() -> JSONResponse:
    """Return current rehearsal mode state."""
    return JSONResponse(rehearsal_mod.get_state())


@router.post("/start")
async def start_rehearsal() -> JSONResponse:
    """Enable rehearsal mode."""
    state = rehearsal_mod.activate()
    write_action("operator", "rehearsal_start", {}, "ok")
    return JSONResponse({"ok": True, **state})


@router.post("/stop")
async def stop_rehearsal() -> JSONResponse:
    """Disable rehearsal mode."""
    state = rehearsal_mod.deactivate()
    write_action("operator", "rehearsal_stop", {}, "ok")
    return JSONResponse({"ok": True, **state})
