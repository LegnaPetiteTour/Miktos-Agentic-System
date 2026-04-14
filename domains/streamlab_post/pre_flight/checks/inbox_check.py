"""
inbox_check — Pre-flight Check 4 (hard failure).

Inspects data/messages/post_stream_processor/pending/ for leftover
.json message files. Stale messages from a previous run will be
processed by the coordinator immediately after the next stream ends,
producing false-success results for the wrong session.

Fail fast: if any .json files are present, block the operator and
require manual clearing before streaming.
"""

from pathlib import Path


_PENDING_DIR = Path("data/messages/post_stream_processor/pending")


def run(dry_run: bool = False, pending_dir: str | Path | None = None) -> dict:
    """
    Check for stale pending messages.

    Args:
        dry_run:     If True return ok without filesystem access.
        pending_dir: Override pending directory path (used in tests).

    Returns:
        {"name": "inbox", "status": "ok"|"fail", "message": str}
    """
    if dry_run:
        return {
            "name": "inbox",
            "status": "ok",
            "message": "Inbox — empty (dry-run)",
        }

    inbox = Path(pending_dir) if pending_dir else _PENDING_DIR

    if not inbox.exists():
        # No directory means no pending messages — this is fine.
        return {
            "name": "inbox",
            "status": "ok",
            "message": "Inbox — empty (pending directory does not exist)",
        }

    stale = list(inbox.glob("*.json"))
    count = len(stale)

    if count > 0:
        return {
            "name": "inbox",
            "status": "fail",
            "message": (
                f"Inbox — {count} stale message(s) pending — "
                "clear inbox before streaming"
            ),
        }

    return {
        "name": "inbox",
        "status": "ok",
        "message": "Inbox — empty",
    }
