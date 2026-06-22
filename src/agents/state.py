"""
AgentState — the shared memory of the workflow.

This TypedDict is passed between every node in the LangGraph graph.
Think of it as a baton in a relay race: each agent reads what came before,
does its work, and writes its output back into the state.

The `Annotated[List[...], operator.add]` pattern on `research_items` tells
LangGraph to APPEND new items rather than REPLACE the list — this is how
we accumulate research across multiple Researcher calls.
"""
import operator
from typing import TypedDict, List, Optional, Annotated


class ResearchItem(TypedDict):
    """One completed unit of research: a question + findings."""
    query: str        # The research question that was asked
    findings: str     # The synthesized answer from web search + LLM


class AgentState(TypedDict):
    """
    The complete state of one agent workflow run.

    Flow of information:
        topic          (set by user)
            → research_plan    (set by Planner)
                → research_items   (accumulated by Researcher, one per question)
                    → synthesis        (set by Synthesizer)
                        → final_report     (set by Writer)
    """
    # --- Input ---
    topic: str                    # The research topic from the user
    run_id: str                   # UUID linking this run to the database

    # --- Planner output ---
    research_plan: List[str]      # ["Question 1", "Question 2", ...]
    research_index: int           # Which question we're currently researching

    # --- Researcher output (accumulates across multiple calls) ---
    # operator.add means new items are APPENDED, not replaced
    research_items: Annotated[List[ResearchItem], operator.add]

    # --- Synthesizer output ---
    synthesis: str                # Combined insights from all research

    # --- Writer output ---
    final_report: str             # Final polished markdown report

    # --- Control ---
    status: str                   # Human-readable progress ("researching_2_of_4")
    error: Optional[str]          # Error message if something failed
