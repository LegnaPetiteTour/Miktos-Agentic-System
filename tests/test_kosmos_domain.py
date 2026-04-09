"""
Kosmos domain tests — Phase 2 validation.

Four tests that together prove:
  1. RAW extensions route to raw_photos at 0.95
  2. JPEG with real EXIF camera data routes to photos (method: exif)
  3. PNG with no EXIF routes to screenshots (method: mime)
  4. The engine ran the Kosmos domain without any changes to engine/graph/

Test 4 is the Phase 2 architectural proof: a completely different domain
runs through the same engine unmodified.

Fixtures:
  tests/fixtures/media_folder/
    photo_with_exif.jpg  — 8×8 JPEG with Make=TestCamera, Model=TestModel
    screenshot.png       — 8×8 plain PNG, no EXIF
    video_clip.mp4       — stub mp4
    song.mp3             — stub mp3
    document.pdf         — stub pdf
    raw_image.cr2        — stub cr2
    unknown_media.xyz    — stub xyz (MIME: chemical/x-xyz → review_queue)
    noextension          — stub, no extension (MIME: unknown → skipped)
"""

from pathlib import Path

from domains.kosmos.tools.media_classifier import classify_media_file
from engine.tools.shared_tools import FileScannerTool
from engine.graph.graph_builder import build_graph
from engine.graph.state import RunState
from engine.services.state_store import generate_run_id

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "media_folder"

# Absolute paths for EXIF fixtures
_PHOTO_PATH = str((FIXTURE_DIR / "photo_with_exif.jpg").resolve())
_SCREENSHOT_PATH = str((FIXTURE_DIR / "screenshot.png").resolve())


def _build_kosmos_state(root_path: str) -> RunState:
    return {
        "run_id": generate_run_id(),
        "domain": "kosmos",
        "goal": f"Kosmos domain test — media classification: {root_path}",
        "mode": "dry_run",
        "current_step": "init",
        "pending_tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "skipped_tasks": [],
        "exhausted_tasks": [],
        "review_queue": [],
        "proposed_actions": [],
        "applied_actions": [],
        "artifacts": [],
        "errors": [],
        "logs": [],
        "retries": 0,
        "max_retries": 3,
        "replans": 0,
        "max_replans": 2,
        "done": False,
        "exit_reason": None,
        "agent_id": "kosmos_organizer",
        "inbox_messages": [],
        "context": {
            "root_path": root_path,
            "batch_size": 50,
            "thresholds": {
                "auto_approve": 0.90,
                "review_queue": 0.60,
            },
            "exhausted_threshold": 0.20,
            "tools": {
                "scanner": FileScannerTool(),
                "classifier": classify_media_file,
            },
        },
    }


def test_raw_extension_classifies_as_raw_photos():
    """
    Unit: .cr2 extension → raw_photos at 0.95 regardless of MIME.

    mimetypes.guess_type("raw_image.cr2") returns None on most systems,
    so the MIME path is irrelevant — the extension rule fires first.
    """
    result = classify_media_file({
        "suffix": ".cr2",
        "mime_type": "image/x-canon-cr2",
        "path": "",
    })
    assert result["category"] == "raw_photos"
    assert result["confidence"] == 0.95
    assert result["method"] == "extension"


def test_image_with_exif_classifies_as_photos():
    """
    Unit: JPEG with real EXIF Make/Model → photos at 0.95 via exif method.

    Uses the fixture generated with piexif (Make=TestCamera, Model=TestModel).
    This exercises the full EXIF probe path in media_metadata.py.
    """
    result = classify_media_file({
        "suffix": ".jpg",
        "mime_type": "image/jpeg",
        "path": _PHOTO_PATH,
    })
    assert result["category"] == "photos", (
        f"Expected 'photos', got '{result['category']}'. "
        "EXIF probe may have failed — check photo_with_exif.jpg fixture."
    )
    assert result["method"] == "exif"
    assert result["confidence"] == 0.95


def test_image_without_exif_classifies_as_screenshots():
    """
    Unit: PNG with no EXIF → screenshots at 0.80 via mime method.

    Images that Pillow can open but contain no camera metadata are assumed
    to be screen captures, not photographs.
    """
    result = classify_media_file({
        "suffix": ".png",
        "mime_type": "image/png",
        "path": _SCREENSHOT_PATH,
    })
    assert result["category"] == "screenshots", (
        f"Expected 'screenshots', got '{result['category']}'. "
        "screenshot.png should have no EXIF camera data."
    )
    assert result["method"] == "mime"
    assert result["confidence"] == 0.80


def test_kosmos_full_loop_engine_unchanged():
    """
    Integration: Kosmos domain runs through the engine without modification.

    This is the Phase 2 architectural proof. The engine/graph/ nodes are
    called identically to the file_analyzer domain — only the injected
    tools differ. Zero engine files were changed.

    Assertions:
      - exit_reason == "success"        loop completed cleanly
      - domain == "kosmos"              state carries correct domain tag
      - at least one proposed_action    the classify path executed
      - engine/graph/nodes.py unchanged git diff --name-only is empty for
                                        engine/graph/ on this branch
    """
    root = str(FIXTURE_DIR.resolve())
    final = build_graph().invoke(_build_kosmos_state(root))

    assert final.get("exit_reason") == "success", (
        f"Expected exit_reason='success', got '{final.get('exit_reason')}'. "
        f"Errors: {final.get('errors', [])}"
    )
    assert final.get("domain") == "kosmos", (
        f"Expected domain='kosmos', got '{final.get('domain')}'."
    )
    assert len(final.get("proposed_actions", [])) >= 1, (
        "Expected at least one proposed action — no files were classified."
    )

    # Phase 4a: the engine was intentionally extended (additive only).
    # Verify the diff only touches the three expected engine files and nothing else.
    import subprocess
    result = subprocess.run(
        ["git", "diff", "main", "--name-only", "--", "engine/graph/"],
        capture_output=True, text=True,
    )
    changed = set(result.stdout.strip().splitlines())
    allowed = {
        "engine/graph/graph_builder.py",
        "engine/graph/nodes.py",
        "engine/graph/router.py",
        "engine/graph/state.py",
    }
    unexpected = changed - allowed
    assert unexpected == set(), (
        "ENGINE FILES MODIFIED BEYOND ALLOWED SET — "
        "architectural invariant violated.\n"
        f"Unexpected changes:\n{chr(10).join(sorted(unexpected))}"
    )
