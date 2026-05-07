"""
web/api/pearl.py — /api/pearl/* endpoints.

GET  /api/pearl/channels              → all Pearl channels (auto-discovery)
GET  /api/pearl/channels/{id}/info    → single channel metadata
GET  /api/pearl/inputs                → all Pearl inputs (auto-discovery)
GET  /api/pearl/layouts/{channel_id}  → layout list (wraps PearlClient)
POST /api/pearl/switch                → switches layout + appends layout_log.jsonl
POST /api/pearl/assign                → assign channel to EN or FR role in session config
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests as _requests
import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from domains.epiphan.tools.pearl_client import PearlClient
from engine.paths import get_config_dir, get_data_dir

router = APIRouter()

_LAYOUT_LOG = get_data_dir() / "logs" / "layout_log.jsonl"
_CONFIG_PATH = get_config_dir() / "session_config.yaml"


def _read_config() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open("r") as fh:
        return yaml.safe_load(fh) or {}


def _write_config(data: dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _CONFIG_PATH.open("w") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Discovery endpoints
# ---------------------------------------------------------------------------


@router.get("/channels")
async def get_all_channels() -> JSONResponse:
    """
    Return all Pearl channels discovered live from the device.

    Each channel includes id, name, and current EN/FR role assignment
    from session_config.yaml so the UI can highlight which channels
    are already assigned.
    """
    try:
        client = PearlClient()
        channels = client.get_channels()
        cfg = _read_config()
        pearl_cfg = cfg.get("pearl", {})
        en_id = str(pearl_cfg.get("channel_en", ""))
        fr_id = str(pearl_cfg.get("channel_fr", ""))
        for ch in channels:
            ch_id = str(ch.get("id", ""))
            if ch_id == en_id:
                ch["role"] = "en"
            elif ch_id == fr_id:
                ch["role"] = "fr"
            else:
                ch["role"] = None
        return JSONResponse({"channels": channels, "channel_en": en_id, "channel_fr": fr_id})
    except _requests.RequestException as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/channels/{channel_id}/info")
async def get_channel_info(channel_id: str) -> JSONResponse:
    """Return full metadata for a single Pearl channel."""
    try:
        client = PearlClient()
        info = client.get_channel_info(channel_id)
        return JSONResponse({"channel": info})
    except _requests.RequestException as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/inputs")
async def get_all_inputs() -> JSONResponse:
    """
    Return all Pearl inputs discovered live from the device.
    Includes HDMI, SDI, NDI, SRT, USB, Audio, and overlay inputs.
    """
    try:
        client = PearlClient()
        inputs = client.get_inputs()
        return JSONResponse({"inputs": inputs})
    except _requests.RequestException as exc:
        # Pearl may return 404 if firmware doesn't support /api/inputs
        return JSONResponse({"error": str(exc), "inputs": []}, status_code=200)


# ---------------------------------------------------------------------------
# Channel role assignment
# ---------------------------------------------------------------------------


class AssignRequest(BaseModel):
    channel_id: str
    role: str  # "en" or "fr"


@router.post("/assign")
async def assign_channel(body: AssignRequest) -> JSONResponse:
    """
    Assign a Pearl channel to the EN or FR role in session_config.yaml.
    Validates that the channel exists before writing.
    """
    if body.role not in ("en", "fr"):
        return JSONResponse({"success": False, "error": "role must be 'en' or 'fr'"}, status_code=422)
    try:
        client = PearlClient()
        channels = client.get_channels()
        ids = [str(ch.get("id", "")) for ch in channels]
        if str(body.channel_id) not in ids:
            return JSONResponse(
                {"success": False, "error": f"Channel {body.channel_id} not found on Pearl"},
                status_code=404,
            )
        cfg = _read_config()
        if "pearl" not in cfg:
            cfg["pearl"] = {}
        key = "channel_en" if body.role == "en" else "channel_fr"
        cfg["pearl"][key] = int(body.channel_id)
        _write_config(cfg)
        return JSONResponse({"success": True, "role": body.role, "channel_id": body.channel_id})
    except _requests.RequestException as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=503)


# ---------------------------------------------------------------------------
# Layout endpoints
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

        # Append to layout_log.jsonl
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
