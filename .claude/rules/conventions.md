# Conductor — Build Log, Bugs, and Conventions

This file documents every bug encountered, every fix applied, and every convention established while building and running the Conductor multi-agent orchestration system. A fresh Claude Code session reading this file should be able to reproduce the working state instantly.

---

## Project Summary

Conductor is a multi-agent research system. A user POSTs a topic → FastAPI creates a DB record and enqueues a Celery task → a Celery worker runs a LangGraph graph (Planner → Researcher loop → Synthesizer → Writer) → results are saved to Postgres → user polls GET /runs/{id} for the report.

**Stack:** FastAPI · Celery · Redis · LangGraph · Gemini API · Postgres · SQLAlchemy · psycopg v3 · Pydantic v2

**Running environment:** Windows 10, no Docker, using:
- **Neon** (cloud-hosted Postgres) for the database
- **Upstash** (cloud-hosted Redis) for the Celery broker

---

## Directory

```
conductor/
├── src/
│   ├── config.py
│   ├── db/         models.py · session.py · init_db.py
│   ├── agents/     state.py · tools.py · nodes.py
│   ├── graphs/     workflow.py
│   ├── workers/    celery_app.py · tasks.py
│   └── api/        main.py · schemas.py · routes/runs.py · routes/health.py
├── requirements.txt
├── .env / .env.example
└── docker-compose.yml  (not used on Windows — see below)
```

---

## Bugs Encountered and Fixed

---

### BUG 1 — `sqlalchemy==2.0.36` version conflict

**Error:**
```
langchain-community 0.3.7 requires sqlalchemy<2.0.36
```

**Root cause:** The spec pinned `sqlalchemy==2.0.36` but `langchain-community==0.3.7` requires `<2.0.36`.

**Fix:** Downgrade in `requirements.txt`:
```
sqlalchemy==2.0.35
```

---

### BUG 2 — `make: command not recognized` on Windows

**Error:** Running `make up` fails because `make` is a Unix tool not available on Windows by default.

**Fix:** Run Docker commands directly:
```powershell
docker compose up --build -d
```
Or skip Docker entirely (see Cloud Setup below).

---

### BUG 3 — Celery SSL error with Upstash `rediss://` URL

**Error:**
```
ValueError: A rediss:// URL must have parameter ssl_cert_reqs and this must be set to CERT_NONE, CERT_OPTIONAL, or CERT_REQUIRED.
```

**Root cause:** Upstash provides a `rediss://` (TLS) URL. Celery's Redis transport requires an explicit `ssl_cert_reqs` query parameter in the URL.

**Fix:** Append `?ssl_cert_reqs=CERT_NONE` to the Redis URL in `.env`:
```bash
REDIS_URL=rediss://default:YOUR_TOKEN@cunning-dolphin-91906.upstash.io:6379?ssl_cert_reqs=CERT_NONE
```

---

### BUG 4 — Celery worker crash on Windows: `billiard` / multiprocessing

**Error:** Celery workers crash or hang on Windows with the default `prefork` pool.

**Fix:** Start the worker with `--pool=solo`:
```powershell
celery -A src.workers.celery_app.celery_app worker --loglevel=info --pool=solo
```
`solo` runs tasks in the same process, no forking — required on Windows.

---

### BUG 5 — `InFailedSqlTransaction` on `checkpointer.setup()`

**Error:**
```
psycopg.errors.InFailedSqlTransaction: current transaction is aborted, commands ignored until end of transaction block
```

**Root cause:** `PostgresSaver.setup()` runs a series of `CREATE TABLE IF NOT EXISTS` migrations. Without `autocommit=True`, these all share one transaction. If any migration statement fails (e.g., because the table already exists and a constraint differs), the transaction enters an aborted state and all subsequent statements fail.

**Fix:** Pass `autocommit=True` to `psycopg.connect()` in `src/graphs/workflow.py`:
```python
conn = psycopg.connect(settings.POSTGRES_URL_SYNC, autocommit=True)
checkpointer = PostgresSaver(conn)
checkpointer.setup()
```

**File:** [src/graphs/workflow.py](../../conductor/src/graphs/workflow.py) — `build_graph_with_checkpointer()`, line ~92.

---

### BUG 6 — Invalid Gemini model name `gemini-2.0-flash`

**Error:**
```
google.api_core.exceptions.InvalidArgument: 400 * GenerateContentRequest.model: unexpected model name format
```

**Root cause:** `gemini-2.0-flash` is not a valid model ID for `langchain-google-genai==2.0.4`. The API requires a versioned name like `gemini-2.0-flash-001`.

**Fix:** Changed to `gemini-2.0-flash-001` as the default. Additionally moved the model name into config so it is controlled from `.env`.

**Additional complication:** A linter silently changed the model string to `"\tgemini-3-flash-preview"` (prepended a tab character, also an invalid model). Always read the file before editing to catch silent mutations.

---

### BUG 7 — Gemini model pulled into config (not strictly a bug, but a key change)

**Problem:** Model name was hardcoded in `src/agents/nodes.py`. The user's target model is `gemini-3.5-flash`, which differs from the spec default.

**Fix:** Added `GEMINI_MODEL` to `src/config.py`:
```python
class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash-001"
```

