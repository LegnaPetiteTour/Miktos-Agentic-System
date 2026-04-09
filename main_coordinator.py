"""
Miktos Agentic System — Session Coordinator
Entry point for the Phase 4c coordinator agent.

Listens for recording_ready messages and coordinates three workers
(organize, thumbnail, metadata) to produce a complete session artifact.

The coordinator is not a domain. It is a meta-agent.
It uses the message bus directly, not the LangGraph engine graph.

Usage:
  python main_coordinator.py
  python main_coordinator.py --poll-interval 5
  python main_coordinator.py --once
"""

import argparse
import time

from engine.coordinator.coordinator import SessionCoordinator
from engine.messaging.bus import MessageBus

AGENT_ID = "session_coordinator"


def _print_session(artifact: dict) -> None:
    session_id = artifact.get("session_id", "?")
    exit_reason = artifact.get("exit_reason", "?")
    slots = artifact.get("slots", {})
    to_agent = "streamlab_monitor"

    print(f"\n  Session {session_id}")

    organize = slots.get("organize", {})
    if organize.get("success"):
        cat = organize.get("category", "?")
        conf = organize.get("confidence", 0.0)
        prop = organize.get("proposed_path", "")
        print(f"  ├── organize   ✅  {cat} ({conf:.2f})  →  {prop}")
    else:
        err = organize.get("error", "unknown error")
        print(f"  ├── organize   ❌  {err}")

    thumb = slots.get("thumbnail", {})
    if thumb.get("success"):
        tp = thumb.get("thumbnail_path", "")
        print(f"  ├── thumbnail  ✅  {tp}")
    else:
        err = thumb.get("error", "unknown error")
        print(f"  ├── thumbnail  ❌  {err}")

    meta = slots.get("metadata", {})
    if meta.get("success"):
        mp = meta.get("metadata_path", "")
        dur = meta.get("duration_seconds", 0.0)
        print(f"  └── metadata   ✅  {mp}  ({dur}s)")
    else:
        err = meta.get("error", "unknown error")
        print(f"  └── metadata   ❌  {err}")

    print(f"  exit: {exit_reason} | posted session_complete → {to_agent}")


def listen_loop(args: argparse.Namespace) -> None:
    bus = MessageBus()
    coordinator = SessionCoordinator(bus, agent_id=AGENT_ID)

    if args.once:
        print("\n  Miktos Coordinator — Single-drain mode")
    else:
        print("\n  Miktos Coordinator — Listen Mode")
    print(f"  Agent ID : {AGENT_ID}")
    if not args.once:
        print(f"  Poll interval : {args.poll_interval}s")
    print("  Waiting for messages... (Ctrl+C to stop)\n")

    def drain() -> None:
        messages = bus.read_pending(for_agent=AGENT_ID)
        for msg in messages:
            if msg.message_type != "recording_ready":
                bus.acknowledge(msg)
                continue
            print(f"  [Inbox] Message from {msg.from_agent}: {msg.message_type}")
            artifact = coordinator.handle(msg)
            bus.acknowledge(msg)
            _print_session(artifact)

    if args.once:
        drain()
        return

    try:
        while True:
            drain()
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\n  Stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Miktos Session Coordinator")
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        metavar="N",
        help="Seconds between inbox polls (default: 5)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Drain inbox once then exit (useful for CI/tests)",
    )
    args = parser.parse_args()
    listen_loop(args)


if __name__ == "__main__":
    main()
