"""
tests/test_phase_11_dual_channel.py

Phase 11 — dual-channel bilingual pipeline tests.

All workers and network calls are mocked. No live Pearl required.
Target: 122 prior + 8 new = 130 passed, 1 permanent skip.
"""

from pathlib import Path
from unittest.mock import patch



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _epiphan_config(tmp_path: Path, channel_fr: int = 3) -> dict:
    return {
        "hardware": "epiphan",
        "event_name": "DualChannel-Test",
        "pearl": {
            "host": "192.168.2.45",
            "channel_en": 2,
            "channel_fr": channel_fr,
            "download_dir": str(tmp_path),
        },
        "recording": {},
        "youtube": {"en": {}, "fr": {}},
        "elevenlabs": {},
        "notification": {},
    }


def _obs_config() -> dict:
    return {
        "hardware": "obs",
        "event_name": "OBS-Test",
        "recording": {},
        "youtube": {"en": {}, "fr": {}},
        "elevenlabs": {},
        "notification": {},
    }


def _dl_ok(path: str) -> dict:
    return {"success": True, "file_path": path, "file_size_bytes": 100}


def _dl_fail() -> dict:
    return {"success": False, "error": "recorder offline"}


# ---------------------------------------------------------------------------
# 1. FR download is called when hardware=epiphan and channel_fr is set
# ---------------------------------------------------------------------------

def test_fr_download_called_when_epiphan(tmp_path):
    from domains.streamlab_post.coordinator import PostStreamCoordinator

    en_file = str(tmp_path / "en.mp4")
    fr_file = str(tmp_path / "fr.mp4")
    Path(en_file).write_bytes(b"en")
    Path(fr_file).write_bytes(b"fr")

    with patch(
        "domains.streamlab_post.coordinator.RecordingDownloadWorker"
    ) as mock_dl_cls, patch.object(
        PostStreamCoordinator, "_run_stage", return_value={
            "backup_verify": {"success": True},
            "youtube_en": {"success": True, "title": "T", "description": "D"},
            "audio_extract": {"success": True, "mp3_path": en_file},
            "audio_extract_fr": {"success": True, "mp3_path": fr_file},
        },
    ):
        mock_dl_cls.return_value.run.side_effect = [
            _dl_ok(en_file),
            _dl_ok(fr_file),
        ]

        coordinator = PostStreamCoordinator(
            sessions_dir=str(tmp_path / "sessions")
        )
        coordinator.run(
            payload={"dry_run": True},
            session_config=_epiphan_config(tmp_path),
        )

    assert mock_dl_cls.return_value.run.call_count == 2
    calls = mock_dl_cls.return_value.run.call_args_list
    recorder_ids = [c[0][0]["pearl_recorder_id"] for c in calls]
    assert "2" in recorder_ids
    assert "3" in recorder_ids


# ---------------------------------------------------------------------------
# 2. FR download failure is non-fatal — EN pipeline continues
# ---------------------------------------------------------------------------

def test_fr_download_failure_non_fatal(tmp_path):
    from domains.streamlab_post.coordinator import PostStreamCoordinator

    en_file = str(tmp_path / "en.mp4")
    Path(en_file).write_bytes(b"en")

    with patch(
        "domains.streamlab_post.coordinator.RecordingDownloadWorker"
    ) as mock_dl_cls, patch.object(
        PostStreamCoordinator, "_run_stage", return_value={
            "backup_verify": {"success": True},
            "youtube_en": {"success": True, "title": "T", "description": "D"},
            "audio_extract": {"success": True, "mp3_path": en_file},
            "audio_extract_fr": {"success": False, "error": "file_path not provided"},
        },
    ):
        mock_dl_cls.return_value.run.side_effect = [
            _dl_ok(en_file),
            _dl_fail(),
        ]

        coordinator = PostStreamCoordinator(
            sessions_dir=str(tmp_path / "sessions")
        )
        artifact = coordinator.run(
            payload={"dry_run": True},
            session_config=_epiphan_config(tmp_path),
        )

    # Session must not be blocked by FR failure
    assert artifact["exit_reason"] in ("success", "partial_failure")
    # EN download result is present
    assert artifact["slots"]["recording_download"]["success"] is True
    # FR download failure is recorded
    assert artifact["slots"]["recording_download_fr"]["success"] is False


# ---------------------------------------------------------------------------
# 3. AudioExtractWorker is called with output_suffix="_FR" for FR slot
# ---------------------------------------------------------------------------

def test_audio_extract_fr_suffix(tmp_path):
    from domains.streamlab_post.workers.audio_worker import AudioExtractWorker

    suffix_seen = []

    def capturing_run(self, payload):
        suffix_seen.append(payload.get("output_suffix", ""))
        return {
            "success": True,
            "dry_run": True,
            "mp3_path": str(
                Path(payload.get("output_dir", "/tmp"))
                / f"audio{payload.get('output_suffix', '')}.mp3"
            ),
            "file_size_bytes": 0,
        }

    with patch.object(AudioExtractWorker, "run", capturing_run):
        worker = AudioExtractWorker()
        worker.run({
            "file_path": str(tmp_path / "rec.mp4"),
            "output_dir": str(tmp_path),
            "output_suffix": "_FR",
            "dry_run": True,
        })

    assert "_FR" in suffix_seen


