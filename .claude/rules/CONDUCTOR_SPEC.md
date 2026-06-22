# CONDUCTOR — Multi-Agent Orchestration System
### Complete Build Specification for Claude Code

---

## 0. Instructions for Claude Code

Implement this project exactly as specified. Every file listed in the directory structure should be created. Where full code is provided, use it exactly. Where described in prose, implement accordingly. The goal is a working, runnable project that doubles as an educational reference for anyone learning agent orchestration.

---

## 1. Project Overview

**Conductor** is a multi-agent orchestration system that uses specialized AI agents to perform deep research on any topic. A user submits a research topic via a REST API; the system orchestrates four specialized agents in sequence to produce a structured research report. Every run is executed asynchronously, its state is checkpointed for resilience, and results are persisted in a database.

**What it demonstrates:**
- Agent orchestration using a directed state graph (LangGraph)
- Specialized agents with distinct roles and tools
- Asynchronous task execution (Celery)
- State checkpointing for fault tolerance (Postgres)
- A production-style API layer (FastAPI)

**Use case:** User submits `"Explain how transformer attention mechanisms work"` → four agents collaborate → returns a polished markdown research report.

---

## 2. Tech Stack — Roles & Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                        CONDUCTOR STACK                          │
│                                                                 │
│  FastAPI         → REST API: accepts requests, returns results  │
│  Celery          → Async workers: run agent pipelines in BG     │
│  Redis           → Celery's message broker + results backend    │
│  LangGraph       → Agent workflow: defines the graph of agents  │
│  Gemini API      → LLM: powers each agent's reasoning           │
│  Postgres        → LangGraph checkpointer + run history         │
│  Python          → Language                                     │
└─────────────────────────────────────────────────────────────────┘
```

**Key pairings:**
- **Celery needs Redis** — Redis is the queue Celery pushes tasks into and workers pull from
- **LangGraph needs Postgres** — Postgres stores graph state snapshots so runs can be resumed if interrupted
- **FastAPI orchestrates Celery** — API receives HTTP request → creates a Celery task → returns immediately with a run ID
- **Celery workers run LangGraph** — The worker is where the actual agent graph executes

---

## 3. Architecture

### Request Lifecycle

```
User
  │
  │  POST /api/v1/runs  {"topic": "transformer attention"}
  ▼
FastAPI
  │  1. Saves run record to Postgres (status: "pending")
  │  2. Enqueues Celery task with run_id
  │  3. Returns run_id immediately (non-blocking)
  ▼
Redis (message broker)
  │  Task sits in queue
  ▼
Celery Worker
  │  Picks up task, fetches run from Postgres
  │  Updates status → "running"
  │  Executes LangGraph workflow
  ▼
LangGraph Workflow
  │  State is checkpointed to Postgres at every node
  │  Agents call Gemini API for reasoning
  │  Research tool calls DuckDuckGo for web data
  │
  │  ┌──────────┐    ┌────────────┐    ┌─────────────┐    ┌────────┐
  └─▶│  Planner │───▶│ Researcher │───▶│ Synthesizer │───▶│ Writer │
     └──────────┘    └──────┬─────┘    └─────────────┘    └────────┘
                            │  (loops until all research questions done)
                            └──────────────────┘
  │
  │  Final report saved to Postgres (status: "complete")
  ▼
