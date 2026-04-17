"""
Phase 8b tests — Live layout control (pearl_control.py).

Four CI-friendly tests (no live Pearl device required).

Tests:
  1. test_layout_list_parsed       — get_layouts mock → layouts command prints list
  2. test_layout_fuzzy_match       — _resolve_layout substring match
  3. test_layout_switch_calls_api  — switch command resolves name and calls switch_layout
  4. test_status_shows_current_layout — status command prints active layout name
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from domains.epiphan.tools.pearl_client import PearlClient
from scripts.pearl_control import (
    _resolve_layout,
    cmd_layouts,
    cmd_switch,
    cmd_status,
)

_LAYOUTS = [
    {"id": "1", "name": "Speaker View"},
    {"id": "2", "name": "Interpreter View"},
    {"id": "3", "name": "Full Screen"},
]

_ACTIVE = {"id": "1", "name": "Speaker View"}


# ---------------------------------------------------------------------------
# 1. layouts command — list printed, active marked
# ---------------------------------------------------------------------------

def test_layout_list_parsed(capsys):
    client = MagicMock(spec=PearlClient)
    client.get_layouts.return_value = _LAYOUTS
    client.get_active_layout.return_value = _ACTIVE

    args = SimpleNamespace(channel="2")
    rc = cmd_layouts(args, client)

    assert rc == 0
    out = capsys.readouterr().out
    assert "Speaker View" in out
    assert "Interpreter View" in out
    assert "← active" in out
    client.get_layouts.assert_called_once_with("2")
    client.get_active_layout.assert_called_once_with("2")


# ---------------------------------------------------------------------------
# 2. _resolve_layout — fuzzy (substring) match
# ---------------------------------------------------------------------------

def test_layout_fuzzy_match():
    # Substring match — "speaker" matches "Speaker View"
    result = _resolve_layout(_LAYOUTS, "speaker")
    assert result is not None
    assert result["id"] == "1"

    # Exact ID match takes precedence
    result = _resolve_layout(_LAYOUTS, "2")
    assert result is not None
    assert result["name"] == "Interpreter View"

    # No match returns None
    result = _resolve_layout(_LAYOUTS, "nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# 3. switch command — resolves name and calls client.switch_layout
# ---------------------------------------------------------------------------

def test_layout_switch_calls_api(capsys):
    client = MagicMock(spec=PearlClient)
    client.get_layouts.return_value = _LAYOUTS

    args = SimpleNamespace(channel="2", layout="interpreter")
    rc = cmd_switch(args, client)

    assert rc == 0
    client.switch_layout.assert_called_once_with("2", "2")
    out = capsys.readouterr().out
    assert "Interpreter View" in out


def test_layout_switch_unknown_returns_error(capsys):
    client = MagicMock(spec=PearlClient)
    client.get_layouts.return_value = _LAYOUTS

    args = SimpleNamespace(channel="2", layout="bogus_layout_xyz")
    rc = cmd_switch(args, client)

    assert rc == 1
    client.switch_layout.assert_not_called()


# ---------------------------------------------------------------------------
# 4. status command — shows active layout name
# ---------------------------------------------------------------------------

def test_status_shows_current_layout(capsys):
    client = MagicMock(spec=PearlClient)
    client.get_channels.return_value = [
        {"id": "2", "name": "EN"},
        {"id": "3", "name": "FR"},
    ]
    client.get_active_layout.side_effect = [
        {"id": "1", "name": "Speaker View"},
        {"id": "2", "name": "Interpreter View"},
    ]

    args = SimpleNamespace(channel=None)
    rc = cmd_status(args, client)

    assert rc == 0
    out = capsys.readouterr().out
    assert "Speaker View" in out
    assert "Interpreter View" in out