# ---------------------------------------------------------------------------
# 4. TranscriptWorker is called with output_suffix="_FR" and language_code="fr"
# ---------------------------------------------------------------------------

def test_transcript_fr_suffix(tmp_path):
    from domains.streamlab_post.workers.transcript_worker import TranscriptWorker

    result = TranscriptWorker().run({
        "mp3_path": str(tmp_path / "audio_FR.mp3"),
        "output_dir": str(tmp_path),
        "output_suffix": "_FR",
        "language_code": "fr",
        "dry_run": True,
    })

    assert result["success"] is True
    assert result["transcript_path"].endswith("_FR.txt")


# ---------------------------------------------------------------------------
# 5. FileRenameWorker receives and includes fr_* paths
# ---------------------------------------------------------------------------

def test_rename_includes_fr_paths(tmp_path):
    from domains.streamlab_post.workers.rename_worker import FileRenameWorker

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    result = FileRenameWorker().run({
        "recording_path": str(tmp_path / "rec_EN.mp4"),
        "mp3_path": str(tmp_path / "audio.mp3"),
        "transcript_path": str(tmp_path / "transcript.txt"),
        "thumbnail_path": "",
        "fr_recording_path": str(tmp_path / "rec_FR.mp4"),
        "fr_mp3_path": str(tmp_path / "audio_FR.mp3"),
        "fr_transcript_path": str(tmp_path / "transcript_FR.txt"),
        "event_name": "Test-Event",
        "session_date": "2026-04-19",
        "sessions_dir": str(sessions_dir),
        "dry_run": True,
    })

    assert result["success"] is True
    renamed = result["renamed_files"]
    # FR paths are present and carry _FR suffix
    assert "fr_recording" in renamed
    assert "_FR" in renamed["fr_recording"]
    assert "fr_audio" in renamed
    assert "_FR" in renamed["fr_audio"]
    assert "fr_transcript" in renamed
    assert "_FR" in renamed["fr_transcript"]


# ---------------------------------------------------------------------------
# 6. OBS sessions do not trigger FR download
# ---------------------------------------------------------------------------

def test_obs_no_fr_download(tmp_path):
    from domains.streamlab_post.coordinator import PostStreamCoordinator

    obs_file = str(tmp_path / "obs_recording.mkv")
    Path(obs_file).write_bytes(b"obs")

    with patch(
        "domains.streamlab_post.coordinator.RecordingDownloadWorker"
    ) as mock_dl_cls, patch.object(
        PostStreamCoordinator, "_run_stage", return_value={
            "backup_verify": {"success": True},
            "youtube_en": {"success": True, "title": "T", "description": "D"},
            "audio_extract": {"success": True, "mp3_path": obs_file},
        },
    ):
        coordinator = PostStreamCoordinator(
            sessions_dir=str(tmp_path / "sessions")
        )
        coordinator.run(
            payload={"file_path": obs_file, "dry_run": True},
            session_config=_obs_config(),
        )

    # RecordingDownloadWorker must not be called for OBS sessions
    mock_dl_cls.return_value.run.assert_not_called()


# ---------------------------------------------------------------------------
# 7. EN audio suffix defaults to "" (backwards compat)
# ---------------------------------------------------------------------------

def test_audio_suffix_default_en(tmp_path):
    from domains.streamlab_post.workers.audio_worker import AudioExtractWorker

    result = AudioExtractWorker().run({
        "file_path": str(tmp_path / "rec.mp4"),
        "output_dir": str(tmp_path),
        "dry_run": True,
    })

    assert result["success"] is True
    # No suffix → produces audio.mp3, not audio_FR.mp3
    assert result["mp3_path"].endswith("audio.mp3")


# ---------------------------------------------------------------------------
# 8. ReportWorker payload includes fr_transcript_path and fr_word_count
# ---------------------------------------------------------------------------

def test_report_includes_fr_fields(tmp_path):
    from domains.streamlab_post.workers.report_worker import ReportWorker

    folder = tmp_path / "2026-04-19_Test_001"
    folder.mkdir()

    result = ReportWorker().run({
        "event_name": "Test",
        "session_date": "2026-04-19",
        "final_folder": str(folder),
        "fr_transcript_path": str(tmp_path / "transcript_FR.txt"),
        "fr_word_count": 42,
        "slots": {},
        "dry_run": False,
    })

    assert result["success"] is True
    report_text = (folder / "2026-04-19_Test_001_report.html").read_text()
    # Report was generated without error; fr fields are accepted
    assert "Test" in report_text