User polls GET /api/v1/runs/{run_id} → receives full report
```

### Agent Roles

| Agent | Input | Output | Tools Used |
|---|---|---|---|
| **Planner** | Raw topic | List of 3–5 research questions | None (pure reasoning) |
| **Researcher** | One research question | Findings for that question | DuckDuckGo Search |
| **Synthesizer** | All research findings | Structured key insights | None |
| **Writer** | Synthesized insights | Final polished markdown report | None |

### LangGraph State Object

The `AgentState` TypedDict is passed between every node — this is the "shared memory" of the workflow.

```
AgentState {
    topic            → original user query
    run_id           → links back to database record
    research_plan    → list of questions (set by Planner)
    research_index   → which question we're on (used by loop logic)
    research_items   → accumulated findings (appended by each Researcher call)
    synthesis        → combined insights (set by Synthesizer)
    final_report     → markdown report (set by Writer)
    status           → human-readable progress string
    error            → error message if something failed
}
```

---

## 4. Directory Structure

Create exactly this structure:

```
conductor/
├── SPEC.md                          # This file (keep for reference)
├── README.md                        # Tutorial-style documentation
├── docker-compose.yml               # Postgres + Redis + API + Worker
├── Makefile                         # Common dev commands
├── requirements.txt
├── .env.example
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── config.py                    # Settings from environment variables
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py                # SQLAlchemy ORM models
│   │   ├── session.py               # Database session factory
│   │   └── init_db.py               # Table creation script
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py                 # AgentState TypedDict definition
│   │   ├── tools.py                 # Search + utility tools
│   │   └── nodes.py                 # Each agent as a LangGraph node function
│   │
│   ├── graphs/
│   │   ├── __init__.py
│   │   └── workflow.py              # LangGraph StateGraph assembly
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Celery application instance
│   │   └── tasks.py                 # Celery task definitions
│   │
│   └── api/
│       ├── __init__.py
│       ├── main.py                  # FastAPI application + startup
│       ├── schemas.py               # Pydantic request/response models
│       └── routes/
│           ├── __init__.py
│           ├── runs.py              # /runs endpoints
│           └── health.py            # /health endpoint
│
├── docs/
│   ├── concepts.md                  # Deep dive: agents, graphs, state
│   └── api.md                       # API usage examples
│
└── tests/
    ├── __init__.py
    ├── test_nodes.py
    ├── test_workflow.py
    └── test_api.py
```

---

## 5. File Implementations

### `requirements.txt`

```
# Core
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.0
pydantic-settings==2.5.2
python-dotenv==1.0.1

# LangGraph + LangChain
langgraph==0.2.38
langchain==0.3.7
langchain-core==0.3.15
langchain-google-genai==2.0.4
langchain-community==0.3.7
langgraph-checkpoint-postgres==2.0.4

# Gemini
google-generativeai==0.8.3

# Search tool
duckduckgo-search==6.3.7

# Database
sqlalchemy==2.0.36
psycopg[binary,pool]==3.2.3
alembic==1.13.3

# Async / task queue
celery==5.4.0
redis==5.1.1

# HTTP client
httpx==0.27.2

# Utilities
python-json-logger==2.0.7
tenacity==9.0.0
```

---

### `.env.example`

```bash
# Copy this to .env and fill in your values

# Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Postgres
POSTGRES_USER=conductor
POSTGRES_PASSWORD=conductor_pass
POSTGRES_DB=conductor_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# App
APP_ENV=development
LOG_LEVEL=INFO
```

---

### `.gitignore`

```
.env
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.venv/
venv/
*.egg-info/
dist/
build/
.DS_Store
*.log
```

---

### `docker-compose.yml`

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-conductor}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-conductor_pass}
      POSTGRES_DB: ${POSTGRES_DB:-conductor_db}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U conductor"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build: .
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      POSTGRES_HOST: postgres
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - .:/app

  worker:
    build: .
    command: celery -A src.workers.celery_app.celery_app worker --loglevel=info --concurrency=4
    env_file: .env
    environment:
      POSTGRES_HOST: postgres
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - .:/app

  flower:
    build: .
    command: celery -A src.workers.celery_app.celery_app flower --port=5555
    ports:
      - "5555:5555"
    env_file: .env
    environment:
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis
      - worker

volumes:
  postgres_data:
```

---

### `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
```

---

### `Makefile`

```makefile
.PHONY: help up down api worker init-db logs test

help:
	@echo "Conductor — Multi-Agent Orchestration System"
	@echo ""
	@echo "  make up          Start all services (Docker)"
	@echo "  make down        Stop all services"
	@echo "  make init-db     Create database tables"
	@echo "  make api         Run API server locally"
	@echo "  make worker      Run Celery worker locally"
	@echo "  make logs        Tail logs from all containers"
	@echo "  make test        Run tests"

