"""
domains/captioning/caption_worker.py — Tail-based caption reader.

Watches  data/captions/captions.jsonl  for new lines and yields them as
caption events.  Each line must be a JSON object:

    {"ts": "2026-05-02T00:00:00Z", "channel": "en", "text": "Hello world"}

Usage (async context)::

    async for caption in tail_captions():
        print(caption["text"])

The generator seeks to EOF on entry so only *new* lines are yielded —
existing history is not replayed.  Callers can pass a smaller
``poll_interval`` for tests.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from engine.paths import get_data_dir

# Public path — captions.py and tests import this directly.
CAPTIONS_FILE: Path = get_data_dir() / "captions" / "captions.jsonl"

_POLL_INTERVAL: float = 0.5  # seconds between EOF polls in production


async def tail_captions(
    poll_interval: float = _POLL_INTERVAL,
    captions_file: Path | None = None,
) -> AsyncGenerator[dict, None]:
    """Async generator that yields caption dicts as they are appended.

    Args:
        poll_interval: Seconds to sleep between EOF polls.
        captions_file: Override the default CAPTIONS_FILE path (for tests).
    """
    target = captions_file if captions_file is not None else CAPTIONS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.touch()

    with target.open("r", encoding="utf-8") as fh:
        fh.seek(0, 2)  # jump to EOF — do not replay history
        while True:
            line = fh.readline()
            if line:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass  # skip malformed lines silently
            else:
                await asyncio.sleep(poll_interval)
