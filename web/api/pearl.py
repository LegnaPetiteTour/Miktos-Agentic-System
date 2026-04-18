"""
web/api/pearl.py — /api/pearl/* endpoints.

GET  /api/pearl/layouts/{channel_id}  → layout list (wraps PearlClient)
POST /api/pearl/switch                → switches layout + appends layout_log.jsonl
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests as _requests
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from domains.epiphan.tools.pearl_client import PearlClient

router = APIRouter()

_LAYOUT_LOG = Path("data/logs/layout_log.jsonl")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/layouts/{channel_id}")
async def get_layouts(channel_id: str) -> JSONResponse:
    try:
        client = PearlClient()
        layouts = client.get_layouts(channel_id)
        try:
            active = client.get_active_layout(channel_id)
        except _requests.RequestException:
            active = {}
        return JSONResponse({"layouts": layouts, "active": active})
    except _requests.RequestException as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


class SwitchRequest(BaseModel):
    channel_id: str
    layout_id: str


@router.post("/switch")
async def switch_layout(body: SwitchRequest) -> JSONResponse:
    try:
        client = PearlClient()
        client.switch_layout(body.channel_id, body.layout_id)

        # Resolve layout name for the log entry
        layout_name = body.layout_id
        try:
            layouts = client.get_layouts(body.channel_id)
            for lay in layouts:
                if str(lay.get("id")) == str(body.layout_id):
                    layout_name = lay.get("name", body.layout_id)
                    break
        except _requests.RequestException:
            pass

        # Append to layout_log.jsonl (same format as pearl_control.py)
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "channel": body.channel_id,
            "layout_id": body.layout_id,
            "layout_name": layout_name,
        }
        _LAYOUT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _LAYOUT_LOG.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")

        return JSONResponse({"success": True, "layout_name": layout_name})
    except _requests.RequestException as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=503)
