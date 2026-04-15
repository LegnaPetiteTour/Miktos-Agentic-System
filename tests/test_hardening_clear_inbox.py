"""Tests for scripts/clear_inbox.py"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _setup(tmp_path: Path, agent: str, n_messages: int = 0) -> Path:
    pending = tmp_path / "data/messages" / agent / "pending"
    pending.mkdir(parents=True)
    log_path = tmp_path / "data/messages/message.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    for i in range(n_messages):
        msg = {
            "timestamp": "2026-04-13T22:53:14Z",
            "message_type": "recording_stopped",
            "from_agent": "streamlab_monitor",
        }
        (pending / f"msg{i}.json").write_text(json.dumps(msg))
    return pending


def _run(tmp_path: Path, agent: str, dry_run: bool,
         confirm: str = "y") -> int:
    log_path = tmp_path / "data/messages/message.log"
    with patch("scripts.clear_inbox.REPO_ROOT", tmp_path), \
         patch("scripts.clear_inbox.MESSAGE_LOG", log_path), \
         patch("builtins.input", return_value=confirm):
        from scripts.clear_inbox import run as clear_run
        return clear_run(agent=agent, dry_run=dry_run)


def test_empty_inbox_exits_cleanly(tmp_path, capsys):
    _setup(tmp_path, "test_agent", n_messages=0)
    rc = _run(tmp_path, "test_agent", dry_run=False)
    assert rc == 0
    assert "empty" in capsys.readouterr().out.lower()


def test_dry_run_lists_without_moving(tmp_path, capsys):
    pending = _setup(tmp_path, "test_agent", n_messages=1)
    rc = _run(tmp_path, "test_agent", dry_run=True)
    assert rc == 0
    assert "Dry run" in capsys.readouterr().out
    assert len(list(pending.glob("*.json"))) == 1


def test_confirming_moves_files_and_appends_log(tmp_path):
    agent = "test_agent"
    pending = _setup(tmp_path, agent, n_messages=1)
    log_path = tmp_path / "data/messages/message.log"
    rc = _run(tmp_path, agent, dry_run=False, confirm="y")
    assert rc == 0
    delivered = tmp_path / "data/messages" / agent / "delivered"
    assert len(list(delivered.glob("*.json"))) == 1
    assert len(list(pending.glob("*.json"))) == 0
    log_text = log_path.read_text()
    assert "CLEARED" in log_text
    assert agent in log_text


def test_aborting_leaves_inbox_unchanged(tmp_path):
    agent = "test_agent"
    pending = _setup(tmp_path, agent, n_messages=1)
    rc = _run(tmp_path, agent, dry_run=False, confirm="n")
    assert rc == 0
    assert len(list(pending.glob("*.json"))) == 1
