"""
tests/test_phase_12_onboarding.py — Phase 12 onboarding wizard tests.

10 tests, FastAPI TestClient, mocked external calls.
Target: 130 prior + 10 = 140 passed, 1 skip.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from web.server import app

client = TestClient(app, follow_redirects=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    """Point write_env_key / read_env_keys at a temp .env file."""
    import web.api.onboarding as ob

    env_file = tmp_path / ".env"
    monkeypatch.setattr(ob, "_ENV_PATH", env_file)
    return env_file


@pytest.fixture()
def tmp_cfg(tmp_path, monkeypatch):
    """Point _CONFIG_PATH at a temp session_config.yaml."""
    import web.api.onboarding as ob

    cfg_file = tmp_path / "session_config.yaml"
    monkeypatch.setattr(ob, "_CONFIG_PATH", cfg_file)
    return cfg_file


# ---------------------------------------------------------------------------
# 1. test_status_all_missing
# ---------------------------------------------------------------------------


def test_status_all_missing(tmp_env, tmp_cfg):
    """Fresh .env and no config → all credential flags false, hardware None."""
    resp = client.get("/api/onboarding/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["youtube_client"] is False
    assert data["youtube_en"] is False
    assert data["youtube_fr"] is False
    assert data["translate"] is False
    assert data["elevenlabs"] is False
    assert data["hardware"] is None


# ---------------------------------------------------------------------------
# 2. test_status_partial
# ---------------------------------------------------------------------------


def test_status_partial(tmp_env, tmp_cfg):
    """Some keys set → partial status returned correctly."""
    import web.api.onboarding as ob

    ob.write_env_key("YOUTUBE_CLIENT_ID", "client-id-value")
    ob.write_env_key("YOUTUBE_CLIENT_SECRET", "client-secret-value")
    ob.write_env_key("YOUTUBE_REFRESH_TOKEN_EN", "en-token")

    resp = client.get("/api/onboarding/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["youtube_client"] is True
    assert data["youtube_en"] is True
    assert data["youtube_fr"] is False
    assert data["translate"] is False
    assert data["elevenlabs"] is False


# ---------------------------------------------------------------------------
# 3. test_write_env_key_new
# ---------------------------------------------------------------------------


def test_write_env_key_new(tmp_env):
    """write_env_key appends a new key to an empty .env."""
    import web.api.onboarding as ob

    ob.write_env_key("MY_NEW_KEY", "my-value")

    content = tmp_env.read_text(encoding="utf-8")
    assert "MY_NEW_KEY=my-value" in content


# ---------------------------------------------------------------------------
# 4. test_write_env_key_update
# ---------------------------------------------------------------------------


def test_write_env_key_update(tmp_env):
    """write_env_key updates an existing key and preserves all other keys."""
    import web.api.onboarding as ob

    tmp_env.write_text(
        "KEEP_ME=keep-value\nTARGET_KEY=old-value\nANOTHER=another-value\n",
        encoding="utf-8",
    )

    ob.write_env_key("TARGET_KEY", "new-value")

    content = tmp_env.read_text(encoding="utf-8")
    assert "TARGET_KEY=new-value" in content
    assert "old-value" not in content
    assert "KEEP_ME=keep-value" in content
    assert "ANOTHER=another-value" in content


# ---------------------------------------------------------------------------
# 5. test_write_env_key_atomic
# ---------------------------------------------------------------------------


def test_write_env_key_atomic(tmp_env):
    """write_env_key uses a temp file + rename — no .env.tmp. file left behind."""
    import web.api.onboarding as ob

    ob.write_env_key("ATOMIC_KEY", "atomic-value")

    # Final file must exist
    assert tmp_env.exists()
    assert "ATOMIC_KEY=atomic-value" in tmp_env.read_text(encoding="utf-8")

    # No leftover temp files
    leftover = list(tmp_env.parent.glob(".env.tmp.*"))
    assert leftover == [], f"Temp files left behind: {leftover}"


# ---------------------------------------------------------------------------
# 6. test_validate_elevenlabs_success
# ---------------------------------------------------------------------------


def test_validate_elevenlabs_success(tmp_env):
    """Mock 200 response from ElevenLabs → key written to .env."""
    import web.api.onboarding as ob

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    with patch.object(ob._requests, "get", return_value=mock_resp):
        resp = client.post(
            "/api/onboarding/validate/elevenlabs",
            json={"api_key": "sk_test_valid_key"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["error"] is None
    assert "ELEVENLABS_API_KEY=sk_test_valid_key" in tmp_env.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 7. test_validate_elevenlabs_failure
# ---------------------------------------------------------------------------


def test_validate_elevenlabs_failure(tmp_env):
    """Mock 401 response from ElevenLabs → error returned, nothing written."""
    import web.api.onboarding as ob
    import requests as real_requests

    def _raise_401(*args, **kwargs):
        raise real_requests.HTTPError("401 Unauthorized")

    with patch.object(ob._requests, "get", side_effect=_raise_401):
        resp = client.post(
            "/api/onboarding/validate/elevenlabs",
            json={"api_key": "sk_bad_key"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["error"] is not None
    # Key must NOT be written
    assert not tmp_env.exists() or "ELEVENLABS_API_KEY" not in tmp_env.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 8. test_validate_translate_success
# ---------------------------------------------------------------------------


def test_validate_translate_success(tmp_env):
    """Mock successful Translate API response → key written to .env."""
    import web.api.onboarding as ob

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    with patch.object(ob._requests, "get", return_value=mock_resp):
        resp = client.post(
            "/api/onboarding/validate/translate",
            json={"api_key": "AIza_test_translate_key"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "GOOGLE_TRANSLATE_API_KEY=AIza_test_translate_key" in tmp_env.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 9. test_validate_pearl_success
# ---------------------------------------------------------------------------


def test_validate_pearl_success(tmp_env, tmp_cfg):
    """Mock Pearl /api/channels response → connection confirmed, config written."""
    import web.api.onboarding as ob

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = '{"firmware": "3.15.2"}'
    mock_resp.json.return_value = {"firmware": "3.15.2"}

    with patch.object(ob._requests, "get", return_value=mock_resp):
        resp = client.post(
            "/api/onboarding/validate/pearl",
            json={"host": "192.168.2.45", "port": 80},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["firmware"] == "3.15.2"
    assert data["error"] is None

    # Config file should record hardware=epiphan
    import yaml

    cfg = yaml.safe_load(tmp_cfg.read_text(encoding="utf-8"))
    assert cfg["hardware"] == "epiphan"
    assert cfg["pearl"]["host"] == "192.168.2.45"


# ---------------------------------------------------------------------------
# 10. test_onboarding_index_renders
# ---------------------------------------------------------------------------


def test_onboarding_index_renders():
    """GET /onboarding returns 200 with wizard HTML."""
    resp = client.get("/onboarding")
    assert resp.status_code == 200
    assert "Operator Setup Wizard" in resp.text or "onboarding" in resp.text.lower()
