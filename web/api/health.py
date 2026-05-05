"""
web/api/health.py — /api/health/* endpoints.

GET /api/health/snapshot → {obs_ok, obs_version, pearl_ok, pearl_firmware,
                             network_quality}

All probes are best-effort: a failure in one does not block the others.
The endpoint always returns 200 — callers inspect the *_ok booleans.
"""

from __future__ import annotations

import json
import os
import subprocess

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


def _obs_probe() -> tuple[bool, str | None]:
    """Return (reachable, obs_version). Never raises."""
    try:
        import obsws_python as obs  # type: ignore[import-untyped]

        cl = obs.ReqClient(
            host=os.getenv("OBS_HOST", "localhost"),
            port=int(os.getenv("OBS_PORT", "4455")),
            password=os.getenv("OBS_PASSWORD", ""),
            timeout=3,
        )
        version: str = cl.get_version().obs_version
        cl.disconnect()
        return True, version
    except Exception:
        return False, None


def _pearl_probe() -> tuple[bool, str | None]:
    """Return (reachable, channel_summary). Never raises.

    Uses /api/channels (always present on Pearl) rather than the firmware
    endpoint which returns {"status": "notfound"} on some firmware versions.
    """
    try:
        from domains.epiphan.tools.pearl_client import PearlClient

        client = PearlClient()
        channels = client.get_channels()
        count = len(channels) if isinstance(channels, list) else 0
        return True, f"{count} channels"
    except Exception:
        return False, None


def _network_quality() -> str | None:
    """
    Run macOS networkQuality (Sequoia+) in single-shot (-s) JSON (-c) mode.
    Returns a human-readable summary string, or None if unavailable.
    """
    try:
        result = subprocess.run(
            ["networkQuality", "-s", "-c"],
            capture_output=True,
            text=True,
            timeout=12,
        )
        data = json.loads(result.stdout)
        dl = data.get("dl_throughput", 0)
        ul = data.get("ul_throughput", 0)
        return f"↓{dl / 1_000_000:.0f} Mbps ↑{ul / 1_000_000:.0f} Mbps"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/snapshot")
async def health_snapshot() -> JSONResponse:
    """Return a hardware and network health snapshot."""
    obs_ok, obs_version = _obs_probe()
    pearl_ok, pearl_firmware = _pearl_probe()
    network = _network_quality()
    return JSONResponse(
        {
            "obs_ok": obs_ok,
            "obs_version": obs_version,
            "pearl_ok": pearl_ok,
            "pearl_firmware": pearl_firmware,
            "network_quality": network,
        }
    )
