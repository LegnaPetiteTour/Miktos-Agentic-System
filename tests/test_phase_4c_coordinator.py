"""
Phase 4c tests — Coordinator / Task Delegation.

Five CI-friendly tests using tmp_path fixture for isolation.

Tests:
  1. KosmosWorker classifies a video file correctly
  2. ThumbnailWorker: either succeeds (real video) or fails gracefully (stub)
  3. MetadataWorker writes session.json with required keys
  4. SessionCoordinator handles recording_ready end-to-end
  5. append_log() writes parseable lines for POSTED and ACKNOWLEDGED events
"""

import json
from pathlib import Path

from engine.coordinator.coordinator import SessionCoordinator
from engine.coordinator.workers import KosmosWorker, MetadataWorker, ThumbnailWorker
from engine.messaging.bus import MessageBus

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "media_folder"
VIDEO_FIXTURE = FIXTURE_DIR / "video_clip.mp4"
PHOTO_FIXTURE = FIXTURE_DIR / "photo_with_exif.jpg"


# ---------------------------------------------------------------------------
# Test 1 — KosmosWorker classifies video
# ---------------------------------------------------------------------------

def test_kosmos_worker_classifies_video(tmp_path: Path) -> None:
    worker = KosmosWorker()
    result = worker.run({
        "file_path": str(VIDEO_FIXTURE),
        "output_dir": str(tmp_path),
    })
    assert result["success"] is True
    assert result["category"] == "videos"
    assert result["confidence"] == 0.95
    assert result["method"] == "extension"
    assert "videos" in result["proposed_path"]


# ---------------------------------------------------------------------------
# Test 2 — ThumbnailWorker: graceful on stub file (not a real video)
# ---------------------------------------------------------------------------

def test_thumbnail_worker_graceful_on_non_video(tmp_path: Path) -> None:
    """
    video_clip.mp4 is a stub (ASCII text). ffmpeg will fail.
    Worker must return success=False with an error string, never raise.
    """
    worker = ThumbnailWorker()
    result = worker.run({
        "file_path": str(VIDEO_FIXTURE),
        "output_dir": str(tmp_path),
    })
    # Either outcome is acceptable — worker must not raise
    assert "success" in result
    if not result["success"]:
        assert "error" in result
        assert isinstance(result["error"], str)


# ---------------------------------------------------------------------------
# Test 3 — MetadataWorker writes session.json
# ---------------------------------------------------------------------------

def test_metadata_worker_writes_session_json(tmp_path: Path) -> None:
    worker = MetadataWorker()
    result = worker.run({
        "file_path": str(VIDEO_FIXTURE),
        "output_dir": str(tmp_path),
        "session_id": "test_session_001",
        "scene": "Test Scene",
        "thumbnail_path": str(tmp_path / "thumbnail.jpg"),
        "category": "videos",
        "trigger_run_id": "run_test",
    })
    assert result["success"] is True
    meta_path = Path(result["metadata_path"])
    assert meta_path.exists()
    with open(meta_path) as f:
        data = json.load(f)
    for key in ("session_id", "recording_path", "scene", "duration_seconds",
                "file_size_bytes", "thumbnail_path", "category", "timestamp",
                "trigger_run_id"):
        assert key in data, f"Missing key: {key}"
    assert data["session_id"] == "test_session_001"
    assert data["scene"] == "Test Scene"
    assert data["category"] == "videos"
    assert isinstance(data["duration_seconds"], float)


# ---------------------------------------------------------------------------
# Test 4 — SessionCoordinator handles recording_ready end-to-end
# ---------------------------------------------------------------------------

def test_coordinator_handles_recording_ready(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=str(tmp_path / "messages"))
    bus.post(
        from_agent="streamlab_monitor",
        to_agent="session_coordinator",
        message_type="recording_ready",
        payload={
            "file_path": str(VIDEO_FIXTURE),
            "scene": "CI Test Scene",
            "trigger_run_id": "test_4c_ci",
        },
        run_id="test_4c_ci",
    )
    messages = bus.read_pending(for_agent="session_coordinator")
    assert len(messages) == 1

    coordinator = SessionCoordinator(
        bus=bus,
        sessions_dir=str(tmp_path / "sessions"),
        agent_id="session_coordinator",
    )
    artifact = coordinator.handle(messages[0])
    bus.acknowledge(messages[0])

    # exit_reason must be success or partial_failure (fixtures aren't real videos)
    assert artifact["exit_reason"] in ("success", "partial_failure")
    assert "session_id" in artifact
    assert "slots" in artifact

    # session_complete must have been posted back
    replies = bus.read_pending(for_agent="streamlab_monitor")
    assert len(replies) == 1
    assert replies[0].message_type == "session_complete"
    assert replies[0].payload["session_id"] == artifact["session_id"]

    # session output_dir must exist
    output_dir = Path(artifact["output_dir"])
    assert output_dir.exists()


# ---------------------------------------------------------------------------
# Test 5 — append_log writes parseable lines
# ---------------------------------------------------------------------------

def test_coordinator_message_log_written(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=str(tmp_path / "messages"))

    # Post and acknowledge one message — triggers POSTED + ACKNOWLEDGED log lines
    msg = bus.post(
        from_agent="streamlab_monitor",
        to_agent="session_coordinator",
        message_type="recording_ready",
        payload={
            "file_path": str(VIDEO_FIXTURE),
            "scene": "Log Test",
            "trigger_run_id": "log_test",
        },
    )
    bus.acknowledge(msg)

    # Also run the coordinator to get DISPATCHED/COMPLETED/FAILED lines
    coordinator = SessionCoordinator(
        bus=bus,
        sessions_dir=str(tmp_path / "sessions"),
        agent_id="session_coordinator",
    )
    bus.post(
        from_agent="streamlab_monitor",
        to_agent="session_coordinator",
        message_type="recording_ready",
        payload={
            "file_path": str(VIDEO_FIXTURE),
            "scene": "Log Test 2",
            "trigger_run_id": "log_test_2",
        },
    )
    messages = bus.read_pending(for_agent="session_coordinator")
    if messages:
        coordinator.handle(messages[0])

    log_path = Path(tmp_path) / "messages" / "message.log"
    assert log_path.exists(), "message.log was not created"

    lines = log_path.read_text().splitlines()
    assert len(lines) >= 2, "Expected at least POSTED and ACKNOWLEDGED lines"

    # Each line must have at least 4 whitespace-separated fields
    for line in lines:
        fields = line.split()
        assert len(fields) >= 4, f"Unparseable log line: {line!r}"

    # Must contain at least one POSTED and one ACKNOWLEDGED event
    events = [line.split()[1] for line in lines if len(line.split()) >= 2]
    assert any("POSTED" in e for e in events), "No POSTED event in log"
    assert any("ACKNOWLEDGED" in e for e in events), "No ACKNOWLEDGED event in log"
