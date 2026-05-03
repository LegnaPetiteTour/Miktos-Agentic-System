"""
web/api/adapters.py — /api/adapters/* endpoints.

GET /api/adapters/capabilities  → current adapter capability flags

The cockpit uses these flags to show or hide controls rather than
hard-coding hardware names (ADR-009).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/capabilities")
async def get_capabilities() -> JSONResponse:
    """
    Return capability flags for the active hardware adapter.

    Uses ``HARDWARE_ADAPTER`` / ``HARDWARE_PLATFORM`` env vars to select
    the adapter (default: OBS Studio).  ``capabilities()`` never requires
    a live connection.
    """
    try:
        from engine.adapters.registry import get_adapter  # noqa: PLC0415

        adapter = get_adapter()
        caps = adapter.capabilities()
        return JSONResponse(caps.as_dict())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"error": str(exc), "platform_name": "unknown"}, status_code=503
        )
