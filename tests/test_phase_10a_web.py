"""
tests/test_phase_10a_web.py — Phase 10a web cockpit tests.

All 8 tests use FastAPI TestClient.
No live Pearl device or OBS required — Pearl tests mock PearlClient.
"""

import json
import re
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from web.server import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_config(tmp_path, monkeypatch):
    """Point session config path to a temp file."""
    import web.api.session as sess_mod

    cfg_path = tmp_path / "session_config.yaml"
    cfg_path.write_text(
        yaml.dump({"event_name": "Test-001", "hardware": "obs"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(sess_mod, "_CONFIG_PATH", cfg_path)
    return cfg_path


@pytest.fixture()
def tmp_sessions_dir(tmp_path, monkeypatch):
    """Create a fake sessions directory with named + hex-UUID dirs."""
    import web.api.session as sess_mod

    sessions = tmp_path / "sessions"
    sessions.mkdir()

    # Named sessions
    named = [
        "2026-04-11_Miktos-Demo_001",
        "2026-04-13_Miktos-Demo_002",
        "2026-04-15_Pearl-Test_001",
    ]
    for name in named:
        d = sessions / name
        d.mkdir()
        (d / f"{name}_report.html").write_text("<html><body>Report</body></html>")

    # Hex-UUID dirs — must be excluded
    for hex_name in ["00cd8d72537c", "f8ddc8426a9b", "b1a0bf41f75b"]:
        (sessions / hex_name).mkdir()

    monkeypatch.setattr(sess_mod, "_SESSIONS_DIR", sessions)
    return sessions


# ---------------------------------------------------------------------------
# 1. test_config_read
# ---------------------------------------------------------------------------


def test_config_read(tmp_config):
    resp = client.get("/api/session/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_name"] == "Test-001"
    assert data["hardware"] == "obs"


# ---------------------------------------------------------------------------
# 2. test_config_write_valid
# ---------------------------------------------------------------------------


def test_config_write_valid(tmp_config):
    resp = client.post(
        "/api/session/config",
        json={"event_name": "Updated-Session", "hardware": "epiphan"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["errors"] == []

    # Verify file was written
    with tmp_config.open() as fh:
        saved = yaml.safe_load(fh)
    assert saved["event_name"] == "Updated-Session"
    assert saved["hardware"] == "epiphan"


# ---------------------------------------------------------------------------
# 3. test_config_write_invalid
# ---------------------------------------------------------------------------


def test_config_write_invalid(tmp_config):
    resp = client.post(
        "/api/session/config",
        json={"hardware": "obs"},  # missing event_name
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert any("event_name" in e for e in body["errors"])


# ---------------------------------------------------------------------------
# 4. test_sessions_list
# ---------------------------------------------------------------------------


def test_sessions_list(tmp_sessions_dir):
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    names = [s["name"] for s in sessions]
    assert "2026-04-11_Miktos-Demo_001" in names
    assert "2026-04-13_Miktos-Demo_002" in names
    assert "2026-04-15_Pearl-Test_001" in names


# ---------------------------------------------------------------------------
# 5. test_sessions_named_only — hex-UUID folders excluded
# ---------------------------------------------------------------------------


def test_sessions_named_only(tmp_sessions_dir):
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    names = [s["name"] for s in sessions]

    _UUID_RE = re.compile(r"^[0-9a-f]{12}$")
    for name in names:
        assert not _UUID_RE.match(name), f"UUID dir leaked into results: {name}"


# ---------------------------------------------------------------------------
# 6. test_pearl_layouts_mock
# ---------------------------------------------------------------------------


def test_pearl_layouts_mock():
    mock_layouts = [{"id": "1", "name": "Camera"}, {"id": "2", "name": "Interpreter View"}]
    mock_active = {"id": "2", "name": "Interpreter View"}

    with patch("web.api.pearl.PearlClient") as MockClient:
        instance = MockClient.return_value
        instance.get_layouts.return_value = mock_layouts
        instance.get_active_layout.return_value = mock_active

        resp = client.get("/api/pearl/layouts/2")

    assert resp.status_code == 200
    data = resp.json()
    assert data["layouts"] == mock_layouts
    assert data["active"] == mock_active


# ---------------------------------------------------------------------------
# 7. test_pearl_switch_mock — switches layout + appends layout_log.jsonl
# ---------------------------------------------------------------------------


def test_pearl_switch_mock(tmp_path, monkeypatch):
    import web.api.pearl as pearl_mod

    layout_log = tmp_path / "layout_log.jsonl"
    monkeypatch.setattr(pearl_mod, "_LAYOUT_LOG", layout_log)

    mock_layouts = [{"id": "1", "name": "Camera"}, {"id": "2", "name": "Interpreter View"}]

    with patch("web.api.pearl.PearlClient") as MockClient:
        instance = MockClient.return_value
        instance.switch_layout.return_value = None
        instance.get_layouts.return_value = mock_layouts

        resp = client.post(
            "/api/pearl/switch",
            json={"channel_id": "2", "layout_id": "1"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["layout_name"] == "Camera"

    # Log entry was appended
    assert layout_log.exists()
    entry = json.loads(layout_log.read_text().strip())
    assert entry["channel"] == "2"
    assert entry["layout_id"] == "1"
    assert entry["layout_name"] == "Camera"


# ---------------------------------------------------------------------------
# 8. test_index_renders
# ---------------------------------------------------------------------------


def test_index_renders():
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    # All five cockpit panels should be present
    assert "panel-hardware" in html
    assert "panel-stream" in html
    assert "panel-health" in html
    assert "panel-pearl" in html
    assert "panel-pipeline" in html
