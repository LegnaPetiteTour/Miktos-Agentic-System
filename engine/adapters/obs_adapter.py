"""
engine/adapters/obs_adapter.py — OBS Studio adapter (ADR-009).

Wraps ``obsws_python`` to satisfy the ``DeviceAdapter`` protocol.

OBS capabilities (per ADR-009):
  ✓ stream start/stop          ✓ scene switch
  ✓ recording start/stop       ✓ snapshot (GetSourceScreenshot)
  ✓ audio mute/volume          ✓ overlay (Browser Source / SetInputSettings)
  ✓ health                     ✓ transition control
  ✗ layout switch  (Pearl concept)
  ✗ recording download         (files are on the OBS host machine)
  ✗ live preview HLS/WebRTC
"""

from __future__ import annotations

import base64
import os

from engine.adapters.base import AdapterCapabilities


def _make_client():  # noqa: ANN202
    import obsws_python as obs  # noqa: PLC0415

    return obs.ReqClient(
        host=os.getenv("OBS_HOST", "localhost"),
        port=int(os.getenv("OBS_PORT", "4455")),
        password=os.getenv("OBS_PASSWORD", ""),
        timeout=5,
    )


def _safe_disconnect(cl) -> None:  # noqa: ANN001
    try:
        cl.disconnect()
    except Exception:  # noqa: BLE001
        pass


class OBSAdapter:
    """OBS Studio WebSocket adapter."""

    def connect(self) -> bool:
        try:
            cl = _make_client()
            cl.get_version()
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        pass  # connections are per-call; nothing to hold open

    def health(self) -> dict:
        try:
            cl = _make_client()
            version = cl.get_version().obs_version
            _safe_disconnect(cl)
            return {"ok": True, "platform": "obs_studio", "version": version}
        except Exception as exc:
            return {"ok": False, "platform": "obs_studio", "error": str(exc)}

    def capabilities(self) -> AdapterCapabilities:
        """Return OBS capability flags.  Does NOT require a live connection."""
        return AdapterCapabilities(
            supports_stream_start=True,
            supports_stream_stop=True,
            supports_recording_start=True,
            supports_recording_stop=True,
            supports_recording_download=False,   # files reside on OBS host
            supports_layout_switch=False,        # Pearl concept; OBS uses scenes
            supports_scene_switch=True,
            supports_snapshot=True,
            supports_overlay=True,
            supports_audio_mute=True,
            supports_audio_volume=True,
            supports_health=True,
            supports_live_preview_hls=False,
            supports_live_preview_webrtc=False,
            supports_caption_ingest=False,
            supports_transition_control=True,
            supported_channels=[],
            platform_name="obs_studio",
        )

    def get_state(self) -> dict:
        try:
            cl = _make_client()
            stream = cl.get_stream_status()
            scenes = cl.get_scene_list()
            _safe_disconnect(cl)
            return {
                "ok": True,
                "streaming": stream.output_active,
                "current_scene": scenes.current_program_scene_name,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def start_stream(self, channel: str | None = None) -> bool:
        try:
            cl = _make_client()
            cl.start_stream()
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def stop_stream(self, channel: str | None = None) -> bool:
        try:
            cl = _make_client()
            cl.stop_stream()
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def start_recording(self, channel: str | None = None) -> bool:
        try:
            cl = _make_client()
            cl.start_record()
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def stop_recording(self, channel: str | None = None) -> bool:
        try:
            cl = _make_client()
            cl.stop_record()
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def get_layouts(self, channel: str | None = None) -> list[dict]:
        return []  # OBS uses scenes, not layouts

    def switch_layout(self, layout_id: str, channel: str | None = None) -> bool:
        return False  # Use switch_scene via scene_name instead

    def switch_scene(self, scene_name: str) -> bool:
        """OBS-specific: switch the program scene."""
        try:
            cl = _make_client()
            cl.set_current_program_scene(scene_name)
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def mute(self, channel: str) -> bool:
        try:
            cl = _make_client()
            cl.set_input_mute(channel, True)
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def unmute(self, channel: str) -> bool:
        try:
            cl = _make_client()
            cl.set_input_mute(channel, False)
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def set_volume(self, channel: str, level: float) -> bool:
        try:
            cl = _make_client()
            cl.set_input_volume(channel, vol_db=level)
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def snapshot(self, channel: str | None = None) -> bytes | None:
        """Return raw JPEG bytes from OBS GetSourceScreenshot."""
        try:
            src = channel or os.getenv("OBS_PREVIEW_SOURCE", "Program")
            cl = _make_client()
            resp = cl.get_source_screenshot(src, "jpg", 320, 180, 85)
            _safe_disconnect(cl)
            # image_data is already base64; decode to raw bytes
            b64 = resp.image_data
            if b64.startswith("data:"):
                b64 = b64.split(",", 1)[1]
            return base64.b64decode(b64)
        except Exception:
            return None

    def apply_overlay(self, payload: dict) -> bool:
        """Push text to OBS Browser Source named by ``payload["input"]``."""
        try:
            cl = _make_client()
            input_name = payload.get("input", os.getenv("OBS_LOWER_THIRD_SOURCE", "Lower Third"))
            settings = {k: v for k, v in payload.items() if k != "input"}
            cl.set_input_settings(input_name, settings, True)
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def clear_overlay(self, overlay_id: str) -> bool:
        try:
            cl = _make_client()
            cl.set_input_settings(overlay_id, {"text": ""}, True)
            _safe_disconnect(cl)
            return True
        except Exception:
            return False

    def list_recordings(self, channel: str | None = None) -> list[dict]:
        return []  # OBS recordings are local to the host machine

    def download_recording(self, recording_id: str, dest_dir: str) -> str:
        raise NotImplementedError("OBS does not support remote recording download")
