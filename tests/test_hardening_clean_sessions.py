"""Tests for scripts/clean_sessions.py"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_session(sessions_dir: Path, name: str, age_days: int = 10) -> Path:
    p = sessions_dir / name
    p.mkdir(parents=True, exist_ok=True)
    # Set mtime to simulate age
    mtime = (datetime.now() - timedelta(days=age_days)).timestamp()
    import os
    os.utime(str(p), (mtime, mtime))
    return p


def _run(sessions_dir: Path, dry_run: bool, archive_all: bool = True,
         days: int = 0, confirm: str = "y") -> int:
    with patch("scripts.clean_sessions.SESSIONS_DIR", sessions_dir), \
         patch("scripts.clean_sessions.ARCHIVE_DIR",
               sessions_dir / "archive"), \
         patch("builtins.input", return_value=confirm):
        from scripts.clean_sessions import run as clean_run
        return clean_run(dry_run=dry_run, archive_all=archive_all, days=days)


def test_production_sessions_excluded_from_archive(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _make_session(sessions, "2026-04-13_Miktos-Demo_005", age_days=5)
    _make_session(sessions, "abc123hex", age_days=10)

    rc = _run(sessions, dry_run=True, archive_all=True)
    assert rc == 0
    # Production session still present
    assert (sessions / "2026-04-13_Miktos-Demo_005").exists()


def test_dry_run_lists_without_moving(tmp_path, capsys):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _make_session(sessions, "abc123hex", age_days=10)

    rc = _run(sessions, dry_run=True, archive_all=True)
    assert rc == 0
    assert "Dry run" in capsys.readouterr().out
    assert (sessions / "abc123hex").exists()


def test_age_filter_excludes_recent_sessions(tmp_path, capsys):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _make_session(sessions, "old_session", age_days=10)
    _make_session(sessions, "new_session", age_days=2)

    rc = _run(sessions, dry_run=True, archive_all=False, days=7)
    assert rc == 0
    out = capsys.readouterr().out
    assert "old_session" in out
    assert "new_session" not in out


def test_confirming_moves_to_archive(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _make_session(sessions, "abc123hex", age_days=10)

    rc = _run(sessions, dry_run=False, archive_all=True, confirm="y")
    assert rc == 0
    assert (sessions / "archive" / "abc123hex").exists()
    assert not (sessions / "abc123hex").exists()


def test_idempotent_already_archived_not_relisted(tmp_path, capsys):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    archive = sessions / "archive"
    archive.mkdir()
    _make_session(archive, "abc123hex", age_days=10)
    # Only archive/ dir in sessions — nothing to archive
    rc = _run(sessions, dry_run=True, archive_all=True)
    assert rc == 0
    assert "Nothing to archive" in capsys.readouterr().out
