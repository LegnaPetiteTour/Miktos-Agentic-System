# engine/adapters — Formal adapter contract (ADR-009)
#
# All platform adapters implement DeviceAdapter (Protocol) and return
# an accurate AdapterCapabilities dataclass.
#
# Exports consumed by application code:
#   from engine.adapters import DeviceAdapter, AdapterCapabilities, get_adapter

from engine.adapters.base import AdapterCapabilities, DeviceAdapter
from engine.adapters.registry import get_adapter

__all__ = ["AdapterCapabilities", "DeviceAdapter", "get_adapter"]
