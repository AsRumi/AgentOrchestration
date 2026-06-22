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
