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
