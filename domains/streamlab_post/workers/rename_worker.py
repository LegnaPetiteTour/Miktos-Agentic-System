"""
FileRenameWorker — Phase 5 post-stream closure.

Applies the Miktos session naming convention and organizes all
artifacts into a dated session folder under data/sessions/.

Naming convention: YYYY-MM-DD_EventName_NNN
  - NNN is a zero-padded 3-digit sequence number scanned from data/sessions/
  - One folder per stream event; sequence number handles same-day repeats

Files organized:
  recording  → YYYY-MM-DD_EventName_NNN_EN.mp4 (preserves original extension)
  audio      → YYYY-MM-DD_EventName_NNN.mp3
  transcript → YYYY-MM-DD_EventName_NNN_transcript.txt
  thumbnail  → YYYY-MM-DD_EventName_NNN_thumbnail.jpg (if exists)
  session.json stays as session.json

This is a Stage 3 slot — receives paths from all prior stages.
"""

import json
import re
import shutil
from datetime import date
from pathlib import Path


class FileRenameWorker:
    """
    Apply naming convention and organize all session artifacts.

    Uses shutil.move() for cross-filesystem safety.
    Creates the final folder, moves all files, updates session.json paths.
    Never raises — returns success: False with error details on failure.
    """

    name = "file_rename_worker"

    def run(self, payload: dict) -> dict:
        """
        Rename and organize session artifacts.

        Payload keys:
          recording_path (str)   — original recording file path
          mp3_path (str)         — extracted audio MP3 path (may be empty)
          transcript_path (str)  — transcript text file path (may be empty)
          thumbnail_path (str)   — thumbnail JPEG path (may be empty)
          event_name (str)       — event name (no spaces; hyphens OK)
          session_date (str)     — YYYY-MM-DD; auto-filled from today if blank
          sessions_dir (str)     — base sessions directory (default data/sessions)
          dry_run (bool)         — if True, compute paths only, do not move files

        Returns:
          {success, final_folder, renamed_files: {slot: new_path}}
          or {success: False, error: str}
        """
        recording_path = payload.get("recording_path", "")
        mp3_path = payload.get("mp3_path", "")
        transcript_path = payload.get("transcript_path", "")
        thumbnail_path = payload.get("thumbnail_path", "")
        event_name = payload.get("event_name", "Event")
        session_date = payload.get("session_date", "") or date.today().isoformat()
        sessions_dir = Path(payload.get("sessions_dir", "data/sessions"))
        dry_run = payload.get("dry_run", False)

        # Sanitize event name for filesystem safety
        safe_event = re.sub(r"[^\w\-]", "-", event_name).strip("-")

        # Determine next sequence number
        prefix = f"{session_date}_{safe_event}_"
        existing = sorted(
            d.name
            for d in sessions_dir.glob(f"{prefix}*")
            if d.is_dir()
        )
        seq = len(existing) + 1
        session_name = f"{prefix}{seq:03d}"
        final_folder = sessions_dir / session_name

        if dry_run:
            ext = Path(recording_path).suffix if recording_path else ".mp4"
            return {
                "success": True,
                "dry_run": True,
                "final_folder": str(final_folder),
                "renamed_files": {
                    "recording": str(final_folder / f"{session_name}_EN{ext}"),
                    "audio": str(final_folder / f"{session_name}.mp3"),
                    "transcript": str(final_folder / f"{session_name}_transcript.txt"),
                    "thumbnail": str(final_folder / f"{session_name}_thumbnail.jpg"),
                },
            }

        try:
            final_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {
                "success": False,
                "error": f"Could not create session folder {final_folder}: {exc}",
            }

        renamed: dict[str, str] = {}

        def _move(src: str, dst: Path) -> str | None:
            """Move src to dst; return new path or None if src missing."""
            if not src or not Path(src).exists():
                return None
            try:
                shutil.move(src, dst)
                return str(dst)
            except (OSError, shutil.Error) as exc:
                raise RuntimeError(f"Failed to move {src} to {dst}: {exc}") from exc

        try:
            if recording_path and Path(recording_path).exists():
                ext = Path(recording_path).suffix
                dst = final_folder / f"{session_name}_EN{ext}"
                new_path = _move(recording_path, dst)
                if new_path:
                    renamed["recording"] = new_path

            mp3_new = _move(mp3_path, final_folder / f"{session_name}.mp3")
            if mp3_new:
                renamed["audio"] = mp3_new

            txt_new = _move(
                transcript_path,
                final_folder / f"{session_name}_transcript.txt",
            )
            if txt_new:
                renamed["transcript"] = txt_new

            thumb_new = _move(
                thumbnail_path,
                final_folder / f"{session_name}_thumbnail.jpg",
            )
            if thumb_new:
                renamed["thumbnail"] = thumb_new

        except RuntimeError as exc:
            return {"success": False, "error": str(exc)}

        # Update session.json with new artifact paths if it exists in any
        # of the source directories
        for src_dir in {
            Path(p).parent
            for p in [recording_path, mp3_path, transcript_path]
            if p
        }:
            session_json = src_dir / "session.json"
            dest_json = final_folder / "session.json"
            if session_json.exists() and not dest_json.exists():
                try:
                    data = json.loads(session_json.read_text())
                    data["final_folder"] = str(final_folder)
                    data["renamed_files"] = renamed
                    dest_json.write_text(json.dumps(data, indent=2))
                    session_json.unlink(missing_ok=True)
                except (OSError, json.JSONDecodeError):
                    pass  # best-effort; don't fail the slot

        return {
            "success": True,
            "final_folder": str(final_folder),
            "renamed_files": renamed,
        }
