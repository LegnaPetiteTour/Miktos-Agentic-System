"""
web/api/audio_control.py — /api/audio/* endpoints.

GET  /api/audio/inputs   → list OBS audio inputs with mute/volume state
POST /api/audio/mute     → set mute state for a named input
POST /api/audio/volume   → set volume (dB) for a named input

All endpoints require OBS WebSocket to be reachable.  On failure they
return 503 with an {error: ...} body so the UI can show "OBS offline".
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper
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
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/inputs")
async def list_audio_inputs() -> JSONResponse:
    """Return all OBS audio inputs with mute state and volume in dB."""
    try:
        cl = _obs_client()
        inputs_resp = cl.get_input_list()
        result: list[dict] = []
        for inp in inputs_resp.inputs or []:
            name: str = inp.get("inputName", "")
            kind: str = inp.get("inputKind", "")
            muted: bool | None = None
            volume_db: float | None = None
            try:
                muted = cl.get_input_mute(name).input_muted
                volume_db = cl.get_input_volume(name).input_volume_db
            except Exception:
                pass
            result.append(
                {"name": name, "kind": kind, "muted": muted, "volume_db": volume_db}
            )
        cl.disconnect()
        return JSONResponse({"inputs": result})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


class MuteBody(BaseModel):
    input_name: str
    muted: bool


@router.post("/mute")
async def set_mute(body: MuteBody) -> JSONResponse:
    """Set mute state for an OBS audio input."""
    try:
        cl = _obs_client()
        cl.set_input_mute(body.input_name, body.muted)
        cl.disconnect()
        return JSONResponse(
            {"success": True, "input_name": body.input_name, "muted": body.muted}
        )
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=503)


class VolumeBody(BaseModel):
    input_name: str
    volume_db: float


@router.post("/volume")
async def set_volume(body: VolumeBody) -> JSONResponse:
    """Set volume in dB for an OBS audio input."""
    try:
        cl = _obs_client()
        cl.set_input_volume(body.input_name, vol_db=body.volume_db)
        cl.disconnect()
        return JSONResponse(
            {
                "success": True,
                "input_name": body.input_name,
                "volume_db": body.volume_db,
            }
        )
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=503)
