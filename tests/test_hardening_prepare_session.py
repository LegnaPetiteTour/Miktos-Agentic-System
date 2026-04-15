"""Tests for scripts/prepare_session.py"""
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.prepare_session import run


def _write_config(tmp_path: Path) -> Path:
    cfg = {
        "event_name": "Old-Event",
        "stream_date": "",
        "stream_type": "obs_simple",
        "recording": {"local_path": "/tmp", "min_size_bytes": 1048576},
        "youtube": {
            "en": {"video_id": "old_en", "channel_id": "UC_en",
                   "title": "", "description": "", "playlist_id": ""},
            "fr": {"video_id": "old_fr", "channel_id": "UC_fr",
                   "title": "", "description": "", "playlist_id": ""},
        },
    }
    p = tmp_path / "session_config.yaml"
    p.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
    return p


def test_valid_input_writes_correct_fields(tmp_path):
    cfg_path = _write_config(tmp_path)
    inputs = iter(["New-Event", "new_en_vid", "new_fr_vid", "y"])
    with patch("builtins.input", side_effect=inputs):
        rc = run(cfg_path, dry_run=False)
    assert rc == 0
    data = yaml.safe_load(cfg_path.read_text())
    assert data["event_name"] == "New-Event"
    assert data["youtube"]["en"]["video_id"] == "new_en_vid"
    assert data["youtube"]["fr"]["video_id"] == "new_fr_vid"
    # Other fields preserved
    assert data["stream_type"] == "obs_simple"
    assert data["recording"]["min_size_bytes"] == 1048576


def test_empty_event_name_rejected_then_accepted(tmp_path):
    cfg_path = _write_config(tmp_path)
    # First event_name empty (rejected), second valid
    inputs = iter(["", "Valid-Event", "", "", "y"])
    with patch("builtins.input", side_effect=inputs):
        rc = run(cfg_path, dry_run=False)
    assert rc == 0
    data = yaml.safe_load(cfg_path.read_text())
    assert data["event_name"] == "Valid-Event"


def test_enter_on_video_id_preserves_existing_value(tmp_path):
    cfg_path = _write_config(tmp_path)
    # Enter empty string for both video_ids → keeps existing
    inputs = iter(["New-Event", "", "", "y"])
    with patch("builtins.input", side_effect=inputs):
        rc = run(cfg_path, dry_run=False)
    assert rc == 0
    data = yaml.safe_load(cfg_path.read_text())
    assert data["youtube"]["en"]["video_id"] == "old_en"
    assert data["youtube"]["fr"]["video_id"] == "old_fr"


def test_dry_run_does_not_write(tmp_path):
    cfg_path = _write_config(tmp_path)
    original = cfg_path.read_text()
    rc = run(cfg_path, dry_run=True)
    assert rc == 0
    assert cfg_path.read_text() == original
