"""
web/api/action_log.py — /api/action_log/* endpoints.

GET  /api/action_log/recent          → last N action log entries
POST /api/action_log/entry           → write a manual action log entry
GET  /api/adapters/capabilities      → registered adapter capabilities
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from engine.action_log import read_recent, write_action

router = APIRouter()


class ActionEntryBody(BaseModel):
    actor: str = "operator"
    action: str
    payload: dict = {}
    result: str = "ok"


@router.get("/recent")
async def get_recent(limit: int = 20) -> JSONResponse:
    """Return the most recent *limit* action log entries."""
    entries = read_recent(min(limit, 200))
    return JSONResponse({"entries": entries})


@router.post("/entry")
async def post_entry(body: ActionEntryBody) -> JSONResponse:
    """Write a manual action log entry."""
    entry = write_action(body.actor, body.action, body.payload, body.result)
    return JSONResponse({"ok": True, "entry": entry})
