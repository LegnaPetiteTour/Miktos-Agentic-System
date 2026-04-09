"""
Workers for the Phase 4c session coordinator.

Each worker:
  - Has a unique `name` class attribute
  - Implements run(payload: dict) -> dict
  - Is independently testable without the coordinator
  - Never raises — returns {"success": False, "error": ...} on failure
  - Has no awareness of other workers or the coordinator's goal

Slot → Worker mapping:
  organize  → KosmosWorker   (classify and propose organized path)
  thumbnail → ThumbnailWorker (extract first-frame JPEG via ffmpeg)
  metadata  → MetadataWorker  (write session.json via ffprobe)
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from domains.kosmos.tools.media_classifier import classify_media_file
from domains.kosmos.tools.media_metadata import extract_media_metadata


class KosmosWorker:
    """
    Classifies the recording file using the Kosmos media classifier.
    Returns category, confidence, method, and proposed organized path.
    Never moves the file — proposes path only (dry_run semantics).
    """

    name = "kosmos_worker"

    def run(self, payload: dict) -> dict:
        file_path = payload.get("file_path", "")
        output_dir = payload.get("output_dir", "")

        try:
            path = Path(file_path)
            meta = extract_media_metadata(file_path)
            file_meta = {
                "path": file_path,
                "suffix": path.suffix.lower(),
                "mime_type": meta.get("mime_type", "unknown"),
            }
            result = classify_media_file(file_meta)
            category = result["category"]
            confidence = result["confidence"]
            method = result["method"]
            proposed_path = (
                str(Path(output_dir) / category / path.name) if output_dir else ""
            )
            return {
                "success": True,
                "category": category,
                "confidence": confidence,
                "method": method,
                "proposed_path": proposed_path,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class ThumbnailWorker:
    """
    Extracts a thumbnail from the recording using ffmpeg.
    Seeks to 1 second in, extracts one frame as JPEG.

    Falls back gracefully if ffmpeg fails or the file is not a video.
    Never raises.
    """

    name = "thumbnail_worker"

    def run(self, payload: dict) -> dict:
        file_path = payload.get("file_path", "")
        output_dir = payload.get("output_dir", "")

        thumbnail_path = (
            str(Path(output_dir) / "thumbnail.jpg")
            if output_dir
            else "/tmp/thumbnail.jpg"
        )
        try:
            Path(thumbnail_path).parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-i", file_path,
                    "-ss", "00:00:01",
                    "-vframes", "1",
                    "-q:v", "2",
                    thumbnail_path,
                    "-y",
                    "-loglevel", "error",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                error = result.stderr.strip() or "ffmpeg exited non-zero"
                return {
                    "success": False,
                    "error": error,
                    "thumbnail_path": thumbnail_path,
                }
            if not Path(thumbnail_path).exists():
                return {
                    "success": False,
                    "error": "ffmpeg succeeded but output file missing",
                }
            return {"success": True, "thumbnail_path": thumbnail_path}
        except FileNotFoundError:
            return {"success": False, "error": "ffmpeg not found on PATH"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class MetadataWorker:
    """
    Reads file info and stream duration via ffprobe; writes session.json.
    Always succeeds — a session without duration is still a valid session.
    Never raises.
    """

    name = "metadata_worker"

    def run(self, payload: dict) -> dict:
        file_path = payload.get("file_path", "")
        output_dir = payload.get("output_dir", "")
        session_id = payload.get("session_id", "")
        scene = payload.get("scene", "")
        thumbnail_path = payload.get("thumbnail_path", "")
        category = payload.get("category", "")
        trigger_run_id = payload.get("trigger_run_id", "")

        metadata_path = (
            str(Path(output_dir) / "session.json")
            if output_dir
            else "/tmp/session.json"
        )
        duration_seconds = 0.0
        file_size_bytes = 0

        try:
            p = Path(file_path)
            if p.exists():
                file_size_bytes = p.stat().st_size
        except OSError:
            pass

        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    file_path,
                ],
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                probe_data = json.loads(probe.stdout)
                duration_str = probe_data.get("format", {}).get("duration", "0")
                try:
                    duration_seconds = float(duration_str)
                except ValueError:
                    duration_seconds = 0.0
        except Exception:
            pass

        session_data = {
            "session_id": session_id,
            "recording_path": file_path,
            "scene": scene,
            "duration_seconds": round(duration_seconds, 3),
            "file_size_bytes": file_size_bytes,
            "thumbnail_path": thumbnail_path,
            "category": category,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger_run_id": trigger_run_id,
        }

        try:
            Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_path, "w") as f:
                json.dump(session_data, f, indent=2)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        return {
            "success": True,
            "metadata_path": metadata_path,
            "duration_seconds": round(duration_seconds, 3),
        }
