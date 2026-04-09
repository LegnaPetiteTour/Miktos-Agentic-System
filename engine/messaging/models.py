"""
AgentMessage — the envelope for all inter-agent communication.

Fields:
  message_id   str   unique ID (uuid hex)
  from_agent   str   sender identity  e.g. "streamlab_monitor"
  to_agent     str   recipient identity e.g. "kosmos_organizer"
  message_type str   intent label  e.g. "recording_ready"
  payload      dict  message-type-specific data
  timestamp    str   ISO format
  status       str   "pending" | "delivered" | "acknowledged"
  run_id       str   run_id of the originating graph.invoke() call
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class AgentMessage:
    from_agent: str
    to_agent: str
    message_type: str
    payload: dict[str, Any]
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "pending"
    run_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "status": self.status,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMessage":
        return cls(
            message_id=data["message_id"],
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            message_type=data["message_type"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", ""),
            status=data.get("status", "pending"),
            run_id=data.get("run_id", ""),
        )
