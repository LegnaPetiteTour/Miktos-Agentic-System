"""
tests/test_phase_14.py — Phase 14 live-production-panel tests.

12 tests covering:
  - /api/switcher/obs/scenes   (list + unavailable)
  - /api/switcher/obs/switch   (success + error)
  - /api/switcher/pearl/channels (unavailable)
  - /api/health/snapshot       (always 200, obs+pearl probed)
  - /api/audio/inputs          (list + unavailable)
  - /api/audio/mute            (success)
  - /api/audio/volume          (success)
  - /api/captions/stream       (200 text/event-stream)
  - /api/captions/append       (writes + returns entry)

Target: 140 prior + 12 = 152 passed, 1 permanent skip.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from web.server import app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# /api/switcher — OBS scenes
# ---------------------------------------------------------------------------


def test_switcher_obs_scenes_unavailable():
    """OBS offline → 503 with error key."""
    with patch("web.api.switcher._obs_client", side_effect=ConnectionRefusedError("refused")):
        resp = client.get("/api/switcher/obs/scenes")
    assert resp.status_code == 503
    assert "error" in resp.json()


def test_switcher_obs_scenes_ok():
    """OBS reachable → 200 with scenes list and current."""
    mock_cl = MagicMock()
    mock_cl.get_scene_list.return_value = MagicMock(
        current_program_scene_name="Main",
        scenes=[{"sceneName": "Main"}, {"sceneName": "Titles"}],
    )
    with patch("web.api.switcher._obs_client", return_value=mock_cl):
        resp = client.get("/api/switcher/obs/scenes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current"] == "Main"
    assert "Titles" in data["scenes"]


def test_switcher_obs_switch_ok():
    """POST /switch → 200 success."""
    mock_cl = MagicMock()
    with patch("web.api.switcher._obs_client", return_value=mock_cl):
        resp = client.post(
            "/api/switcher/obs/switch",
            json={"scene_name": "Titles"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["scene"] == "Titles"
    mock_cl.set_current_program_scene.assert_called_once_with("Titles")


def test_switcher_obs_switch_error():
    """POST /switch with OBS error → 503."""
    with patch("web.api.switcher._obs_client", side_effect=OSError("connect failed")):
        resp = client.post(
            "/api/switcher/obs/switch",
            json={"scene_name": "Main"},
        )
    assert resp.status_code == 503
    assert resp.json()["success"] is False


def test_switcher_pearl_channels_unavailable():
    """Pearl offline → 503 with error key."""
    # PearlClient is imported inside the route function, so we patch it at its
    # source module to intercept the runtime import lookup.
    with patch("domains.epiphan.tools.pearl_client.PearlClient") as MockPC:
        MockPC.return_value.get_channels.side_effect = Exception("timeout")
        resp = client.get("/api/switcher/pearl/channels")
    assert resp.status_code == 503
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------


def test_health_snapshot_always_200():
    """Snapshot always returns 200 regardless of hardware state."""
    with (
        patch("web.api.health._obs_probe", return_value=(False, None)),
        patch("web.api.health._pearl_probe", return_value=(False, None)),
        patch("web.api.health._network_quality", return_value=None),
    ):
        resp = client.get("/api/health/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "obs_ok" in data
    assert "pearl_ok" in data
    assert "network_quality" in data
    assert data["obs_ok"] is False
    assert data["pearl_ok"] is False


# ---------------------------------------------------------------------------
# /api/audio
# ---------------------------------------------------------------------------


def test_audio_inputs_unavailable():
    """OBS offline → 503."""
    with patch("web.api.audio_control._obs_client", side_effect=OSError("refused")):
        resp = client.get("/api/audio/inputs")
    assert resp.status_code == 503
    assert "error" in resp.json()


def test_audio_inputs_ok():
    """OBS reachable → 200 with inputs list."""
    mock_cl = MagicMock()
    mock_cl.get_input_list.return_value = MagicMock(
        inputs=[{"inputName": "Mic", "inputKind": "wasapi_input_capture"}]
    )
    mock_cl.get_input_mute.return_value = MagicMock(input_muted=False)
    mock_cl.get_input_volume.return_value = MagicMock(input_volume_db=-6.0)
    with patch("web.api.audio_control._obs_client", return_value=mock_cl):
        resp = client.get("/api/audio/inputs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["inputs"]) == 1
    assert data["inputs"][0]["name"] == "Mic"
    assert data["inputs"][0]["muted"] is False


def test_audio_mute_ok():
    """POST /mute → 200 success, set_input_mute called."""
    mock_cl = MagicMock()
    with patch("web.api.audio_control._obs_client", return_value=mock_cl):
        resp = client.post(
            "/api/audio/mute",
            json={"input_name": "Mic", "muted": True},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["muted"] is True
    mock_cl.set_input_mute.assert_called_once_with("Mic", True)


def test_audio_volume_ok():
    """POST /volume → 200 success, set_input_volume called."""
    mock_cl = MagicMock()
    with patch("web.api.audio_control._obs_client", return_value=mock_cl):
        resp = client.post(
            "/api/audio/volume",
            json={"input_name": "Mic", "volume_db": -12.5},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["volume_db"] == pytest.approx(-12.5)
    mock_cl.set_input_volume.assert_called_once_with("Mic", vol_db=-12.5)


# ---------------------------------------------------------------------------
# /api/captions
# ---------------------------------------------------------------------------


def test_captions_stream_accessible():
    """GET /api/captions/stream → 200 text/event-stream."""

    async def _finite_gen(*_args, **_kwargs):
        """Yields one caption then stops — avoids infinite blocking in tests."""
        yield {"ts": "2026-05-02T00:00:00Z", "channel": "en", "text": "hi"}

    with patch("web.api.captions.tail_captions", _finite_gen):
        resp = client.get("/api/captions/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


def test_captions_append_ok(tmp_path, monkeypatch):
    """POST /api/captions/append → writes entry and returns success."""
    import web.api.captions as cap_mod
    import domains.captioning.caption_worker as cw_mod

    tmp_file = tmp_path / "captions.jsonl"
    monkeypatch.setattr(cap_mod, "CAPTIONS_FILE", tmp_file)
    monkeypatch.setattr(cw_mod, "CAPTIONS_FILE", tmp_file)

    resp = client.post(
        "/api/captions/append",
        json={"channel": "fr", "text": "Bonjour le monde"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["entry"]["channel"] == "fr"
    assert data["entry"]["text"] == "Bonjour le monde"

    import json
    lines = [json.loads(l) for l in tmp_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    assert lines[0]["text"] == "Bonjour le monde"
