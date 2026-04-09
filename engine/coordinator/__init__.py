"""
engine.coordinator — Phase 4c coordinator / task delegation layer.

The coordinator is a meta-agent that sits above the LangGraph engine.
It decomposes a goal into parallel heterogeneous subtasks, dispatches
workers, and aggregates results into a single session artifact.

This is NOT a LangGraph graph. It is a plain Python coordinator class
that uses the message bus for I/O and ThreadPoolExecutor for dispatch.

Public API:
  SessionCoordinator  — coordinates organize, thumbnail, metadata workers
"""

from engine.coordinator.coordinator import SessionCoordinator
from engine.coordinator.workers import KosmosWorker, MetadataWorker, ThumbnailWorker

__all__ = [
    "SessionCoordinator",
    "KosmosWorker",
    "ThumbnailWorker",
    "MetadataWorker",
]
