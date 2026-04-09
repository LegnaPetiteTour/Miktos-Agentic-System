"""
Router logic for the Miktos engine graph.

Defines conditional edges — what happens after each node based on state.
"""

from engine.graph.state import RunState


def _execution_target(state: RunState) -> str:
    """Return the correct execution node name based on execution_mode in context."""
    mode = state.get("context", {}).get("execution_mode", "sequential")
    return "parallel_execution_node" if mode == "parallel" else "execution_node"


def route_to_execution(state: RunState) -> str:
    """After planner_node, route to sequential or parallel execution."""
    return _execution_target(state)


def route_from_orchestrator(state: RunState) -> str:
    """After orchestrator, route based on current_step."""
    if state.get("done"):
        return "end"
    step = state.get("current_step", "")
    if step == "execution":
        return _execution_target(state)
    return "planner_node"


def route_after_decision(state: RunState) -> str:
    """After state_update, route based on exit_reason."""
    if state.get("done"):
        return "exit"

    exit_reason = state.get("exit_reason", "")

    if exit_reason == "retry":
        return _execution_target(state)
    elif exit_reason == "replan":
        return "planner_node"
    elif exit_reason in ("escalate", "stop"):
        return "exit"
    else:
        return "orchestrator_node"  # continue
