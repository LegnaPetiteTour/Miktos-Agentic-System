"""
Builds the LangGraph execution graph for the Miktos engine.

This wires all nodes and conditional edges together.
The graph is the maze.
"""

# Uncomment once LangGraph is installed:
# from langgraph.graph import StateGraph, END
# from engine.graph.state import RunState
# from engine.graph import nodes, router


def build_graph():
    """Build and return the compiled Miktos engine graph."""
    # graph = StateGraph(RunState)
    # graph.add_node("orchestrator_node", nodes.orchestrator_node)
    # graph.add_node("planner_node", nodes.planner_node)
    # graph.add_node("execution_node", nodes.execution_node)
    # graph.add_node("review_node", nodes.review_node)
    # graph.add_node("decision_node", nodes.decision_node)
    # graph.add_node("state_update_node", nodes.state_update_node)
    # graph.set_entry_point("orchestrator_node")
    # graph.add_edge("orchestrator_node", "planner_node")
    # graph.add_edge("planner_node", "execution_node")
    # graph.add_edge("execution_node", "review_node")
    # graph.add_edge("review_node", "decision_node")
    # graph.add_edge("decision_node", "state_update_node")
    # graph.add_conditional_edges("state_update_node", router.route_after_decision)
    # return graph.compile()
    raise NotImplementedError("Install LangGraph and uncomment graph wiring.")
