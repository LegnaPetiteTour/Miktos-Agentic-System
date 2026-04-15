"""
run_session.py — Single launcher for a stream session.

Enforces correct order: pre-flight → post-stream listener → stream monitor.

Usage:
    python scripts/run_session.py [--config PATH] [--poll-interval N]
"""

import argparse
import re
import signal
import subprocess
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

from domains.streamlab_post.pre_flight.checker import PreFlightChecker

try:
    from scripts.session_status import StatusDisplay
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False

load_dotenv()

# Repo root is one level up from scripts/
REPO_ROOT = Path(__file__).resolve().parent.parent


# Patterns for extracting status updates from coordinator/worker log lines
_RE_STAGE = re.compile(r"Stage\s+(\d+)", re.IGNORECASE)
_RE_SLOT_OK = re.compile(
    r"(backup_verify|youtube_en|audio_extract|translate"
    r"|transcript|youtube_fr|file_rename|notify|report)"
    r".*?(success|ok|done|complete|\u2705)",
    re.IGNORECASE,
)
_RE_SLOT_FAIL = re.compile(
    r"(backup_verify|youtube_en|audio_extract|translate"
    r"|transcript|youtube_fr|file_rename|notify|report)"
    r".*?(fail|error|\u274c)",
    re.IGNORECASE,
)
_RE_SLOT_RUNNING = re.compile(
    r"Running\s+(backup_verify|youtube_en|audio_extract|translate"
    r"|transcript|youtube_fr|file_rename|notify|report)",
    re.IGNORECASE,
)
_RE_REPORT_PATH = re.compile(r"report[:\s]+([^\s]+\.html)", re.IGNORECASE)

# Map slot name → stage number
_SLOT_STAGE: dict[str, int] = {
    "backup_verify": 1, "youtube_en": 1, "audio_extract": 1,
    "translate": 2, "transcript": 2,
    "youtube_fr": 3, "file_rename": 3,
    "notify": 4, "report": 4,
}


def _update_display_from_line(display: "StatusDisplay", text: str) -> None:
    """Parse a log line and update the display state if patterns match."""
    # Stream state
    tl = text.lower()
    if "monitoring" in tl or "armed" in tl:
        display.set_stream_state("armed")
    elif "recording_stopped" in tl:
        display.set_stream_state("recording_stopped")

    # Slot running
    m = _RE_SLOT_RUNNING.search(text)
    if m:
        slot = m.group(1).lower()
        display.set_stage(_SLOT_STAGE.get(slot, 1), slot, "running")
        return

    # Slot ok
    m = _RE_SLOT_OK.search(text)
    if m:
        slot = m.group(1).lower()
        display.set_stage(_SLOT_STAGE.get(slot, 1), slot, "ok")
        return

    # Slot failed
    m = _RE_SLOT_FAIL.search(text)
    if m:
        slot = m.group(1).lower()
        display.set_stage(_SLOT_STAGE.get(slot, 1), slot, "failed")
        return

    # Session done / report path
    m = _RE_REPORT_PATH.search(text)
    if m:
        display.set_session_done(m.group(1))
        display.set_stream_state("done")


def _forward_output(
    proc: subprocess.Popen, display: "StatusDisplay | None" = None
) -> None:
    """Forward subprocess stdout to our terminal (runs in daemon thread)."""
    assert proc.stdout is not None
    for line in proc.stdout:
        text = line.decode()
        print(text, end="", flush=True)  # raw output always printed
        if display is not None:
            try:
                _update_display_from_line(display, text)
            except Exception:
                pass  # display errors must never crash the session


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

    # Initialise status display (no-op wrapper when rich is absent)
    display: "StatusDisplay | None" = None
    if _RICH_AVAILABLE:
        display = StatusDisplay()
        display.set_preflight(True)
        display.start()

    # Step 2 — Start post-stream listener
    post = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "main_post_stream.py"),
         "--poll-interval", str(poll_interval)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
    )

    if post.poll() is not None:
        if display is not None:
            display.stop()
        print("Failed to start main_post_stream.py", file=sys.stderr)
        return 1

    # Forward post-stream output to terminal via daemon thread
    threading.Thread(
        target=_forward_output, args=(post, display), daemon=True
    ).start()

    print(f"✅  Post-stream listener started (PID {post.pid})")
    print("Starting stream monitor… (Ctrl+C to stop)\n")

    # Step 3 — Stream monitor (foreground, blocks until OBS/operator stops it)
    monitor = None
    try:
        monitor = subprocess.run(
            [sys.executable, str(REPO_ROOT / "main_streamlab.py"), "--handoff"],
            cwd=str(REPO_ROOT),
        )
        if display is not None:
            display.set_stream_state("done")
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
        if display is not None:
            display.stop()
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
