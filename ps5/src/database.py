"""SQLAlchemy engine and session handling for the PS5 platform.

Supports both PostgreSQL and local SQLite databases.
Provides init_db to create tables and FastAPI get_db dependency.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.db_models import Base

# Ensure parent directory exists for SQLite files
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite"):
    path_str = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    if path_str and not path_str.startswith(":memory:"):
        db_path = Path(path_str)
        db_path.parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=settings.LOG_LEVEL.upper() == "DEBUG",
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def init_db() -> None:
    """Create tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
