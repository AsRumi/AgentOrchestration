"""
FastAPI application entry point.

This module creates the FastAPI app, registers routers, and handles startup/shutdown.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import runs, health
from src.db.init_db import init_db
from src.config import settings

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.

    On startup: Initialize database tables.
    On shutdown: (nothing currently — connections are pooled)
    """
    logger.info("Conductor API starting up...")
    init_db()
    logger.info("Database ready.")
    yield
    logger.info("Conductor API shutting down.")


app = FastAPI(
    title="Conductor — Multi-Agent Orchestration API",
    description="""
A multi-agent research system powered by LangGraph and Gemini.

## How to use

1. **POST /api/v1/runs** with a `topic` → get back a `run_id`
2. **GET /api/v1/runs/{run_id}** repeatedly until `status` is `complete`
3. The `final_report` field contains your research report in Markdown

## Architecture

Requests are handled asynchronously:
- FastAPI accepts the request and returns immediately
- Celery workers execute the LangGraph agent pipeline in the background
- Results are stored in Postgres and retrieved via polling
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Allow all origins in development — tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": "Conductor",
        "description": "Multi-Agent Orchestration System",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
