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
    pearl_layouts:  list[dict],    # latest entry per channel from layout_log.jsonl
    pipeline_slots: list[str],     # files present in latest named session dir
    elapsed:        str            # wall-clock age of last session dir (HH:MM)
  }
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

import yaml
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

_CONFIG_PATH = Path("domains/streamlab_post/config/session_config.yaml")
_MESSAGE_LOG = Path("data/messages/message.log")
_LAYOUT_LOG = Path("data/logs/layout_log.jsonl")
_SESSIONS_DIR = Path("data/sessions")

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
    """Latest layout entry per channel from layout_log.jsonl."""
    if not _LAYOUT_LOG.exists():
        return []
    by_channel: dict[str, dict] = {}
    with _LAYOUT_LOG.open() as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
                ch = str(entry.get("channel", ""))
                if ch:
                    by_channel[ch] = entry
            except json.JSONDecodeError:
                continue
    return list(by_channel.values())


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


def _latest_session_info() -> tuple[list[str], str]:
    """Returns (pipeline_slots, elapsed_HH:MM) for the most recent named session."""
    sessions = _named_sessions()
    if not sessions:
        return [], "—"
    latest = sessions[-1]
    slots = [f.name for f in sorted(latest.iterdir())]
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

    while True:
        hardware = _read_hardware()
        stream_state, tick, alerts = _parse_message_log()
        pearl_layouts = _read_pearl_layouts()
        pipeline_slots, elapsed = _latest_session_info()
        runner = get_runner_state()

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
