"""
Phase 4d tests — Pub/Sub event bus.

Five CI-friendly tests using tmp_path for full isolation.

Tests:
  1. subscribe() registers an agent in subscriptions.json
  2. subscribe() is idempotent — duplicate registrations are no-ops
  3. publish() delivers to all subscribers with correct payload
  4. publish() to an empty topic returns [] with no side effects
  5. publish() writes a PUBLISHED log line before per-subscriber POSTED lines
"""

import json
from pathlib import Path

from engine.messaging.bus import MessageBus


# ---------------------------------------------------------------------------
# Test 1 — subscribe registers agent
# ---------------------------------------------------------------------------

def test_subscribe_registers_agent(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=str(tmp_path / "messages"))
    bus.subscribe("recording_stopped", "agent_a")
    bus.subscribe("recording_stopped", "agent_b")

    subs_path = tmp_path / "messages" / "subscriptions.json"
    assert subs_path.exists(), "subscriptions.json was not created"

    with open(subs_path) as f:
        data = json.load(f)

    assert "recording_stopped" in data
    assert "agent_a" in data["recording_stopped"]
    assert "agent_b" in data["recording_stopped"]


# ---------------------------------------------------------------------------
# Test 2 — subscribe is idempotent
# ---------------------------------------------------------------------------

def test_subscribe_is_idempotent(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=str(tmp_path / "messages"))
    bus.subscribe("topic_x", "agent_a")
    bus.subscribe("topic_x", "agent_a")  # duplicate — must be no-op
    bus.subscribe("topic_x", "agent_a")  # third call — also no-op

    subs_path = tmp_path / "messages" / "subscriptions.json"
    with open(subs_path) as f:
        data = json.load(f)

    assert data["topic_x"].count("agent_a") == 1


# ---------------------------------------------------------------------------
# Test 3 — publish delivers to all subscribers
# ---------------------------------------------------------------------------

def test_publish_delivers_to_all_subscribers(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=str(tmp_path / "messages"))
    bus.subscribe("test_topic", "agent_a")
    bus.subscribe("test_topic", "agent_b")

    payload = {"key": "value", "num": 42}
    returned = bus.publish(
        topic="test_topic",
        from_agent="publisher",
        payload=payload,
    )

    assert len(returned) == 2

    # Both agents must have exactly one message
    msgs_a = bus.read_pending(for_agent="agent_a")
    msgs_b = bus.read_pending(for_agent="agent_b")
    assert len(msgs_a) == 1
    assert len(msgs_b) == 1

    # Payload must be identical
    assert msgs_a[0].payload == payload
    assert msgs_b[0].payload == payload

    # from_agent must be the publisher, not the bus
    assert msgs_a[0].from_agent == "publisher"
    assert msgs_b[0].from_agent == "publisher"

    # message_type must equal the topic name
    assert msgs_a[0].message_type == "test_topic"
    assert msgs_b[0].message_type == "test_topic"

    # Publisher must NOT have a message in its own inbox
    publisher_inbox = bus.read_pending(for_agent="publisher")
    assert publisher_inbox == []


# ---------------------------------------------------------------------------
# Test 4 — publish to empty topic returns [] silently
# ---------------------------------------------------------------------------

def test_publish_to_empty_topic_returns_empty_list(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=str(tmp_path / "messages"))
    # No subscriptions registered at all
    result = bus.publish(
        topic="no_subscribers_topic",
        from_agent="publisher",
        payload={"x": 1},
    )
    assert result == []

    # No pending/ directories should have been created for any agent
    messages_dir = tmp_path / "messages"
    agent_dirs = [
        d for d in messages_dir.iterdir()
        if d.is_dir() and d.name not in (".gitkeep",)
    ] if messages_dir.exists() else []
    assert agent_dirs == [], f"Unexpected dirs created: {agent_dirs}"


# ---------------------------------------------------------------------------
# Test 5 — publish writes PUBLISHED log line before POSTED lines
# ---------------------------------------------------------------------------

def test_publish_logged_correctly(tmp_path: Path) -> None:
    bus = MessageBus(base_dir=str(tmp_path / "messages"))
    bus.subscribe("log_topic", "sub_one")
    bus.subscribe("log_topic", "sub_two")

    bus.publish(
        topic="log_topic",
        from_agent="log_publisher",
        payload={"event": "test"},
    )

    log_path = tmp_path / "messages" / "message.log"
    assert log_path.exists(), "message.log was not written"

    lines = log_path.read_text().splitlines()
    # Filter to just our publish event lines
    relevant = [
        line for line in lines
        if "log_topic" in line or "log_publisher" in line
    ]
    assert len(relevant) >= 3, (
        f"Expected at least 3 log lines (1 PUBLISHED + 2 POSTED), "
        f"got {len(relevant)}: {relevant}"
    )

    # The PUBLISHED line must exist
    published_lines = [line for line in relevant if "PUBLISHED" in line]
    assert len(published_lines) == 1, "Expected exactly one PUBLISHED line"
    assert "[2 subscriber(s)]" in published_lines[0]

    # The POSTED lines must exist — one per subscriber
    posted_lines = [line for line in relevant if "POSTED" in line]
    assert len(posted_lines) == 2, (
        f"Expected 2 POSTED lines, got {len(posted_lines)}"
    )

    # PUBLISHED must appear before POSTED lines in the log
    published_idx = relevant.index(published_lines[0])
    for posted_line in posted_lines:
        posted_idx = relevant.index(posted_line)
        assert published_idx < posted_idx, (
            "PUBLISHED line must appear before POSTED lines"
        )
