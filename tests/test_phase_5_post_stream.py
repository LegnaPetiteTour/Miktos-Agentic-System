"""
Phase 5 — Post-Stream Closure Engine tests.

All 8 tests run without real API credentials by using dry_run=True or
by verifying credential-missing error returns. Tests that require ffmpeg
create a real 2-second MP4 via ffmpeg lavfi so the worker exercises real
subprocess paths.

Tests:
  1. test_backup_worker_passes_valid_file
  2. test_backup_worker_fails_missing_file
  3. test_audio_worker_extracts_mp3
  4. test_transcript_worker_handles_missing_key
  5. test_youtube_worker_handles_missing_credentials
  6. test_translation_worker_handles_missing_key
  7. test_rename_worker_applies_naming_convention
  8. test_notify_worker_skips_when_not_configured
"""

import subprocess
from pathlib import Path

import pytest

from domains.streamlab_post.workers.audio_worker import AudioExtractWorker
from domains.streamlab_post.workers.backup_worker import BackupVerificationWorker
from domains.streamlab_post.workers.notify_worker import NotificationWorker
from domains.streamlab_post.workers.rename_worker import FileRenameWorker
from domains.streamlab_post.workers.transcript_worker import TranscriptWorker
from domains.streamlab_post.workers.translation_worker import TranslationWorker
from domains.streamlab_post.workers.youtube_worker import YouTubeWorker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_ffmpeg() -> bool:
    """Return True if both ffmpeg and ffprobe are available on PATH."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["ffprobe", "-version"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _make_test_video(output_path: Path) -> bool:
    """
    Create a 2-second synthetic MP4 with ffmpeg lavfi.
    Returns True on success, False if ffmpeg is unavailable.
    """
    result = subprocess.run(
        [
            "ffmpeg",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:d=2",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "2",
            str(output_path),
            "-y",
            "-loglevel", "error",
        ],
        capture_output=True,
    )
    return result.returncode == 0


_ffmpeg_available = _has_ffmpeg()
_skip_if_no_ffmpeg = pytest.mark.skipif(
    not _ffmpeg_available,
    reason="ffmpeg/ffprobe not available on PATH",
)


# ---------------------------------------------------------------------------
# 1 — BackupVerificationWorker: valid file
# ---------------------------------------------------------------------------


@_skip_if_no_ffmpeg
def test_backup_worker_passes_valid_file(tmp_path: Path) -> None:
    """Worker passes when the recording file exists and ffprobe validates it."""
    mp4 = tmp_path / "stream.mp4"
    assert _make_test_video(mp4), "ffmpeg failed to create test video"

    worker = BackupVerificationWorker()
    result = worker.run(
        {
            "file_path": str(mp4),
            "min_size_bytes": 1,  # tiny threshold — synthetic file is small
            "dry_run": False,
        }
    )

    assert result["success"] is True
    assert result["file_path"] == str(mp4)
    assert result["file_size_bytes"] > 0
    assert result["duration_seconds"] > 0


# ---------------------------------------------------------------------------
# 2 — BackupVerificationWorker: missing file
# ---------------------------------------------------------------------------


def test_backup_worker_fails_missing_file() -> None:
    """Worker returns success=False when the recording path does not exist."""
    worker = BackupVerificationWorker()
    result = worker.run(
        {
            "file_path": "/nonexistent/path/stream.mp4",
            "dry_run": False,
        }
    )

    assert result["success"] is False
    assert "not found" in result["error"].lower() or "Recording file" in result["error"]


# ---------------------------------------------------------------------------
# 3 — AudioExtractWorker: real ffmpeg extraction
# ---------------------------------------------------------------------------


@_skip_if_no_ffmpeg
def test_audio_worker_extracts_mp3(tmp_path: Path) -> None:
    """Worker runs ffmpeg and produces a real MP3 in output_dir."""
    mp4 = tmp_path / "stream.mp4"
    assert _make_test_video(mp4), "ffmpeg failed to create test video"

    output_dir = tmp_path / "out"
    output_dir.mkdir()

    worker = AudioExtractWorker()
    result = worker.run(
        {
            "file_path": str(mp4),
            "output_dir": str(output_dir),
            "dry_run": False,
        }
    )

    assert result["success"] is True
    mp3_path = Path(result["mp3_path"])
    assert mp3_path.exists(), "MP3 file not found on disk"
    assert mp3_path.stat().st_size > 0
    assert result["file_size_bytes"] > 0


# ---------------------------------------------------------------------------
# 4 — TranscriptWorker: missing API key
# ---------------------------------------------------------------------------


def test_transcript_worker_handles_missing_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Worker returns success=False when ELEVENLABS_API_KEY is unset."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    worker = TranscriptWorker()
    result = worker.run(
        {
            "mp3_path": str(tmp_path / "audio.mp3"),
            "output_dir": str(tmp_path),
            "dry_run": False,
        }
    )

    assert result["success"] is False
    assert "ELEVENLABS_API_KEY" in result["error"]


# ---------------------------------------------------------------------------
# 5 — YouTubeWorker: missing credentials
# ---------------------------------------------------------------------------


def test_youtube_worker_handles_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker returns success=False when YouTube env vars are unset."""
    for var in (
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        "YOUTUBE_REFRESH_TOKEN_EN",
        "YOUTUBE_REFRESH_TOKEN_FR",
    ):
        monkeypatch.delenv(var, raising=False)

    worker = YouTubeWorker()
    result = worker.run(
        {
            "language": "en",
            "title": "Committee Meeting 2025",
            "description": "Monthly board meeting.",
            "channel_id": "UCxxxxxxxxxxxxxxxx",
            "video_id": "",
            "dry_run": False,
        }
    )

    assert result["success"] is False
    assert "credentials" in result["error"].lower() or "missing" in result["error"].lower()


