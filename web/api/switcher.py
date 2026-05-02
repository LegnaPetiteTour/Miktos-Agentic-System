"""
web/api/switcher.py — /api/switcher/* endpoints.

GET  /api/switcher/obs/scenes      → list OBS scenes + current program scene
POST /api/switcher/obs/switch      → set current OBS program scene
GET  /api/switcher/pearl/channels  → list Pearl channels via PearlClient
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
# Endpoints — OBS scenes
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
# Endpoints — Pearl channels
# ---------------------------------------------------------------------------


@router.get("/pearl/channels")
async def list_pearl_channels() -> JSONResponse:
    """Return Pearl channel list from PearlClient."""
    try:
        from domains.epiphan.tools.pearl_client import PearlClient

        client = PearlClient()
        channels = client.get_channels()
        return JSONResponse({"channels": channels})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
