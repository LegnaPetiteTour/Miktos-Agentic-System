"""
Miktos Agentic System — Epiphan Pearl Monitor
Entry point for the Epiphan Pearl domain adapter.

Usage:
  python main_epiphan.py
  python main_epiphan.py --handoff --recorder 1
  python main_epiphan.py --duration 60 --poll-interval 10
  python main_epiphan.py --dry-run

The outer loop runs indefinitely (or for --duration seconds).
Each tick: poll Pearl → classify violations → run one engine graph cycle → sleep.

Same outer-loop pattern as main_streamlab.py — zero engine modifications.
"""

import argparse
import json
import time
from pathlib import Path
from typing import cast

import yaml
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from engine.graph.graph_builder import build_graph  # noqa: E402
from engine.graph.state import RunState  # noqa: E402
from engine.messaging.bus import MessageBus  # noqa: E402
from engine.services.state_store import generate_run_id  # noqa: E402
from domains.epiphan.tools.pearl_client import PearlClient  # noqa: E402
from domains.epiphan.tools.pearl_monitor import EpiphanMonitorTool  # noqa: E402
from domains.epiphan.tools.alert_classifier import (  # noqa: E402
    classify_alert,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_thresholds() -> dict:
    config_path = (
        Path(__file__).parent
        / "domains" / "epiphan" / "config" / "thresholds.yaml"
    )
    with open(config_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Miktos Epiphan — Pearl Stream Health Monitor"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Run for this many seconds then exit (0 = run indefinitely)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=0,
        help=(
            "Seconds between Pearl polls "
            "(0 = use value from thresholds.yaml)"
        ),
    )
    parser.add_argument(
        "--handoff",
        action="store_true",
        help=(
            "Publish a recording_stopped event to all registered subscribers "
            "when a recording_stopped alert is detected."
        ),
    )
    parser.add_argument(
        "--recorder",
        default="1",
        help="Pearl recorder/channel ID to monitor and pull from (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Instantiate the monitor but exit immediately (for smoke tests).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# State builder
# ---------------------------------------------------------------------------

def _has_recording_stopped(final_state: RunState) -> bool:
    """Return True if a recording_stopped alert is approved."""
    actions = final_state.get("proposed_actions", [])
    return any(
        a.get("category") == "recording_stopped"
        for a in actions
    )


def build_tick_state(
    tick: int,
    monitor: EpiphanMonitorTool,
) -> RunState:
    """Build one graph tick state. The monitor is the scanner."""
    return {
        "run_id": generate_run_id(),
        "domain": "epiphan",
        "goal": f"Monitor Pearl stream health — tick {tick}",
        "mode": "dry_run",
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
        "agent_id": "epiphan_monitor",
        "inbox_messages": [],
        "context": {
            "root_path": "pearl://stream",
            "batch_size": 50,
            "thresholds": {
                "auto_approve": 0.90,
                "review_queue": 0.60,
            },
            "exhausted_threshold": 0.20,
            "tools": {
                "scanner": monitor,
                "classifier": classify_alert,
            },
            "tick": tick,
        },
    }


# ---------------------------------------------------------------------------
# Tick summary printer
# ---------------------------------------------------------------------------

def print_tick_summary(tick: int, final_state: RunState) -> None:
    actions = final_state.get("proposed_actions", [])
    approved = [a for a in actions if a.get("review_status") == "approved"]
    queued = [a for a in actions if a.get("review_status") == "queued"]
    errors = final_state.get("errors", [])

    status_icon = "🔴" if approved else ("⚠️ " if queued else "✅")

    alert_summary = ""
    if approved or queued:
        cats: dict = {}
        for a in actions:
            cat = a.get("category", "unknown")
            cats[cat] = cats.get(cat, 0) + 1
        alert_summary = "  " + ", ".join(
            f"{cat}×{n}" for cat, n in sorted(cats.items())
        )

    print(
        f"  [{tick:>3}] {status_icon} "
        f"exit={final_state.get('exit_reason', '?')} | "
        f"alerts={len(actions)} "
        f"(approved={len(approved)}, queued={len(queued)}, "
        f"errors={len(errors)})"
        f"{alert_summary}"
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


# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------

def print_final_summary(
    ticks: int,
    total_alerts: int,
    elapsed_seconds: float,
) -> None:
    print("\n" + "=" * 60)
    print("  MIKTOS EPIPHAN — SESSION SUMMARY")
    print("=" * 60)
    print(f"  Ticks completed : {ticks}")
    print(f"  Total alerts    : {total_alerts}")
    print(f"  Elapsed         : {elapsed_seconds:.1f}s")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main outer loop
# ---------------------------------------------------------------------------

def main() -> None:
    config = load_thresholds()
    args = parse_args()

    poll_interval = (
        args.poll_interval or config.get("poll_interval_seconds", 5)
    )
    stream_thresholds: dict = config.get("stream", {})
    recorder_id = args.recorder

    client = PearlClient()
    monitor = EpiphanMonitorTool(
        thresholds=stream_thresholds,
        client=client,
        recorder_id=recorder_id,
        channel_id=recorder_id,
    )
    graph = build_graph()

    print("\n  Miktos Epiphan Monitor")
    print(f"  Recorder/Channel : {recorder_id}")
    print(f"  Poll interval    : {poll_interval}s")
    if args.duration:
        print(f"  Duration         : {args.duration}s")
    else:
        print("  Duration         : indefinite (Ctrl+C to stop)")
    if args.handoff:
        print("  Handoff          : enabled → publish(recording_stopped)")
    print()

    if args.dry_run:
        print("  Dry run — exiting cleanly.")
        return

    tick = 0
    total_alerts = 0
    start_time = time.time()

    was_recording_active = False
    handoff_published = False

    try:
        while True:
            elapsed = time.time() - start_time
            if args.duration and elapsed >= args.duration:
                print(f"\n  Duration {args.duration}s reached. Exiting cleanly.")
                break

            tick += 1
            initial_state = build_tick_state(tick, monitor)
            final_state = cast(RunState, graph.invoke(initial_state))

            alert_count = len(final_state.get("proposed_actions", []))
            total_alerts += alert_count
            print_tick_summary(tick, final_state)

            # Edge-triggered handoff: publish recording_stopped only on
            # the active → stopped transition (once per session).
            if args.handoff:
                recording_stopped_now = _has_recording_stopped(final_state)
                if not recording_stopped_now:
                    was_recording_active = True
                    handoff_published = False
                elif was_recording_active and not handoff_published:
                    bus = MessageBus()
                    delivered = bus.publish(
                        topic="recording_stopped",
                        from_agent="epiphan_monitor",
                        payload={
                            "recorder_id": recorder_id,
                            "trigger_run_id": final_state["run_id"],
                            "timestamp": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                            ),
                        },
                        run_id=final_state["run_id"],
                    )
                    print(
                        f"  → Published recording_stopped"
                        f" to {len(delivered)} subscriber(s)"
                    )
                    handoff_published = True
                    was_recording_active = False

            if args.duration:
                remaining = args.duration - (time.time() - start_time)
                sleep_for = min(poll_interval, max(0.0, remaining))
            else:
                sleep_for = poll_interval

            if sleep_for > 0:
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        print("\n  Interrupted. Printing final summary...")

    print_final_summary(tick, total_alerts, time.time() - start_time)


if __name__ == "__main__":
    main()