up:
	docker compose up --build -d
	@echo "API running at http://localhost:8000"
	@echo "Flower (task monitor) at http://localhost:5555"
	@echo "API docs at http://localhost:8000/docs"

down:
	docker compose down

init-db:
	python -m src.db.init_db

api:
	uvicorn src.api.main:app --reload --port 8000

worker:
	celery -A src.workers.celery_app.celery_app worker --loglevel=info

logs:
	docker compose logs -f

test:
	pytest tests/ -v
```

---

### `src/__init__.py`

```python
# Conductor: Multi-Agent Orchestration System
```

---

### `src/config.py`

```python
"""
Configuration module.

Reads all settings from environment variables (or .env file).
Using pydantic-settings means every config value is type-checked at startup.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Gemini
    GEMINI_API_KEY: str

    # Postgres
    POSTGRES_USER: str = "conductor"
    POSTGRES_PASSWORD: str = "conductor_pass"
    POSTGRES_DB: str = "conductor_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def POSTGRES_URL(self) -> str:
        """SQLAlchemy-compatible connection string."""
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def POSTGRES_URL_SYNC(self) -> str:
        """psycopg (v3) sync DSN for LangGraph checkpointer."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance. Call this everywhere instead of instantiating directly."""
    return Settings()


settings = get_settings()
```

---

### `src/db/__init__.py`

```python
```

---

### `src/db/models.py`

```python
"""
Database models.

We store a record for every agent run so the API can report status and results.
The LangGraph checkpointer creates its own tables automatically — we don't manage those.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


class RunStatus(str, enum.Enum):
    PENDING = "pending"       # Created, waiting for worker
    RUNNING = "running"       # Worker is actively executing
    COMPLETE = "complete"     # Finished successfully
    FAILED = "failed"         # Encountered an unrecoverable error


class AgentRun(Base):
    """
    Represents one execution of the agent workflow.
    
    Lifecycle: pending → running → complete | failed
    """
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(String(1000), nullable=False)
    status = Column(SAEnum(RunStatus), default=RunStatus.PENDING, nullable=False)

    # Progress tracking
    current_step = Column(String(100), nullable=True)   # e.g. "researcher_2_of_4"
    research_plan = Column(Text, nullable=True)          # JSON array of questions

    # Final outputs
    final_report = Column(Text, nullable=True)           # Markdown report
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<AgentRun id={self.id} status={self.status} topic={self.topic[:50]!r}>"
```

---

### `src/db/session.py`

```python
"""
Database session factory.

Uses SQLAlchemy 2.0 with a connection pool.
Import `get_session` as a FastAPI dependency, or `SessionLocal` for direct use in workers.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.config import settings

