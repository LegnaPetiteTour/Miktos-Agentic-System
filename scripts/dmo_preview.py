"""
DMO Preview — Phase 4d pub/sub demonstration.

Simulates the workflow that Phase 5 (DMO / Ecosystem) will automate:

  1. Register subscribers for "recording_stopped" topic
  2. Simulate StreamLab publishing "recording_stopped"
  3. Both session_coordinator AND kosmos_organizer receive the event
     from ONE publish() call
  4. Show that StreamLab does not name the recipients
  5. Print the message.log showing PUBLISHED event + individual POSTED events

This script proves the architectural foundation for Phase 5:
  - One event, multiple independent reactions
  - Publisher has zero knowledge of subscribers
  - Adding a new subscriber requires zero code changes

Usage:
  python scripts/dmo_preview.py
  python scripts/dmo_preview.py --clean   # acknowledge demo messages after run
"""

import argparse
import sys
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.messaging.bus import MessageBus  # noqa: E402


TOPIC = "recording_stopped"
PUBLISHER = "streamlab_monitor"
SUBSCRIBERS = ["session_coordinator", "kosmos_organizer"]

DEMO_PAYLOAD = {
    "recordings_path": str(Path.home() / "Movies"),
    "scene": "DMO Preview Scene",
    "trigger_run_id": "dmo_preview_demo",
    "timestamp": "2026-04-09T22:00:00Z",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 4d — Pub/Sub Demo"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Acknowledge (clear) demo messages from inboxes after run",
    )
    return parser.parse_args()


def print_separator() -> None:
    print("=" * 54)


def main() -> None:
    args = parse_args()
    bus = MessageBus()

    print()
    print_separator()
    print("  Phase 4d — Pub/Sub Demo")
    print_separator()

    # Step 1 — register subscribers
    for agent in SUBSCRIBERS:
        bus.subscribe(TOPIC, agent)

    # Show current subscriber list
    subs = bus._load_subscriptions()
    registered = subs.get(TOPIC, [])
    print(f"  Topic         : {TOPIC}")
    print(f"  Subscribers   : {', '.join(registered)}")
    print(f"  Publisher     : {PUBLISHER} (does not name recipients)")
    print()

    # Step 2 — publish once
    print("  publish() called once.")
    print()
    delivered = bus.publish(
        topic=TOPIC,
        from_agent=PUBLISHER,
        payload=DEMO_PAYLOAD,
        run_id="dmo_preview_demo",
    )

    # Step 3 — verify each inbox received the message
    all_ok = True
    for agent in SUBSCRIBERS:
        pending = bus.read_pending(for_agent=agent)
        demo_msgs = [
            m for m in pending
            if m.run_id == "dmo_preview_demo"
        ]
        count = len(demo_msgs)
        icon = "✅" if count >= 1 else "❌"
        print(
            f"  {agent}/pending/"
            f"{'.' * max(1, 38 - len(agent))}"
            f" {count} new message {icon}"
        )
        if count < 1:
            all_ok = False

    print()
    print(
        "  Old way (Phase 4b):  "
        f"{len(SUBSCRIBERS)} × post() calls, publisher names each recipient"
    )
    print(
        "  New way (Phase 4d):  "
        "1 × publish() call, publisher knows no recipients"
    )

    # Step 4 — show last lines of message.log
    log_path = Path("data/messages/message.log")
    if log_path.exists():
        lines = log_path.read_text().splitlines()
        # Find the PUBLISHED line and the POSTED lines that follow it
        demo_lines: list[str] = []
        in_block = False
        for line in lines:
            if "PUBLISHED" in line and TOPIC in line:
                in_block = True
            if in_block:
                demo_lines.append(line)

        if demo_lines:
            print()
            print("  message.log (this run):")
            for line in demo_lines[-10:]:
                print(f"    {line}")

    print()
    print_separator()
    result = "✅ PASS" if all_ok else "❌ FAIL"
    print(
        f"  Phase 4d proof: one publish, "
        f"{len(delivered)} deliveries, zero coupling.  {result}"
    )
    print_separator()
    print()

    # Step 5 — optionally clean up demo messages
    if args.clean:
        for agent in SUBSCRIBERS:
            pending = bus.read_pending(for_agent=agent)
            for msg in pending:
                if msg.run_id == "dmo_preview_demo":
                    bus.acknowledge(msg)
        print("  Demo messages acknowledged (inboxes clean).\n")


if __name__ == "__main__":
    main()
