"""
Phase 8a tests — Epiphan Pearl domain adapter.

Nine CI-friendly tests (no live Pearl device required).

Tests:
  1. test_pearl_client_get_channels       — mock GET → channel list
  2. test_pearl_client_get_recorders      — mock GET → recorder list
  3. test_pearl_client_download_recording — mock streamed GET → file on disk
  4. test_epiphan_monitor_healthy         — all active → zero alerts
  5. test_epiphan_monitor_recording_stopped — recorder idle → recording_stopped alert
  6. test_recording_download_worker_success — mock client → success result
  7. test_recording_download_worker_dry_run — dry_run=True → no network, success
  8. test_recording_download_worker_never_raises — bad host → failure dict, no raise
  9. test_coordinator_epiphan_pre_stage1  — hardware:epiphan wires download result
                                            into pipeline (no NameError)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from domains.epiphan.tools.pearl_client import PearlClient
from domains.epiphan.tools.pearl_monitor import EpiphanMonitorTool
from domains.streamlab_post.workers.recording_download_worker import (
    RecordingDownloadWorker,
)


# ---------------------------------------------------------------------------
# 1. PearlClient.get_channels
# ---------------------------------------------------------------------------

def test_pearl_client_get_channels():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "result": [
            {"id": "channel_en", "name": "Video EN"},
            {"id": "channel_fr", "name": "Video FR"},
        ]
    }
    mock_resp.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_resp) as mock_get:
        client = PearlClient()
        channels = client.get_channels()

    mock_get.assert_called_once()
    assert len(channels) == 2
    assert channels[0]["id"] == "channel_en"


# ---------------------------------------------------------------------------
# 2. PearlClient.get_recorders
# ---------------------------------------------------------------------------

def test_pearl_client_get_recorders():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "result": [
            {"id": "1", "name": "Recorder EN", "multisource": False},
        ]
    }
    mock_resp.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_resp):
        client = PearlClient()
        recorders = client.get_recorders()

    assert isinstance(recorders, list)
    assert recorders[0]["id"] == "1"


# ---------------------------------------------------------------------------
# 3. PearlClient.download_recording — chunked write to disk
# ---------------------------------------------------------------------------

def test_pearl_client_download_recording(tmp_path):
    fake_content = b"FAKE_VIDEO_DATA_CHUNK"
    dest_file = str(tmp_path / "recording.mp4")

    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.raise_for_status.return_value = None
    mock_resp.iter_content.return_value = iter([fake_content])

    with patch("requests.get", return_value=mock_resp):
        client = PearlClient()
        result = client.download_recording("1", "file_001", dest_file)

    assert result == dest_file
    written = Path(dest_file).read_bytes()
    assert written == fake_content


# ---------------------------------------------------------------------------
# 4. EpiphanMonitorTool — healthy (no alerts)
# ---------------------------------------------------------------------------

def test_epiphan_monitor_healthy():
    mock_client = MagicMock(spec=PearlClient)
    mock_client.get_recorder_status.return_value = {
        "result": {"state": "started"}
    }
    mock_client.get_channel_publisher_status.return_value = {
        "result": [{"id": "1", "type": "rtmp", "status": {"state": "started", "started": True}}]
    }

    monitor = EpiphanMonitorTool(
        thresholds={},
        client=mock_client,
        recorder_id="1",
        channel_id="1",
    )
    result = monitor.run({"root_path": "pearl://stream"})

    assert result["count"] == 0
    assert result["files"] == []


# ---------------------------------------------------------------------------
# 5. EpiphanMonitorTool — recording stopped
# ---------------------------------------------------------------------------

def test_epiphan_monitor_recording_stopped():
    mock_client = MagicMock(spec=PearlClient)
    mock_client.get_recorder_status.return_value = {
        "result": {"state": "stopped"}  # not "started"
    }
    mock_client.get_channel_publisher_status.return_value = {
        "result": [{"id": "1", "type": "rtmp", "status": {"state": "started", "started": True}}]
    }

    monitor = EpiphanMonitorTool(
        thresholds={},
        client=mock_client,
        recorder_id="1",
        channel_id="1",
    )
    result = monitor.run({"root_path": "pearl://stream"})

    assert result["count"] >= 1
    metric_types = [item["metric_type"] for item in result["files"]]
    assert "recording_stopped" in metric_types


# ---------------------------------------------------------------------------
# 6. RecordingDownloadWorker — success path
# ---------------------------------------------------------------------------

def test_recording_download_worker_success(tmp_path, monkeypatch):
    fake_path = str(tmp_path / "session_2025.mp4")

    mock_client = MagicMock(spec=PearlClient)
    mock_client.get_recorder_files.return_value = [
        {"id": "f001", "name": "session_2025.mp4"},
    ]
    mock_client.download_recording.return_value = fake_path

    # Create the "downloaded" file so stat() works
    Path(fake_path).write_bytes(b"fake_video")

    monkeypatch.setenv("PEARL_HOST", "192.168.2.45")

    with patch(
        "domains.streamlab_post.workers.recording_download_worker.PearlClient",
        return_value=mock_client,
    ):
        result = RecordingDownloadWorker().run(
            {
                "pearl_host": "192.168.2.45",
                "pearl_recorder_id": "1",
                "download_dir": str(tmp_path),
                "dry_run": False,
            }
        )

    assert result["success"] is True
    assert result["file_path"] == fake_path
    assert result["file_size_bytes"] >= 0


# ---------------------------------------------------------------------------
# 7. RecordingDownloadWorker — dry_run=True
# ---------------------------------------------------------------------------

def test_recording_download_worker_dry_run(monkeypatch):
    monkeypatch.setenv("PEARL_HOST", "192.168.2.45")

    result = RecordingDownloadWorker().run(
        {
            "pearl_recorder_id": "1",
            "download_dir": "~/Downloads/test",
            "dry_run": True,
        }
    )

    assert result["success"] is True
    assert result.get("dry_run") is True
    assert "file_path" in result
    assert result["file_size_bytes"] == 0


# ---------------------------------------------------------------------------
# 8. RecordingDownloadWorker — bad host → failure dict, never raises
# ---------------------------------------------------------------------------

def test_recording_download_worker_never_raises(monkeypatch):
    import requests

    monkeypatch.setenv("PEARL_HOST", "192.0.2.1")  # TEST-NET, not routable

    with patch(
        "domains.streamlab_post.workers.recording_download_worker.PearlClient"
    ) as mock_cls:
        mock_inst = mock_cls.return_value
        mock_inst.get_recorder_files.side_effect = (
            requests.ConnectionError("unreachable")
        )
        result = RecordingDownloadWorker().run(
            {
                "pearl_host": "192.0.2.1",
                "pearl_recorder_id": "1",
                "download_dir": "~/Downloads/test",
                "dry_run": False,
            }
        )

    assert result["success"] is False
    assert "error" in result
    # No exception propagated


# ---------------------------------------------------------------------------
# 9. Coordinator — hardware:epiphan wires download result into pipeline
#    Verifies the NameError bug fix: all_results must be initialized before
#    the Pre-Stage 1 block, not after.
# ---------------------------------------------------------------------------

def test_coordinator_epiphan_pre_stage1(tmp_path, monkeypatch):
    """
    When session_config has hardware:epiphan and no file_path in payload,
    PostStreamCoordinator must run RecordingDownloadWorker before Stage 1
    and record the result in all_results — without raising NameError.

    All downstream workers are patched to dry_run no-ops so the test
    requires no real files or network.
    """
    from domains.streamlab_post.coordinator import PostStreamCoordinator

    fake_file = str(tmp_path / "pearl_recording.mp4")
    Path(fake_file).write_bytes(b"fake")

    session_config = {
        "hardware": "epiphan",
        "event_name": "Test Event",
        "pearl": {
            "host": "192.168.2.45",
            "channel_en": "1",
            "download_dir": str(tmp_path),
        },
        "recording": {},
        "youtube": {},
        "elevenlabs": {},
        "notification": {},
    }

    dl_success = {
        "success": True,
        "file_path": fake_file,
        "file_size_bytes": 4,
    }

    with patch(
        "domains.streamlab_post.coordinator.RecordingDownloadWorker"
    ) as mock_dl_cls, patch.object(
        PostStreamCoordinator,
        "_run_stage",
        return_value={
            "backup_verify": {"success": True},
            "youtube_en": {"success": True, "title": "T", "description": "D"},
            "audio_extract": {"success": True, "mp3_path": fake_file},
        },
    ):
        mock_dl_cls.return_value.run.return_value = dl_success

        coordinator = PostStreamCoordinator(
            sessions_dir=str(tmp_path / "sessions")
        )
        artifact = coordinator.run(
            payload={"dry_run": True},
            session_config=session_config,
        )

    # RecordingDownloadWorker.run() was called once
    mock_dl_cls.return_value.run.assert_called_once()

    # Pre-Stage 1 result is present in the final artifact under "slots"
    assert artifact.get("slots", {}).get(
        "recording_download", {}
    ).get("success") is True

    # Coordinator did not error out (exit_reason is not an unexpected exception)
    assert artifact.get("exit_reason") in ("success", "partial_failure")