Added to `.env.example`:
```bash
GEMINI_MODEL=gemini-3.5-flash
```

Updated `src/agents/nodes.py` `get_llm()` to use `settings.GEMINI_MODEL`:
```python
def get_llm(temperature: float = 0.3) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
    )
```

---

### BUG 8 — Pydantic `ValidationError` on `GET /api/v1/runs/{run_id}`

**Error:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for RunDetail
research_plan
  Input should be a valid list [type=list_type, input_value='["What is..."]', input_type=str]
```

**Root cause:** `research_plan` is stored in Postgres as a JSON string (e.g., `'["q1", "q2"]'`). The `RunDetail` Pydantic schema declares it as `Optional[List[str]]`. Calling `RunDetail.model_validate(run)` passes the raw ORM object directly to Pydantic, which sees a string where it expects a list and fails — before any JSON parsing code could execute.

**Fix:** Parse the JSON string first, then construct `RunDetail` explicitly with keyword arguments instead of using `model_validate`:

```python
# In src/api/routes/runs.py — get_run()

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
```

**General rule:** Never use `model_validate(orm_object)` when any field in the ORM model stores structured data as a serialized string (JSON, CSV, etc.). Parse those fields manually first, then use the explicit constructor.

---

## Windows / No-Docker Setup (Cloud Services)

### Postgres — Neon

1. Create a free project at [neon.tech](https://neon.tech)
2. Copy the connection string from the dashboard
3. Set in `.env`:
```bash
POSTGRES_USER=your_neon_user
POSTGRES_PASSWORD=your_neon_password
POSTGRES_DB=your_neon_db
POSTGRES_HOST=your-project.us-east-2.aws.neon.tech
POSTGRES_PORT=5432
```

### Redis — Upstash

1. Create a free database at [console.upstash.com](https://console.upstash.com)
2. Go to **Connect** → **Redis Clients** tab → copy the TCP URL (format: `rediss://default:TOKEN@host:port`)
3. Append `?ssl_cert_reqs=CERT_NONE` to the URL
4. Set in `.env`:
```bash
REDIS_URL=rediss://default:YOUR_TOKEN@your-host.upstash.io:6379?ssl_cert_reqs=CERT_NONE
```

**Important:** Use the **TCP** tab URL, not the REST API URL. The REST URL (starting with `https://`) is for HTTP clients and will not work with Celery.

### Starting the System Locally (No Docker)

```powershell
# 1. Install dependencies (from conductor/ directory)
pip install -r requirements.txt

# 2. Initialize the database (creates agent_runs table)
python -m src.db.init_db

# 3. Start the API server (in one terminal)
uvicorn src.api.main:app --reload --port 8000

# 4. Start the Celery worker (in a second terminal)
celery -A src.workers.celery_app.celery_app worker --loglevel=info --pool=solo
```

### Submitting a Research Topic

PowerShell (use backtick for line continuation):
```powershell
curl -X POST http://localhost:8000/api/v1/runs `
  -H "Content-Type: application/json" `
  -d '{"topic": "How do transformer attention mechanisms work in large language models?"}'
```

Bash:
```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{"topic": "How do transformer attention mechanisms work in large language models?"}'
```

### Polling for Results

```powershell
curl http://localhost:8000/api/v1/runs/YOUR_RUN_ID_HERE
```

When `status` is `complete`, `final_report` contains the markdown research report.

---

## Key Conventions

### LangGraph `autocommit` is non-negotiable
Any psycopg connection passed to `PostgresSaver` must use `autocommit=True`. This is not optional — the setup migrations will fail silently or loudly without it.

### `operator.add` on `research_items`
```python
research_items: Annotated[List[ResearchItem], operator.add]
```
This tells LangGraph to **append** new items to the list rather than replace it. Without this, each Researcher call would overwrite all previous findings. Every node returns `[research_item]` (a list with one item), and LangGraph appends it. This is how the loop accumulates findings.

### Nodes return partial dicts
Every node function returns only the fields it changes, not the full `AgentState`. LangGraph merges the partial dict into the existing state. This is intentional and correct — do not return the full state object.

### `model_validate` vs explicit constructor
- Use `model_validate(orm_obj)` only when all ORM fields map cleanly to Pydantic field types.
- If any ORM field stores structured data as a string (JSON, etc.), parse it first, then use the explicit `ModelClass(field=value, ...)` constructor.

### Gemini model naming
- `langchain-google-genai==2.0.4` requires versioned model names like `gemini-2.0-flash-001`.
- `gemini-2.0-flash` (without version suffix) is rejected with a 400 error.
- The model is now controlled via `GEMINI_MODEL` in `.env` — no code changes needed to switch models.

### Celery on Windows
- Always use `--pool=solo` on Windows. The default `prefork` pool uses multiprocessing which is unreliable on Windows.
- `task_acks_late=True` and `worker_prefetch_multiplier=1` in `celery_app.py` ensure a crashed worker re-queues the task rather than losing it.

### PYTHONPATH
Set `PYTHONPATH` to the project root so `src.*` imports resolve:
```powershell
$env:PYTHONPATH = "."
```
Or set it permanently in your shell profile. The Dockerfile sets `ENV PYTHONPATH=/app`.
