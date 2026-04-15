"""Tests for scripts/run_session.py"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.run_session import run


def _make_pre_flight(fail: bool):
    results = [{"name": "obs_connection", "status": "fail" if fail else "ok",
                "message": "OBS WebSocket — connection failed"}]
    checker = MagicMock()
    checker.return_value.run.return_value = results
    return checker


def test_preflight_failure_exits_before_subprocesses():
    checker = _make_pre_flight(fail=True)
    with patch("scripts.run_session.PreFlightChecker", checker):
        rc = run(config_path=None, poll_interval=5)
    assert rc == 1
    checker.return_value.run.assert_called_once()


def test_both_processes_start_when_preflight_passes():
    checker = _make_pre_flight(fail=False)
    mock_post = MagicMock()
    mock_post.poll.return_value = None   # process alive
    mock_post.pid = 12345
    mock_post.stdout = iter([])          # no output lines

    mock_monitor_result = MagicMock()
    mock_monitor_result.returncode = 0

    with patch("scripts.run_session.PreFlightChecker", checker), \
         patch("scripts.run_session.subprocess.Popen", return_value=mock_post), \
         patch("scripts.run_session.subprocess.run",
               return_value=mock_monitor_result), \
         patch("scripts.run_session.threading.Thread"):
        rc = run(config_path=None, poll_interval=5)
    assert rc == 0


def test_post_process_immediate_exit_triggers_failure():
    checker = _make_pre_flight(fail=False)
    mock_post = MagicMock()
    mock_post.poll.return_value = 1   # process already died
    mock_post.stdout = iter([])

    with patch("scripts.run_session.PreFlightChecker", checker), \
         patch("scripts.run_session.subprocess.Popen", return_value=mock_post):
        rc = run(config_path=None, poll_interval=5)
    assert rc == 1
