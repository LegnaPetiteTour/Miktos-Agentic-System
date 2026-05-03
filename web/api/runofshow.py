"""
web/api/runofshow.py — /api/runofshow/* endpoints.

GET  /api/runofshow/show           → current show state + active/next cue
POST /api/runofshow/load           → load a named template, reset position
POST /api/runofshow/advance        → move to next cue
POST /api/runofshow/jump/{cue_id} → jump to a specific cue by id
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import engine.runofshow as ros

router = APIRouter()


class LoadBody(BaseModel):
    template: str


@router.get("/show")
async def get_show() -> JSONResponse:
    """Return current run-of-show state including active and next cue."""
    return JSONResponse(ros.get_state())


@router.post("/load")
async def load_show(body: LoadBody) -> JSONResponse:
    """Load a template and reset position to cue 0."""
    try:
        state = ros.load_template(body.template)
        return JSONResponse({"ok": True, **state})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/advance")
async def advance_cue() -> JSONResponse:
    """Advance to the next cue.  Returns updated state."""
    state = ros.advance()
    return JSONResponse({"ok": True, **state})


@router.post("/jump/{cue_id}")
async def jump_to_cue(cue_id: str) -> JSONResponse:
    """Jump to a specific cue by id.  Returns updated state."""
    state = ros.jump_to(cue_id)
    return JSONResponse({"ok": True, **state})
