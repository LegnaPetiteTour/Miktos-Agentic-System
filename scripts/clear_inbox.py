"""
clear_inbox.py — Clear stale pending messages from an agent's inbox.

Moves files to delivered/ (never deletes). Appends a CLEARED line to
message.log matching the existing log column format.

Usage:
    python scripts/clear_inbox.py [--dry-run] [--agent AGENT_ID]
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AGENT = "post_stream_processor"
MESSAGE_LOG = REPO_ROOT / "data/messages/message.log"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_summary(path: Path) -> tuple[str, str, str]:
    """Return (timestamp, event_type, sender) from a message JSON."""
    try:
        with open(path) as fh:
            msg = json.load(fh)
        ts = msg.get("timestamp", "")[:20].replace(" ", "T")
        if not ts.endswith("Z"):
            ts = ts + "Z"
        event = msg.get("message_type", "unknown")
        sender = msg.get("from_agent", "unknown")
        return ts, event, sender
    except Exception:
        return "unknown", "unknown", "unknown"


def run(agent: str, dry_run: bool) -> int:
    pending_dir = REPO_ROOT / "data/messages" / agent / "pending"
    delivered_dir = REPO_ROOT / "data/messages" / agent / "delivered"

    if not pending_dir.exists():
        print(f"Inbox not found: {pending_dir}")
        print("Inbox is empty. Nothing to clear.")
        return 0

    messages = sorted(pending_dir.glob("*.json"))

    if not messages:
        print("Inbox is empty. Nothing to clear.")
        return 0

    print(f"Found {len(messages)} pending message(s) in {agent}/pending/:\n")
    for i, path in enumerate(messages, 1):
        ts, event, sender = _read_summary(path)
        print(f"  [{i}] {ts}  {event:<25}  from: {sender}")

    print()

    if dry_run:
        print("Dry run — no changes made.")
        return 0

    answer = input(f"Clear {len(messages)} message(s)? [y/N]: ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return 0

    delivered_dir.mkdir(parents=True, exist_ok=True)
    for path in messages:
        shutil.move(str(path), str(delivered_dir / path.name))

    n = len(messages)
    ts = _utc_now()
    log_line = (
        f"{ts}  CLEARED    "
        f"{agent} pending inbox ({n} message(s))\n"
    )
    with open(MESSAGE_LOG, "a") as fh:
        fh.write(log_line)

    print(f"✅  Cleared {n} message(s). Logged to message.log.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clear stale pending messages."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--agent", default=DEFAULT_AGENT)
    args = parser.parse_args()
    sys.exit(run(args.agent, args.dry_run))


if __name__ == "__main__":
    main()
