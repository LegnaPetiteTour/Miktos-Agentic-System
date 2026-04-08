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
from pathlib import Path
from typing import cast

from engine.graph.graph_builder import build_graph
from engine.graph.state import RunState
from engine.services.state_store import generate_run_id
from engine.tools.shared_tools import FileScannerTool
from domains.kosmos.tools.media_classifier import classify_media_file


def parse_args():
    parser = argparse.ArgumentParser(
        description="Miktos Kosmos — Media Library Organizer"
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Root folder to scan and organize",
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
    return parser.parse_args()


def build_initial_state(
    root_path: str,
    mode: str,
    batch_size: int,
) -> RunState:
    return {
        "run_id": generate_run_id(),
        "domain": "kosmos",
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
    print(f"  Run ID     : {final_state['run_id']}")
    print(f"  Mode       : {final_state['mode']}")
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


def main():
    args = parse_args()
    root_path = str(Path(args.path).resolve())

    if not Path(root_path).exists():
        print(f"ERROR: Path does not exist: {root_path}")
        sys.exit(1)

    print("\n  Miktos Kosmos Media Organizer")
    print(f"  Mode      : {args.mode}")
    print(f"  Target    : {root_path}")
    print(f"  Batch size: {args.batch_size}")

    initial_state = build_initial_state(
        root_path,
        args.mode,
        args.batch_size,
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
