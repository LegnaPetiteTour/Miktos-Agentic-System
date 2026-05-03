"""
tests/test_phase_17.py — Phase 17: run-of-show, rehearsal, templates.

Target: 175 existing + 12 new = 187 passed, 1 skipped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.server import app

client = TestClient(app)


# ===========================================================================
# 1 — RunOfShow dataclass unit tests
# ===========================================================================


def test_runofshow_defaults() -> None:
    """RunOfShow built from cues has index 0 and returns the first cue."""
    from engine.runofshow import Cue, RunOfShow

    cues = [
        Cue(id="intro", label="Intro"),
        Cue(id="qa", label="Q&A"),
        Cue(id="outro", label="Outro"),
    ]
    ros = RunOfShow(show_id="test", show_name="Test Show", cues=cues)
    assert ros.active_cue_index == 0
    active = ros.active_cue()
    assert active is not None
    assert active.id == "intro"


def test_runofshow_advance() -> None:
    """advance() increments the index and returns None at end."""
    from engine.runofshow import Cue, RunOfShow

    cues = [Cue(id="a", label="A"), Cue(id="b", label="B")]
    ros = RunOfShow(show_id="t", show_name="T", cues=cues)

    result = ros.advance()
    assert result is not None
    assert result.id == "b"
    assert ros.active_cue_index == 1

    # Already at last cue → None
    result2 = ros.advance()
    assert result2 is None
    assert ros.active_cue_index == 1  # unchanged


def test_runofshow_jump() -> None:
    """jump() sets the correct index; unknown id returns None without moving."""
    from engine.runofshow import Cue, RunOfShow

    cues = [
        Cue(id="intro", label="Intro"),
        Cue(id="qa", label="Q&A"),
        Cue(id="outro", label="Outro"),
    ]
    ros = RunOfShow(show_id="t", show_name="T", cues=cues)

    result = ros.jump("qa")
    assert result is not None
    assert result.id == "qa"
    assert ros.active_cue_index == 1

    # Unknown id
    result2 = ros.jump("nonexistent")
    assert result2 is None
    assert ros.active_cue_index == 1  # unchanged


# ===========================================================================
# 4 — API: load template
# ===========================================================================


def test_runofshow_api_load_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/runofshow/load returns 200 when the template exists."""
    import engine.runofshow as ros_mod

    # Create a minimal template file
    tdir = tmp_path / "templates"
    tdir.mkdir()
    template = {
        "id": "test_tpl",
        "name": "Test Template",
        "description": "Test",
        "cues": [
            {"id": "a", "label": "Cue A", "notes": "", "scene": "", "lower_third": "", "transition": "fade"},
        ],
    }
    (tdir / "test_tpl.json").write_text(json.dumps(template), encoding="utf-8")

    orig_tdir = ros_mod.TEMPLATES_DIR
    orig_state = ros_mod.RUNOFSHOW_STATE_FILE
    ros_mod.TEMPLATES_DIR = tdir
    ros_mod.RUNOFSHOW_STATE_FILE = tmp_path / "runofshow.json"
    try:
        r = client.post("/api/runofshow/load", json={"template": "test_tpl"})
        assert r.status_code == 200
        data = r.json()
        assert data["show_name"] == "Test Template"
    finally:
        ros_mod.TEMPLATES_DIR = orig_tdir
        ros_mod.RUNOFSHOW_STATE_FILE = orig_state


# ===========================================================================
# 5 — API: get show state
# ===========================================================================


