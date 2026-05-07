"""
web/api/switcher.py — /api/switcher/* endpoints.

GET  /api/switcher/obs/scenes              → list OBS scenes + current program scene
GET  /api/switcher/obs/sources/{scene}     → list sources for a specific OBS scene
POST /api/switcher/obs/switch              → set current OBS program scene
GET  /api/switcher/pearl/channels          → list all Pearl channels (auto-discovery)
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _obs_client():  # type: ignore[return]
    """Return a connected obsws_python.ReqClient using env vars."""
    import obsws_python as obs  # type: ignore[import-untyped]

    return obs.ReqClient(
        host=os.getenv("OBS_HOST", "localhost"),
        port=int(os.getenv("OBS_PORT", "4455")),
        password=os.getenv("OBS_PASSWORD", ""),
        timeout=5,
    )


# ---------------------------------------------------------------------------
# OBS — scenes
# ---------------------------------------------------------------------------


@router.get("/obs/scenes")
async def list_obs_scenes() -> JSONResponse:
    """Return all OBS scene names and the current program scene."""
    try:
        cl = _obs_client()
        resp = cl.get_scene_list()
        current: str = resp.current_program_scene_name
        scenes: list[str] = [s["sceneName"] for s in (resp.scenes or [])]
        cl.disconnect()
        return JSONResponse({"scenes": scenes, "current": current})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


# ---------------------------------------------------------------------------
# OBS — sources per scene (auto-discovery)
# ---------------------------------------------------------------------------


@router.get("/obs/sources/{scene_name:path}")
async def list_obs_sources(scene_name: str) -> JSONResponse:
    """
    Return all sources (inputs) for a specific OBS scene.

    Each source includes: id, name, type, enabled.
    This allows the cockpit to display what inputs are in each scene
    without requiring manual configuration.
    """
    try:
        cl = _obs_client()
        resp = cl.get_scene_item_list(scene_name)
        sources = [
            {
                "id": item.get("sceneItemId"),
                "name": item.get("sourceName"),
                "type": item.get("inputKind", item.get("sourceType", "unknown")),
                "enabled": item.get("sceneItemEnabled", True),
            }
            for item in (resp.scene_items or [])
        ]
        cl.disconnect()
        return JSONResponse({"scene": scene_name, "sources": sources})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


# ---------------------------------------------------------------------------
# OBS — switch scene
# ---------------------------------------------------------------------------


class SwitchSceneBody(BaseModel):
    scene_name: str


@router.post("/obs/switch")
async def switch_obs_scene(body: SwitchSceneBody) -> JSONResponse:
    """Set the OBS current program scene."""
    try:
        cl = _obs_client()
        cl.set_current_program_scene(body.scene_name)
        cl.disconnect()
        return JSONResponse({"success": True, "scene": body.scene_name})
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=503)


# ---------------------------------------------------------------------------
# Pearl — channel discovery
# ---------------------------------------------------------------------------


@router.get("/pearl/channels")
async def list_pearl_channels() -> JSONResponse:
    """
    Return all Pearl channels discovered live from the device.
    Redirects to /api/pearl/channels which includes role assignments.
    This endpoint exists for compatibility — prefer /api/pearl/channels.
    """
    try:
        from domains.epiphan.tools.pearl_client import PearlClient

        client = PearlClient()
        channels = client.get_channels()
        return JSONResponse({"channels": channels})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
