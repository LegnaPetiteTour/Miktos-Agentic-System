"""
web/api/safe_mode.py — /api/safe_mode/* endpoints.

Emergency/safe-mode control. When activated:
  1. State flag is persisted to ``data/state/safe_mode.json``
  2. Best-effort attempt to stop all streams on OBS and Pearl
  3. Action log entry is written

All endpoints always return 200 — hardware failure during stop is
tolerated and logged, but does not prevent the flag from being set.

GET  /api/safe_mode/state       → {"active": bool, "ts": str | null}
POST /api/safe_mode/activate    → set flag, stop hardware (best-effort)
POST /api/safe_mode/deactivate  → clear flag
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from engine.action_log import write_action
from engine.paths import get_data_dir

router = APIRouter()

# Module-level path — tests can monkeypatch ``safe_mode_mod.SAFE_MODE_FILE``
SAFE_MODE_FILE = get_data_dir() / "state" / "safe_mode.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_state() -> dict:
    if not SAFE_MODE_FILE.exists():
        return {"active": False, "ts": None}
    try:
        return json.loads(SAFE_MODE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"active": False, "ts": None}


def _write_state(active: bool) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = {"active": active, "ts": ts}
    SAFE_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SAFE_MODE_FILE.write_text(json.dumps(state), encoding="utf-8")
    return state


def _stop_all_hardware() -> None:
    """
    Best-effort stop of all active streams on OBS and Pearl.
    Never raises; failures are silently swallowed so the safe-mode flag
    is always persisted regardless of hardware state.
    """
    # OBS
    try:
        import obsws_python as obs  # noqa: PLC0415

        cl = obs.ReqClient(
            host=os.getenv("OBS_HOST", "localhost"),
            port=int(os.getenv("OBS_PORT", "4455")),
            password=os.getenv("OBS_PASSWORD", ""),
            timeout=3,
        )
        try:
            cl.stop_stream()
        except Exception:  # noqa: BLE001
            pass
        try:
            cl.stop_record()
        except Exception:  # noqa: BLE001
            pass
        try:
            cl.disconnect()
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass

    # Pearl
    try:
        from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

        pc = PearlClient()
        channels = pc.get_channels()
        for ch in channels:
            try:
                pc.stop_streaming(str(ch.get("id", "")))
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/state")
async def get_state() -> JSONResponse:
    """Return current safe-mode state."""
    return JSONResponse(_read_state())


@router.post("/activate")
async def activate() -> JSONResponse:
    """
    Activate emergency safe mode.

    Persists the flag, attempts a best-effort hardware stop, and writes
    an action log entry.  Always returns 200.
    """
    state = _write_state(True)
    _stop_all_hardware()
    write_action("operator", "safe_mode_activate", {}, "ok")
    return JSONResponse({"ok": True, **state})


@router.post("/deactivate")
async def deactivate() -> JSONResponse:
    """Clear the safe-mode flag and write an action log entry."""
    state = _write_state(False)
    write_action("operator", "safe_mode_deactivate", {}, "ok")
    return JSONResponse({"ok": True, **state})
