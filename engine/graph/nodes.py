"""
Node definitions for the Miktos engine graph.

Each node represents one layer of the core architecture:
  INPUT -> ORCHESTRATOR -> PLANNER -> EXECUTION -> REVIEW -> DECISION -> STATE UPDATE -> LOOP/EXIT

Nodes are domain-agnostic. Domain logic is injected through context and tool registry.
"""

from engine.graph.state import RunState


def orchestrator_node(state: RunState) -> RunState:
    """Control center. Routes work, tracks progress, decides what happens next."""
    # Classify task, load context, decide workflow, route to next step
    raise NotImplementedError


def planner_node(state: RunState) -> RunState:
    """Decomposes goal into tasks, dependencies, and success criteria."""
    raise NotImplementedError


def execution_node(state: RunState) -> RunState:
    """Performs actions through tools. The only node that touches the real world."""
    raise NotImplementedError


def review_node(state: RunState) -> RunState:
    """Validates outputs against success criteria. Does not decide -- only evaluates."""
    raise NotImplementedError


def decision_node(state: RunState) -> RunState:
    """Gates the loop. Chooses: continue / retry / replan / escalate / stop."""
    raise NotImplementedError


def state_update_node(state: RunState) -> RunState:
    """Persists progress, failures, outputs, and changed context."""
    raise NotImplementedError
