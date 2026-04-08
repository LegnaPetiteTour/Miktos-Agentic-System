"""
Builds the LangGraph execution graph for the Miktos engine.

This wires all nodes and conditional edges together.
The graph is the maze.

Architecture:
  orchestrator_node
      | (conditional: planner or execution or end)
  planner_node
      | (conditional: sequential or parallel)
  execution_node | parallel_execution_node
      |
  review_node
      |
  decision_node
      |
  state_update_node
      | (conditional: loop back to orchestrator, or exit)
"""

from langgraph.graph import StateGraph, END
from engine.graph.state import RunState
from engine.graph import nodes, router


def build_graph():
    """Build and return the compiled Miktos engine graph."""
    graph = StateGraph(RunState)

    # Register nodes
    graph.add_node("orchestrator_node", nodes.orchestrator_node)
    graph.add_node("planner_node", nodes.planner_node)
    graph.add_node("execution_node", nodes.execution_node)
    graph.add_node("parallel_execution_node", nodes.parallel_execution_node)
    graph.add_node("review_node", nodes.review_node)
    graph.add_node("decision_node", nodes.decision_node)
    graph.add_node("state_update_node", nodes.state_update_node)

    # Entry point
    graph.set_entry_point("orchestrator_node")

    # Conditional routing from orchestrator
    graph.add_conditional_edges(
        "orchestrator_node",
        router.route_from_orchestrator,
        {
            "planner_node": "planner_node",
            "execution_node": "execution_node",
            "parallel_execution_node": "parallel_execution_node",
            "end": END,
        },
    )

    # After planner: conditional route to sequential or parallel execution
    graph.add_conditional_edges(
        "planner_node",
        router.route_to_execution,
        {
            "execution_node": "execution_node",
            "parallel_execution_node": "parallel_execution_node",
        },
    )

    # Both execution paths feed into review
    graph.add_edge("execution_node", "review_node")
    graph.add_edge("parallel_execution_node", "review_node")

    graph.add_edge("review_node", "decision_node")
    graph.add_edge("decision_node", "state_update_node")

    # Conditional loop from state_update
    graph.add_conditional_edges(
        "state_update_node",
        router.route_after_decision,
        {
            "orchestrator_node": "orchestrator_node",
            "execution_node": "execution_node",
            "parallel_execution_node": "parallel_execution_node",
            "planner_node": "planner_node",
            "exit": END,
        },
    )

    return graph.compile()
