"""
Node implementations for the Miktos engine graph.

Each node represents one layer of the core architecture:
  ORCHESTRATOR -> PLANNER -> EXECUTION -> REVIEW -> DECISION -> STATE UPDATE

All nodes are domain-agnostic.
Domain logic is injected via state["context"]["tools"].

Tool registry convention (set in main.py before run):
  state["context"]["tools"]["scanner"]    -> BaseTool with .safe_run()
  state["context"]["tools"]["classifier"] -> callable(file_meta: dict) -> dict
"""

import uuid
import logging
from datetime import datetime
from engine.graph.state import RunState
from engine.services.state_store import save_state

logger = logging.getLogger(__name__)


# -----------------------------
# ORCHESTRATOR
# -----------------------------

def orchestrator_node(state: RunState) -> RunState:
    """
    Control center. Assesses current state and sets the next routing step.

    Routing logic:
    - No tasks at all          -> planner (first run)
    - Pending tasks remain     -> execution (continue loop)
    - No pending tasks left    -> done
    """
    logs = list(state.get("logs", []))

    pending = state.get("pending_tasks", [])
    completed = state.get("completed_tasks", [])
    failed = state.get("failed_tasks", [])

    # First run — nothing planned yet
    if not pending and not completed and not failed:
        logs.append(f"[{_now()}] ORCHESTRATOR: Fresh run. Routing to planner.")
        return {**state, "current_step": "planner", "logs": logs}

    # Work remains
    if pending:
        logs.append(
            f"[{_now()}] ORCHESTRATOR: {len(pending)} tasks pending. "
            "Routing to execution."
        )
        return {**state, "current_step": "execution", "logs": logs}

    # All done
    logs.append(f"[{_now()}] ORCHESTRATOR: All tasks processed. Finalizing.")
    return {
        **state,
        "current_step": "finalize",
        "done": True,
        "exit_reason": "success",
        "logs": logs,
    }


# -----------------------------
# PLANNER
# -----------------------------

def planner_node(state: RunState) -> RunState:
    """
    Scans the target environment and builds the task list.

    Requires in context:
      - tools.scanner  : BaseTool
      - root_path      : str
    """
    logs = list(state.get("logs", []))
    errors = list(state.get("errors", []))

    scanner = state["context"].get("tools", {}).get("scanner")
    root_path = state["context"].get("root_path", "")

    logs.append(f"[{_now()}] PLANNER: Scanning '{root_path}'.")

    if not scanner:
        msg = "No scanner tool registered in context."
        errors.append({"step": "planner", "error": msg})
        logs.append(f"[{_now()}] PLANNER: ERROR — {msg}")
        return {
            **state,
            "errors": errors,
            "done": True,
            "exit_reason": "stop",
            "logs": logs,
        }

    result = scanner.safe_run({"root_path": root_path})

    if not result["success"]:
        errors.append({"step": "planner", "error": result["error"]})
        logs.append(f"[{_now()}] PLANNER: Scan failed — {result['error']}")
        return {
            **state,
            "errors": errors,
            "done": True,
            "exit_reason": "stop",
            "logs": logs,
        }

    files = result["result"]["files"]
    count = result["result"]["count"]
    logs.append(
        f"[{_now()}] PLANNER: Found {count} files. Building task list."
    )

    tasks = [
        {
            "task_id": uuid.uuid4().hex[:12],
            "file": f,
            "status": "pending",
            "retries": 0,
        }
        for f in files
    ]

    return {
        **state,
        "pending_tasks": tasks,
        "current_step": "execution",
        "logs": logs,
        "errors": errors,
    }


# -----------------------------
# EXECUTION
# -----------------------------