# ---------------------------------------------------------------------------
# 6 — TranslationWorker: missing API key
# ---------------------------------------------------------------------------


def test_translation_worker_handles_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker returns success=False when GOOGLE_TRANSLATE_API_KEY is unset."""
    monkeypatch.delenv("GOOGLE_TRANSLATE_API_KEY", raising=False)

    worker = TranslationWorker()
    result = worker.run(
        {
            "title_en": "Monthly Committee Meeting",
            "description_en": "Board meeting — April 2025.",
            "dry_run": False,
        }
    )

    assert result["success"] is False
    assert "GOOGLE_TRANSLATE_API_KEY" in result["error"]


# ---------------------------------------------------------------------------
# 7 — FileRenameWorker: naming convention (dry_run)
# ---------------------------------------------------------------------------


def test_rename_worker_applies_naming_convention(tmp_path: Path) -> None:
    """
    Worker computes correct session name in dry_run mode.

    With an empty sessions_dir the sequence number should be 001.
    The folder and file names must match:
      YYYY-MM-DD_EventName_001
    """
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    session_date = "2026-04-09"
    event_name = "Committee-Meeting"

    worker = FileRenameWorker()
    result = worker.run(
        {
            "recording_path": str(tmp_path / "stream.mp4"),
            "mp3_path": str(tmp_path / "audio.mp3"),
            "transcript_path": str(tmp_path / "transcript.txt"),
            "event_name": event_name,
            "session_date": session_date,
            "sessions_dir": str(sessions_dir),
            "dry_run": True,
        }
    )

    assert result["success"] is True
    assert result["dry_run"] is True

    expected_session = f"{session_date}_{event_name}_001"
    final_folder = result["final_folder"]
    assert Path(final_folder).name == expected_session, (
        f"Expected folder name '{expected_session}', got '{Path(final_folder).name}'"
    )

    # All renamed file paths must start with the session name
    for file_path in result["renamed_files"].values():
        stem = Path(file_path).name
        assert stem.startswith(expected_session), (
            f"File '{stem}' does not start with '{expected_session}'"
        )


# ---------------------------------------------------------------------------
# 8 — NotificationWorker: skips when no channels configured
# ---------------------------------------------------------------------------


def test_notify_worker_skips_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Worker returns success=True with 'skipped' in notes when neither
    recipients_email nor TEAMS_WEBHOOK_URL is provided.
    """
    monkeypatch.delenv("TEAMS_WEBHOOK_URL", raising=False)

    worker = NotificationWorker()
    result = worker.run(
        {
            "transcript_path": "",
            "final_folder": "/data/sessions/2026-04-09_Committee-Meeting_001",
            "event_name": "Committee-Meeting",
            "duration_seconds": 3600.0,
            "date": "2026-04-09",
            "recipients_email": [],        # empty list → no email channel
            "recipients_teams": "",        # empty → no Teams channel
            "dry_run": False,
        }
    )

    assert result["success"] is True
    assert result["sent_via"] == []
    assert "skipped" in result["notes"].lower()
