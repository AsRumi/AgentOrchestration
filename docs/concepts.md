# Conductor — Core Concepts

A deep dive into the ideas behind the Conductor multi-agent orchestration system. Read this if you want to understand *why* the system is built the way it is, not just *how* to run it.

---

## 1. What is an AI Agent?

An **AI agent** is a system that combines three things:

1. **An LLM** — the reasoning engine that understands language and generates responses
2. **Tools** — functions the LLM can call to interact with the outside world (search, read files, call APIs)
3. **A control loop** — logic that decides when to call tools, when to respond, and when to stop

The key insight is the control loop. A plain LLM just takes input and produces output. An agent *acts*: it observes a situation, decides what tool to use, executes the tool, observes the result, and repeats until it achieves its goal.

In Conductor, each agent is simpler — it receives state, performs one focused task (planning, searching, synthesizing, writing), and returns its output. The orchestration system handles the control loop at the workflow level.

**Example from this project:**
The Researcher agent receives one research question, calls `web_search`, receives the results, then calls the LLM to extract key findings. That's it — one focused action, done well.

---

## 2. What is Agent Orchestration?

A single agent is powerful but limited. Complex tasks require:
- Breaking work into steps
- Running steps in the right order
- Passing information between steps
- Handling failures and retries
- Maintaining coherent state across the whole process

**Agent orchestration** is the system that coordinates multiple specialized agents to complete complex tasks that no single agent could handle well alone.

The key design principle is **specialization**: instead of one "do everything" agent, you have multiple agents each excellent at one thing:
- The Planner is great at decomposing complex topics into focused questions
- The Researcher is great at finding specific information
- The Synthesizer is great at finding patterns across disparate findings
- The Writer is great at turning analysis into readable prose

This mirrors how human teams work: a research project has strategists, researchers, analysts, and writers — each contributing their specialty to the final output.

**Why not one big prompt?**
You could theoretically do all this in one LLM call. In practice:
- Long single-shot prompts produce worse outputs than focused, iterative calls
- You can't loop a single prompt (researcher needs to run once per question)
- State becomes impossible to track and checkpoint
- Failures cascade — one step failing kills everything

---

## 3. What is a State Graph?

LangGraph models the workflow as a **directed state graph**:

```
START → [Planner] → [Researcher] → [Synthesizer] → [Writer] → END
                         ↑_____________↓
                    (conditional loop)
```

Three concepts:

**Nodes** — Each agent is a node. A node is a Python function that receives the current state and returns a partial update to that state. Nodes are the units of computation.

**Edges** — Edges define the flow between nodes. A normal edge (`add_edge`) always goes from A to B. A conditional edge (`add_conditional_edges`) calls a routing function to decide where to go next — this is what creates the Researcher loop.

**State** — A TypedDict object that every node shares. Each node reads what it needs from state and writes its outputs back. State is the "shared memory" of the workflow — it accumulates information as it flows through the graph.

The graph structure in `workflow.py`:
```python
workflow.add_edge(START, "planner")           # Always start here
workflow.add_edge("planner", "researcher")    # Planner feeds Researcher

workflow.add_conditional_edges(               # After Researcher: loop or proceed?
    "researcher",
    should_continue_research,                 # This function decides
    {
        "continue_research": "researcher",    # More questions → loop back
        "synthesize": "synthesizer",          # Done → move forward
    }
)

workflow.add_edge("synthesizer", "writer")    # Linear from here
workflow.add_edge("writer", END)
```

---

## 4. What is State in LangGraph?

State is the central data structure passed through every node. In Conductor, it's defined as a `TypedDict` in `src/agents/state.py`:

```python
class AgentState(TypedDict):
    topic: str                                        # User's input
    run_id: str                                       # Database link
    research_plan: List[str]                          # Set by Planner
    research_index: int                               # Current question pointer
    research_items: Annotated[List[ResearchItem], operator.add]  # Accumulated findings
    synthesis: str                                    # Set by Synthesizer
    final_report: str                                 # Set by Writer
    status: str                                       # Progress indicator
    error: Optional[str]                              # Error message
```

**Key rules:**
1. Every node receives the *full* current state
2. Every node returns a *partial* dict — only the fields it changed
3. LangGraph merges the partial update back into the full state
4. The `Annotated[List[...], operator.add]` on `research_items` is special: instead of replacing the list, LangGraph *appends* to it. This is how research findings accumulate across multiple Researcher calls.

**Why TypedDict?**
TypedDict gives you Python type checking without the overhead of a full Pydantic model. LangGraph uses it to understand what fields exist and how to merge updates.

---

## 5. What is Checkpointing?

Checkpointing means saving a complete snapshot of the state after every node completes.

In Conductor, LangGraph saves to Postgres using `PostgresSaver`. After Planner runs, it saves. After each Researcher call, it saves. The snapshot includes the full `AgentState` at that point.

**Why this matters:**

*Fault tolerance*: If the Celery worker crashes mid-run (machine dies, OOM kill, network error), the workflow can resume from the last checkpoint instead of starting over. A 3-minute run that fails at step 4 of 6 can resume from step 4, not step 1.

*Observability*: You can inspect the exact state at any point in a run's history. "What did the Planner generate? What did the second Researcher call return?" — all answerable by querying the checkpoint.

*Isolation*: Each run gets its own `thread_id` in the checkpointer. Multiple runs can execute concurrently without interfering with each other's state.

The checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) are created automatically by `checkpointer.setup()` the first time a workflow runs.

---

## 6. Why Async Execution with Celery?

LLM API calls are slow. A single Gemini call can take 2–10 seconds. Our workflow makes 4+ LLM calls plus web searches — a total runtime of 30–120 seconds per research run.

If FastAPI waited synchronously for the workflow to complete before responding, every HTTP request would hold a connection open for 30–120 seconds. This:
- Blocks the web server thread (can't handle other requests)
- Times out at the HTTP layer (browsers/proxies typically cut off after 30–60s)
- Creates a terrible user experience

**The async pattern solves this:**
1. FastAPI receives the request, creates a DB record, enqueues a task to Redis, and returns immediately (< 100ms) with a `run_id`
2. The Celery worker picks up the task from Redis and executes the workflow in the background
3. The client polls `GET /runs/{run_id}` every few seconds until status is `complete`

This is the standard pattern for any long-running operation in web APIs — file conversions, email sends, video processing, etc.

**Redis's role:**
Redis acts as the message broker — a queue that Celery pushes tasks into and workers pull from. It also stores task completion state so Celery knows which tasks are done.

**Why not Python's asyncio?**
Python asyncio handles I/O concurrency within a single process. LLM calls and DB writes involve network I/O that *could* be awaited, but Celery provides stronger isolation (separate processes), proper retry semantics, and a task monitor (Flower). For production systems, the operational benefits of Celery outweigh the complexity cost.

---

## Putting It Together

The system design answers one question at each layer:

| Layer | Question answered |
|---|---|
| **AgentState** | What information flows through the workflow? |
| **Agent nodes** | What does each specialized agent do? |
| **LangGraph graph** | In what order do agents run, and how do they loop? |
| **Postgres checkpointer** | How do we survive failures mid-run? |
| **Celery task** | How do we run this without blocking the API? |
| **Redis broker** | How do we queue and distribute tasks? |
| **FastAPI routes** | How does a user start a run and get results? |

Each layer is independently testable and replaceable — swap Gemini for another LLM, swap DuckDuckGo for a different search API, swap Celery for another task queue — the interfaces between layers stay stable.
