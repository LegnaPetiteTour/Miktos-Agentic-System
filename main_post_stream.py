"""
Miktos Agentic System — Post-Stream Closure Engine
Entry point for Phase 5.

Listens for "recording_stopped" pub/sub events via the message bus,
then runs the PostStreamCoordinator to close out the stream session.

Reads session_config.yaml from domains/streamlab_post/config/ before each run.
Config file is re-read on every event — no restart needed to apply config changes.

Usage:
  python main_post_stream.py
  python main_post_stream.py --poll-interval 10
  python main_post_stream.py --once          # process inbox once then exit
  python main_post_stream.py --dry-run       # log steps without calling external APIs
"""

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

from domains.streamlab_post.coordinator import PostStreamCoordinator
from engine.messaging.bus import MessageBus

load_dotenv()

_AGENT_ID = "post_stream_processor"
_TOPIC = "recording_stopped"
_CONFIG_PATH = Path("domains/streamlab_post/config/session_config.yaml")
_CONFIG_EXAMPLE_PATH = Path(
    "domains/streamlab_post/config/session_config.example.yaml"
)
_DIVIDER = "─" * 45


def _load_session_config() -> dict:
    """
    Load session_config.yaml from the domain config directory.
    Falls back to the example file if the runtime config is absent.
    Re-read on every event — no restart needed for config changes.
    """
    config_path = _CONFIG_PATH if _CONFIG_PATH.exists() else _CONFIG_EXAMPLE_PATH
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def _print_session_report(
    session_name: str,
    artifact: dict,
    elapsed: float,
) -> None:
    """Print the formatted session report to stdout."""
    print(f"\nPost-Stream Session {session_name}")
    print(f"  {_DIVIDER}")

    stage_order = [
        ("Stage 1", ["backup_verify", "youtube_en", "audio_extract"]),
        ("Stage 2", ["translate", "transcript"]),
        ("Stage 3", ["youtube_fr", "file_rename"]),
        ("Stage 4", ["notify"]),
    ]
    slots = artifact.get("slots", {})

    for stage_label, slot_names in stage_order:
        # Only print stages that have results
        stage_slots = [(n, slots[n]) for n in slot_names if n in slots]
        if not stage_slots:
            continue

        print(f"\n  {stage_label}")
        for i, (slot_name, result) in enumerate(stage_slots):
            is_last = i == len(stage_slots) - 1
            connector = "└──" if is_last else "├──"
            icon = "✅" if result.get("success") else "❌"

            # Build a short summary for each slot
            detail = _slot_detail(slot_name, result)
            print(f"  {connector} {slot_name:<16} {icon}  {detail}")

    print()
    exit_reason = artifact.get("exit_reason", "unknown")
    failure = artifact.get("failure_reason", "")
    if failure:
        print(f"  exit: {exit_reason} — {failure}")
    else:
        final_folder = artifact.get("final_folder", "")
        folder_str = f" | → {final_folder}" if final_folder else ""
        print(f"  exit: {exit_reason}{folder_str} | session closed in {elapsed:.0f}s")
    print(f"  {_DIVIDER}\n")


def _slot_detail(slot_name: str, result: dict) -> str:
    """Return a short one-line detail string for a slot result."""
    if not result.get("success"):
        return result.get("error", "failed")[:60]

    if slot_name == "backup_verify":
        size_gb = result.get("file_size_bytes", 0) / 1_073_741_824
        dur = result.get("duration_seconds", 0)
        path = result.get("file_path", "")
        return f"{path}  ({size_gb:.1f} GB, {dur:.0f}s)"

    if slot_name in ("youtube_en", "youtube_fr"):
        vid = result.get("video_id", "")
        vis = result.get("visibility", "")
        pl = "playlist added" if result.get("playlist_added") else "no playlist"
        return f"video_id={vid[:8]}... | {vis} | {pl}"

    if slot_name == "audio_extract":
        size_mb = result.get("file_size_bytes", 0) / 1_048_576
        mp3 = Path(result.get("mp3_path", "")).name
        return f"{mp3}  ({size_mb:.0f} MB)"

    if slot_name == "translate":
        return "title + description translated EN→FR"

    if slot_name == "transcript":
        words = result.get("word_count", 0)
        langs = "/".join(result.get("detected_languages", []))
        return f"{words:,} words | {langs} detected"

    if slot_name == "file_rename":
        folder = result.get("final_folder", "")
        return f"→ {folder}"

    if slot_name == "notify":
        via = result.get("sent_via", [])
        recipients = result.get("recipient_count", 0)
        channels = " + ".join(via) if via else "skipped"
        if recipients:
            return f"{channels} + {recipients} email recipient(s)"
        return channels

    return "ok"


def process_once(bus: MessageBus, dry_run: bool) -> int:
    """
    Read all pending recording_stopped messages and run the coordinator.
    Returns the number of messages processed.
    """
    messages = bus.read_pending(for_agent=_AGENT_ID)
    if not messages:
        return 0

    session_config = _load_session_config()
    coordinator = PostStreamCoordinator()
    processed = 0

    for message in messages:
        if message.message_type != _TOPIC:
            # Not ours — leave in inbox
            continue

        payload = dict(message.payload)
        payload["dry_run"] = dry_run

        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()

        artifact = coordinator.run(payload=payload, session_config=session_config)

        elapsed = time.monotonic() - t0
        session_date = artifact.get("session_date", started_at.strftime("%Y-%m-%d"))
        event_name = artifact.get("event_name", "Event")

        # Determine the sequence number from final_folder name if available
        final_folder = artifact.get("final_folder", "")
        folder_name = Path(final_folder).name if final_folder else ""
        session_name = folder_name or f"{session_date}_{event_name}_???"

        _print_session_report(session_name, artifact, elapsed)
        bus.acknowledge(message)
        processed += 1

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Miktos Post-Stream Closure Engine (Phase 5)"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        metavar="SECONDS",
        help="How often to poll the message bus (default: 5s)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process inbox once then exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all stages without calling external APIs",
    )
    args = parser.parse_args()

    bus = MessageBus()
    bus.subscribe(_TOPIC, _AGENT_ID)

    mode = "dry-run" if args.dry_run else "live"
    print(
        f"Post-Stream Closure Engine started  [{mode}]\n"
        f"  Subscribed to: {_TOPIC}\n"
        f"  Agent ID:      {_AGENT_ID}\n"
        f"  Poll interval: {args.poll_interval}s\n"
        f"  Config:        "
        f"{'session_config.yaml' if _CONFIG_PATH.exists() else 'session_config.example.yaml (fallback)'}\n"
    )

    if args.once:
        count = process_once(bus, dry_run=args.dry_run)
        if count == 0:
            print("No pending recording_stopped messages in inbox.")
        return

    # Continuous poll loop
    try:
        while True:
            process_once(bus, dry_run=args.dry_run)
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nPost-Stream Closure Engine stopped.")


if __name__ == "__main__":
    main()
