"""
web/api/templates.py — /api/templates/* endpoints.

GET /api/templates                → list all available show templates
GET /api/templates/{name}         → get full template data (including cues)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

import engine.runofshow as ros

router = APIRouter()


@router.get("")
async def list_templates() -> JSONResponse:
    """Return a list of all available show templates (id, name, description, cue_count)."""
    templates = ros.list_templates()
    return JSONResponse({"templates": templates})


@router.get("/{template_name}")
async def get_template(template_name: str) -> JSONResponse:
    """Return full template data including the cue list."""
    try:
        data = ros.get_template(template_name)
        return JSONResponse(data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
