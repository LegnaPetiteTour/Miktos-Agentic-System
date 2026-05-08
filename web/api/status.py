"""
web/api/status.py — /api/status/stream  (Server-Sent Events).

Pushes a JSON snapshot every second.  All reads are from existing files
written by the running system — no new state is generated here.

Payload shape:
  {
    hardware:       str,           # from session_config.yaml
    stream_state:   str,           # last event type from message.log
    tick:           int,           # count of TICK events seen in message.log
    alerts:         list[str],     # recent alert descriptions
    pearl_layouts:  list[dict],    # per-channel: {channel, active_id, active_name, layouts:[{id,name}]}
    pipeline_slots: list[str],     # files present in latest named session dir
    elapsed:        str            # wall-clock age of last session dir (HH:MM)
  }
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

import yaml
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from engine.paths import get_config_dir, get_data_dir

router = APIRouter()

_CONFIG_PATH = get_config_dir() / "session_config.yaml"
_MESSAGE_LOG = get_data_dir() / "messages" / "message.log"
_LAYOUT_LOG = get_data_dir() / "logs" / "layout_log.jsonl"
_SESSIONS_DIR = get_data_dir() / "sessions"
_CAPTIONS_FILE = get_data_dir() / "captions" / "captions.jsonl"

# Cache for the OBS network probe (expensive — gate to every 30 s)
_obs_cache: dict = {"ok": False, "ts": 0.0}

_UUID_RE = re.compile(r"^[0-9a-f]{12}$")
_LOG_LINE_RE = re.compile(
    r"^(?P<ts>\S+)\s+(?P<action>\S+)\s+(?P<source>\S+)\s+->\s+(?P<rest>.+)$"
)


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------


def _read_hardware() -> str:
    if not _CONFIG_PATH.exists():
        return "unknown"
    with _CONFIG_PATH.open() as fh:
        cfg = yaml.safe_load(fh) or {}
    return cfg.get("hardware", "unknown")


def _parse_message_log() -> tuple[str, int, list[str]]:
    """Returns (stream_state, tick_count, recent_alerts)."""
    if not _MESSAGE_LOG.exists():
        return "idle", 0, []

    stream_state = "idle"
    tick = 0
    alerts: list[str] = []

    with _MESSAGE_LOG.open() as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            parts = line.split(None, 5)
            if len(parts) < 5:
                continue
            event_type = parts[3] if len(parts) > 3 else ""
            # parts layout: ts  ACTION  source -> target  event_type  msg_id [...]
            # Find the event_type token — it's the 5th whitespace-delimited token
            # in lines like:
            #   2026-04-17T05:10:30Z  PUBLISHED  epiphan_monitor
            #     -> [3 subscriber(s)]  recording_stopped  ...
            # We split on two-or-more spaces to separate the tab-aligned columns
            cols = re.split(r"\s{2,}", line)
            if len(cols) >= 4:
                event_type = cols[3].split()[0]  # strip trailing msg_id refs
                action = cols[1]
                if action in ("PUBLISHED", "POSTED"):
                    if "tick" in event_type.lower():
                        tick += 1
                    elif event_type in ("recording_started", "stream_started"):
                        stream_state = "streaming"
                    elif event_type in ("recording_stopped", "stream_stopped"):
                        stream_state = "stopped"
                    elif "alert" in event_type.lower():
                        alerts.append(event_type)

    return stream_state, tick, alerts[-5:]


def _read_pearl_layouts() -> list[dict]:
    """
    Per-channel layout data derived from layout_log.jsonl.

    Scans the full log to collect every unique layout seen per channel
    (ordered by first appearance), then identifies the latest active one.

    Returns a list of::

        {
          "channel":     str,         # channel ID
          "active_id":   str,         # layout_id of the most-recently-seen entry
          "active_name": str,         # human name of the active layout
          "layouts":     list[dict],  # [{"id": str, "name": str}, ...] all known
        }
    """
    if not _LAYOUT_LOG.exists():
        return []
    # channel -> {"active": latest_entry, "seen": {layout_id: layout_name}}
    by_channel: dict[str, dict] = {}
    with _LAYOUT_LOG.open() as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
                ch = str(entry.get("channel", ""))
                lid = str(entry.get("layout_id", ""))
                lname = entry.get("layout_name", lid)
                if not ch or not lid:
                    continue
                if ch not in by_channel:
                    by_channel[ch] = {"active": entry, "seen": {}}
                else:
                    by_channel[ch]["active"] = entry  # always update to latest
                by_channel[ch]["seen"].setdefault(lid, lname)
            except json.JSONDecodeError:
                continue
    result = []
    for ch, data in by_channel.items():
        active_id = str(data["active"].get("layout_id", ""))
        result.append({
            "channel": ch,
            "active_id": active_id,
            "active_name": data["active"].get("layout_name", active_id),
            "layouts": [
                {"id": lid, "name": lname}
                for lid, lname in data["seen"].items()
            ],
        })
    return result


def _named_sessions() -> list[Path]:
    if not _SESSIONS_DIR.exists():
        return []
    return sorted(
        (
            d for d in _SESSIONS_DIR.iterdir()
            if d.is_dir() and not _UUID_RE.match(d.name)
        ),
        key=lambda d: d.name,
    )


def _read_session_name() -> str:
    """Return the name of the most-recent named session dir, or '—'."""
    sessions = _named_sessions()
    return sessions[-1].name if sessions else "—"


def _read_rehearsal_active() -> bool:
    """Read rehearsal state file without importing the full module."""
    state_file = get_data_dir() / "state" / "rehearsal.json"
    if not state_file.exists():
        return False
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return bool(data.get("active", False))
    except Exception:  # noqa: BLE001
        return False


def _read_captions_channel_status() -> tuple[str, str]:
    """Scan the last 200 lines of captions.jsonl for recent EN / FR activity.

    Returns a tuple (en_status, fr_status) where each value is one of:
        "active"   — a caption was written within the last 60 seconds
        "idle"     — file exists but no recent captions for that channel
        "—"        — file absent or unreadable
    """
    if not _CAPTIONS_FILE.exists():
        return "—", "—"
    now = datetime.now(timezone.utc).timestamp()
    en_fresh = fr_fresh = False
    try:
        with _CAPTIONS_FILE.open(encoding="utf-8") as fh:
            lines = fh.readlines()
        for raw in lines[-200:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
                ch = entry.get("channel", "")
                ts_str = entry.get("ts", "")
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                if now - ts < 60:
                    if ch == "en":
                        en_fresh = True
                    elif ch == "fr":
                        fr_fresh = True
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return "—", "—"
    return ("active" if en_fresh else "idle"), ("active" if fr_fresh else "idle")


def _probe_obs_sync() -> bool:
    """Synchronous OBS reachability probe; returns True on success."""
    try:
        import obsws_python as obs  # type: ignore[import-untyped]

        cl = obs.ReqClient(
            host=os.getenv("OBS_HOST", "localhost"),
            port=int(os.getenv("OBS_PORT", "4455")),
            password=os.getenv("OBS_PASSWORD", ""),
            timeout=2,
        )
        cl.get_version()
        cl.disconnect()
        return True
    except Exception:  # noqa: BLE001
        return False


def _latest_session_info() -> tuple[list[str], str]:
    """Returns (pipeline_slots, elapsed_HH:MM) for the most recent named session."""
    sessions = _named_sessions()
    if not sessions:
        return [], "—"
    latest = sessions[-1]
    slots = [f.name for f in sorted(latest.iterdir()) if not _UUID_RE.match(f.name)]
    try:
        mtime = latest.stat().st_mtime
        age_s = int(datetime.now(timezone.utc).timestamp() - mtime)
        h, rem = divmod(abs(age_s), 3600)
        m = rem // 60
        elapsed = f"{h:02d}:{m:02d}"
    except OSError:
        elapsed = "—"
    return slots, elapsed


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------


async def _event_stream() -> AsyncGenerator[str, None]:
    from web.api.runner import get_runner_state  # local import avoids circular deps

    loop = asyncio.get_event_loop()

    while True:
        hardware = _read_hardware()
        stream_state, tick, alerts = _parse_message_log()
        pearl_layouts = _read_pearl_layouts()
        pipeline_slots, elapsed = _latest_session_info()
        runner = get_runner_state()

        # Mission Status Bar fields
        session_name = _read_session_name()
        rehearsal_active = _read_rehearsal_active()
        en_cap_status, fr_cap_status = _read_captions_channel_status()
        pearl_ok = bool(pearl_layouts)

        # OBS probe — run in thread executor; gate to every 30 s
        now_mono = time.monotonic()
        if now_mono - _obs_cache["ts"] > 30.0:
            obs_ok = await loop.run_in_executor(None, _probe_obs_sync)
            _obs_cache["ok"] = obs_ok
            _obs_cache["ts"] = now_mono
        else:
            obs_ok = _obs_cache["ok"]

        # Captions "pipeline active" = at least one channel has recent captions
        captions_ok = en_cap_status == "active" or fr_cap_status == "active"

        payload = {
            "hardware": hardware,
            "stream_state": stream_state,
            "tick": tick,
            "alerts": alerts,
            "pearl_layouts": pearl_layouts,
            "pipeline_slots": pipeline_slots,
            "elapsed": elapsed,
            "session_running": runner["running"],
            "session_pid": runner["pid"],
            # Mission Status Bar
            "session_name": session_name,
            "rehearsal_active": rehearsal_active,
            "en_status": stream_state,          # EN is the primary recording channel
            "fr_status": fr_cap_status,         # FR alive = FR captions flowing
            "obs_ok": obs_ok,
            "pearl_ok": pearl_ok,
            "captions_ok": captions_ok,
        }
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/stream")
async def status_stream() -> StreamingResponse:
    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
