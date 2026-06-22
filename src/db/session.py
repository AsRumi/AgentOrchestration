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