engine = create_engine(
    settings.POSTGRES_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # Verify connection health before use
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    """
    FastAPI dependency that yields a database session and ensures it's closed after the request.
    
    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_session)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

### `src/db/init_db.py`

```python
"""
Database initialization script.

Run this once before starting the application:
    python -m src.db.init_db

This creates all SQLAlchemy-managed tables. LangGraph will create its own
checkpointer tables the first time a workflow runs.
"""
from src.db.models import Base
from src.db.session import engine
from src.config import settings


def init_db():
    print(f"Connecting to: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully.")
    print("  Tables: agent_runs")
    print("  Note: LangGraph checkpointer tables will be created on first workflow run.")


if __name__ == "__main__":
    init_db()
```

---

### `src/agents/__init__.py`

```python
```

---

### `src/agents/state.py`

```python
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
```

---

### `src/agents/tools.py`

```python
"""
Tools available to agents.

A "tool" in LangGraph/LangChain is a Python function the agent can call
to interact with the outside world — searching the web, reading files,
calling APIs, etc.

Currently implemented:
  - web_search: DuckDuckGo search (free, no API key required)
  - fetch_url: Retrieve page content from a URL

To add a new tool, define a function decorated with @tool and add it
to the RESEARCHER_TOOLS list.
"""
from langchain_core.tools import tool
from duckduckgo_search import DDGS
import httpx
import re


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo and return a formatted summary of results.
    
    Args:
        query: The search query string
        max_results: Number of results to return (default 5)
    
    Returns:
        Formatted string with titles, URLs, and snippets
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return f"No results found for: {query}"
        
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"    URL: {r.get('href', 'No URL')}\n"
                f"    {r.get('body', 'No description')}"
            )
        
        return "\n\n".join(formatted)
    
    except Exception as e:
        return f"Search failed: {str(e)}"


@tool
def fetch_url(url: str) -> str:
    """
    Fetch the text content of a webpage.
    
    Args:
        url: The URL to fetch
    
    Returns:
        Cleaned text content of the page (first 3000 chars)
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ConductorBot/1.0)"}
        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        response.raise_for_status()
        
        # Basic HTML stripping
        text = re.sub(r'<[^>]+>', ' ', response.text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text[:3000] + ("..." if len(text) > 3000 else "")
    
    except Exception as e:
        return f"Failed to fetch {url}: {str(e)}"


# The tools available to the Researcher agent
RESEARCHER_TOOLS = [web_search, fetch_url]
```

---

### `src/agents/nodes.py`

```python
"""
Agent nodes — the individual agents in the workflow.

Each agent is a plain Python function that:
  1. Receives the current AgentState
  2. Does its work (calls LLM, uses tools, etc.)
  3. Returns a dict with ONLY the fields it wants to update in state

LangGraph merges the returned dict into the existing state.
Returning a partial dict (not the full state) is intentional and correct.

Agents defined here:
  - planner_node       → Creates the research plan
  - researcher_node    → Researches one question (called in a loop)
  - synthesizer_node   → Synthesizes all findings
  - writer_node        → Writes the final report
  - should_continue_research → Conditional edge logic (not a node)
"""
import json
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from src.agents.state import AgentState, ResearchItem
from src.agents.tools import RESEARCHER_TOOLS, web_search
from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM Factory
# ---------------------------------------------------------------------------

def get_llm(temperature: float = 0.3) -> ChatGoogleGenerativeAI:
    """
    Returns a Gemini LLM instance.
    
    We use gemini-2.0-flash for all agents — it's fast and capable.
    Temperature 0.3 gives focused, consistent outputs (lower = more deterministic).
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Planner Node
# ---------------------------------------------------------------------------

def planner_node(state: AgentState) -> dict:
    """
    PLANNER AGENT
    
    Responsibility: Take the user's topic and decompose it into 3–5
    specific, answerable research questions.
    
    Why: A single broad query produces shallow results. Breaking it into
    targeted sub-questions lets the Researcher go deep on each aspect.
    
    Output: Updates `research_plan` and `research_index` in state.
    """
    logger.info(f"[Planner] Creating research plan for: {state['topic']}")
    llm = get_llm(temperature=0.2)

    system_prompt = """You are a research strategist. Your job is to decompose a broad topic 
into 3 to 5 specific, focused research questions that together provide comprehensive coverage.

Rules:
- Each question must be answerable with web search
- Questions should cover different aspects (definition, mechanics, examples, applications, limitations)
- Be specific, not vague

IMPORTANT: Respond with ONLY a valid JSON array of strings. No preamble, no explanation, no markdown.
Example output: ["What is X?", "How does X work mechanically?", "What are real-world applications of X?"]"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Decompose this research topic: {state['topic']}")
    ])

    try:
        # Strip any accidental markdown code fences
        content = response.content.strip().strip("```json").strip("```").strip()
        plan = json.loads(content)
        if not isinstance(plan, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"[Planner] Failed to parse JSON, using fallback. Error: {e}")
        # Fallback: create basic questions from the topic
        plan = [
            f"What is {state['topic']} and how does it work?",
            f"What are the key components of {state['topic']}?",
            f"What are practical applications and real-world examples of {state['topic']}?",
        ]

    logger.info(f"[Planner] Created {len(plan)} research questions")
    return {
        "research_plan": plan,
        "research_index": 0,
        "status": f"planning_complete_{len(plan)}_questions",
    }


