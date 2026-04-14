"""
process_check — Pre-flight Check 5 (hard failure).

Detects an already-running `main_streamlab.py --handoff` process.
Two concurrent instances of the monitor will both publish
`recording_stopped` at stream end, resulting in duplicate coordinator
executions and double-processed sessions.

Uses psutil to scan all running processes for a matching cmdline.
"""

import psutil  # type: ignore[import]


def run(dry_run: bool = False) -> dict:
    """
    Check for a duplicate main_streamlab.py --handoff process.

    Args:
        dry_run: If True return ok without scanning processes.

    Returns:
        {"name": "duplicate_process", "status": "ok"|"fail", "message": str}
    """
    if dry_run:
        return {
            "name": "duplicate_process",
            "status": "ok",
            "message": "Duplicate process — none found (dry-run)",
        }

    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmd_str = " ".join(cmdline)
            if "main_streamlab.py" in cmd_str and "--handoff" in cmd_str:
                pid = proc.info["pid"]
                return {
                    "name": "duplicate_process",
                    "status": "fail",
                    "message": (
                        f"main_streamlab.py --handoff already running "
                        f"(PID {pid}) — stop it first"
                    ),
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "name": "duplicate_process",
        "status": "ok",
        "message": "Duplicate process — none found",
    }
