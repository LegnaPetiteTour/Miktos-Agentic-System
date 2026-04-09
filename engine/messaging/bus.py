"""
MessageBus — JSON-backed inter-agent message bus.

Storage: data/messages/<to_agent>/pending/<message_id>.json
After delivery: moved to data/messages/<to_agent>/delivered/

This is the v1 implementation. The interface is stable.
Swap the backing store in Phase 4d by replacing this class.

Atomicity guarantee: post() writes to a temp file then renames.
This prevents partial reads if the process is interrupted mid-write.
"""

import json
import os
import tempfile
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
          <ISO timestamp>  <event>  <from_agent> -> <to_agent>  <message_type>  <msg_id[:8]>  <notes>

        Append-only. Never truncated. Safe to tail -f.
        """
        self.base_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.base_dir / "message.log"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        short_id = message_id[:8]
        parts = [ts, f"{event:<13}", f"{from_agent} -> {to_agent}", message_type, short_id]
        if notes:
            parts.append(notes)
        line = "  ".join(parts) + "\n"
        with open(log_path, "a") as f:
            f.write(line)
