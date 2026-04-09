# engine/messaging — inter-agent message bus (Phase 4b)
from engine.messaging.models import AgentMessage
from engine.messaging.bus import MessageBus

__all__ = ["AgentMessage", "MessageBus"]
