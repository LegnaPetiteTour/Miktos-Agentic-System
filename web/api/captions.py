"""
web/api/captions.py — /api/captions/* endpoints.

GET  /api/captions/stream  → SSE stream of caption dicts (tails captions.jsonl)
GET  /api/captions/stats   → reliability metrics (count/60s, lag, stale flag)
POST /api/captions/append  → write one caption line (used for testing / injection)

SSE event format:
    data: {"ts": "...", "channel": "en", "text": "Hello world"}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from domains.captioning.caption_worker import CAPTIONS_FILE, tail_captions

router = APIRouter()


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------


@router.get("/stream")
async def caption_stream() -> StreamingResponse:
    """Stream new caption events as Server-Sent Events."""

    async def _generate() -> AsyncGenerator[str, None]:
        async for caption in tail_captions():
            yield f"data: {json.dumps(caption)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Manual append (testing / operator injection)
# ---------------------------------------------------------------------------


class CaptionBody(BaseModel):
    channel: str = "en"
    text: str


@router.post("/append")
async def append_caption(body: CaptionBody) -> JSONResponse:
    """Append one caption line to captions.jsonl."""
    if not body.text.strip():
        return JSONResponse(
            {"success": False, "error": "text is required"}, status_code=422
        )
    CAPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "channel": body.channel,
        "text": body.text,
    }
    with CAPTIONS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return JSONResponse({"success": True, "entry": entry})


# ---------------------------------------------------------------------------
# Caption reliability stats
# ---------------------------------------------------------------------------


@router.get("/stats")
async def caption_stats() -> JSONResponse:
    """
    Return caption feed reliability metrics.

    Response
    --------
    ``count_last_60s`` : int   — captions received in the last 60 s
    ``last_ts``        : str|null — ISO-8601 timestamp of the most recent caption
    ``lag_seconds``    : float|null — seconds since the last caption
    ``stale``          : bool  — True when no caption arrived in the last 30 s
    """
    if not CAPTIONS_FILE.exists():
        return JSONResponse(
            {"count_last_60s": 0, "last_ts": None, "lag_seconds": None, "stale": True}
        )

    now = datetime.now(timezone.utc)
    count_60 = 0
    last_ts: str | None = None

    try:
        with CAPTIONS_FILE.open("r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    entry = json.loads(ln)
                    ts_str = entry.get("ts", "")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        last_ts = ts_str
                        if (now - ts).total_seconds() <= 60:
                            count_60 += 1
                except Exception:  # noqa: BLE001
                    pass
    except OSError:
        pass

    lag_seconds: float | None = None
    stale = True
    if last_ts:
        try:
            ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            lag_seconds = round((now - ts).total_seconds(), 1)
            stale = lag_seconds > 30
        except Exception:  # noqa: BLE001
            pass

    return JSONResponse(
        {
            "count_last_60s": count_60,
            "last_ts": last_ts,
            "lag_seconds": lag_seconds,
            "stale": stale,
        }
    )
