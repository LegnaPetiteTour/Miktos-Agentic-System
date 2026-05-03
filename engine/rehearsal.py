"""
engine/rehearsal.py — Rehearsal / simulation mode state.

When rehearsal mode is active the adapter registry substitutes a
``RehearsalAdapter`` for all hardware calls.  The cockpit renders
and behaves normally; no live Pearl or OBS connection is opened.

Use cases:
  - Operator training without a live studio
  - Pre-show cue-list dry run
  - QA / demo without hardware present
  - Integration testing with hardware offline

State file: data/state/rehearsal.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from engine.paths import get_data_dir

# Module-level path — tests can monkeypatch this
REHEARSAL_STATE_FILE: Path = get_data_dir() / "state" / "rehearsal.json"


def _read() -> dict:
    if not REHEARSAL_STATE_FILE.exists():
        return {"active": False, "ts": None}
    try:
        return json.loads(REHEARSAL_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"active": False, "ts": None}


def _write(active: bool) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = {"active": active, "ts": ts}
    REHEARSAL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    REHEARSAL_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    return state


def is_rehearsal_active() -> bool:
    """Return ``True`` when rehearsal mode is currently enabled."""
    return bool(_read().get("active", False))


def get_state() -> dict:
    """Return ``{"active": bool, "ts": str | null}``."""
    return _read()


def activate() -> dict:
    """Enable rehearsal mode.  Returns updated state."""
    return _write(True)


def deactivate() -> dict:
    """Disable rehearsal mode.  Returns updated state."""
    return _write(False)
