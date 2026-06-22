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
