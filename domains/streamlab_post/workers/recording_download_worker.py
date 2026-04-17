"""
recording_download_worker.py — Pre-Stage 1 worker for Pearl sessions.

Downloads the most recently completed recording from an Epiphan Pearl
device via its REST API to a local path, after which the post-stream
pipeline continues identically to the OBS workflow.
"""

import os
from pathlib import Path

from domains.epiphan.tools.pearl_client import PearlClient


class RecordingDownloadWorker:
    """
    Pull the most recently completed recording from Pearl.

    Pre-Stage 1 worker — runs only when session_config.yaml has
    hardware: epiphan. Its output (file_path) is injected into the
    standard Stage 1 payload so all downstream workers are unchanged.

    Never raises.
    """

    name = "recording_download"

    def run(self, payload: dict) -> dict:
        """
        Pull the most recently completed Pearl recording to local disk.

        Payload keys:
          pearl_host        str   Pearl IP (falls back to PEARL_HOST env var)
          pearl_recorder_id str   Recorder ID — same value as channel_en
          download_dir      str   Local directory to save to (created if absent)
          dry_run           bool

        Returns:
          {"success": True, "file_path": str, "file_size_bytes": int}
          {"success": False, "error": str}
        """
        try:
            return self._run(payload)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _run(self, payload: dict) -> dict:
        dry_run: bool = payload.get("dry_run", False)
        recorder_id: str = str(payload.get("pearl_recorder_id", "1"))
        download_dir: str = payload.get(
            "download_dir",
            os.path.expanduser("~/Downloads/pearl-recordings"),
        )

        # Override PEARL_HOST if provided in payload
        pearl_host = payload.get("pearl_host", "")
        if pearl_host:
            os.environ.setdefault("PEARL_HOST", pearl_host)

        if dry_run:
            fake_path = str(
                Path(download_dir) / "dry_run_recording.mp4"
            )
            return {
                "success": True,
                "dry_run": True,
                "file_path": fake_path,
                "file_size_bytes": 0,
            }

        client = PearlClient()

        # Find the most recently completed file for this recorder
        files = client.get_recorder_files(recorder_id)
        if not files:
            return {
                "success": False,
                "error": (
                    f"No files found for recorder {recorder_id!r}"
                ),
            }

        # Pick the last file in the list (most recent completed recording).
        # Pearl returns files in chronological order.
        latest = files[-1]
        file_id = str(latest.get("id", ""))
        file_name = latest.get("name", f"{file_id}.mp4")

        if not file_id:
            return {
                "success": False,
                "error": "Could not determine file ID from recorder file list",
            }

        dest_path = str(Path(os.path.expanduser(download_dir)) / file_name)
        local_path = client.download_recording(recorder_id, file_id, dest_path)

        file_size = Path(local_path).stat().st_size
        return {
            "success": True,
            "file_path": local_path,
            "file_size_bytes": file_size,
        }
