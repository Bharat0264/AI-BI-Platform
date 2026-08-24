"""Shared SQLAlchemy configuration; DATABASE_URL selects PostgreSQL or SQLite."""
from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = f"sqlite:///{(ROOT / 'data' / 'platform.db').as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_URL)

class Base(DeclarativeBase):
    pass

def _engine(url=DATABASE_URL):
    kwargs = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)

engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

def get_session():
    return SessionLocal()

def init_database():
    from . import models  # ensure metadata registration
    Base.metadata.create_all(engine)
