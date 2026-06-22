"""
Celery Application Instance.

Celery is a distributed task queue. It lets FastAPI hand off long-running
work (like running a multi-agent pipeline) to background workers, so the
API can respond immediately without waiting.

How it works:
  1. FastAPI calls .delay() on a Celery task → pushes a message to Redis
  2. A Celery worker process (running separately) picks up the message
  3. Worker executes the task function
  4. Result is stored back in Redis (or Postgres)
  5. FastAPI polls Postgres for the result

Redis plays two roles here:
  - BROKER: The message queue (tasks go in here)
  - RESULT BACKEND: Where Celery stores task completion state
"""
from celery import Celery
from src.config import settings

celery_app = Celery(
    "conductor",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.workers.tasks"],
)

celery_app.conf.update(
    # Serialize tasks as JSON (readable, debuggable)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # If a worker is killed mid-task, re-queue the task once
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # Don't pre-fetch; each worker handles one task at a time

    # Task timeout: 10 minutes max per run
    task_time_limit=600,
    task_soft_time_limit=540,

    # Keep results for 24 hours
    result_expires=86400,
)
