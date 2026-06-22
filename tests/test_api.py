"""Integration tests for the FastAPI routes."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@patch("src.api.routes.runs.run_agent_workflow")
def test_create_run(mock_task):
    mock_task.delay = MagicMock(return_value=MagicMock(id="celery-task-id"))

    response = client.post("/api/v1/runs", json={"topic": "How does quantum computing work at the hardware level?"})
    assert response.status_code == 202
    assert "run_id" in response.json()
    assert response.json()["status"] == "pending"


def test_create_run_topic_too_short():
    response = client.post("/api/v1/runs", json={"topic": "short"})
    assert response.status_code == 422


def test_get_nonexistent_run():
    response = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