# ---------------------------------------------------------------------------
# Researcher Node
# ---------------------------------------------------------------------------

def researcher_node(state: AgentState) -> dict:
    """
    RESEARCHER AGENT
    
    Responsibility: Research ONE question from the plan. This node is called
    in a loop (once per question) by the conditional edge logic below.
    
    How it works:
    1. Gets the current question (research_plan[research_index])
    2. Searches the web using the DuckDuckGo tool
    3. Uses the LLM to extract and structure the key findings
    4. Appends a ResearchItem to research_items
    5. Increments research_index so the next call gets the next question
    
    Output: Appends to `research_items`, increments `research_index`.
    """
    current_index = state["research_index"]
    total = len(state["research_plan"])
    current_query = state["research_plan"][current_index]

    logger.info(f"[Researcher] Question {current_index + 1}/{total}: {current_query}")

    # Step 1: Search the web
    search_results = web_search.invoke({"query": current_query, "max_results": 5})

    # Step 2: LLM extracts structured findings from raw search results
    llm = get_llm(temperature=0.2)
    system_prompt = """You are a research analyst. Given a research question and raw web search results,
extract the most relevant, factual information.

Your output should:
- Directly answer the research question
- Include specific facts, numbers, or examples where available
- Be 200–400 words
- Be in clear prose (not bullet points)
- Focus on accuracy, not comprehensiveness"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Research Question: {current_query}\n\nSearch Results:\n{search_results}")
    ])

    research_item: ResearchItem = {
        "query": current_query,
        "findings": response.content,
    }

    logger.info(f"[Researcher] Completed question {current_index + 1}/{total}")
    return {
        "research_items": [research_item],   # operator.add will APPEND this
        "research_index": current_index + 1,
        "status": f"researched_{current_index + 1}_of_{total}",
    }


# ---------------------------------------------------------------------------
# Conditional Edge Logic
# ---------------------------------------------------------------------------

def should_continue_research(state: AgentState) -> str:
    """
    This is NOT a node — it's the conditional routing logic for the loop.
    
    LangGraph calls this function after each Researcher call to decide
    what happens next:
      - If there are more questions: route back to researcher_node
      - If all questions done: route to synthesizer_node
    
    The returned string must match keys in `add_conditional_edges(...)`.
    """
    if state["research_index"] < len(state["research_plan"]):
        return "continue_research"
    return "synthesize"


# ---------------------------------------------------------------------------
# Synthesizer Node
# ---------------------------------------------------------------------------

def synthesizer_node(state: AgentState) -> dict:
    """
    SYNTHESIZER AGENT
    
    Responsibility: Take all the individual research findings and produce
    a cohesive synthesis — identifying themes, patterns, and key insights.
    
    Why a separate synthesis step: Raw research findings are a pile of facts.
    The synthesizer connects them, finds patterns, and resolves contradictions
    before the writer turns them into prose.
    
    Output: Sets `synthesis` in state.
    """
    logger.info(f"[Synthesizer] Synthesizing {len(state['research_items'])} research items")
    llm = get_llm(temperature=0.4)

    # Format all research items for the LLM
    research_text = "\n\n---\n\n".join([
        f"**Research Question:** {item['query']}\n\n**Findings:** {item['findings']}"
        for item in state["research_items"]
    ])

    system_prompt = """You are a research synthesizer. Given multiple research findings on a topic,
produce a structured synthesis that:

1. Identifies the 3–5 most important themes that cut across the findings
2. Highlights the most significant insights and facts
3. Notes any tensions, contradictions, or open questions
4. Groups related information together logically

