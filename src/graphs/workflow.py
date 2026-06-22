"""
LangGraph Workflow — the orchestration graph.

This file is the heart of the system. It assembles the individual agent
nodes into a directed graph with defined edges and conditional routing.

Concepts demonstrated:
  - StateGraph: A graph where nodes share a typed state object
  - Nodes: Python functions that transform state
  - Edges: Connections between nodes (can be conditional)
  - Checkpointer: Saves state after every node so runs are resumable
  - Conditional edges: Routing logic that creates loops

Graph structure:
  START → planner → researcher → (loop or) synthesizer → writer → END
                        ↑___________↓ (conditional loop)
"""
import logging
import psycopg
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from src.agents.state import AgentState
from src.agents.nodes import (
    planner_node,
    researcher_node,
    synthesizer_node,
    writer_node,
    should_continue_research,
)
from src.config import settings

logger = logging.getLogger(__name__)


def build_graph():
    """
    Assemble the LangGraph workflow.

    Returns a compiled graph WITHOUT a checkpointer (useful for testing).
    For production use, call build_graph_with_checkpointer().
    """
    workflow = StateGraph(AgentState)

    # --- Register Nodes ---
    # Each node is a function: (AgentState) -> dict
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("writer", writer_node)

    # --- Define Edges ---
    # Entry point: always start with the planner
    workflow.add_edge(START, "planner")

    # Planner always goes to researcher (first question)
    workflow.add_edge("planner", "researcher")

    # After researcher: conditional routing
    # should_continue_research() returns "continue_research" or "synthesize"
    # The dict maps those return values to the next node
    workflow.add_conditional_edges(
        "researcher",
        should_continue_research,
        {
            "continue_research": "researcher",   # loop back for next question
            "synthesize": "synthesizer",          # done, move to synthesis
        }
    )

    # Linear from here on
    workflow.add_edge("synthesizer", "writer")
    workflow.add_edge("writer", END)

    return workflow.compile()


def build_graph_with_checkpointer():
    """
    Assemble the workflow with a Postgres checkpointer.

    The checkpointer saves a snapshot of the AgentState after EVERY node completes.
    This means:
    - If the worker crashes mid-run, the workflow can resume from the last checkpoint
    - You can inspect the state at any point in a run's history
    - Multiple runs are fully isolated by their thread_id (= run_id)

    Returns (compiled_graph, psycopg_connection) — caller must close the connection.
    """
    # autocommit=True is required for checkpointer.setup() — it runs CREATE TABLE IF NOT EXISTS
    # migrations that must each commit independently. Without autocommit, a failed migration
    # aborts the transaction and all subsequent commands fail with InFailedSqlTransaction.
    conn = psycopg.connect(settings.POSTGRES_URL_SYNC, autocommit=True)
    checkpointer = PostgresSaver(conn)

    # Creates LangGraph's checkpoint tables if they don't exist
    # Tables: checkpoints, checkpoint_blobs, checkpoint_writes
    checkpointer.setup()

    workflow = StateGraph(AgentState)
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("writer", writer_node)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_conditional_edges(
        "researcher",
        should_continue_research,
        {
            "continue_research": "researcher",
            "synthesize": "synthesizer",
        }
    )
    workflow.add_edge("synthesizer", "writer")
    workflow.add_edge("writer", END)

    graph = workflow.compile(checkpointer=checkpointer)
    return graph, conn
