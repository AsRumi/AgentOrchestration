"""Tests for the LangGraph workflow graph assembly."""
import pytest
from unittest.mock import patch, MagicMock


def test_build_graph_compiles():
    """Verify the graph builds and compiles without errors."""
    with patch("src.agents.nodes.ChatGoogleGenerativeAI"):
        from src.graphs.workflow import build_graph
        graph = build_graph()
        assert graph is not None


def test_graph_has_expected_nodes():
    """Verify the graph contains all four agent nodes."""
    with patch("src.agents.nodes.ChatGoogleGenerativeAI"):
        from src.graphs.workflow import build_graph
        graph = build_graph()
        # LangGraph compiled graphs expose their node names
        node_names = set(graph.get_graph().nodes.keys())
        assert "planner" in node_names
        assert "researcher" in node_names
        assert "synthesizer" in node_names
        assert "writer" in node_names
