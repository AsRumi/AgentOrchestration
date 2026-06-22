"""
Run endpoints — the main API surface.

Endpoints:
  POST /api/v1/runs          → Create a new agent run
  GET  /api/v1/runs          → List all runs
  GET  /api/v1/runs/{run_id} → Get status and result of a specific run
  DELETE /api/v1/runs/{run_id} → Cancel / delete a run
"""
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    RunSummary,
    RunDetail,
)
from src.db.models import AgentRun, RunStatus
from src.db.session import get_session
from src.workers.tasks import run_agent_workflow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/runs", tags=["Agent Runs"])


@router.post("", response_model=CreateRunResponse, status_code=202)
def create_run(
    request: CreateRunRequest,
    db: Session = Depends(get_session),
):
    """
    Start a new multi-agent research run.

    This endpoint returns IMMEDIATELY (HTTP 202 Accepted) with a run_id.
    The actual agent work happens asynchronously in a Celery worker.
    Poll GET /api/v1/runs/{run_id} to check status and retrieve the report.
    """
    # 1. Create database record
    run = AgentRun(topic=request.topic, status=RunStatus.PENDING)
    db.add(run)
    db.commit()
    db.refresh(run)

    logger.info(f"[API] Created run {run.id} for topic: {request.topic!r}")

    # 2. Dispatch to Celery worker
    # .delay() is non-blocking — it pushes a message to Redis and returns immediately
    run_agent_workflow.delay(str(run.id))

    return CreateRunResponse(
        run_id=run.id,
        status="pending",
        message="Run created. Poll the poll_url to check status.",
        poll_url=f"/api/v1/runs/{run.id}",
    )


@router.get("", response_model=List[RunSummary])
def list_runs(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_session),
):
    """List recent agent runs, newest first."""
    runs = (
        db.query(AgentRun)
        .order_by(AgentRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return runs


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_session)):
    """
    Get the status and result of a specific run.

    Status lifecycle: pending → running → complete | failed

    When status is 'complete', the `final_report` field contains the markdown report.
    """
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Parse research_plan from JSON string before Pydantic validation
    research_plan = None
    if run.research_plan:
        try:
            research_plan = json.loads(run.research_plan)
        except (json.JSONDecodeError, TypeError):
            research_plan = None

    return RunDetail(
        id=run.id,
        topic=run.topic,
        status=run.status,
        current_step=run.current_step,
        research_plan=research_plan,
        final_report=run.final_report,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.delete("/{run_id}", status_code=204)
def delete_run(run_id: str, db: Session = Depends(get_session)):
    """Delete a run record. Does not cancel an in-progress run."""
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    db.delete(run)
    db.commit()
