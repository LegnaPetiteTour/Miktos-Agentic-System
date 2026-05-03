"""
engine/adapters/pearl_adapter.py — Epiphan Pearl adapter (ADR-009).

Wraps ``PearlClient`` to satisfy the ``DeviceAdapter`` protocol.

Pearl capabilities (per ADR-009):
  ✓ stream start/stop          ✓ recording download
  ✓ recording start/stop*      ✓ layout switch
  ✓ snapshot (thumbnail)       ✓ health
  ✓ live preview (HLS)         ✗ scene switch  (OBS concept)
  ✗ overlay / graphics         ✗ audio mute/volume
  ✗ transition control

  * Pearl exposes recorder start/stop via the legacy CGI API;
    this adapter uses the v2 REST API which provides status only.
    Recording control is exposed at the capability level but returns
    False until the legacy CGI path is wired.
"""

from __future__ import annotations

import os

from engine.adapters.base import AdapterCapabilities


class PearlAdapter:
    """Epiphan Pearl REST adapter."""

    def connect(self) -> bool:
        try:
            from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

            pc = PearlClient()
            pc.get_firmware_info()
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        pass  # Pearl is stateless HTTP

    def health(self) -> dict:
        try:
            from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

            pc = PearlClient()
            info = pc.get_firmware_info()
            return {
                "ok": True,
                "platform": "epiphan_pearl",
                "firmware_version": info.get("version") or info.get("firmware_version"),
            }
        except Exception as exc:
            return {"ok": False, "platform": "epiphan_pearl", "error": str(exc)}

    def capabilities(self) -> AdapterCapabilities:
        """Return Pearl capability flags.  Does NOT require a live connection."""
        env_ch_en = os.getenv("PEARL_CHANNEL_EN", "1")
        env_ch_fr = os.getenv("PEARL_CHANNEL_FR", "2")
        return AdapterCapabilities(
            supports_stream_start=True,
            supports_stream_stop=True,
            supports_recording_start=False,   # legacy CGI only; not wired yet
            supports_recording_stop=False,
            supports_recording_download=True,
            supports_layout_switch=True,
            supports_scene_switch=False,
            supports_snapshot=True,
            supports_overlay=False,
            supports_audio_mute=False,
            supports_audio_volume=False,
            supports_health=True,
            supports_live_preview_hls=True,
            supports_live_preview_webrtc=False,
            supports_caption_ingest=False,
            supports_transition_control=False,
            supported_channels=[env_ch_en, env_ch_fr],
            platform_name="epiphan_pearl",
        )

    def get_state(self) -> dict:
        try:
            from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

            pc = PearlClient()
            channels = pc.get_channels()
            return {"ok": True, "channels": channels}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def start_stream(self, channel: str | None = None) -> bool:
        try:
            from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

            pc = PearlClient()
            pc.start_streaming(channel or os.getenv("PEARL_CHANNEL_EN", "1"))
            return True
        except Exception:
            return False

    def stop_stream(self, channel: str | None = None) -> bool:
        try:
            from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

            pc = PearlClient()
            pc.stop_streaming(channel or os.getenv("PEARL_CHANNEL_EN", "1"))
            return True
        except Exception:
            return False

    def start_recording(self, channel: str | None = None) -> bool:
        return False  # Not yet wired via v2 API

    def stop_recording(self, channel: str | None = None) -> bool:
        return False  # Not yet wired via v2 API

    def get_layouts(self, channel: str | None = None) -> list[dict]:
        try:
            from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

            pc = PearlClient()
            return pc.get_layouts(channel or os.getenv("PEARL_CHANNEL_EN", "1"))
        except Exception:
            return []

    def switch_layout(self, layout_id: str, channel: str | None = None) -> bool:
        try:
            from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

            pc = PearlClient()
            pc.switch_layout(channel or os.getenv("PEARL_CHANNEL_EN", "1"), layout_id)
            return True
        except Exception:
            return False

    def mute(self, channel: str) -> bool:
        return False

    def unmute(self, channel: str) -> bool:
        return False

    def set_volume(self, channel: str, level: float) -> bool:
        return False

    def snapshot(self, channel: str | None = None) -> bytes | None:
        try:
            import requests  # noqa: PLC0415
            from requests.auth import HTTPBasicAuth  # noqa: PLC0415

            host = os.getenv("PEARL_HOST", "192.168.255.250")
            port = os.getenv("PEARL_PORT", "80")
            password = os.getenv("PEARL_PASSWORD", "")
            ch = channel or os.getenv("PEARL_CHANNEL_EN", "1")
            resp = requests.get(
                f"http://{host}:{port}/api/channels/{ch}/thumbnail",
                auth=HTTPBasicAuth("admin", password),
                timeout=5,
            )
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None

    def apply_overlay(self, payload: dict) -> bool:
        return False  # Pearl does not support runtime text overlays

    def clear_overlay(self, overlay_id: str) -> bool:
        return False

    def list_recordings(self, channel: str | None = None) -> list[dict]:
        try:
            from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

            pc = PearlClient()
            recorders = pc.get_recorders()
            files: list[dict] = []
            for rec in recorders:
                try:
                    rec_files = pc.get_recorder_files(str(rec.get("id", "")))
                    files.extend(rec_files)
                except Exception:
                    pass
            return files
        except Exception:
            return []

    def download_recording(self, recording_id: str, dest_dir: str) -> str:
        # recording_id format: "{recorder_id}/{file_id}"
        try:
            from domains.epiphan.tools.pearl_client import PearlClient  # noqa: PLC0415

            recorder_id, file_id = recording_id.split("/", 1)
            pc = PearlClient()
            dest_path = f"{dest_dir}/{file_id}"
            return pc.download_recording(recorder_id, file_id, dest_path)
        except Exception as exc:
            raise RuntimeError(f"Pearl download failed: {exc}") from exc
