"""
Tests for the engine state store.
"""

import pytest
from engine.services.state_store import save_state, load_state, generate_run_id


def make_test_state(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "domain": "test",
        "goal": "test goal",
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
        "context": {},
    }


def test_save_and_load_state(tmp_path, monkeypatch):
    import engine.services.state_store as store
    monkeypatch.setattr(store, "STATE_DIR", tmp_path)

    run_id = generate_run_id()
    state = make_test_state(run_id)

    save_state(state)
    loaded = load_state(run_id)

    assert loaded["run_id"] == run_id
    assert loaded["domain"] == "test"
    assert loaded["done"] is False