Write in clear, organized prose. Use headers for each theme. Be analytical, not just descriptive.
Length: 400–600 words."""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Topic: {state['topic']}\n\nResearch Findings:\n\n{research_text}")
    ])

    logger.info("[Synthesizer] Synthesis complete")
    return {
        "synthesis": response.content,
        "status": "synthesis_complete",
    }


# ---------------------------------------------------------------------------
# Writer Node
# ---------------------------------------------------------------------------

def writer_node(state: AgentState) -> dict:
    """
    WRITER AGENT
    
    Responsibility: Turn the synthesis into a polished, professional
    research report that a reader would find genuinely useful.
    
    Why a separate writer: The synthesizer is analytical but terse. The writer's
    job is to make the output readable — adding context, transitions, and structure.
    
    Output: Sets `final_report` in state (markdown formatted).
    """
    logger.info("[Writer] Writing final report")
    llm = get_llm(temperature=0.5)

    system_prompt = """You are a professional technical writer. Given a research synthesis,
produce a well-structured research report in Markdown.

Required structure:
# [Title based on topic]

## Executive Summary
2–3 sentence overview of the key findings.

## Background
Brief context for the topic.

## Key Findings
### [Theme 1]
### [Theme 2]
### [Theme 3]
(etc.)

## Analysis & Implications
What do these findings mean? Why does it matter?

## Conclusion
Wrap up with the most important takeaways.

---
*Report generated by Conductor Multi-Agent System*

Style: Clear, professional, accessible to a technical audience. Use concrete examples.
Length: 600–900 words."""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Topic: {state['topic']}\n\nSynthesis to expand into a report:\n\n{state['synthesis']}"
        )
    ])

    logger.info("[Writer] Report complete")
    return {
        "final_report": response.content,
        "status": "complete",
    }
```

---

### `src/graphs/__init__.py`

```python
```

---

### `src/graphs/workflow.py`

```python
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
    conn = psycopg.connect(settings.POSTGRES_URL_SYNC)
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
```

---

### `src/workers/__init__.py`

```python
```

---

### `src/workers/celery_app.py`

```python
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
```

---

### `src/workers/tasks.py`

```python
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
```

---

### `src/api/__init__.py`

```python
```

---

### `src/api/schemas.py`

```python
"""
Pydantic schemas for API request and response validation.

FastAPI uses these to:
  - Validate incoming request bodies
  - Serialize outgoing responses
  - Generate the OpenAPI (Swagger) documentation automatically
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


# ---------------------------------------------------------------------------
# Request schemas (what the client sends)
# ---------------------------------------------------------------------------

class CreateRunRequest(BaseModel):
    """Request body for POST /api/v1/runs"""
    topic: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="The research topic or question to investigate",
        example="How do transformer attention mechanisms work in large language models?"
    )


# ---------------------------------------------------------------------------
# Response schemas (what we send back)
# ---------------------------------------------------------------------------

class RunSummary(BaseModel):
    """Lightweight run info — returned in list endpoints."""
    id: uuid.UUID
    topic: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True   # Allow creation from SQLAlchemy model instances


