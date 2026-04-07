"""
Milestone 1.2 — Review Queue & Confidence Band Integration Test.

Stresses the confidence bands against real mixed content:

  Fixture: tests/fixtures/mixed_folder/
    report.pdf, photo.jpg, video.mp4,   <- extension match -> 0.95 -> approved
    notes.txt, data.csv, archive.zip, script.py
    unknown.xyz, noextension, ambiguous.dat  <- no match -> 0.40 -> skipped

Thresholds (same as main.py defaults):
  auto_approve  >= 0.90  -> approved
  review_queue  >= 0.60  -> queued
  below          < 0.60  -> skipped

Assertions:
  1. At least one action has review_status == "approved"
  2. At least one file ends up in skipped_tasks
  3. The run exits with exit_reason == "success"
  4. A state file is written to data/state/
"""

from pathlib import Path

from engine.graph.graph_builder import build_graph
from engine.graph.state import RunState
from engine.services.state_store import generate_run_id
from domains.file_analyzer.tools.fs_tools import FileScannerTool
from domains.file_analyzer.tools.classifier import classify_file


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mixed_folder"


def _build_state(root_path: str) -> RunState:
    return {
        "run_id": generate_run_id(),
        "domain": "file_analyzer",
        "goal": f"Milestone 1.2 test — confidence bands: {root_path}",
        "mode": "dry_run",
        "current_step": "init",
        "pending_tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "skipped_tasks": [],
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
        "context": {
            "root_path": root_path,
            "batch_size": 50,
            "thresholds": {
                "auto_approve": 0.90,
                "review_queue": 0.60,
            },
            "tools": {
                "scanner": FileScannerTool(),
                "classifier": classify_file,
            },
        },
    }


def test_confidence_bands_approved():
    """Known-extension files must be auto-approved at 0.95."""
    root = str(FIXTURE_DIR.resolve())
    final = build_graph().invoke(_build_state(root))

    actions = final.get("proposed_actions", [])
    approved = [
        a for a in actions if a.get("review_status") == "approved"
    ]
    details = [
        (a["file_name"], a["confidence"], a.get("review_status"))
        for a in actions
    ]
    assert len(approved) >= 1, (
        f"Expected at least 1 approved action. Got: {details}"
    )


def test_confidence_bands_skipped():
    """Unknown-extension files must be skipped (confidence < 0.60)."""
    root = str(FIXTURE_DIR.resolve())
    final = build_graph().invoke(_build_state(root))

    skipped = final.get("skipped_tasks", [])
    assert len(skipped) >= 1, (
        "Expected at least 1 skipped task. "
        f"Skipped list: {skipped}"
    )


def test_run_exits_success():
    """Full loop must exit cleanly with exit_reason == 'success'."""
    root = str(FIXTURE_DIR.resolve())
    final = build_graph().invoke(_build_state(root))

    assert final.get("exit_reason") == "success", (
        f"Expected exit_reason='success', got '{final.get('exit_reason')}'. "
        f"Errors: {final.get('errors', [])}"
    )


def test_state_file_written():
    """State must be persisted to data/state/ after the run."""
    root = str(FIXTURE_DIR.resolve())
    state = _build_state(root)
    final = build_graph().invoke(state)

    run_id = final["run_id"]
    state_file = Path("data/state") / f"{run_id}.json"
    assert state_file.exists(), (
        f"Expected state file at {state_file} — not found."
    )
