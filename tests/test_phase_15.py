"""
tests/test_phase_15.py — Phase 15 visual production surface tests.

10 tests covering:
  - GET /api/preview/thumbnail?source=obs         (OBS unavailable → 200 data=None)
  - GET /api/preview/thumbnail?source=obs         (OBS available → 200 with base64)
  - GET /api/preview/thumbnail?source=pearl_en    (Pearl OK → 200 with base64)
  - GET /api/preview/thumbnail?source=pearl_en    (Pearl fail → 200 data=None)
  - POST /api/graphics/lower_third                (OBS ok → 200)
  - POST /api/graphics/lower_third                (OBS fail → 503)
  - DELETE /api/graphics/lower_third              (OBS ok → 200)
  - POST /api/graphics/transition                 (OBS ok → 200)
  - POST /api/graphics/intro                      (OBS ok → 200)
  - POST /api/graphics/outro                      (OBS ok → 200)

Target: 152 prior + 10 = 162 passed, 1 permanent skip.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from web.server import app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# /api/preview/thumbnail — OBS
# ---------------------------------------------------------------------------


def test_preview_obs_unavailable():
    """OBS offline → 200 with data=None (best-effort)."""
    with patch(
        "web.api.preview._obs_client",
        side_effect=ConnectionRefusedError("refused"),
    ):
        resp = client.get("/api/preview/thumbnail?source=obs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "obs"
    assert data["data"] is None
    assert "error" in data


def test_preview_obs_ok():
    """OBS available → 200 with base64 image_data."""
    mock_cl = MagicMock()
    mock_cl.get_source_screenshot.return_value = MagicMock(
        image_data="AAAABBBBCCCC"  # fake base64
    )
    with patch("web.api.preview._obs_client", return_value=mock_cl):
        resp = client.get("/api/preview/thumbnail?source=obs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "obs"
    assert data["data"] == "AAAABBBBCCCC"
    assert data["content_type"] == "image/jpeg"


# ---------------------------------------------------------------------------
# /api/preview/thumbnail — Pearl
# ---------------------------------------------------------------------------


def test_preview_pearl_en_ok():
    """Pearl EN available → 200 with base64-encoded JPEG."""
    fake_jpeg = b"\xff\xd8\xff\xe0Hello"
    mock_resp = MagicMock()
    mock_resp.content = fake_jpeg
    mock_resp.raise_for_status = MagicMock()
    with patch("web.api.preview._pearl_thumbnail", return_value=fake_jpeg):
        resp = client.get("/api/preview/thumbnail?source=pearl_en")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "pearl_en"
    assert data["data"] is not None
    assert data["content_type"] == "image/jpeg"
    # Verify it's valid base64
    import base64
    decoded = base64.b64decode(data["data"])
    assert decoded == fake_jpeg


def test_preview_pearl_en_fail():
    """Pearl unreachable → 200 with data=None (best-effort)."""
    with patch(
        "web.api.preview._pearl_thumbnail",
        side_effect=Exception("connection refused"),
    ):
        resp = client.get("/api/preview/thumbnail?source=pearl_en")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "pearl_en"
    assert data["data"] is None
    assert "error" in data


# ---------------------------------------------------------------------------
# /api/graphics/lower_third
# ---------------------------------------------------------------------------


def test_graphics_lower_third_ok():
    """POST lower_third → 200, OBS set_input_settings called."""
    mock_cl = MagicMock()
    with patch("web.api.graphics._obs_client", return_value=mock_cl):
        resp = client.post(
            "/api/graphics/lower_third",
            json={"name": "Alice", "title": "Engineer", "org": "ACME"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "Alice" in data["text"]
    mock_cl.set_input_settings.assert_called_once()


def test_graphics_lower_third_obs_error():
    """OBS unavailable → 503."""
    with patch(
        "web.api.graphics._obs_client",
        side_effect=ConnectionRefusedError("refused"),
    ):
        resp = client.post(
            "/api/graphics/lower_third",
            json={"name": "Bob"},
        )
    assert resp.status_code == 503
    assert resp.json()["ok"] is False


def test_graphics_clear_lower_third_ok():
    """DELETE lower_third → 200, empty text sent."""
    mock_cl = MagicMock()
    with patch("web.api.graphics._obs_client", return_value=mock_cl):
        resp = client.delete("/api/graphics/lower_third")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    mock_cl.set_input_settings.assert_called_once()
    _, kwargs = mock_cl.set_input_settings.call_args
    # Either positional or keyword, text should be empty string
    call_args = mock_cl.set_input_settings.call_args
    settings_arg = call_args[0][1] if call_args[0] else call_args[1].get("settings", {})
    assert settings_arg.get("text", None) == ""


# ---------------------------------------------------------------------------
# /api/graphics/transition
# ---------------------------------------------------------------------------


def test_graphics_transition_ok():
    """POST /transition → 200, trigger_studio_mode_transition called."""
    mock_cl = MagicMock()
    with patch("web.api.graphics._obs_client", return_value=mock_cl):
        resp = client.post(
            "/api/graphics/transition",
            json={"type": "fade"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["type"] == "fade"
    mock_cl.trigger_studio_mode_transition.assert_called_once()


# ---------------------------------------------------------------------------
# /api/graphics/intro  &  /api/graphics/outro
# ---------------------------------------------------------------------------


def test_graphics_intro_ok():
    """POST /intro → 200, set_current_program_scene called."""
    mock_cl = MagicMock()
    with patch("web.api.graphics._obs_client", return_value=mock_cl):
        resp = client.post("/api/graphics/intro")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    mock_cl.set_current_program_scene.assert_called_once()


def test_graphics_outro_ok():
    """POST /outro → 200, set_current_program_scene called."""
    mock_cl = MagicMock()
    with patch("web.api.graphics._obs_client", return_value=mock_cl):
        resp = client.post("/api/graphics/outro")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    mock_cl.set_current_program_scene.assert_called_once()
