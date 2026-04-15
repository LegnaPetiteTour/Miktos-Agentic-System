"""
run_session.py — Single launcher for a stream session.

Enforces correct order: pre-flight → post-stream listener → stream monitor.

Usage:
    python scripts/run_session.py [--config PATH] [--poll-interval N]
"""

import argparse
import signal
import subprocess
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

from domains.streamlab_post.pre_flight.checker import PreFlightChecker

load_dotenv()

# Repo root is one level up from scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent


def _forward_output(proc: subprocess.Popen) -> None:
    """Forward subprocess stdout to our terminal (runs in daemon thread)."""
    for line in proc.stdout:
        print(line.decode(), end="", flush=True)


def run(config_path: Path | None, poll_interval: int) -> int:
    # Step 1 — Pre-flight
    print("\n  Miktos Run Session")
    print("  ─────────────────────────────────────────")

    config_kwarg = {"config_path": config_path} if config_path else {}
    results = PreFlightChecker().run(dry_run=False, **config_kwarg)
    failures = [r for r in results if r["status"] == "fail"]

    if failures:
        for r in failures:
            print(f"  ❌  {r['message']}")
        print("\nPre-flight failed. Fix the above before streaming.")
        return 1

    # Step 2 — Start post-stream listener
    post = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "main_post_stream.py"),
         "--poll-interval", str(poll_interval)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
    )

    if post.poll() is not None:
        print("Failed to start main_post_stream.py", file=sys.stderr)
        return 1

    # Forward post-stream output to terminal via daemon thread
    threading.Thread(target=_forward_output, args=(post,), daemon=True).start()

    print(f"✅  Post-stream listener started (PID {post.pid})")
    print("Starting stream monitor… (Ctrl+C to stop)\n")

    # Step 3 — Stream monitor (foreground, blocks until OBS/operator stops it)
    monitor = None
    try:
        monitor = subprocess.run(
            [sys.executable, str(REPO_ROOT / "main_streamlab.py"), "--handoff"],
            cwd=str(REPO_ROOT),
        )
    except KeyboardInterrupt:
        pass
    finally:
        # Step 4 — Cleanup
        if post.poll() is None:
            post.send_signal(signal.SIGTERM)
            try:
                post.wait(timeout=5)
            except subprocess.TimeoutExpired:
                post.kill()
        print("\nSession ended. Post-stream listener stopped.")

    return monitor.returncode if monitor is not None else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a full stream session.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--poll-interval", type=int, default=5)
    args = parser.parse_args()
    sys.exit(run(args.config, args.poll_interval))


if __name__ == "__main__":
    main()
