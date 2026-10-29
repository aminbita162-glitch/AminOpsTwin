"""SQLAlchemy 2 declarative base for the persistence layer (P27).

All models inherit from :class:`Base` so that Alembic can discover them
for migration generation.
"""

from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

__all__ = ["Base", "get_engine", "get_session_factory"]


class Base(DeclarativeBase):
    """Declarative base for all persistence models (P27)."""

    pass


def get_engine(url: str) -> Engine:
    """Create a SQLAlchemy engine for the given URL.

    This is a convenience wrapper for tests and the local compose stack.
    """
    from sqlalchemy import create_engine

    return create_engine(url, future=True)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to *engine*."""
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)
