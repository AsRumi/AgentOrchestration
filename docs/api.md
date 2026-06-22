# Conductor API Reference

Base URL: `http://localhost:8000`

Interactive docs (Swagger UI): `http://localhost:8000/docs`

---

## Endpoints

### POST /api/v1/runs

Start a new multi-agent research run.

Returns immediately with a `run_id`. The actual research happens asynchronously.

**Request body:**
```json
{
  "topic": "How do transformer attention mechanisms work in large language models?"
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `topic` | string | Yes | 10–500 characters |

**Response (202 Accepted):**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Run created. Poll the poll_url to check status.",
  "poll_url": "/api/v1/runs/550e8400-e29b-41d4-a716-446655440000"
}
```

---

### GET /api/v1/runs/{run_id}

Get the current status and result of a specific run.

**Path parameter:** `run_id` — UUID returned from POST /runs

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "topic": "How do transformer attention mechanisms work?",
  "status": "complete",
  "current_step": "complete",
  "research_plan": [
    "What is the attention mechanism in transformers?",
    "How is self-attention computed mathematically?",
    "What are the different types of attention (multi-head, cross-attention)?",
    "What are the computational challenges of attention at scale?"
  ],
  "final_report": "# Transformer Attention Mechanisms\n\n## Executive Summary\n...",
  "error_message": null,
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:01Z",
  "completed_at": "2024-01-15T10:31:45Z"
}
```

**Status values:**
| Status | Meaning |
|---|---|
| `pending` | Created, waiting for a Celery worker to pick it up |
| `running` | Worker is actively executing the agent pipeline |
| `complete` | Done. `final_report` contains the markdown report. |
| `failed` | An error occurred. `error_message` has details. |

---

### GET /api/v1/runs

List recent runs, newest first.

**Query parameters:**
| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 20 | Max runs to return |
| `offset` | integer | 0 | Skip this many runs (for pagination) |

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "topic": "How do transformer attention mechanisms work?",
    "status": "complete",
    "created_at": "2024-01-15T10:30:00Z",
    "completed_at": "2024-01-15T10:31:45Z"
  }
]
```

---

### DELETE /api/v1/runs/{run_id}

Delete a run record from the database.

**Note:** This does not cancel an in-progress run. The Celery task will continue running even after the record is deleted.

**Response:** 204 No Content

---

### GET /api/v1/health

Check that the API is running.

**Response (200 OK):**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## Usage Examples

### Full workflow with curl

```bash
# 1. Start a research run
RUN_ID=$(curl -s -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{"topic": "How does RLHF training work for large language models?"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['run_id'])")

echo "Run ID: $RUN_ID"

# 2. Poll until complete
while true; do
  STATUS=$(curl -s http://localhost:8000/api/v1/runs/$RUN_ID | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  if [ "$STATUS" = "complete" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 5
done

# 3. Get the report
curl -s http://localhost:8000/api/v1/runs/$RUN_ID \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['final_report'])"
```

### With Python httpx

```python
import httpx
import time

client = httpx.Client(base_url="http://localhost:8000")

# Start a run
response = client.post("/api/v1/runs", json={
    "topic": "What are the key differences between RAG and fine-tuning for LLMs?"
})
run_id = response.json()["run_id"]
print(f"Started run: {run_id}")

# Poll for completion
while True:
    run = client.get(f"/api/v1/runs/{run_id}").json()
    print(f"Status: {run['status']}")
    
    if run["status"] == "complete":
        print("\n--- REPORT ---\n")
        print(run["final_report"])
        break
    elif run["status"] == "failed":
        print(f"Run failed: {run['error_message']}")
        break
    
    time.sleep(5)
```

---

## Error Responses

All errors follow this format:
```json
{
  "detail": "Error message here"
}
```

| HTTP Status | When |
|---|---|
| 400 Bad Request | Invalid request body |
| 404 Not Found | Run ID doesn't exist |
| 422 Unprocessable Entity | Validation error (e.g. topic too short) |
| 500 Internal Server Error | Unexpected server error |
