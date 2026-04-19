"""
AudioExtractWorker — Phase 5 post-stream closure.

Extracts audio from the recording file as a 192k MP3 using ffmpeg.
The MP3 is passed to TranscriptWorker in Stage 2.

This is a Stage 1 required slot.
"""

import subprocess
from pathlib import Path


class AudioExtractWorker:
    """
    Extract audio from the recording as MP3.

    ffmpeg command:
      ffmpeg -i <file_path> -vn -acodec libmp3lame -ar 44100 -ab 192k
             <output_dir>/audio.mp3 -y -loglevel error

    Never raises — returns success: False with stderr on failure.
    """

    name = "audio_extract_worker"

    def run(self, payload: dict) -> dict:
        """
        Extract audio from the recording as MP3.

        Payload keys:
          file_path (str)   — path to the recording file
          output_dir (str)  — directory to write audio.mp3 into
          dry_run (bool)    — if True, skip ffmpeg, return mock result

        Returns:
          {success, mp3_path, file_size_bytes}
          or {success: False, error: str}
        """
        file_path = payload.get("file_path", "")
        output_dir = payload.get("output_dir", "")
        output_suffix = payload.get("output_suffix", "")
        dry_run = payload.get("dry_run", False)

        if dry_run:
            mp3_path = str(
                Path(output_dir or "/tmp") / f"audio{output_suffix}.mp3"
            )
            return {
                "success": True,
                "dry_run": True,
                "mp3_path": mp3_path,
                "file_size_bytes": 134_217_728,  # 128 MB placeholder
            }

        if not file_path:
            return {"success": False, "error": "file_path not provided in payload"}
        if not output_dir:
            return {"success": False, "error": "output_dir not provided in payload"}

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        mp3_file = out_dir / f"audio{output_suffix}.mp3"

        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-i", str(file_path),
                    "-vn",
                    "-acodec", "libmp3lame",
                    "-ar", "44100",
                    "-ab", "192k",
                    str(mp3_file),
                    "-y",
                    "-loglevel", "error",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except FileNotFoundError:
            return {"success": False, "error": "ffmpeg not found — install ffmpeg"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "ffmpeg audio extraction timed out"}

        if result.returncode != 0:
            stderr = result.stderr.strip() or "unknown ffmpeg error"
            return {"success": False, "error": f"ffmpeg failed: {stderr}"}

        if not mp3_file.exists() or mp3_file.stat().st_size == 0:
            return {
                "success": False,
                "error": "ffmpeg completed but output MP3 is missing or empty",
            }

        return {
            "success": True,
            "mp3_path": str(mp3_file),
            "file_size_bytes": mp3_file.stat().st_size,
        }