def execution_node(state: RunState) -> RunState:
    """
    Classifies files from the pending task queue in batches.

    Requires in context:
      - tools.classifier : callable(file_meta: dict) -> dict
      - batch_size       : int (default 50)
    """
    logs = list(state.get("logs", []))
    errors = list(state.get("errors", []))
    pending = list(state.get("pending_tasks", []))
    completed = list(state.get("completed_tasks", []))
    failed = list(state.get("failed_tasks", []))
    exhausted = list(state.get("exhausted_tasks", []))
    proposed_actions = list(state.get("proposed_actions", []))

    classifier = state["context"].get("tools", {}).get("classifier")
    batch_size = state["context"].get("batch_size", 50)
    max_retries = state.get("max_retries", 3)

    if not classifier:
        msg = "No classifier tool registered in context."
        errors.append({"step": "execution", "error": msg})
        logs.append(f"[{_now()}] EXECUTION: ERROR — {msg}")
        return {
            **state,
            "errors": errors,
            "done": True,
            "exit_reason": "stop",
            "logs": logs,
        }

    batch = pending[:batch_size]
    remaining = pending[batch_size:]

    logs.append(
        f"[{_now()}] EXECUTION: Processing batch of {len(batch)} "
        f"({len(remaining)} remaining after this batch)."
    )

    for task in batch:
        try:
            file_meta = task["file"]
            classification = classifier(file_meta)

            action = {
                "action_id": uuid.uuid4().hex[:12],
                "task_id": task["task_id"],
                "action_type": "classify",
                "file_path": file_meta["path"],
                "file_name": file_meta["name"],
                "category": classification["category"],
                "confidence": classification["confidence"],
                "method": classification["method"],
                "applied": False,
                "dry_run": state["mode"] == "dry_run",
            }
            proposed_actions.append(action)
            completed.append(
                {
                    **task,
                    "status": "classified",
                    "action_id": action["action_id"],
                }
            )

        except Exception as e:
            error_msg = str(e)
            task_retries = task.get("retries", 0)
            unrecoverable = _is_unrecoverable(error_msg)

            errors.append(
                {
                    "task_id": task.get("task_id"),
                    "step": "execution",
                    "error": error_msg,
                    "unrecoverable": unrecoverable,
                }
            )
            failed.append(
                {**task, "status": "failed", "error": error_msg}
            )

            if unrecoverable or task_retries >= max_retries:
                exhausted.append(
                    {
                        **task,
                        "status": "exhausted",
                        "error": error_msg,
                        "retries": task_retries,
                    }
                )
                logs.append(
                    f"[{_now()}] EXECUTION: Task"
                    f" {task.get('task_id')} exhausted"
                    f" (retries={task_retries},"
                    f" unrecoverable={unrecoverable})"
                    f" — {error_msg}"
                )
            else:
                remaining.append(
                    {
                        **task,
                        "retries": task_retries + 1,
                        "status": "pending",
                    }
                )
                logs.append(
                    f"[{_now()}] EXECUTION: Task"
                    f" {task.get('task_id')}"
                    f" retry {task_retries + 1}/{max_retries}"
                    f" — {error_msg}"
                )

    logs.append(
        f"[{_now()}] EXECUTION: Batch done. "
        f"proposed_actions total={len(proposed_actions)}."
    )

    return {
        **state,
        "pending_tasks": remaining,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "exhausted_tasks": exhausted,
        "proposed_actions": proposed_actions,
        "current_step": "review",
        "logs": logs,
        "errors": errors,
    }


# -----------------------------
# REVIEW
# -----------------------------

def review_node(state: RunState) -> RunState:
    """
    Validates proposed actions against confidence thresholds.

    Confidence bands (from context.thresholds):
      >= auto_approve  -> approved (auto-proceed)
      >= review_queue  -> queued for human review
      < review_queue   -> skipped and logged

    Does not decide — only evaluates.
    """
    logs = list(state.get("logs", []))
    proposed_actions = list(state.get("proposed_actions", []))
    review_queue = list(state.get("review_queue", []))
    skipped_tasks = list(state.get("skipped_tasks", []))

    thresholds = state["context"].get("thresholds", {})
    auto_approve = thresholds.get("auto_approve", 0.90)
    review_threshold = thresholds.get("review_queue", 0.60)

    unreviewed = [a for a in proposed_actions if "review_status" not in a]
    already_reviewed = [a for a in proposed_actions if "review_status" in a]

    approved_count = queued_count = skipped_count = 0
    reviewed = []

    for action in unreviewed:
        confidence = action.get("confidence", 0.0)

        if confidence >= auto_approve:
            action["review_status"] = "approved"
            approved_count += 1
        elif confidence >= review_threshold:
            action["review_status"] = "queued"
            review_queue.append(action)
            queued_count += 1
        else:
            action["review_status"] = "skipped"
            skipped_tasks.append({
                "action_id": action["action_id"],
                "file": action["file_path"],
                "reason": "confidence_below_threshold",
                "confidence": confidence,
            })
            skipped_count += 1

        reviewed.append(action)

    logs.append(
        f"[{_now()}] REVIEW: approved={approved_count}, "
        f"queued={queued_count}, skipped={skipped_count}."
    )

    return {
        **state,
        "proposed_actions": already_reviewed + reviewed,
        "review_queue": review_queue,
        "skipped_tasks": skipped_tasks,
        "current_step": "decision",
        "logs": logs,
    }


