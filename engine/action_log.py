"""
engine/action_log.py — Structured action log writer.

Appends JSON-L entries to ``data/logs/action_log.jsonl``.
Every operator action that mutates hardware state (safe mode, lower thirds,
transitions, etc.) should write an entry via ``write_action()``.

Schema per line:
    {
        "ts":      "<ISO-8601 UTC>",
        "actor":   "operator" | "system" | "<component>",
        "action":  "<verb_noun>",
        "payload": {…},
        "result":  "ok" | "error" | "<message>"
    }
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from engine.paths import get_data_dir

# Module-level path so tests can monkeypatch it
ACTION_LOG_FILE: Path = get_data_dir() / "logs" / "action_log.jsonl"


def write_action(
    actor: str,
    action: str,
    payload: dict | None = None,
    result: str = "ok",
) -> dict:
    """
    Append one action entry to ``ACTION_LOG_FILE``.

    Parameters
    ----------
    actor:   Who triggered the action (``"operator"``, ``"system"``, …)
    action:  Verb-noun identifier (e.g. ``"safe_mode_activate"``)
    payload: Optional context dict
    result:  ``"ok"`` or a short error description

    Returns the written entry dict.
    """
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": actor,
        "action": action,
        "payload": payload or {},
        "result": result,
    }
    ACTION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ACTION_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def read_recent(limit: int = 20) -> list[dict]:
    """
    Return the most recent *limit* entries from the action log.

    Returns an empty list if the log does not exist or is unreadable.
    """
    if not ACTION_LOG_FILE.exists():
        return []
    entries: list[dict] = []
    try:
        with ACTION_LOG_FILE.open("r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    entries.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    except OSError:
        return []
    return entries[-limit:]
