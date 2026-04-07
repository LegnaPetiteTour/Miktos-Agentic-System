"""
Milestone 1.4 — Classifier Coverage: four-tier confidence system.

Validates the new mime_unhandled tier (0.60) introduced in M1.4:

  Tier              Confidence  Method           Outcome
  ─────────────────────────────────────────────────────────
  Extension match   0.95        "extension"      approved
  Handled MIME      0.80        "mime"           approved
  Detected, unmapped 0.60       "mime_unhandled" review_queue
  No MIME at all    0.40        "fallback"       skipped

Key invariant:
  mime_type == "unknown"  →  ALWAYS tier 4 (fallback), NEVER tier 3.

Fixture:
  tests/fixtures/mixed_folder/molecule.xyz — MIME: chemical/x-xyz
    (.xyz not in EXTENSION_MAP, prefix "chemical/" not in handled list)
    Expected path: tier 3 → 0.60 → review_queue (not skipped_tasks)

Tests:
  1. test_mime_unhandled_classifies_correctly
     Unit test: pure classifier output for tier-3 input.

  2. test_mime_unhandled_routes_to_review_queue
     Integration: full graph run on mixed_folder — molecule.xyz must
     appear in review_queue, not in skipped_tasks.

  3. test_text_prefix_routes_to_documents
     Unit: text/ prefix (tier 2) → documents, confidence 0.80.

  4. test_no_mime_still_falls_to_fallback
     Unit: mime_type == "unknown" must remain at tier 4, not promoted
     to tier 3. This is the critical boundary regression test.
"""

from pathlib import Path

from domains.file_analyzer.tools.classifier import classify_file
from domains.file_analyzer.tools.fs_tools import FileScannerTool
from engine.graph.graph_builder import build_graph
from engine.graph.state import RunState
from engine.services.state_store import generate_run_id

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mixed_folder"


def _build_state(root_path: str) -> RunState:
    return {
        "run_id": generate_run_id(),
        "domain": "file_analyzer",
        "goal": f"Milestone 1.4 test — classifier coverage: {root_path}",
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


def test_mime_unhandled_classifies_correctly():
    """
    Unit: .xyz + chemical/x-xyz must yield tier-3 mime_unhandled at 0.60.

    "chemical/" is a real MIME prefix that Python's mimetypes detects but
    the classifier has no rule for it — exactly what tier 3 is for.
    """
    result = classify_file({"suffix": ".xyz", "mime_type": "chemical/x-xyz"})
    assert result["category"] == "unclassified"
    assert result["method"] == "mime_unhandled"
    assert result["confidence"] == 0.60


def test_mime_unhandled_routes_to_review_queue():
    """
    Integration: molecule.xyz must land in review_queue, not skipped_tasks.

    molecule.xyz → mimetypes.guess_type → "chemical/x-xyz" → tier 3 → 0.60
    0.60 == review_queue threshold → queued, not skipped.
    """
    root = str(FIXTURE_DIR.resolve())
    final = build_graph().invoke(_build_state(root))

    review_queue = final.get("review_queue", [])
    skipped_tasks = final.get("skipped_tasks", [])

    queued_names = [a.get("file_name", "") for a in review_queue]
    skipped_files = [s.get("file", "") for s in skipped_tasks]

    assert any("molecule.xyz" in name for name in queued_names), (
        f"Expected molecule.xyz in review_queue. "
        f"Queued files: {queued_names}. "
        f"Skipped files: {skipped_files}."
    )
    assert not any("molecule.xyz" in f for f in skipped_files), (
        f"molecule.xyz must NOT be in skipped_tasks. "
        f"Skipped files: {skipped_files}."
    )


def test_text_prefix_routes_to_documents():
    """
    Unit: text/ prefix is a handled MIME → tier 2 → documents at 0.80.

    .unknown suffix has no extension match so classification falls through
    to the MIME prefix table where "text/" → documents, 0.80, method "mime".
    """
    result = classify_file({"suffix": ".unknown", "mime_type": "text/plain"})
    assert result["category"] == "documents"
    assert result["method"] == "mime"
    assert result["confidence"] == 0.80


def test_no_mime_still_falls_to_fallback():
    """
    Unit: mime_type == "unknown" must stay at tier 4 (0.40), never tier 3.

    This is the critical boundary invariant:
      - tier 3 applies when MIME is detected but unmapped
      - tier 4 applies when MIME is absent / undetectable

    "unknown" is the sentinel value set by fs_tools when
    mimetypes.guess_type returns None. It must never be treated as a
    detected MIME type.
    """
    result = classify_file({"suffix": ".dat", "mime_type": "unknown"})
    assert result["category"] == "unclassified"
    assert result["method"] == "fallback"
    assert result["confidence"] == 0.40
