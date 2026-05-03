"""
tests/test_phase_16.py — Phase 16 adapter contract & ops tests.

13 tests covering:
  Adapter contract (4):
    - AdapterCapabilities defaults
    - PearlAdapter capabilities flags
    - OBSAdapter capabilities flags
    - GET /api/adapters/capabilities → 200

  Action log (3):
    - write_action + read_recent round-trip (via monkeypatching)
    - POST /api/action_log/entry → 200
    - GET  /api/action_log/recent → 200 list

  Caption stats (2):
    - GET /api/captions/stats when file does not exist → stale=True
    - GET /api/captions/stats with a recent entry → stale=False

  Safe mode (4):
    - GET /api/safe_mode/state → 200 active=False (initial)
    - POST /api/safe_mode/activate → 200 active=True
    - POST /api/safe_mode/deactivate → 200 active=False
    - GET /panels/safe_mode → 200 HTML

Target: 162 prior + 13 = 175 passed, 1 permanent skip.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from web.server import app

client = TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Adapter contract
# ===========================================================================


def test_adapter_capabilities_defaults():
    """AdapterCapabilities defaults — all flags False, name empty."""
    from engine.adapters.base import AdapterCapabilities

    caps = AdapterCapabilities()
    assert caps.supports_snapshot is False
    assert caps.supports_overlay is False
    assert caps.supports_scene_switch is False
    assert caps.platform_name == ""
    assert caps.supported_channels == []


def test_pearl_adapter_capabilities():
    """PearlAdapter.capabilities() — correct Pearl flags, no connection needed."""
    from engine.adapters.pearl_adapter import PearlAdapter

    adapter = PearlAdapter()
    caps = adapter.capabilities()

    assert caps.platform_name == "epiphan_pearl"
    assert caps.supports_layout_switch is True
    assert caps.supports_scene_switch is False
    assert caps.supports_snapshot is True
    assert caps.supports_overlay is False
    assert caps.supports_stream_start is True
    assert caps.supports_stream_stop is True
    assert caps.supports_recording_download is True
    assert caps.supports_transition_control is False


def test_obs_adapter_capabilities():
    """OBSAdapter.capabilities() — correct OBS flags, no connection needed."""
    from engine.adapters.obs_adapter import OBSAdapter

    adapter = OBSAdapter()
    caps = adapter.capabilities()

    assert caps.platform_name == "obs_studio"
    assert caps.supports_scene_switch is True
    assert caps.supports_layout_switch is False
    assert caps.supports_overlay is True
    assert caps.supports_audio_mute is True
    assert caps.supports_audio_volume is True
    assert caps.supports_transition_control is True
    assert caps.supports_recording_download is False


def test_adapters_api_endpoint():
    """GET /api/adapters/capabilities → 200 with platform_name + flag keys."""
    resp = client.get("/api/adapters/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert "platform_name" in data
    assert "supports_snapshot" in data
    assert "supports_overlay" in data
    assert "supports_scene_switch" in data


# ===========================================================================
# Action log
# ===========================================================================


def test_action_log_write_read(tmp_path):
    """write_action + read_recent round-trip using a temp file."""
    import engine.action_log as al_mod

    orig = al_mod.ACTION_LOG_FILE
    al_mod.ACTION_LOG_FILE = tmp_path / "action_log.jsonl"
    try:
        entry = al_mod.write_action("pytest", "test_action", {"k": "v"}, "ok")
        assert entry["actor"] == "pytest"
        assert entry["action"] == "test_action"
        assert entry["result"] == "ok"

        recent = al_mod.read_recent(10)
        assert len(recent) == 1
        assert recent[0]["action"] == "test_action"
    finally:
        al_mod.ACTION_LOG_FILE = orig


def test_action_log_post_entry():
    """POST /api/action_log/entry → 200 ok=True."""
    resp = client.post(
        "/api/action_log/entry",
        json={"actor": "test_suite", "action": "phase_16_check", "payload": {}, "result": "ok"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["entry"]["action"] == "phase_16_check"


def test_action_log_get_recent():
    """GET /api/action_log/recent → 200 with entries list."""
    resp = client.get("/api/action_log/recent?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert isinstance(data["entries"], list)


# ===========================================================================
# Caption reliability stats
# ===========================================================================


def test_captions_stats_no_file(tmp_path):
    """Stats endpoint with non-existent file → stale=True, count=0."""
    import web.api.captions as cap_mod

    orig = cap_mod.CAPTIONS_FILE
    cap_mod.CAPTIONS_FILE = tmp_path / "nonexistent.jsonl"
    try:
        resp = client.get("/api/captions/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count_last_60s"] == 0
        assert data["stale"] is True
        assert data["last_ts"] is None
    finally:
        cap_mod.CAPTIONS_FILE = orig


def test_captions_stats_recent_entry(tmp_path):
    """Stats endpoint with a fresh entry → stale=False, count=1."""
    import web.api.captions as cap_mod
    from datetime import datetime, timezone

    orig = cap_mod.CAPTIONS_FILE
    cap_file = tmp_path / "captions.jsonl"
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cap_file.write_text(
        json.dumps({"ts": now_ts, "channel": "en", "text": "Hello"}) + "\n",
        encoding="utf-8",
    )
    cap_mod.CAPTIONS_FILE = cap_file
    try:
        resp = client.get("/api/captions/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count_last_60s"] == 1
        assert data["stale"] is False
        assert data["last_ts"] == now_ts
    finally:
        cap_mod.CAPTIONS_FILE = orig


# ===========================================================================
# Safe mode
# ===========================================================================


def test_safe_mode_initial_state(tmp_path):
    """GET /api/safe_mode/state → 200 active=False when no file exists."""
    import web.api.safe_mode as sm_mod

    orig = sm_mod.SAFE_MODE_FILE
    sm_mod.SAFE_MODE_FILE = tmp_path / "safe_mode.json"
    try:
        resp = client.get("/api/safe_mode/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False
    finally:
        sm_mod.SAFE_MODE_FILE = orig


def test_safe_mode_activate(tmp_path):
    """POST /api/safe_mode/activate → 200 active=True, hardware stop attempted."""
    import web.api.safe_mode as sm_mod

    orig = sm_mod.SAFE_MODE_FILE
    sm_mod.SAFE_MODE_FILE = tmp_path / "safe_mode.json"
    try:
        # Hardware is offline in CI — _stop_all_hardware must not raise
        resp = client.post("/api/safe_mode/activate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["active"] is True
        # State file must exist
        assert sm_mod.SAFE_MODE_FILE.exists()
        state = json.loads(sm_mod.SAFE_MODE_FILE.read_text())
        assert state["active"] is True
    finally:
        sm_mod.SAFE_MODE_FILE = orig


def test_safe_mode_deactivate(tmp_path):
    """POST /api/safe_mode/deactivate → 200 active=False."""
    import web.api.safe_mode as sm_mod

    orig = sm_mod.SAFE_MODE_FILE
    sm_mod.SAFE_MODE_FILE = tmp_path / "safe_mode.json"
    try:
        # First activate, then deactivate
        client.post("/api/safe_mode/activate")
        resp = client.post("/api/safe_mode/deactivate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["active"] is False
    finally:
        sm_mod.SAFE_MODE_FILE = orig


def test_safe_mode_panel_ok():
    """GET /panels/safe_mode → 200 HTML containing the emergency button."""
    resp = client.get("/panels/safe_mode")
    assert resp.status_code == 200
    assert "Emergency" in resp.text
