"""
Phase 8a tests — Epiphan Pearl domain adapter.

Eight CI-friendly tests (no live Pearl device required).

Tests:
  1. test_pearl_client_get_channels       — mock GET → channel list
  2. test_pearl_client_get_recorders      — mock GET → recorder list
  3. test_pearl_client_download_recording — mock streamed GET → file on disk
  4. test_epiphan_monitor_healthy         — all active → zero alerts
  5. test_epiphan_monitor_recording_stopped — recorder idle → recording_stopped alert
  6. test_recording_download_worker_success — mock client → success result
  7. test_recording_download_worker_dry_run — dry_run=True → no network, success
  8. test_recording_download_worker_never_raises — bad host → failure dict, no raise
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
        "result": {"state": "recording"}
    }
    mock_client.get_channel_publisher_status.return_value = {
        "result": [{"state": "publishing"}]
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
        "result": {"state": "idle"}  # not "recording"
    }
    mock_client.get_channel_publisher_status.return_value = {
        "result": [{"state": "publishing"}]
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
