"""
Miktos Agentic System — Kosmos Media Organizer
Entry point for Domain 2.

Usage:
  python main_kosmos.py --path "/path/to/media/folder"
  python main_kosmos.py --path "/path/to/media/folder" --mode live
  python main_kosmos.py --path "/path/to/media/folder" --batch-size 100

Modes:
  dry_run  (default) — scans and classifies, proposes actions, writes nothing
  live               — executes approved actions (moves files)

The engine (engine/graph/) is called identically to main.py.
Only the domain name and injected tools differ.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from engine.graph.graph_builder import build_graph, build_graph_with_messaging
from engine.graph.state import RunState
from engine.messaging.bus import MessageBus
from engine.services.state_store import generate_run_id
from engine.tools.shared_tools import FileScannerTool
from domains.kosmos.tools.media_classifier import classify_media_file


def parse_args():
    parser = argparse.ArgumentParser(
        description="Miktos Kosmos — Media Library Organizer"
    )
    parser.add_argument(
        "--path",
        required=False,
        default=None,
        help="Root folder to scan and organize (required unless --listen)",
    )
    parser.add_argument(
        "--mode",
        choices=["dry_run", "live"],
        default="dry_run",
        help="dry_run (default): propose only. live: execute actions.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of files per loop iteration (default: 50)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Use parallel execution (ThreadPoolExecutor)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers when --parallel is set (default: 4)",
    )
    parser.add_argument(
        "--listen",
        action="store_true",
        help=(
            "Poll inbox for recording_ready messages and process each one. "
            "Runs indefinitely until Ctrl+C."
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Seconds between inbox polls in --listen mode (default: 5)",
    )
    return parser.parse_args()


def build_initial_state(
    root_path: str,
    mode: str,
    batch_size: int,
    parallel: bool = False,
    workers: int = 4,
    agent_id: str = "kosmos_organizer",
    inbox_messages: list | None = None,
    enable_messaging: bool = False,
    messages_dir: str = "data/messages",
) -> RunState:
    return {
        "run_id": generate_run_id(),
        "domain": "kosmos",
        "agent_id": agent_id,
        "inbox_messages": inbox_messages or [],
        "goal": f"Scan and classify all media files in: {root_path}",
        "mode": mode,
        "current_step": "init",
        "pending_tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "skipped_tasks": [],
        "exhausted_tasks": [],
        "review_queue": [],
        "proposed_actions": [],
        "applied_actions": [],
        "artifacts": [],
        "errors": [],
        "logs": [],
        "retries": 0,
        "max_retries": 3,
        "replans": 0,
        "max_replans": 2,
        "done": False,
        "exit_reason": None,
        "context": {
            "root_path": root_path,
            "batch_size": batch_size,
            "execution_mode": "parallel" if parallel else "sequential",
            "parallel_workers": workers,
            "enable_messaging": enable_messaging,
            "messages_dir": messages_dir,
            "thresholds": {
                "auto_approve": 0.90,
                "review_queue": 0.60,
            },
            "exhausted_threshold": 0.20,
            "tools": {
                "scanner": FileScannerTool(),
                "classifier": classify_media_file,
            },
        },
    }


def print_summary(final_state: RunState) -> None:
    print("\n" + "=" * 60)
    print("  MIKTOS KOSMOS — RUN SUMMARY")
    print("=" * 60)
    exec_mode = final_state["context"].get("execution_mode", "sequential")
    workers = final_state["context"].get("parallel_workers", 4)
    exec_label = (
        f"parallel ({workers} workers)" if exec_mode == "parallel" else "sequential"
    )
    print(f"  Run ID     : {final_state['run_id']}")
    print(f"  Mode       : {final_state['mode']}")
    print(f"  Execution  : {exec_label}")
    print(f"  Exit       : {final_state.get('exit_reason', 'unknown')}")
    print(f"  Completed  : {len(final_state.get('completed_tasks', []))}")
    print(f"  Failed     : {len(final_state.get('failed_tasks', []))}")
    print(f"  Skipped    : {len(final_state.get('skipped_tasks', []))}")
    print(f"  Exhausted  : {len(final_state.get('exhausted_tasks', []))}")
    print(f"  Review Q   : {len(final_state.get('review_queue', []))}")
    print(f"  Errors     : {len(final_state.get('errors', []))}")

    actions = final_state.get("proposed_actions", [])
    approved = [a for a in actions if a.get("review_status") == "approved"]
    if approved:
        categories: dict = {}
        for a in approved:
            cat = a.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        print("\n  Category Breakdown (approved):")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"    {cat:<20} {count}")

        # Photos vs Screenshots split — shows the EXIF-based routing works
        photos_count = categories.get("photos", 0)
        screenshots_count = categories.get("screenshots", 0)
        if photos_count or screenshots_count:
            print(
                f"\n  EXIF split  : "
                f"{photos_count} photos (camera EXIF) / "
                f"{screenshots_count} screenshots (no EXIF)"
            )

    review_queue = final_state.get("review_queue", [])
    if review_queue:
        rq_path = (
            Path("data/review_queue")
            / f"{final_state['run_id']}_review.json"
        )
        rq_path.parent.mkdir(parents=True, exist_ok=True)
        with open(rq_path, "w") as f:
            json.dump(review_queue, f, indent=2, default=str)
        print(f"\n  Review queue written to: {rq_path}")

    print("=" * 60 + "\n")


def _run_for_path(
    recordings_path: str,
    mode: str,
    batch_size: int,
    parallel: bool,
    workers: int,
    inbox_messages: list | None = None,
    enable_messaging: bool = False,
) -> RunState:
    """Build state, invoke graph, return final state."""
    initial_state = build_initial_state(
        recordings_path,
        mode,
        batch_size,
        parallel=parallel,
        workers=workers,
        inbox_messages=inbox_messages,
        enable_messaging=enable_messaging,
    )
    graph = (
        build_graph_with_messaging() if enable_messaging else build_graph()
    )
    return cast(RunState, graph.invoke(initial_state))


def listen_loop(args: argparse.Namespace) -> None:
    """Poll inbox for recording_ready messages and process each one."""
    bus = MessageBus()
    agent_id = "kosmos_organizer"
    print("\n  Miktos Kosmos — Listen Mode")
    print(f"  Agent ID      : {agent_id}")
    print(f"  Poll interval : {args.poll_interval}s")
    print("  Waiting for messages... (Ctrl+C to stop)\n")

    try:
        while True:
            messages = bus.read_pending(agent_id)
            for msg in messages:
                if msg.message_type != "recording_ready":
                    bus.acknowledge(msg)
                    continue

                recordings_path = msg.payload.get("recordings_path", "")
                print(
                    f"  [Inbox] Message from {msg.from_agent}: "
                    f"{msg.message_type}"
                )
                print(f"  Scanning {recordings_path} ...")

                if not Path(recordings_path).exists():
                    print(
                        f"  WARNING: recordings_path does not exist: "
                        f"{recordings_path}"
                    )
                    bus.acknowledge(msg)
                    continue

                final_state = _run_for_path(
                    recordings_path,
                    mode="dry_run",
                    batch_size=args.batch_size,
                    parallel=args.parallel,
                    workers=args.workers,
                    inbox_messages=[msg.to_dict()],
                    enable_messaging=True,
                )
                bus.acknowledge(msg)

                completed = len(final_state.get("completed_tasks", []))
                actions = final_state.get("proposed_actions", [])
                cats = {}
                for a in actions:
                    cat = a.get("category", "unknown")
                    cats[cat] = cats.get(cat, 0) + 1
                category_str = (
                    ", ".join(
                        f"{cat}: {n}" for cat, n in sorted(cats.items())
                    )
                    if cats
                    else "none"
                )
                exit_reason = final_state.get("exit_reason", "unknown")
                print(
                    f"  Exit: {exit_reason} | "
                    f"Completed: {completed} | "
                    f"Category: {category_str}"
                )

                # Post completion back to streamlab_monitor
                bus.post(
                    from_agent=agent_id,
                    to_agent="streamlab_monitor",
                    message_type="recording_organized",
                    payload={
                        "recordings_path": recordings_path,
                        "files_processed": completed,
                        "exit_reason": exit_reason,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    run_id=final_state["run_id"],
                )
                print(
                    "  \u2192 Message posted to streamlab_monitor: "
                    "recording_organized\n"
                )

            time.sleep(args.poll_interval)

    except KeyboardInterrupt:
        print("\n  Listen mode stopped.")


def main():
    args = parse_args()

    if args.listen:
        listen_loop(args)
        return

    if not args.path:
        print("ERROR: --path is required unless --listen is set")
        sys.exit(1)

    root_path = str(Path(args.path).resolve())

    if not Path(root_path).exists():
        print(f"ERROR: Path does not exist: {root_path}")
        sys.exit(1)

    exec_label = (
        f"parallel ({args.workers} workers)" if args.parallel else "sequential"
    )
    print("\n  Miktos Kosmos Media Organizer")
    print(f"  Mode      : {args.mode}")
    print(f"  Execution : {exec_label}")
    print(f"  Target    : {root_path}")
    print(f"  Batch size: {args.batch_size}")

    initial_state = build_initial_state(
        root_path,
        args.mode,
        args.batch_size,
        parallel=args.parallel,
        workers=args.workers,
    )
    graph = build_graph()

    print(f"  Run ID    : {initial_state['run_id']}")
    print("  Starting loop...\n")

    final_state = cast(RunState, graph.invoke(initial_state))

    print("\n-- EXECUTION LOG --")
    for line in final_state.get("logs", []):
        print(f"  {line}")

    print_summary(final_state)


if __name__ == "__main__":
    main()
