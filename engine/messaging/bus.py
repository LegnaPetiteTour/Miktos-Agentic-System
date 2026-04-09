"""
MessageBus — JSON-backed inter-agent message bus.

Storage: data/messages/<to_agent>/pending/<message_id>.json
After delivery: moved to data/messages/<to_agent>/delivered/

This is the v1 implementation. The interface is stable.
Swap the backing store in Phase 5 by replacing this class.

Atomicity guarantee: post() writes to a temp file then renames.
This prevents partial reads if the process is interrupted mid-write.

Phase 4d additions — pub/sub:
  subscribe(topic, agent_id)   — register agent as subscriber to topic
  unsubscribe(topic, agent_id) — remove agent from subscriber list
  publish(topic, from_agent, payload) — deliver to all topic subscribers

Subscription registry: data/messages/subscriptions.json
  Format: { "<topic>": ["<agent_id>", ...], ... }
  Atomic writes — safe for concurrent access.
  See data/messages/subscriptions.example.json for the canonical format.
"""

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from engine.messaging.models import AgentMessage


class MessageBus:
    """
    JSON-backed inter-agent message bus.

    Directory layout:
      <base_dir>/<agent>/pending/<message_id>.json
      <base_dir>/<agent>/delivered/<message_id>.json
    """

    def __init__(self, base_dir: str | Path = "data/messages") -> None:
        self.base_dir = Path(base_dir)

    def _inbox(self, agent: str) -> Path:
        p = self.base_dir / agent / "pending"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _delivered(self, agent: str) -> Path:
        p = self.base_dir / agent / "delivered"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def post(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        payload: dict[str, Any],
        run_id: str = "",
    ) -> AgentMessage:
        """Write one message to the recipient's pending inbox. Atomic write."""
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        inbox = self._inbox(to_agent)
        target = inbox / f"{msg.message_id}.json"

        # Atomic: write to temp then rename
        fd, tmp_path = tempfile.mkstemp(dir=inbox, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(msg.to_dict(), f, indent=2)
            os.replace(tmp_path, target)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        self.append_log(
            event="POSTED",
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            message_id=msg.message_id,
        )
        return msg

    def read_pending(self, for_agent: str) -> list[AgentMessage]:
        """Return all pending messages for an agent. Does not mark delivered."""
        inbox = self._inbox(for_agent)
        messages = []
        for path in sorted(inbox.glob("*.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
                messages.append(AgentMessage.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                pass  # skip corrupt files
        return messages

    def acknowledge(self, message: AgentMessage) -> None:
        """Move message from pending/ to delivered/."""
        src = self._inbox(message.to_agent) / f"{message.message_id}.json"
        if not src.exists():
            return
        dst_dir = self._delivered(message.to_agent)
        dst = dst_dir / f"{message.message_id}.json"
        message.status = "acknowledged"
        # Rewrite with updated status then move
        fd, tmp_path = tempfile.mkstemp(dir=dst_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(message.to_dict(), f, indent=2)
            os.replace(tmp_path, dst)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        src.unlink(missing_ok=True)
        self.append_log(
            event="ACKNOWLEDGED",
            from_agent=message.from_agent,
            to_agent=message.to_agent,
            message_type=message.message_type,
            message_id=message.message_id,
        )

    def clear_delivered(self, for_agent: str) -> int:
        """Delete delivered messages. Returns count deleted."""
        delivered = self._delivered(for_agent)
        count = 0
        for path in delivered.glob("*.json"):
            path.unlink(missing_ok=True)
            count += 1
        return count

    def append_log(
        self,
        event: str,
        from_agent: str,
        to_agent: str,
        message_type: str,
        message_id: str,
        notes: str = "",
    ) -> None:
        """
        Append one line to data/messages/message.log.

        Format:
          <ISO timestamp>  <event>  <from_agent> -> <to_agent>
          <message_type>  <msg_id[:8]>  <notes>

        Append-only. Never truncated. Safe to tail -f.
        """
        self.base_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.base_dir / "message.log"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        short_id = message_id[:8]
        parts = [
            ts, f"{event:<13}", f"{from_agent} -> {to_agent}", message_type, short_id
        ]
        if notes:
            parts.append(notes)
        line = "  ".join(parts) + "\n"
        with open(log_path, "a") as f:
            f.write(line)

    # ------------------------------------------------------------------
    # Pub/Sub — Phase 4d
    # ------------------------------------------------------------------

    def _subscriptions_path(self) -> Path:
        return self.base_dir / "subscriptions.json"

    def _load_subscriptions(self) -> dict[str, list[str]]:
        """
        Load the subscription registry from disk.

        Returns an empty dict if the file does not exist or is corrupt.
        Never raises.
        """
        path = self._subscriptions_path()
        if not path.exists():
            return {}
        try:
            with open(path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except json.JSONDecodeError:
            return {}

    def _save_subscriptions(
        self, subscriptions: dict[str, list[str]]
    ) -> None:
        """Persist the subscription registry atomically."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self._subscriptions_path()
        fd, tmp_path = tempfile.mkstemp(dir=self.base_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(subscriptions, f, indent=2)
                f.write("\n")
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def subscribe(self, topic: str, agent_id: str) -> None:
        """
        Register agent_id as a subscriber to topic.

        Subscriptions persist to data/messages/subscriptions.json.
        If the agent is already subscribed to this topic, this is a no-op.
        Atomic write — safe to call concurrently.
        """
        subs = self._load_subscriptions()
        if topic not in subs:
            subs[topic] = []
        if agent_id not in subs[topic]:
            subs[topic].append(agent_id)
            self._save_subscriptions(subs)

    def unsubscribe(self, topic: str, agent_id: str) -> None:
        """
        Remove agent_id from the subscriber list for topic.

        No-op if agent_id is not subscribed or topic does not exist.
        Atomic write.
        """
        subs = self._load_subscriptions()
        if topic in subs and agent_id in subs[topic]:
            subs[topic].remove(agent_id)
            self._save_subscriptions(subs)

    def publish(
        self,
        topic: str,
        from_agent: str,
        payload: dict[str, Any],
        run_id: str = "",
    ) -> list[AgentMessage]:
        """
        Publish an event to all subscribers of topic.

        The publisher does not need to know who the subscribers are.
        Each subscriber receives an independent AgentMessage in their inbox.

        If no subscribers are registered for topic, returns [] silently.
        Logs one PUBLISHED event with subscriber count, then one POSTED
        event per delivery (via the existing post() call).

        This is the core of Phase 4d. One publish(), N deliveries.
        Backing store: JSON (Redis upgrade path available in Phase 5).
        """
        subs = self._load_subscriptions()
        subscribers = subs.get(topic, [])

        if not subscribers:
            return []

        # Log PUBLISHED first so the log entry precedes the per-subscriber
        # POSTED entries that post() writes.
        publish_id = uuid.uuid4().hex
        self.append_log(
            event="PUBLISHED",
            from_agent=from_agent,
            to_agent=f"[{len(subscribers)} subscriber(s)]",
            message_type=topic,
            message_id=publish_id,
            notes=", ".join(subscribers),
        )

        messages: list[AgentMessage] = []
        for subscriber in subscribers:
            msg = self.post(
                from_agent=from_agent,
                to_agent=subscriber,
                message_type=topic,
                payload=payload,
                run_id=run_id,
            )
            messages.append(msg)

        return messages