class RunDetail(BaseModel):
    """Full run info including the report — returned in single-run endpoints."""
    id: uuid.UUID
    topic: str
    status: str
    current_step: Optional[str] = None
    research_plan: Optional[List[str]] = None
    final_report: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CreateRunResponse(BaseModel):
    """Returned immediately after POST /api/v1/runs — before the run completes."""
    run_id: uuid.UUID
    status: str
    message: str
    poll_url: str


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
```

---

### `src/api/routes/__init__.py`

```python
```

---

### `src/api/routes/health.py`

```python
from fastapi import APIRouter
from src.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Check that the API is running."""
    return HealthResponse(status="ok")
```

---

### `src/api/routes/runs.py`

```python
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
    
    # Parse research_plan from JSON string back to list for the response
    result = RunDetail.model_validate(run)
    if run.research_plan:
        try:
            result.research_plan = json.loads(run.research_plan)
        except (json.JSONDecodeError, TypeError):
            result.research_plan = None
    
    return result


@router.delete("/{run_id}", status_code=204)
def delete_run(run_id: str, db: Session = Depends(get_session)):
    """Delete a run record. Does not cancel an in-progress run."""
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    db.delete(run)
    db.commit()
```

---

### `src/api/main.py`

```python
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
```

---

### `docs/concepts.md`

Create this file with detailed explanations of:
1. **What is an AI Agent?** — An LLM + tools + memory that can take actions
2. **What is Agent Orchestration?** — Coordinating multiple agents to complete complex tasks
3. **What is a State Graph?** — A directed graph where nodes are computation steps and edges define flow, sharing a common state object
4. **What is State in LangGraph?** — A TypedDict passed through every node; each node reads it and returns partial updates
5. **What is Checkpointing?** — Snapshotting state after each node so runs are resumable and inspectable
6. **Why async execution?** — LLM calls can take 30+ seconds; workers prevent the API from blocking

---

### `tests/test_nodes.py`

```python
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
```

---

### `tests/test_api.py`

```python
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
```

---

### `tests/__init__.py`

```python
```

---

## 6. README.md to Create

The README must be written in a **tutorial style** — someone with no prior knowledge of agent orchestration should be able to read it and understand the system. Use the structure below exactly.

---

```markdown
# Conductor 🎼

> A multi-agent orchestration system that coordinates specialized AI agents to perform deep research on any topic.

Built with **LangGraph**, **Gemini**, **FastAPI**, **Celery**, **Redis**, and **Postgres** — this project is designed to be readable as a reference implementation for anyone learning agent orchestration.

---

## What is Agent Orchestration?

An **AI agent** is an LLM that can use tools (web search, code execution, APIs) and take actions based on what it observes. A single agent is powerful. Multiple **specialized** agents that collaborate are more powerful — but only if something coordinates them.

**Agent orchestration** is the system that:
- Decides which agent runs when
- Passes information between agents
- Handles retries, failures, and state
- Makes complex multi-step pipelines reliable

This project implements orchestration using a **directed state graph**: each agent is a node, and edges define the flow of work between them.

---

## System Architecture

```
User Request (topic)
       │
       ▼
  ┌─────────┐
  │ FastAPI │  ← HTTP API (non-blocking, returns run_id immediately)
  └────┬────┘
       │ enqueue task
       ▼
  ┌──────────┐
  │  Redis   │  ← Message broker (Celery pushes/pulls tasks from here)
  └────┬─────┘
       │ worker picks up task
       ▼
  ┌────────────────┐
  │ Celery Worker  │  ← Background process that executes the workflow
  └───────┬────────┘
          │ runs graph
          ▼
  ┌───────────────────────────────────────────────────────┐
  │                  LangGraph Workflow                   │
  │                                                       │
  │  ┌─────────┐   ┌────────────┐   ┌─────────────┐     │
  │  │ Planner │──▶│ Researcher │──▶│ Synthesizer │──▶  │
  │  └─────────┘   └──────┬─────┘   └─────────────┘     │
  │                       │  (loops until done)           │
  │                       └──────────┘                    │
  │                                          ┌────────┐   │
  │                                       ──▶│ Writer │   │
  │                                          └────────┘   │
  └───────────────────────────────────────────────────────┘
          │ saves state
          ▼
  ┌──────────┐
  │ Postgres │  ← Stores run results + LangGraph checkpoints
  └──────────┘
```

---

## The Agents

| Agent | Role | Tools |
|---|---|---|
| **Planner** | Decomposes your topic into 3–5 research questions | None |
| **Researcher** | Searches the web for each question | DuckDuckGo Search |
| **Synthesizer** | Identifies themes and patterns across findings | None |
| **Writer** | Produces a structured markdown report | None |

---

## How LangGraph Works

LangGraph models the workflow as a **directed graph**:

```python
# Each node is a function: (state) -> partial_state_update
workflow.add_node("planner", planner_node)
workflow.add_node("researcher", researcher_node)

# Edges define the flow
workflow.add_edge("planner", "researcher")

# Conditional edges create loops
workflow.add_conditional_edges(
    "researcher",
    should_continue_research,   # returns "continue_research" or "synthesize"
    {"continue_research": "researcher", "synthesize": "synthesizer"}
)
```

The **state** (`AgentState`) is a TypedDict shared across all nodes. Each node reads what it needs and writes back its outputs. State is checkpointed to Postgres after every node — so if the worker crashes, the run resumes from where it left off.

---

## What Each Technology Does

| Technology | Exact Role |
|---|---|
| **LangGraph** | Defines and executes the agent workflow graph |
| **Gemini API** | Powers each agent's reasoning and language understanding |
| **FastAPI** | REST API layer — accepts requests, returns run IDs, serves results |
| **Celery** | Async task queue — runs agent pipelines in background workers |
| **Redis** | Celery's message broker — the queue that workers pull tasks from |
| **Postgres** | Stores run records + LangGraph state checkpoints |

---

## Quickstart

### Prerequisites
- Docker + Docker Compose
- A Gemini API key ([get one free at ai.google.dev](https://ai.google.dev))

### 1. Clone and configure

```bash
git clone https://github.com/your-username/conductor.git
cd conductor
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
```

### 2. Start everything

```bash
make up
```

This starts: Postgres, Redis, the FastAPI server, a Celery worker, and Flower (task monitor).

### 3. Submit a research topic

```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{"topic": "How do transformer attention mechanisms work in large language models?"}'
```

Response:
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "poll_url": "/api/v1/runs/550e8400-e29b-41d4-a716-446655440000"
}
```

### 4. Poll for results

```bash
curl http://localhost:8000/api/v1/runs/550e8400-e29b-41d4-a716-446655440000
```

When `status` is `complete`, the `final_report` field contains your research report.

### 5. Explore the system

- **API docs (Swagger UI):** http://localhost:8000/docs
- **Task monitor (Flower):** http://localhost:5555

---

## Project Structure

```
conductor/
├── src/
│   ├── agents/
│   │   ├── state.py        ← AgentState TypedDict (shared workflow memory)
│   │   ├── tools.py        ← Web search and utility tools
│   │   └── nodes.py        ← Each agent as a node function
│   ├── graphs/
│   │   └── workflow.py     ← LangGraph assembly (nodes + edges + checkpointer)
│   ├── workers/
│   │   ├── celery_app.py   ← Celery configuration
│   │   └── tasks.py        ← Background task that runs the workflow
│   ├── api/
│   │   ├── main.py         ← FastAPI app
│   │   └── routes/runs.py  ← REST endpoints
│   └── db/
│       └── models.py       ← SQLAlchemy run record model
├── docs/concepts.md        ← Deep dive on orchestration concepts
└── docker-compose.yml
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Extending the System

**Add a new agent:**
1. Define a new node function in `src/agents/nodes.py`
2. Add fields to `AgentState` in `src/agents/state.py`
3. Register the node and connect it in `src/graphs/workflow.py`

**Add a new tool:**
1. Define a `@tool` function in `src/agents/tools.py`
2. Bind it to the relevant agent in `nodes.py`

**Add a new API endpoint:**
1. Add a route function in `src/api/routes/runs.py`

---

## License

MIT
```

---

## 7. Final Notes for Claude Code

1. All Python files must have `PYTHONPATH=/app` set for imports to resolve correctly (handled in Dockerfile and docker-compose).
2. The `src/db/init_db.py` script is called automatically on API startup via the `lifespan` context manager in `main.py`, so manual invocation is only needed for local (non-Docker) setup.
3. The LangGraph checkpointer tables are created by `checkpointer.setup()` on the first workflow run — not by `init_db.py`. This is intentional.
4. Every node function returns a **partial dict**, not the full `AgentState`. LangGraph merges the partial update. This is correct and intentional.
5. The `research_items` field uses `Annotated[List[ResearchItem], operator.add]` — this tells LangGraph to append new items rather than replace the list. This is what enables the Researcher loop to accumulate findings.
6. `make up` is the single command to run everything. Ensure the Makefile and docker-compose work together correctly.
7. Create the `docs/concepts.md` with meaningful content — not placeholder text. It should genuinely explain agent orchestration concepts as referenced in the README.
