"""
Phase 4b tests — Agent-to-Agent Messaging.

Five CI-friendly tests using tmp_path fixture for isolation.

Tests:
  1. MessageBus.post() + read_pending() round-trip
  2. MessageBus.acknowledge() moves file to delivered/
  3. message_trigger_node injects inbox messages into state
  4. message_trigger_node is skipped when enable_messaging is absent
  5. Full handoff workflow: post → classify → post back
"""

from pathlib import Path
from typing import cast

from domains.kosmos.tools.media_classifier import classify_media_file
from engine.graph.graph_builder import build_graph, build_graph_with_messaging
from engine.graph.state import RunState
from engine.messaging.bus import MessageBus
from engine.services.state_store import generate_run_id
from engine.tools.shared_tools import FileScannerTool

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "media_folder"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_kosmos_state(
    root_path: str,
    agent_id: str = "kosmos_organizer",
    inbox_messages: list | None = None,
    enable_messaging: bool = False,
    messages_dir: str = "data/messages",
) -> RunState:
    return {
        "run_id": generate_run_id(),
        "domain": "kosmos",
        "agent_id": agent_id,
        "inbox_messages": inbox_messages or [],
        "goal": f"Phase 4b test — {root_path}",
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
            "root_path": root_path,
            "batch_size": 50,
            "execution_mode": "sequential",
            "parallel_workers": 4,
            "enable_messaging": enable_messaging,
            "messages_dir": messages_dir,
            "thresholds": {
                "auto_approve": 0.90,
                "review_queue": 0.60,
            },
            "exhausted_threshold": 0.20,
            "tools": {
                "scanner": FileScannerTool(),
                "classifier": classify_media_file,
            },
        },
    }


# ---------------------------------------------------------------------------
# Test 1 — post + read_pending round-trip
# ---------------------------------------------------------------------------

def test_message_bus_post_and_read(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=tmp_path)
    msg = bus.post(
        from_agent="streamlab_monitor",
        to_agent="agent_b",
        message_type="recording_ready",
        payload={"recordings_path": "/Movies", "scene": "Main"},
        run_id="run_abc",
    )

    pending = bus.read_pending("agent_b")
    assert len(pending) == 1

    received = pending[0]
    assert received.message_id == msg.message_id
    assert received.from_agent == "streamlab_monitor"
    assert received.to_agent == "agent_b"
    assert received.message_type == "recording_ready"
    assert received.payload["recordings_path"] == "/Movies"
    assert received.run_id == "run_abc"
    assert received.status == "pending"


# ---------------------------------------------------------------------------
# Test 2 — acknowledge moves to delivered/
# ---------------------------------------------------------------------------

def test_message_bus_acknowledge(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=tmp_path)
    msg = bus.post(
        from_agent="a",
        to_agent="b",
        message_type="ping",
        payload={},
    )

    bus.acknowledge(msg)

    # pending/ must now be empty
    assert bus.read_pending("b") == []

    # delivered/ must contain the file
    delivered_dir = tmp_path / "b" / "delivered"
    delivered_files = list(delivered_dir.glob("*.json"))
    assert len(delivered_files) == 1
    assert delivered_files[0].stem == msg.message_id


# ---------------------------------------------------------------------------
# Test 3 — message_trigger_node injects messages into state
# ---------------------------------------------------------------------------

def test_message_trigger_node_injects_messages(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=tmp_path)
    pre_msg = bus.post(
        from_agent="streamlab_monitor",
        to_agent="kosmos_organizer",
        message_type="recording_ready",
        payload={"recordings_path": str(FIXTURE_DIR)},
    )

    state = _build_kosmos_state(
        root_path=str(FIXTURE_DIR),
        agent_id="kosmos_organizer",
        enable_messaging=True,
        messages_dir=str(tmp_path),
    )
    graph = build_graph_with_messaging()
    final_state = cast(RunState, graph.invoke(state))

    # Trigger node must have populated inbox_messages
    inbox = final_state.get("inbox_messages", [])
    assert len(inbox) == 1
    assert inbox[0]["message_id"] == pre_msg.message_id
    assert inbox[0]["message_type"] == "recording_ready"

    # Run must complete normally
    assert final_state.get("exit_reason") == "success"

    # Pending inbox must be empty after run (acknowledged)
    assert bus.read_pending("kosmos_organizer") == []


# ---------------------------------------------------------------------------
# Test 4 — message_trigger_node is skipped when enable_messaging is absent
# ---------------------------------------------------------------------------

def test_message_trigger_node_skipped_when_disabled(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=tmp_path)
    bus.post(
        from_agent="streamlab_monitor",
        to_agent="kosmos_organizer",
        message_type="recording_ready",
        payload={"recordings_path": str(FIXTURE_DIR)},
    )

    # Use build_graph() (not build_graph_with_messaging) and no enable_messaging
    state = _build_kosmos_state(
        root_path=str(FIXTURE_DIR),
        agent_id="kosmos_organizer",
        enable_messaging=False,  # disabled
        messages_dir=str(tmp_path),
    )
    graph = build_graph()
    final_state = cast(RunState, graph.invoke(state))

    # inbox_messages must remain empty — trigger node never ran
    assert final_state.get("inbox_messages", []) == []

    # Normal execution must be unaffected
    assert final_state.get("exit_reason") == "success"

    # Message must still be in pending (not consumed)
    assert len(bus.read_pending("kosmos_organizer")) == 1


# ---------------------------------------------------------------------------
# Test 5 — full handoff workflow: post → classify → post back
# ---------------------------------------------------------------------------

def test_full_handoff_workflow(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=tmp_path)

    # StreamLab posts recording_ready to kosmos_organizer
    recording_msg = bus.post(
        from_agent="streamlab_monitor",
        to_agent="kosmos_organizer",
        message_type="recording_ready",
        payload={"recordings_path": str(FIXTURE_DIR)},
        run_id="streamlab_run_001",
    )

    # Kosmos runs with messaging enabled — trigger node picks up the message
    state = _build_kosmos_state(
        root_path=str(FIXTURE_DIR),
        agent_id="kosmos_organizer",
        enable_messaging=True,
        messages_dir=str(tmp_path),
    )
    graph = build_graph_with_messaging()
    final_state = cast(RunState, graph.invoke(state))

    # Inbox must contain the pre-written message
    inbox = final_state.get("inbox_messages", [])
    assert any(m["message_id"] == recording_msg.message_id for m in inbox)

    # Execution must succeed
    assert final_state.get("exit_reason") == "success"
    assert final_state.get("domain") == "kosmos"
    assert len(final_state.get("proposed_actions", [])) > 0

    # Pending inbox must be empty (acknowledged during trigger node)
    assert bus.read_pending("kosmos_organizer") == []

    # Simulate Kosmos posting completion back to StreamLab
    completed = len(final_state.get("completed_tasks", []))
    bus.post(
        from_agent="kosmos_organizer",
        to_agent="streamlab_monitor",
        message_type="recording_organized",
        payload={
            "recordings_path": str(FIXTURE_DIR),
            "files_processed": completed,
            "exit_reason": final_state.get("exit_reason"),
        },
        run_id=final_state["run_id"],
    )

    # StreamLab inbox must contain the recording_organized message
    streamlab_pending = bus.read_pending("streamlab_monitor")
    assert len(streamlab_pending) == 1
    assert streamlab_pending[0].message_type == "recording_organized"
    assert streamlab_pending[0].from_agent == "kosmos_organizer"
    assert streamlab_pending[0].payload["files_processed"] == completed
