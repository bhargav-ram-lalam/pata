"""
persistence/database.py
=======================
Database connection, session lifecycle, and schema initialization.
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DEFAULT_DB_URL = "sqlite:///./pata.db"
DATABASE_URL = os.getenv("PATA_DATABASE_URL", DEFAULT_DB_URL)

# Engine configuration
is_sqlite = DATABASE_URL.startswith("sqlite")
engine_kwargs = {}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Enable WAL mode and foreign keys for SQLite
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
