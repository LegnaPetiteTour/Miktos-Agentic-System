"""
engine/adapters/rehearsal_adapter.py — Simulated hardware adapter.

Used automatically when rehearsal mode is active (``engine/rehearsal.py``).
Every hardware call returns plausible fake data without opening any
network connection.  The cockpit renders and behaves normally.

Capabilities are set to ``True`` across the board so every control panel
renders during a rehearsal — the operator can practise the full workflow.
"""

from __future__ import annotations

from engine.adapters.base import AdapterCapabilities


class RehearsalAdapter:
    """
    Mock hardware adapter for rehearsal / simulation mode.

    Implements the full ``DeviceAdapter`` structural Protocol but every
    method returns a safe simulated response instead of touching hardware.
    """

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def capabilities(self) -> AdapterCapabilities:
        """Return full capability set — all controls visible in rehearsal."""
        return AdapterCapabilities(
            supports_stream_start=True,
            supports_stream_stop=True,
            supports_recording_start=True,
            supports_recording_stop=True,
            supports_recording_download=True,
            supports_layout_switch=True,
            supports_scene_switch=True,
            supports_snapshot=True,
            supports_overlay=True,
            supports_audio_mute=True,
            supports_audio_volume=True,
            supports_health=True,
            supports_live_preview_hls=False,
            supports_transition_control=True,
            platform_name="rehearsal",
            supported_channels=["1", "2"],
        )

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:  # noqa: D401
        """No-op — rehearsal mode needs no live connection."""

    def disconnect(self) -> None:
        """No-op."""

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> dict:
        return {
            "status": "rehearsal",
            "streaming": False,
            "recording": False,
            "rehearsal": True,
        }

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def get_state(self) -> dict:
        return {
            "streaming": False,
            "recording": False,
            "scene": "Rehearsal Scene",
            "rehearsal": True,
        }

    # ------------------------------------------------------------------
    # Stream / recording
    # ------------------------------------------------------------------

    def start_stream(self) -> dict:
        return {"ok": True, "rehearsal": True, "message": "Stream started (simulated)"}

    def stop_stream(self) -> dict:
        return {"ok": True, "rehearsal": True, "message": "Stream stopped (simulated)"}

    def start_recording(self) -> dict:
        return {"ok": True, "rehearsal": True, "message": "Recording started (simulated)"}

    def stop_recording(self) -> dict:
        return {"ok": True, "rehearsal": True, "message": "Recording stopped (simulated)"}

    def list_recordings(self) -> list:
        return [
            {"id": "rehearsal/001", "name": "rehearsal_recording_001.mp4", "size_mb": 0}
        ]

    def download_recording(self, recording_id: str, dest_dir: str) -> str:
        return f"{dest_dir}/rehearsal_recording.mp4"

    # ------------------------------------------------------------------
    # Layout / scene
    # ------------------------------------------------------------------

    def get_layouts(self, channel_id: str = "1") -> list:
        return [
            {"id": "1", "name": "Main Presenter"},
            {"id": "2", "name": "Speaker Close-Up"},
            {"id": "3", "name": "Wide Shot"},
            {"id": "4", "name": "Lower Third"},
        ]

    def switch_layout(self, channel_id: str, layout_id: str) -> dict:
        return {"ok": True, "rehearsal": True, "layout_id": layout_id}

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    def mute(self, source: str) -> dict:
        return {"ok": True, "rehearsal": True, "muted": True, "source": source}

    def unmute(self, source: str) -> dict:
        return {"ok": True, "rehearsal": True, "muted": False, "source": source}

    def set_volume(self, source: str, volume_db: float) -> dict:
        return {"ok": True, "rehearsal": True, "volume_db": volume_db, "source": source}

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self, channel_id: str = "1") -> bytes:
        # Return a minimal valid 1×1 white PNG (67 bytes)
        import base64  # noqa: PLC0415

        _PNG_1X1 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
            "z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
        )
        return base64.b64decode(_PNG_1X1)

    # ------------------------------------------------------------------
    # Overlays
    # ------------------------------------------------------------------

    def apply_overlay(self, preset: str, text: str = "") -> dict:
        return {"ok": True, "rehearsal": True, "preset": preset}

    def clear_overlay(self) -> dict:
        return {"ok": True, "rehearsal": True}
