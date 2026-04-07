"""
Router logic for the Miktos engine graph.

Defines conditional edges — what happens after each node based on state.
"""

from engine.graph.state import RunState


def route_from_orchestrator(state: RunState) -> str:
    """After orchestrator, route based on current_step."""
    if state.get("done"):
        return "end"
    step = state.get("current_step", "")
    if step == "execution":
        return "execution_node"
    return "planner_node"


def route_after_decision(state: RunState) -> str:
    """After state_update, route based on exit_reason."""
    if state.get("done"):
        return "exit"

    exit_reason = state.get("exit_reason", "")

    if exit_reason == "retry":
        return "execution_node"
    elif exit_reason == "replan":
        return "planner_node"
    elif exit_reason in ("escalate", "stop"):
        return "exit"
    else:
        return "orchestrator_node"  # continue
