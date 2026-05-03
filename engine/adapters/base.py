"""
engine/adapters/base.py — Formal adapter contract (ADR-009).

Defines the ``DeviceAdapter`` structural Protocol that every platform
adapter must satisfy, and the ``AdapterCapabilities`` dataclass that
drives cockpit rendering.

The cockpit renders controls based on *capabilities*, not hardware names.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Capability flags
# ---------------------------------------------------------------------------


@dataclass
class AdapterCapabilities:
    """
    Flat capability flags returned by every adapter.

    All flags default to ``False`` / empty so adapters only declare what
    they actually support.
    """

    # Streaming
    supports_stream_start: bool = False
    supports_stream_stop: bool = False

    # Recording
    supports_recording_start: bool = False
    supports_recording_stop: bool = False
    supports_recording_download: bool = False

    # Layout / scene switching
    supports_layout_switch: bool = False   # Pearl-style pre-defined layouts
    supports_scene_switch: bool = False    # OBS-style scenes

    # Visual
    supports_snapshot: bool = False

    # Overlays / graphics
    supports_overlay: bool = False

    # Audio
    supports_audio_mute: bool = False
    supports_audio_volume: bool = False

    # Health & diagnostics
    supports_health: bool = False

    # Preview streams
    supports_live_preview_hls: bool = False
    supports_live_preview_webrtc: bool = False

    # Caption ingest (for adapters that also ingest captions)
    supports_caption_ingest: bool = False

    # Transition control
    supports_transition_control: bool = False

    # Channels this adapter operates on (empty = hardware manages internally)
    supported_channels: list[str] = field(default_factory=list)

    # Identification
    platform_name: str = ""
    firmware_version: str | None = None

    def as_dict(self) -> dict:
        """Return all fields as a plain dict (for JSON serialisation)."""
        return {
            "supports_stream_start": self.supports_stream_start,
            "supports_stream_stop": self.supports_stream_stop,
            "supports_recording_start": self.supports_recording_start,
            "supports_recording_stop": self.supports_recording_stop,
            "supports_recording_download": self.supports_recording_download,
            "supports_layout_switch": self.supports_layout_switch,
            "supports_scene_switch": self.supports_scene_switch,
            "supports_snapshot": self.supports_snapshot,
            "supports_overlay": self.supports_overlay,
            "supports_audio_mute": self.supports_audio_mute,
            "supports_audio_volume": self.supports_audio_volume,
            "supports_health": self.supports_health,
            "supports_live_preview_hls": self.supports_live_preview_hls,
            "supports_live_preview_webrtc": self.supports_live_preview_webrtc,
            "supports_caption_ingest": self.supports_caption_ingest,
            "supports_transition_control": self.supports_transition_control,
            "supported_channels": self.supported_channels,
            "platform_name": self.platform_name,
            "firmware_version": self.firmware_version,
        }


# ---------------------------------------------------------------------------
# DeviceAdapter Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DeviceAdapter(Protocol):
    """
    Structural protocol every platform adapter must satisfy.

    Rule: ``capabilities()`` must never require a live hardware connection.
    All other methods may raise or return falsy values when hardware is
    unavailable.
    """

    # -- Lifecycle -----------------------------------------------------------

    def connect(self) -> bool:
        """Open (or verify) hardware connection. Return True on success."""
        ...

    def disconnect(self) -> None:
        """Release connection resources gracefully."""
        ...

    def health(self) -> dict:
        """Return a dict describing current hardware health. Never raises."""
        ...

    # -- Capability discovery ------------------------------------------------

    def capabilities(self) -> AdapterCapabilities:
        """
        Return static capability flags for this platform.

        Must not require a live connection.
        """
        ...

    # -- State ---------------------------------------------------------------

    def get_state(self) -> dict:
        """Return current device state (streaming, recording, …)."""
        ...

    # -- Stream control ------------------------------------------------------

    def start_stream(self, channel: str | None = None) -> bool: ...
    def stop_stream(self, channel: str | None = None) -> bool: ...

    # -- Recording control ---------------------------------------------------

    def start_recording(self, channel: str | None = None) -> bool: ...
    def stop_recording(self, channel: str | None = None) -> bool: ...

    # -- Layout / scene switching --------------------------------------------

    def get_layouts(self, channel: str | None = None) -> list[dict]: ...
    def switch_layout(
        self, layout_id: str, channel: str | None = None
    ) -> bool: ...

    # -- Audio ---------------------------------------------------------------

    def mute(self, channel: str) -> bool: ...
    def unmute(self, channel: str) -> bool: ...
    def set_volume(self, channel: str, level: float) -> bool: ...

    # -- Visual --------------------------------------------------------------

    def snapshot(self, channel: str | None = None) -> bytes | None:
        """Return raw JPEG bytes, or None if unavailable."""
        ...

    # -- Overlays / graphics -------------------------------------------------

    def apply_overlay(self, payload: dict) -> bool: ...
    def clear_overlay(self, overlay_id: str) -> bool: ...

    # -- Recording retrieval -------------------------------------------------

    def list_recordings(self, channel: str | None = None) -> list[dict]: ...
    def download_recording(
        self, recording_id: str, dest_dir: str
    ) -> str: ...