def test_runofshow_api_show(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/runofshow/show always returns 200 with cues key."""
    import engine.runofshow as ros_mod

    orig_state = ros_mod.RUNOFSHOW_STATE_FILE
    ros_mod.RUNOFSHOW_STATE_FILE = tmp_path / "runofshow.json"
    try:
        r = client.get("/api/runofshow/show")
        assert r.status_code == 200
        data = r.json()
        assert "cues" in data
    finally:
        ros_mod.RUNOFSHOW_STATE_FILE = orig_state


# ===========================================================================
# 6 — API: advance cue
# ===========================================================================


def test_runofshow_api_advance(tmp_path: Path) -> None:
    """POST /api/runofshow/advance returns 200 (with or without a loaded show)."""
    import engine.runofshow as ros_mod

    orig_state = ros_mod.RUNOFSHOW_STATE_FILE
    ros_mod.RUNOFSHOW_STATE_FILE = tmp_path / "runofshow.json"
    try:
        r = client.post("/api/runofshow/advance")
        assert r.status_code == 200
        data = r.json()
        assert "ok" in data
    finally:
        ros_mod.RUNOFSHOW_STATE_FILE = orig_state


# ===========================================================================
# 7 — Rehearsal API: state
# ===========================================================================


def test_rehearsal_api_state(tmp_path: Path) -> None:
    """GET /api/rehearsal/state returns 200 with 'active' key."""
    import engine.rehearsal as reh_mod

    orig = reh_mod.REHEARSAL_STATE_FILE
    reh_mod.REHEARSAL_STATE_FILE = tmp_path / "rehearsal.json"
    try:
        r = client.get("/api/rehearsal/state")
        assert r.status_code == 200
        data = r.json()
        assert "active" in data
    finally:
        reh_mod.REHEARSAL_STATE_FILE = orig


# ===========================================================================
# 8 — Rehearsal API: activate / deactivate
# ===========================================================================


def test_rehearsal_api_start_stop(tmp_path: Path) -> None:
    """POST /api/rehearsal/start → active=True; POST /api/rehearsal/stop → active=False."""
    import engine.rehearsal as reh_mod

    orig = reh_mod.REHEARSAL_STATE_FILE
    reh_mod.REHEARSAL_STATE_FILE = tmp_path / "rehearsal.json"
    try:
        r = client.post("/api/rehearsal/start")
        assert r.status_code == 200
        assert r.json()["active"] is True

        r2 = client.post("/api/rehearsal/stop")
        assert r2.status_code == 200
        assert r2.json()["active"] is False
    finally:
        reh_mod.REHEARSAL_STATE_FILE = orig


# ===========================================================================
# 9 — RehearsalAdapter capabilities
# ===========================================================================


def test_rehearsal_adapter_capabilities() -> None:
    """RehearsalAdapter reports platform_name='rehearsal' and core flags as True."""
    from engine.adapters.rehearsal_adapter import RehearsalAdapter

    adapter = RehearsalAdapter()
    caps = adapter.capabilities()

    assert caps.platform_name == "rehearsal"
    assert caps.supports_stream_start is True
    assert caps.supports_recording_start is True
    assert caps.supports_layout_switch is True
    assert caps.supports_snapshot is True


# ===========================================================================
# 10 — Templates list API
# ===========================================================================


def test_templates_list_api(tmp_path: Path) -> None:
    """GET /api/templates returns 200 with list length matching the dir contents."""
    import engine.runofshow as ros_mod

    tdir = tmp_path / "templates"
    tdir.mkdir()
    tpl = {"id": "t1", "name": "T1", "description": "", "cues": []}
    (tdir / "t1.json").write_text(json.dumps(tpl), encoding="utf-8")

    orig_tdir = ros_mod.TEMPLATES_DIR
    ros_mod.TEMPLATES_DIR = tdir
    try:
        r = client.get("/api/templates")
        assert r.status_code == 200
        data = r.json()
        assert len(data["templates"]) == 1
        assert data["templates"][0]["id"] == "t1"
    finally:
        ros_mod.TEMPLATES_DIR = orig_tdir


# ===========================================================================
# 11 — Templates get API (uses real data/templates/)
# ===========================================================================


def test_templates_get_api() -> None:
    """GET /api/templates/press_conference_enfr returns 200 with 'cues' key."""
    r = client.get("/api/templates/press_conference_enfr")
    assert r.status_code == 200
    data = r.json()
    assert "cues" in data
    assert len(data["cues"]) > 0


# ===========================================================================
# 12 — Run-of-show panel HTML
# ===========================================================================


def test_runofshow_panel_ok() -> None:
    """GET /panels/runofshow returns 200 HTML."""
    r = client.get("/panels/runofshow")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
