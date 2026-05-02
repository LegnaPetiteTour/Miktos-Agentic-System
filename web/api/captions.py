"""
web/api/captions.py — /api/captions/* endpoints.

GET  /api/captions/stream  → SSE stream of caption dicts (tails captions.jsonl)
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
