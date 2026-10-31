"""Database connection, session management, and table creation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from sqlmodel import Session, SQLModel, create_engine

# Database storage path
BACKEND_DIR = Path(__file__).resolve().parent.parent
STUDIO_DIR = BACKEND_DIR.parent
DATA_DIR = STUDIO_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "studio.db"
DATABASE_URL = os.environ.get("STUDIO_DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)


def create_db_and_tables():
    """Create all SQLModel tables in database."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency for yielding database session."""
    with Session(engine) as session:
        yield session
