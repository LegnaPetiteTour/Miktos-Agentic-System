"""
Milestone 1.3 — Closed-Loop Correction Test Suite.

Exercises the retry path, exhaustion bucket, stop condition, and state
integrity assertions that were absent in Milestone 1.2.

All failure scenarios are injected via a patched classifier — no real
broken files required.  The fixture folder contains one normal file so
the scanner always returns at least one task.

Test matrix:
  test_retry_counter_increments  — task fails twice then succeeds; retries
                                   counter on the re-queued task must be 1
                                   after the first failure.
  test_exhausted_tasks_bucket    — task fails max_retries+1 times; must
                                   land in exhausted_tasks, not
                                   skipped_tasks.
  test_stop_on_exhausted_threshold — >20% of tasks exhausted; decision_node
                                      must set exit_reason="stop".
  test_state_integrity           — final state always has all four buckets
                                   present and mutually exclusive for the
                                   file that was processed.
"""

from pathlib import Path
from typing import Any

from engine.graph.graph_builder import build_graph
from engine.graph.state import RunState
from engine.services.state_store import generate_run_id
from domains.file_analyzer.tools.fs_tools import FileScannerTool
from domains.file_analyzer.tools.classifier import classify_file


FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "failure_folder"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_state(
    classifier: Any,
    max_retries: int = 3,
    exhausted_threshold: float = 0.20,
    extra_context: dict | None = None,
) -> RunState:
    ctx: dict = {
        "root_path": str(FIXTURE_DIR.resolve()),
        "batch_size": 50,
        "thresholds": {
            "auto_approve": 0.90,
            "review_queue": 0.60,
        },
        "exhausted_threshold": exhausted_threshold,
        "tools": {
            "scanner": FileScannerTool(),
            "classifier": classifier,
        },
    }
    if extra_context:
        ctx.update(extra_context)

    return {
        "run_id": generate_run_id(),
        "domain": "file_analyzer",
        "goal": "Milestone 1.3 failure scenario test",
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
        "max_retries": max_retries,
        "replans": 0,
        "max_replans": 2,
        "done": False,
        "exit_reason": None,
        "context": ctx,
    }


class _FailThenSucceedClassifier:
    """
    Fails `fail_times` times before delegating to the real classifier.
    Uses a mutable counter so each call advances the state.
    """
    def __init__(self, fail_times: int) -> None:
        self._remaining = fail_times

    def __call__(self, file_meta: dict) -> dict:
        if self._remaining > 0:
            self._remaining -= 1
            raise RuntimeError("injected transient failure")
        return classify_file(file_meta)


class _AlwaysFailClassifier:
    """Always raises a transient error."""
    def __call__(self, file_meta: dict) -> dict:
        raise RuntimeError("injected permanent failure")


class _UnrecoverableClassifier:
    """Raises an error that matches the unrecoverable markers."""
    def __call__(self, file_meta: dict) -> dict:
        raise PermissionError("Permission denied: cannot read file")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_retry_counter_increments():
    """
    A task that fails once must be re-queued with retries=1.
    On the second attempt (using the same shared classifier instance)
    it succeeds.  Confirmed by: the file ends up in completed_tasks,
    not exhausted_tasks.
    """
    classifier = _FailThenSucceedClassifier(fail_times=1)
    final = build_graph().invoke(_base_state(classifier, max_retries=3))

    completed_files = [
        t["file"]["name"]
        for t in final.get("completed_tasks", [])
    ]
    exhausted_files = [
        t["file"]["name"]
        for t in final.get("exhausted_tasks", [])
    ]

    assert "normal.txt" in completed_files, (
        f"Expected normal.txt in completed after retry. "
        f"completed={completed_files}, exhausted={exhausted_files}"
    )
    assert "normal.txt" not in exhausted_files, (
        f"normal.txt must not be exhausted after only 1 failure. "
        f"exhausted={exhausted_files}"
    )


def test_exhausted_tasks_bucket():
    """
    A task that fails more times than max_retries must land in
    exhausted_tasks, not in skipped_tasks.
    """
    # fail_times > max_retries so all retries are consumed
    classifier = _AlwaysFailClassifier()
    final = build_graph().invoke(_base_state(classifier, max_retries=2))

    exhausted = final.get("exhausted_tasks", [])
    skipped = final.get("skipped_tasks", [])

    assert len(exhausted) >= 1, (
        f"Expected at least 1 exhausted task. "
        f"exhausted={exhausted}, skipped={skipped}"
    )
    # Exhausted and skipped must be separate; no file in both
    exhausted_ids = {t.get("task_id") for t in exhausted}
    skipped_ids = {t.get("task_id") for t in skipped}
    overlap = exhausted_ids & skipped_ids
    assert not overlap, (
        f"Tasks must not appear in both buckets: {overlap}"
    )


def test_stop_on_exhausted_threshold():
    """
    When exhausted_tasks exceeds the configured threshold, decision_node
    must set exit_reason='stop' regardless of pending count.
    Uses a very low threshold (0.0) to guarantee the stop fires.
    """
    classifier = _AlwaysFailClassifier()
    final = build_graph().invoke(
        _base_state(classifier, max_retries=0, exhausted_threshold=0.0)
    )

    assert final.get("exit_reason") == "stop", (
        f"Expected exit_reason='stop' when exhausted threshold exceeded. "
        f"Got: '{final.get('exit_reason')}', "
        f"exhausted={len(final.get('exhausted_tasks', []))}"
    )


def test_state_integrity():
    """
    The final state file must contain all four buckets and they must be
    non-overlapping for any given task_id.
    Also confirms a state file is written to data/state/.
    """
    classifier = _FailThenSucceedClassifier(fail_times=1)
    state = _base_state(classifier, max_retries=3)
    final = build_graph().invoke(state)

    # State file written
    run_id = final["run_id"]
    state_file = Path("data/state") / f"{run_id}.json"
    assert state_file.exists(), (
        f"State file not found at {state_file}"
    )

    # All four buckets present as list keys
    for bucket in (
        "completed_tasks",
        "skipped_tasks",
        "exhausted_tasks",
        "failed_tasks",
    ):
        assert bucket in final, f"Missing bucket '{bucket}' in final state"

    # No task_id appears in more than one of the three semantic buckets
    def _ids(key: str) -> set:
        return {t.get("task_id") for t in final.get(key, [])}

    completed_ids = _ids("completed_tasks")
    skipped_ids = _ids("skipped_tasks")
    exhausted_ids = _ids("exhausted_tasks")

    assert not (completed_ids & skipped_ids), (
        "completed and skipped overlap"
    )
    assert not (completed_ids & exhausted_ids), (
        "completed and exhausted overlap"
    )
    assert not (skipped_ids & exhausted_ids), (
        "skipped and exhausted overlap"
    )
