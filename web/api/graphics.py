"""
graphics.py — Lower thirds, transitions, intro/outro control.

Routes
------
POST   /api/graphics/lower_third         Push text overlay to OBS Browser Source
DELETE /api/graphics/lower_third         Clear the overlay
POST   /api/graphics/transition          Trigger a scene transition in OBS
POST   /api/graphics/intro               Trigger intro clip/scene in OBS
POST   /api/graphics/outro               Trigger outro clip/scene in OBS

All OBS connectivity errors return HTTP 503.
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Defaults (overridable via env vars)
# ---------------------------------------------------------------------------

_LOWER_THIRD_INPUT = os.getenv("OBS_LOWER_THIRD_SOURCE", "Lower Third")
_INTRO_SCENE = os.getenv("OBS_INTRO_SCENE", "Intro")
_OUTRO_SCENE = os.getenv("OBS_OUTRO_SCENE", "Outro")

# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class LowerThirdBody(BaseModel):
    name: str
    title: str = ""
    org: str = ""
    channel: str = "obs"


class TransitionBody(BaseModel):
    type: str = "cut"
    channel: str = "obs"


# ---------------------------------------------------------------------------
# OBS helper
# ---------------------------------------------------------------------------


def _obs_client():  # pragma: no cover
    import obsws_python as obs  # noqa: PLC0415

    return obs.ReqClient(
        host=os.getenv("OBS_HOST", "localhost"),
        port=int(os.getenv("OBS_PORT", "4455")),
        password=os.getenv("OBS_PASSWORD", ""),
        timeout=5,
    )


def _disconnect(cl) -> None:  # noqa: ANN001
    try:
        cl.disconnect()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/lower_third")
async def push_lower_third(body: LowerThirdBody) -> JSONResponse:
    """Push a lower-third text overlay to OBS Browser Source."""
    try:
        cl = _obs_client()
        parts = [body.name]
        if body.title:
            parts.append(body.title)
        if body.org:
            parts.append(body.org)
        text = " | ".join(parts)
        cl.set_input_settings(_LOWER_THIRD_INPUT, {"text": text}, True)
        _disconnect(cl)
        return JSONResponse({"ok": True, "text": text})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


@router.delete("/lower_third")
async def clear_lower_third() -> JSONResponse:
    """Clear the lower-third overlay by sending an empty string."""
    try:
        cl = _obs_client()
        cl.set_input_settings(_LOWER_THIRD_INPUT, {"text": ""}, True)
        _disconnect(cl)
        return JSONResponse({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


@router.post("/transition")
async def trigger_transition(body: TransitionBody) -> JSONResponse:
    """Trigger a studio-mode scene transition in OBS."""
    try:
        cl = _obs_client()
        cl.trigger_studio_mode_transition()
        _disconnect(cl)
        return JSONResponse({"ok": True, "type": body.type})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


@router.post("/intro")
async def trigger_intro() -> JSONResponse:
    """Switch OBS to the intro scene."""
    try:
        cl = _obs_client()
        cl.set_current_program_scene(_INTRO_SCENE)
        _disconnect(cl)
        return JSONResponse({"ok": True, "scene": _INTRO_SCENE})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)


@router.post("/outro")
async def trigger_outro() -> JSONResponse:
    """Switch OBS to the outro scene."""
    try:
        cl = _obs_client()
        cl.set_current_program_scene(_OUTRO_SCENE)
        _disconnect(cl)
        return JSONResponse({"ok": True, "scene": _OUTRO_SCENE})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)