# -----------------------------
# DECISION
# -----------------------------

def decision_node(state: RunState) -> RunState:
    """
    Gates the loop. Sets exit_reason for the router.

    Outcomes:
      continue  — pending tasks remain, loop back
      stop      — error threshold exceeded
      success   — all tasks processed cleanly
    """
    logs = list(state.get("logs", []))

    pending = state.get("pending_tasks", [])
    errors = state.get("errors", [])
    exhausted = state.get("exhausted_tasks", [])
    completed = state.get("completed_tasks", [])
    retries = state.get("retries", 0)
    max_retries = state.get("max_retries", 3)

    # Stop immediately on any unrecoverable error
    unrecoverable = [e for e in errors if e.get("unrecoverable", False)]
    if unrecoverable:
        logs.append(
            f"[{_now()}] DECISION: Unrecoverable error detected"
            f" ({unrecoverable[0].get('error', '')}). STOP."
        )
        return {
            **state,
            "exit_reason": "stop",
            "done": True,
            "current_step": "state_update",
            "logs": logs,
        }

    # Stop if exhausted tasks exceed configurable threshold (default 20%)
    total = len(completed) + len(exhausted)
    exhausted_threshold = state["context"].get("exhausted_threshold", 0.20)
    exhausted_pct = len(exhausted) / total if total > 0 else 0.0
    if len(exhausted) > 0 and exhausted_pct > exhausted_threshold:
        logs.append(
            f"[{_now()}] DECISION: Exhausted rate"
            f" {exhausted_pct:.0%} exceeds"
            f" threshold {exhausted_threshold:.0%}"
            f" ({len(exhausted)}/{total}). STOP."
        )
        return {
            **state,
            "exit_reason": "stop",
            "done": True,
            "current_step": "state_update",
            "logs": logs,
        }

    # Legacy coarse guard (safety net)
    if len(errors) > 10 and retries >= max_retries:
        logs.append(
            f"[{_now()}] DECISION: Error threshold exceeded "
            f"({len(errors)} errors, "
            f"{retries}/{max_retries} retries). STOP."
        )
        return {
            **state,
            "exit_reason": "stop",
            "done": True,
            "current_step": "state_update",
            "logs": logs,
        }

    if pending:
        logs.append(
            f"[{_now()}] DECISION: {len(pending)} tasks remain. CONTINUE."
        )
        return {
            **state,
            "exit_reason": "continue",
            "current_step": "state_update",
            "logs": logs,
        }

    logs.append(f"[{_now()}] DECISION: All tasks processed. SUCCESS.")
    return {
        **state,
        "exit_reason": "success",
        "done": True,
        "current_step": "state_update",
        "logs": logs,
    }


# -----------------------------
# STATE UPDATE
# -----------------------------

def state_update_node(state: RunState) -> RunState:
    """
    Persists the current run state to disk.

    This is what separates a loop from a reset.
    """
    logs = list(state.get("logs", []))

    try:
        save_state(state)
        logs.append(
            f"[{_now()}] STATE UPDATE: Saved "
            f"(run_id={state['run_id']})."
        )
    except Exception as e:
        logs.append(
            f"[{_now()}] STATE UPDATE: WARNING — could not save state: {e}"
        )

    return {**state, "logs": logs}


# -----------------------------
# HELPERS
# -----------------------------

def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


_UNRECOVERABLE_MARKERS = (
    "permission denied",
    "no space left on device",
    "no such file or directory",
    "read-only file system",
    "errno 13",
    "errno 28",
)


def _is_unrecoverable(error_msg: str) -> bool:
    """Return True if the error message signals a system-level failure."""
    lowered = error_msg.lower()
    return any(marker in lowered for marker in _UNRECOVERABLE_MARKERS)
