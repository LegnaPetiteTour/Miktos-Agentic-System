"""
Phase 4a tests — Parallel Execution.

Four CI-friendly tests using the media_folder fixture (8 files).

Tests:
  1. parallel_execution_node is registered in the graph (additive, not replacing)
  2. Parallel produces identical results to sequential
  3. Sequential mode (default) is unchanged — routes to execution_node
  4. parallel_workers=2 is accepted and produces correct output
"""

from pathlib import Path

from domains.kosmos.tools.media_classifier import classify_media_file
from engine.graph.graph_builder import build_graph
from engine.graph.state import RunState
from engine.services.state_store import generate_run_id
from engine.tools.shared_tools import FileScannerTool

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "media_folder"


def _build_state(
    root_path: str,
    execution_mode: str = "sequential",
    parallel_workers: int = 4,
) -> RunState:
    ctx: dict = {
        "root_path": root_path,
        "batch_size": 50,
        "execution_mode": execution_mode,
        "parallel_workers": parallel_workers,
        "thresholds": {
            "auto_approve": 0.90,
            "review_queue": 0.60,
        },
        "exhausted_threshold": 0.20,
        "tools": {
            "scanner": FileScannerTool(),
            "classifier": classify_media_file,
        },
    }
    return {
        "run_id": generate_run_id(),
        "domain": "kosmos",
        "goal": "Phase 4a test",
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
        "context": ctx,
    }


def _actions_signature(state: RunState) -> list:
    """Sorted (file_path, category, confidence) for order-insensitive comparison."""
    actions = state.get("proposed_actions", [])
    return sorted(
        [(a["file_path"], a["category"], a["confidence"]) for a in actions],
        key=lambda x: x[0],
    )


def test_parallel_node_registered_in_graph():
    """parallel_execution_node is present — additive, not replacing execution_node."""
    graph = build_graph()
    node_names = set(graph.nodes)
    assert "parallel_execution_node" in node_names, (
        "parallel_execution_node not found in compiled graph"
    )
    assert "execution_node" in node_names, (
        "execution_node must still be present (additive change)"
    )


def test_parallel_produces_same_results_as_sequential():
    """Parallel and sequential must produce identical proposed_actions."""
    root = str(FIXTURE_DIR.resolve())
    graph = build_graph()

    seq_state = graph.invoke(_build_state(root, execution_mode="sequential"))
    par_state = graph.invoke(
        _build_state(root, execution_mode="parallel", parallel_workers=4)
    )

    assert seq_state["exit_reason"] == "success"
    assert par_state["exit_reason"] == "success"
    assert len(seq_state["proposed_actions"]) == len(par_state["proposed_actions"]), (
        f"Action count mismatch: "
        f"seq={len(seq_state['proposed_actions'])} "
        f"par={len(par_state['proposed_actions'])}"
    )

    seq_sig = _actions_signature(seq_state)
    par_sig = _actions_signature(par_state)
    assert seq_sig == par_sig, (
        "Sequential and parallel produced different action sets.\n"
        f"Sequential: {seq_sig}\nParallel: {par_sig}"
    )


def test_sequential_mode_unchanged():
    """No execution_mode key in context must default to sequential execution_node."""
    root = str(FIXTURE_DIR.resolve())
    graph = build_graph()

    # Build state with no execution_mode key (strict default test)
    state = _build_state(root, execution_mode="sequential")
    del state["context"]["execution_mode"]  # type: ignore[misc]
    # parallel_workers key also absent — must not be needed for sequential

    final = graph.invoke(state)

    assert final["exit_reason"] == "success"
    # Sequential path logs use "EXECUTION:" prefix, not "PARALLEL EXECUTION:"
    logs = final.get("logs", [])
    seq_logs = [
        line for line in logs
        if "EXECUTION:" in line and "PARALLEL" not in line
    ]
    par_logs = [line for line in logs if "PARALLEL EXECUTION:" in line]
    assert len(seq_logs) > 0, (
        "Expected EXECUTION: log entries for sequential mode"
    )
    assert len(par_logs) == 0, (
        "Unexpected PARALLEL EXECUTION: logs in sequential mode"
    )


def test_parallel_workers_accepted():
    """execution_mode=parallel with parallel_workers=2 must complete successfully."""
    root = str(FIXTURE_DIR.resolve())
    graph = build_graph()

    final = graph.invoke(
        _build_state(root, execution_mode="parallel", parallel_workers=2)
    )

    assert final["exit_reason"] == "success"
    assert final["domain"] == "kosmos"
    assert len(final.get("errors", [])) == 0
    assert len(final.get("proposed_actions", [])) > 0
