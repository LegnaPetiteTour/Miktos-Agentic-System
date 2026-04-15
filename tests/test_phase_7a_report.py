"""
test_phase_7a_report.py — Tests for ReportWorker (Phase 7a).

6 required tests per PHASE7A.md spec.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domains.streamlab_post.workers.report_worker import ReportWorker  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_ALL_SLOT_NAMES = [
    "backup_verify",
    "youtube_en",
    "audio_extract",
    "translate",
    "transcript",
    "youtube_fr",
    "file_rename",
    "notify",
]


def _make_payload(tmp_path: Path, **overrides) -> dict:
    """Return a valid minimal payload writing into tmp_path."""
    base = {
        "event_name": "Council-Meeting",
        "session_date": "2026-04-15",
        "session_id": "abc123def456",
        "duration_seconds": 392.0,
        "file_size_bytes": 173_000_000,
        "mp3_path": "",
        "video_id_en": "vz9ecJuLhLs",
        "title_en": "Council Meeting (EN)",
        "video_id_fr": "w5wdP8c0eU0",
        "title_fr": "Réunion du Conseil (FR)",
        "transcript_path": "",
        "word_count": 42,
        "detected_languages": ["fr", "en"],
        "final_folder": str(tmp_path),
        "slots": {
            name: {"success": True}
            for name in _ALL_SLOT_NAMES
        },
        "dry_run": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_report_written_to_final_folder(tmp_path: Path) -> None:
    """Valid payload → HTML file written at correct path."""
    payload = _make_payload(tmp_path)
    result = ReportWorker().run(payload)

    assert result["success"] is True
    report_path = Path(result["report_path"])
    assert report_path.exists()
    # Named session folder → uses session name prefix
    assert report_path.parent == tmp_path


def test_report_contains_all_slots(tmp_path: Path) -> None:
    """All 8 slot names appear in the generated HTML."""
    payload = _make_payload(tmp_path)
    result = ReportWorker().run(payload)

    assert result["success"] is True
    html = Path(result["report_path"]).read_text(encoding="utf-8")
    for slot in _ALL_SLOT_NAMES:
        assert slot in html, f"Slot '{slot}' not found in HTML"


def test_report_shows_youtube_links_when_video_ids_present(tmp_path: Path) -> None:
    """https://youtu.be/ appears for EN and FR when video_ids are non-empty."""
    payload = _make_payload(
        tmp_path,
        video_id_en="vz9ecJuLhLs",
        video_id_fr="w5wdP8c0eU0",
    )
    result = ReportWorker().run(payload)

    assert result["success"] is True
    html = Path(result["report_path"]).read_text(encoding="utf-8")
    assert "https://youtu.be/vz9ecJuLhLs" in html
    assert "https://youtu.be/w5wdP8c0eU0" in html


def test_report_handles_failed_slot(tmp_path: Path) -> None:
    """Failed slot with error message → error text appears in HTML."""
    payload = _make_payload(
        tmp_path,
        slots={
            **{name: {"success": True} for name in _ALL_SLOT_NAMES},
            "youtube_en": {
                "success": False,
                "error": "OAuth token expired",
            },
        },
    )
    result = ReportWorker().run(payload)

    assert result["success"] is True
    html = Path(result["report_path"]).read_text(encoding="utf-8")
    assert "OAuth token expired" in html
    assert "❌" in html


def test_report_dry_run_does_not_write(tmp_path: Path) -> None:
    """dry_run=True → returns success with report_path, no file written."""
    payload = _make_payload(tmp_path, dry_run=True)
    result = ReportWorker().run(payload)

    assert result["success"] is True
    assert "report_path" in result
    # File must NOT exist — dry run never writes
    assert not Path(result["report_path"]).exists()


def test_report_worker_never_raises(tmp_path: Path) -> None:
    """Invalid/missing final_folder → returns failure dict, never raises."""
    payload = _make_payload(tmp_path, final_folder="/nonexistent/path/xyz")
    result = ReportWorker().run(payload)

    assert isinstance(result, dict)
    assert result["success"] is False
    assert "error" in result
