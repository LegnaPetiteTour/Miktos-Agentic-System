"""
preview.py — GET /api/preview/thumbnail?source=pearl_en|pearl_fr|obs

Fetches a live thumbnail from Pearl channels or the OBS program feed.
All errors are caught and returned as ``data=None`` (best-effort, always 200).
"""

from __future__ import annotations

import base64
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _obs_client():  # pragma: no cover
    import obsws_python as obs  # noqa: PLC0415

    return obs.ReqClient(
        host=os.getenv("OBS_HOST", "localhost"),
        port=int(os.getenv("OBS_PORT", "4455")),
        password=os.getenv("OBS_PASSWORD", ""),
        timeout=5,
    )


def _pearl_thumbnail(channel_id: str) -> bytes:
    """Fetch raw JPEG bytes for *channel_id* from the Pearl REST API."""
    import requests  # noqa: PLC0415
    from requests.auth import HTTPBasicAuth  # noqa: PLC0415

    host = os.getenv("PEARL_HOST", "192.168.255.250")
    port = os.getenv("PEARL_PORT", "80")
    password = os.getenv("PEARL_PASSWORD", "")
    auth = HTTPBasicAuth("admin", password)
    resp = requests.get(
        f"http://{host}:{port}/api/channels/{channel_id}/thumbnail",
        auth=auth,
        timeout=5,
    )
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/thumbnail")
async def get_thumbnail(source: str = "obs") -> JSONResponse:
    """
    Return a base64-encoded JPEG thumbnail.

    Query params
    ------------
    source : str
        ``pearl_en`` — Pearl channel from ``PEARL_CHANNEL_EN`` env (default ``1``)
        ``pearl_fr`` — Pearl channel from ``PEARL_CHANNEL_FR`` env (default ``2``)
        ``obs``      — OBS program screenshot (default)

    Response
    --------
    ``{"source": str, "data": str | None, "content_type": "image/jpeg"}``

    On any error ``data`` is ``None`` and an ``"error"`` key is present.
    HTTP status is always 200.
    """
    try:
        if source in ("pearl_en", "pearl_fr"):
            env_key = "PEARL_CHANNEL_EN" if source == "pearl_en" else "PEARL_CHANNEL_FR"
            default_ch = "1" if source == "pearl_en" else "2"
            channel_id = os.getenv(env_key, default_ch)
            raw = _pearl_thumbnail(channel_id)
            data = base64.b64encode(raw).decode()
            return JSONResponse(
                {"source": source, "data": data, "content_type": "image/jpeg"}
            )

        # OBS
        cl = _obs_client()
        src_name = os.getenv("OBS_PREVIEW_SOURCE", "Program")
        resp = cl.get_source_screenshot(src_name, "jpg", 320, 180, 85)
        try:
            cl.disconnect()
        except Exception:  # noqa: BLE001
            pass
        return JSONResponse(
            {"source": source, "data": resp.image_data, "content_type": "image/jpeg"}
        )

    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"source": source, "data": None, "error": str(exc)})
