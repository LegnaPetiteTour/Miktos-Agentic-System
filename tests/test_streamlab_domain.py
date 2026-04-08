"""
StreamLab domain tests — Phase 3 validation.

Four tests that together prove:
  1. Live OBS connection works via env-var credentials (requires OBS running)
  2. classify_alert correctly routes stream_down to 0.95 / threshold_critical
  3. classify_alert routes dropped_frames warnings to review_queue at 0.80
     (full engine graph run with injected mock monitor)
  4. The engine ran the StreamLab domain without any changes to engine/graph/
     (Phase 3 architectural proof — does NOT require OBS)

Tests 2, 3, and 4 use injected mock data.
Test 1 requires OBS to be running and is automatically skipped if unreachable.

No file fixtures are needed — see tests/fixtures/streamlab/README.md.
"""

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

from domains.streamlab.tools.alert_classifier import classify_alert
from domains.streamlab.tools.obs_client import OBSClientTool
from engine.graph.graph_builder import build_graph
from engine.graph.state import RunState
from engine.services.state_store import generate_run_id
from engine.tools.base_tool import BaseTool

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# ---------------------------------------------------------------------------
# OBS reachability check — evaluated once at collection time
# ---------------------------------------------------------------------------

def _obs_is_reachable() -> bool:
    """Return True if OBS WebSocket responds within 2 seconds."""
    try:
        import obsws_python as obs  # type: ignore[import]

        cl = obs.ReqClient(
            host=os.getenv("OBS_HOST", "localhost"),
            port=int(os.getenv("OBS_PORT", "4455")),
            password=os.getenv("OBS_PASSWORD", ""),
            timeout=2,
        )
        cl.disconnect()
        return True
    except Exception:
        return False


_OBS_AVAILABLE = _obs_is_reachable()

requires_obs = pytest.mark.skipif(
    not _OBS_AVAILABLE,
    reason="OBS WebSocket not reachable — start OBS to run this test",
)


# ---------------------------------------------------------------------------
# Mock scanner for engine integration tests
# ---------------------------------------------------------------------------

class MockOBSMonitorTool(BaseTool):
    """Injects pre-set alert items without touching OBS."""

    name = "mock_obs_monitor"
    description = "Mock OBS monitor for testing."

    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def run(self, input: dict) -> dict[str, Any]:
        return {"files": self._items, "count": len(self._items)}


# ---------------------------------------------------------------------------
# State builder for integration tests
# ---------------------------------------------------------------------------

_STREAM_DOWN_ITEM = {
    "path": "obs://stream/stream_down",
    "name": "stream_down_alert",
    "suffix": ".alert",
    "size_bytes": 0,
    "mime_type": "application/vnd.miktos.stream-alert",
    "parent": "obs://stream",
    "metric_type": "stream_down",
    "value": 0.0,
    "threshold": 1.0,
    "severity": "critical",
    "description": "Stream output is not active",
    "scene": "Test Scene",
}

_DROPPED_FRAMES_WARNING_ITEM = {
    "path": "obs://stream/dropped_frames",
    "name": "dropped_frames_alert",
    "suffix": ".alert",
    "size_bytes": 0,
    "mime_type": "application/vnd.miktos.stream-alert",
    "parent": "obs://stream",
    "metric_type": "dropped_frames",
    "value": 3.5,
    "threshold": 2.0,
    "severity": "warning",
    "description": "Dropped frames at 3.50% (threshold: 2.0%)",
    "scene": "Test Scene",
}


def _build_streamlab_state(mock_items: list[dict]) -> RunState:
    return {
        "run_id": generate_run_id(),
        "domain": "streamlab",
        "goal": "StreamLab domain test",
        "mode": "dry_run",
        "current_step": "init",
        "pending_tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "skipped_tasks": [],
        "exhausted_tasks": [],
        "review_queue": [],
        "proposed_actions": [],
        "applied_actions": [],
        "artifacts": [],
        "errors": [],
        "logs": [],
        "retries": 0,
        "max_retries": 3,
        "replans": 0,
        "max_replans": 2,
        "done": False,
        "exit_reason": None,
        "context": {
            "root_path": "obs://stream",
            "batch_size": 50,
            "thresholds": {
                "auto_approve": 0.90,
                "review_queue": 0.60,
            },
            "exhausted_threshold": 0.20,
            "tools": {
                "scanner": MockOBSMonitorTool(mock_items),
                "classifier": classify_alert,
            },
        },
    }


# ---------------------------------------------------------------------------
# Test 1 — Live OBS connection (requires OBS running)
# ---------------------------------------------------------------------------

