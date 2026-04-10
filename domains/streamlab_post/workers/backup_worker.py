"""
BackupVerificationWorker — Phase 5 post-stream closure.

Verifies the local recording file exists and is valid before any
downstream processing begins. This is a Stage 1 required slot — if
it fails, the coordinator stops immediately.

Checks performed:
  1. File path exists on disk
  2. File size exceeds min_size_bytes (catches empty/corrupt files)
  3. ffprobe can open the file (catches truncated recordings)
"""

import json
import subprocess
from pathlib import Path


class BackupVerificationWorker:
    """
    Verify the local recording file exists and is valid.

    Required Stage 1 slot. Failure stops the coordinator immediately.
    Never raises — returns success: False with error details on failure.
    """

    name = "backup_verification_worker"

    def run(self, payload: dict) -> dict:
        """
        Verify the local recording file exists and is valid.

        Payload keys:
          file_path (str)          — absolute path to the recording file
          min_size_bytes (int)     — minimum acceptable file size (default 1MB)
          dry_run (bool)           — if True, skip ffprobe, return mock result

        Returns:
          {success, file_path, file_size_bytes, duration_seconds}
          or {success: False, error: str}
        """
        file_path = payload.get("file_path", "")
        min_size_bytes = payload.get("min_size_bytes", 1_048_576)
        dry_run = payload.get("dry_run", False)

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "file_path": file_path or "/Users/atorrella/Movies/stream.mkv",
                "file_size_bytes": 1_288_000_000,
                "duration_seconds": 3847.0,
            }

        if not file_path:
            return {"success": False, "error": "file_path not provided in payload"}

        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"Recording file not found: {file_path}",
            }

        file_size = path.stat().st_size
        if file_size < min_size_bytes:
            return {
                "success": False,
                "error": (
                    f"Recording file too small: {file_size} bytes "
                    f"(minimum {min_size_bytes} bytes) — may be empty or corrupt"
                ),
            }

        # Run ffprobe to validate the file is not truncated / corrupt
        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            return {"success": False, "error": "ffprobe not found — install ffmpeg"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "ffprobe timed out after 30s"}

        if probe.returncode != 0:
            stderr = probe.stderr.strip() or "unknown ffprobe error"
            return {
                "success": False,
                "error": f"ffprobe validation failed: {stderr}",
            }

        duration_seconds: float = 0.0
        try:
            probe_data = json.loads(probe.stdout)
            duration_seconds = float(
                probe_data.get("format", {}).get("duration", 0)
            )
        except (json.JSONDecodeError, ValueError):
            pass  # duration is a bonus — don't fail on parse error

        return {
            "success": True,
            "file_path": str(path),
            "file_size_bytes": file_size,
            "duration_seconds": duration_seconds,
        }
