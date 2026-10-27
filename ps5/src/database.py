# src/database.py
"""SQLAlchemy engine and session handling for the PS5 platform.
Uses the Pydantic Settings defined in ``src/config.py``.
Provides a ``init_db`` helper for quick dev startup and a FastAPI
dependency ``get_db`` that yields a session.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.db_models import Base

# Engine – echo enabled for DEBUG level
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL.upper() == "DEBUG",
    future=True,
)

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

def init_db() -> None:
    """Create tables if they do not exist. In production you would run Alembic migrations."""
    Base.metadata.create_all(bind=engine)

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
