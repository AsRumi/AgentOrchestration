# Conductor

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

There are two ways to run Conductor: with **Docker** (one command, everything local) or **without Docker** using cloud-hosted Postgres and Redis (no Docker required).

---

## Option A: Docker Setup

### Prerequisites
- Docker + Docker Compose
- A Gemini API key (get one free at ai.google.dev)

### 1. Clone and configure

```bash
git clone https://github.com/your-username/conductor.git
cd conductor
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
```

### 2. Start everything

```bash
docker compose up --build -d
```

This starts: Postgres, Redis, the FastAPI server, a Celery worker, and Flower (task monitor).

> On Windows, `make` is not available by default. Use `docker compose up --build -d` directly instead of `make up`.

---

## Option B: No Docker — Cloud Postgres + Redis

Run the API and worker locally, with free cloud-hosted databases. No Docker required.

### Prerequisites
- Python 3.12+ with a virtual environment
- A Gemini API key (get one free at ai.google.dev)

### 1. Set up cloud Postgres (Neon)

1. Go to [neon.tech](https://neon.tech) and sign up for a free account
2. Create a new project
3. From the project dashboard, go to **Connection Details**
4. Copy the connection string — it looks like:
   ```
   postgresql://username:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
5. Break it into parts for your `.env`:
   ```bash
   POSTGRES_USER=username
   POSTGRES_PASSWORD=password
   POSTGRES_HOST=ep-xxx.us-east-2.aws.neon.tech
   POSTGRES_PORT=5432
   POSTGRES_DB=neondb
   ```

### 2. Set up cloud Redis (Upstash)

1. Go to [upstash.com](https://upstash.com) and sign up for a free account
2. Click **Create Database**, choose a name, select **Global** or the region closest to you
3. From the database dashboard, click the **TCP** tab under **Connect**
4. Copy the token shown next to `UPSTASH_REDIS_REST_TOKEN`
5. Build your Redis URL using this format:
   ```
   rediss://default:YOUR_TOKEN@your-db-name.upstash.io:6380
   ```
   Note the `rediss://` (double `s`) — this enables TLS, which Upstash requires.
6. Add to your `.env`:
   ```bash
   REDIS_URL=rediss://default:YOUR_TOKEN@your-db-name.upstash.io:6380
   ```

### 3. Configure your `.env`

Copy the example file and fill in all values:

```bash
copy .env.example .env
```

Your completed `.env` should look like:

```bash
GEMINI_API_KEY=your_gemini_api_key_here

POSTGRES_USER=your_neon_user
POSTGRES_PASSWORD=your_neon_password
POSTGRES_HOST=ep-xxx.us-east-2.aws.neon.tech
POSTGRES_PORT=5432
POSTGRES_DB=neondb

REDIS_URL=rediss://default:your_upstash_token@your-db-name.upstash.io:6380

APP_ENV=development
LOG_LEVEL=INFO
```

### 4. Install dependencies

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Initialize the database

This creates the `agent_runs` table in your Neon Postgres database:

```powershell
python -m src.db.init_db
```

You should see:
```
Connecting to: ep-xxx.us-east-2.aws.neon.tech:5432/neondb
✓ Database tables created successfully.
```

### 6. Start the API server

Open a terminal, activate your virtual environment, and run:

```powershell
uvicorn src.api.main:app --reload --port 8000
```

The API is now running at http://localhost:8000.

### 7. Start the Celery worker

Open a **second terminal**, activate your virtual environment, and run:

```powershell
celery -A src.workers.celery_app.celery_app worker --loglevel=info --pool=solo
```

> `--pool=solo` is required on Windows. Without it, Celery's default multiprocessing pool fails on Windows.

---

## Submitting a Research Topic

With the API server and Celery worker both running, submit a topic:

**PowerShell:**
```powershell
curl -X POST http://localhost:8000/api/v1/runs `
  -H "Content-Type: application/json" `
  -d '{"topic": "How do transformer attention mechanisms work in large language models?"}'
```

**bash / Mac / Linux:**
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

## Polling for Results

```powershell
curl http://localhost:8000/api/v1/runs/550e8400-e29b-41d4-a716-446655440000
```

Poll this endpoint every few seconds. The status moves through `pending → running → complete`. When `status` is `complete`, the `final_report` field contains your full research report in Markdown.

## Explore the API

- **API docs (Swagger UI):** http://localhost:8000/docs
- **Task monitor (Flower, Docker only):** http://localhost:5555

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
