"""
Celery Tasks — the bridge between FastAPI and LangGraph.

This module defines the Celery tasks that run in background workers.
When FastAPI wants to start an agent run, it calls `run_agent_workflow.delay(run_id)`.

The task:
  1. Loads the run record from Postgres
  2. Builds the LangGraph workflow (with checkpointer)
  3. Executes the graph
  4. Updates the run record with status + result
"""
import logging
from datetime import datetime
from celery import Task
from src.workers.celery_app import celery_app
from src.db.session import SessionLocal
from src.db.models import AgentRun, RunStatus
from src.graphs.workflow import build_graph_with_checkpointer
from src.agents.state import AgentState

logger = logging.getLogger(__name__)


class BaseTaskWithRetry(Task):
    """Base task class with automatic retry on transient failures."""
    abstract = True
    max_retries = 3
    default_retry_delay = 5  # seconds


@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="conductor.run_agent_workflow",
)
def run_agent_workflow(self, run_id: str) -> dict:
    """
    Execute the multi-agent workflow for a given run.

    Args:
        run_id: UUID of the AgentRun record in Postgres

    Returns:
        dict with status and summary

    This is the main background task. It's called by FastAPI and
    executes entirely in the Celery worker process.
    """
    db = SessionLocal()
    conn = None

    try:
        # 1. Load the run record
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found in database")

        logger.info(f"[Task] Starting run {run_id}: {run.topic!r}")

        # 2. Mark as running
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        db.commit()

        # 3. Build the LangGraph workflow with Postgres checkpointer
        graph, conn = build_graph_with_checkpointer()

        # 4. Define the initial state
        initial_state: AgentState = {
            "topic": run.topic,
            "run_id": str(run_id),
            "research_plan": [],
            "research_index": 0,
            "research_items": [],
            "synthesis": "",
            "final_report": "",
            "status": "starting",
            "error": None,
        }

        # 5. LangGraph config — thread_id isolates this run's checkpoints
        # Every run gets its own checkpoint history in Postgres
        config = {"configurable": {"thread_id": str(run_id)}}

        # 6. Execute the graph
        # .invoke() runs the graph to completion, returning the final state
        logger.info(f"[Task] Invoking graph for run {run_id}")
        final_state = graph.invoke(initial_state, config=config)

        # 7. Save results to Postgres
        import json
        run.status = RunStatus.COMPLETE
        run.final_report = final_state.get("final_report", "")
        run.research_plan = json.dumps(final_state.get("research_plan", []))
        run.current_step = "complete"
        run.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"[Task] Run {run_id} completed successfully")
        return {"status": "complete", "run_id": str(run_id)}

    except Exception as exc:
        logger.error(f"[Task] Run {run_id} failed: {exc}", exc_info=True)

        # Update run status to failed
        try:
            if run:
                run.status = RunStatus.FAILED
                run.error_message = str(exc)
                run.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_exc:
            logger.error(f"[Task] Failed to update run status: {db_exc}")

        # Retry on transient errors (connection issues, rate limits)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10 * (self.request.retries + 1))

        raise

    finally:
        db.close()
        if conn:
            conn.close()
