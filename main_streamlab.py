"""
Miktos Agentic System — StreamLab Monitor
Entry point for Domain 3.

Usage:
  python main_streamlab.py
  python main_streamlab.py --duration 60       # run for 60 seconds then exit
  python main_streamlab.py --poll-interval 10  # poll every 10 seconds

The outer loop runs indefinitely (or for --duration seconds).
Each tick: poll OBS → classify violations → run one engine graph cycle → sleep.

Outer loop pattern
──────────────────
The engine graph (engine/graph/) is called identically to all other domains.
Zero engine modifications were required. The "continuous" nature lives here,
not inside the engine. Each poll cycle is one graph.invoke() call.

The OBSMonitorTool is the scanner. It connects to OBS, queries stream health,
and returns alert items shaped like file-scanner output so the planner node
requires no changes. An empty items list (healthy stream) produces zero tasks;
the graph completes immediately and the outer loop sleeps until the next tick.
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
from engine.services.state_store import generate_run_id  # noqa: E402
from domains.streamlab.tools.obs_monitor import OBSMonitorTool  # noqa: E402
from domains.streamlab.tools.alert_classifier import classify_alert  # noqa: E402


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_thresholds() -> dict:
    config_path = (
        Path(__file__).parent
        / "domains" / "streamlab" / "config" / "thresholds.yaml"
    )
    with open(config_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Miktos StreamLab — OBS Stream Health Monitor"
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
        help="Seconds between OBS polls (0 = use value from thresholds.yaml)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# State builder
# ---------------------------------------------------------------------------

def build_tick_state(
    tick: int,
    monitor: OBSMonitorTool,
) -> RunState:
    """Build one graph tick state. The monitor is the scanner."""
    return {
        "run_id": generate_run_id(),
        "domain": "streamlab",
        "goal": f"Monitor OBS stream health — tick {tick}",
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
        "context": {
            "root_path": "obs://stream",  # virtual URI — OBSMonitorTool ignores it
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

    # Write review queue items to disk if any
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
    print("  MIKTOS STREAMLAB — SESSION SUMMARY")
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

    poll_interval = args.poll_interval or config.get("poll_interval_seconds", 5)
    stream_thresholds: dict = config.get("stream", {})

    monitor = OBSMonitorTool(thresholds=stream_thresholds)
    graph = build_graph()

    print("\n  Miktos StreamLab Monitor")
    print(f"  Poll interval : {poll_interval}s")
    if args.duration:
        print(f"  Duration      : {args.duration}s")
    else:
        print("  Duration      : indefinite (Ctrl+C to stop)")
    print()

    tick = 0
    total_alerts = 0
    start_time = time.time()

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

            # Sleep, but honour --duration if close to the limit
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
