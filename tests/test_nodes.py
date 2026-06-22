"""Unit tests for agent nodes (mock LLM calls)."""
import pytest
from unittest.mock import patch, MagicMock
from src.agents.state import AgentState
from src.agents.nodes import planner_node, should_continue_research


def make_state(**overrides) -> AgentState:
    base = {
        "topic": "transformer attention mechanisms",
        "run_id": "test-run-1",
        "research_plan": [],
        "research_index": 0,
        "research_items": [],
        "synthesis": "",
        "final_report": "",
        "status": "starting",
        "error": None,
    }
    return {**base, **overrides}


def test_should_continue_research_loops():
    state = make_state(research_plan=["q1", "q2", "q3"], research_index=1)
    assert should_continue_research(state) == "continue_research"


def test_should_continue_research_stops():
    state = make_state(research_plan=["q1", "q2", "q3"], research_index=3)
    assert should_continue_research(state) == "synthesize"


@patch("src.agents.nodes.ChatGoogleGenerativeAI")
def test_planner_node_returns_plan(mock_llm_class):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content='["What is X?", "How does X work?", "Why does X matter?"]'
    )
    mock_llm_class.return_value = mock_llm

    state = make_state()
    result = planner_node(state)

    assert "research_plan" in result
    assert len(result["research_plan"]) == 3
    assert result["research_index"] == 0
