"""
tests/test_phase_7b_status.py — Tests for Phase 7b StatusDisplay.

All tests run without a real terminal (rich.live.Live is mocked).
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_display():
    """Import and instantiate StatusDisplay with Live mocked out."""
    from scripts.session_status import StatusDisplay

    display = StatusDisplay()
    # Patch the Live object so no real terminal is touched
    if display._live is not None:
        display._live = MagicMock()
        display._live.is_started = True
    return display


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStatusDisplayInstantiation:
    def test_instantiates_without_crash(self):
        """StatusDisplay() succeeds (rich may or may not be installed)."""
        # Patch Live to avoid a real terminal
        with patch("scripts.session_status.Live"):
            from scripts.session_status import StatusDisplay
            sd = StatusDisplay()
            assert sd is not None


class TestPreflightUpdates:
    def test_set_preflight_passed(self):
        """set_preflight(True) updates internal state without raising."""
        with patch("scripts.session_status.Live"):
            d = _make_display()
            d.set_preflight(True)
            assert d._preflight is True

    def test_set_preflight_failed(self):
        """set_preflight(False) updates internal state without raising."""
        with patch("scripts.session_status.Live"):
            d = _make_display()
            d.set_preflight(False)
            assert d._preflight is False


class TestStageTransitions:
    def test_set_stage_transitions(self):
        """set_stage running → ok produces correct internal state."""
        with patch("scripts.session_status.Live"):
            d = _make_display()
            d.set_stage(1, "backup_verify", "running")
            assert d._slots["backup_verify"] == "running"
            d.set_stage(1, "backup_verify", "ok")
            assert d._slots["backup_verify"] == "ok"

    def test_set_stage_all_statuses(self):
        """All valid status strings are accepted without raising."""
        with patch("scripts.session_status.Live"):
            d = _make_display()
            for status in ("pending", "running", "ok", "failed", "skipped"):
                d.set_stage(1, "youtube_en", status)
                assert d._slots["youtube_en"] == status


class TestFallbackWhenRichAbsent:
    def test_fallback_when_rich_not_available(self, monkeypatch):
        """
        When rich is not importable, run_session._RICH_AVAILABLE is False
        and run_session can be imported without crashing.
        """
        # Build a fake 'rich' that raises ImportError on any attribute access
        # by hiding it from sys.modules before re-importing run_session.
        saved_modules = {}
        for key in list(sys.modules):
            if key == "rich" or key.startswith("rich."):
                saved_modules[key] = sys.modules.pop(key)

        # Also hide session_status so it re-imports fresh
        for key in list(sys.modules):
            if "session_status" in key or "run_session" in key:
                saved_modules[key] = sys.modules.pop(key)

        # Inject a broken 'rich' module
        broken_rich = types.ModuleType("rich")

        def _raise(*a, **kw):
            raise ImportError("rich not available")

        broken_rich.__getattr__ = _raise  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "rich", broken_rich)
        for submod in ("rich.live", "rich.table", "rich.text", "rich.console"):
            monkeypatch.setitem(sys.modules, submod, None)  # type: ignore[call-overload]

        try:
            import importlib
            import scripts.session_status as ss_mod
            importlib.reload(ss_mod)
            # _RICH_AVAILABLE should now be False
            assert ss_mod._RICH_AVAILABLE is False

            # StatusDisplay must still instantiate (no Rich)
            sd = ss_mod.StatusDisplay()
            assert sd._live is None
            sd.set_preflight(True)
            sd.set_stream_state("live")
            sd.set_stage(1, "backup_verify", "ok")
            sd.set_session_done("report.html")
            sd.start()   # no-op
            sd.stop()    # no-op
        finally:
            # Restore original modules
            for key, mod in saved_modules.items():
                sys.modules[key] = mod