@requires_obs
def test_obs_connection_live():
    """
    Live: OBSClientTool connects using env-var credentials.

    Verifies the adapter layer reaches OBS WebSocket and receives a
    well-formed GetStreamStatus response. Does not assert stream state —
    the stream may or may not be active.
    """
    tool = OBSClientTool()
    client = tool.connect()
    status = client.get_stream_status()
    tool.disconnect()

    assert status is not None
    # output_active is a bool regardless of whether stream is live
    assert isinstance(getattr(status, "output_active", None), bool)


# ---------------------------------------------------------------------------
# Test 2 — Classifier: stream_down → 0.95 / threshold_critical
# ---------------------------------------------------------------------------

def test_alert_classifier_stream_down():
    """
    Unit: stream_down metric → correct category, confidence, and method.

    stream_down is always critical — the stream is not running.
    Confidence 0.95 means the engine auto-approves the alert immediately.
    """
    result = classify_alert(_STREAM_DOWN_ITEM)

    assert result["category"] == "stream_down", (
        f"Expected 'stream_down', got '{result['category']}'."
    )
    assert result["confidence"] == 0.95, (
        f"Expected confidence 0.95, got {result['confidence']}."
    )
    assert result["method"] == "threshold_critical", (
        f"Expected 'threshold_critical', got '{result['method']}'."
    )


# ---------------------------------------------------------------------------
# Test 3 — Warning alert routes to review_queue in full engine run
# ---------------------------------------------------------------------------

def test_alert_classifier_warning_routes_to_review_queue():
    """
    Integration: dropped_frames warning → confidence 0.80 → review_queue.

    Part 1: unit assertion on the classifier.
    Part 2: full graph run confirms the engine routes 0.80-confidence
    alerts to review_queue (below auto_approve threshold of 0.90).
    """
    # Part 1: unit
    result = classify_alert(_DROPPED_FRAMES_WARNING_ITEM)

    assert result["confidence"] == 0.80, (
        f"Expected confidence 0.80 for warning, got {result['confidence']}."
    )
    assert result["category"] == "dropped_frames"
    assert result["method"] == "threshold_warning"

    # Part 2: full engine run with the warning item
    final = build_graph().invoke(
        _build_streamlab_state([_DROPPED_FRAMES_WARNING_ITEM])
    )

    assert final.get("exit_reason") == "success", (
        f"Expected exit_reason='success', got '{final.get('exit_reason')}'. "
        f"Errors: {final.get('errors', [])}"
    )

    review_queue = final.get("review_queue", [])
    assert len(review_queue) >= 1, (
        "Expected at least one item in review_queue — "
        "dropped_frames at 0.80 should be queued (below auto_approve 0.90)."
    )

    queued_cats = [a.get("category") for a in review_queue]
    assert "dropped_frames" in queued_cats, (
        f"Expected 'dropped_frames' in review_queue categories. "
        f"Got: {queued_cats}"
    )


# ---------------------------------------------------------------------------
# Test 4 — Full engine loop + engine invariant (no OBS required)
# ---------------------------------------------------------------------------

def test_streamlab_full_loop_engine_unchanged():
    """
    Integration: StreamLab domain runs through the engine unmodified.

    This is the Phase 3 architectural proof. The engine/graph/ nodes are
    called identically to the file_analyzer and kosmos domains — only the
    injected tools differ. Zero engine files were changed.

    Assertions:
      - exit_reason == "success"         loop completed cleanly
      - domain == "streamlab"            state carries correct domain tag
      - at least one proposed_action     the classify path executed
      - engine/graph/ diff is empty      engine unchanged on this branch
    """
    final = build_graph().invoke(
        _build_streamlab_state([_STREAM_DOWN_ITEM])
    )

    assert final.get("exit_reason") == "success", (
        f"Expected exit_reason='success', got '{final.get('exit_reason')}'. "
        f"Errors: {final.get('errors', [])}"
    )
    assert final.get("domain") == "streamlab", (
        f"Expected domain='streamlab', got '{final.get('domain')}'."
    )
    assert len(final.get("proposed_actions", [])) >= 1, (
        "Expected at least one proposed action — "
        "the classify path did not execute."
    )

    # Engine invariant: git diff main -- engine/graph/ must be empty
    result = subprocess.run(
        ["git", "diff", "main", "--name-only", "--", "engine/graph/"],
        capture_output=True,
        text=True,
    )
    engine_changes = result.stdout.strip()
    assert engine_changes == "", (
        "ENGINE FILES WERE MODIFIED — "
        "Phase 3 architectural invariant violated.\n"
        f"Changed files:\n{engine_changes}"
    )
