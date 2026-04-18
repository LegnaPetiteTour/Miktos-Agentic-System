"""
tests/test_phase_10b_runner.py — Phase 10b session-launch tests.

6 tests, FastAPI TestClient, subprocess mocked throughout.
No live run_session.py required.
"""

import signal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from web.server import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(pid: int = 12345, returncode: int | None = None) -> MagicMock:
    """Return a mock Popen object."""
    proc = MagicMock()
    proc.pid = pid
    proc.poll.return_value = returncode  # None = still alive
    proc.send_signal = MagicMock()
    return proc


@pytest.fixture(autouse=True)
def reset_runner():
    """Reset the module-level _proc singleton before each test."""
    import web.api.runner as runner_mod
    runner_mod._proc = None
    yield
    runner_mod._proc = None


# ---------------------------------------------------------------------------
# 1. test_start_launches_process
# ---------------------------------------------------------------------------


def test_start_launches_process():
    with patch("web.api.runner.subprocess.Popen") as MockPopen:
        fake_proc = _make_proc(pid=99001)
        MockPopen.return_value = fake_proc

        resp = client.post("/api/session/start")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["pid"] == 99001
    MockPopen.assert_called_once()


# ---------------------------------------------------------------------------
# 2. test_start_conflict — 409 when already running
# ---------------------------------------------------------------------------


def test_start_conflict():
    import web.api.runner as runner_mod

    runner_mod._proc = _make_proc(pid=55555, returncode=None)

    resp = client.post("/api/session/start")

    assert resp.status_code == 409
    body = resp.json()
    assert body["success"] is False
    assert "already running" in body["error"].lower()


# ---------------------------------------------------------------------------
# 3. test_stop_sends_sigint
# ---------------------------------------------------------------------------


def test_stop_sends_sigint():
    import web.api.runner as runner_mod

    fake_proc = _make_proc(pid=77777, returncode=None)
    runner_mod._proc = fake_proc

    resp = client.post("/api/session/stop")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    fake_proc.send_signal.assert_called_once_with(signal.SIGINT)


# ---------------------------------------------------------------------------
# 4. test_stop_not_running
# ---------------------------------------------------------------------------


def test_stop_not_running():
    # _proc is None (reset by fixture)
    resp = client.post("/api/session/stop")

    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert "not running" in body["error"].lower() or "no session" in body["error"].lower()


# ---------------------------------------------------------------------------
# 5. test_runner_state_idle
# ---------------------------------------------------------------------------


def test_runner_state_idle():
    # No process — _proc is None
    resp = client.get("/api/session/runner")

    assert resp.status_code == 200
    body = resp.json()
    assert body["running"] is False
    assert body["pid"] is None
    assert body["state"] == "idle"


# ---------------------------------------------------------------------------
# 6. test_runner_state_running
# ---------------------------------------------------------------------------


def test_runner_state_running():
    import web.api.runner as runner_mod

    fake_proc = _make_proc(pid=42000, returncode=None)
    runner_mod._proc = fake_proc

    resp = client.get("/api/session/runner")

    assert resp.status_code == 200
    body = resp.json()
    assert body["running"] is True
    assert body["pid"] == 42000
    assert body["state"] == "running"
