"""
Router logic for the Miktos engine graph.

Defines conditional edges -- what happens after each node based on state.
"""

from engine.graph.state import RunState


def route_after_decision(state: RunState) -> str:
    """After the decision node, route to the correct next node."""
    if state["done"]:
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
