"""Alembic migration environment for AminOpsTwin (P27).

The database URL is constructed from environment variables (PGHOST,
PGPORT, PGDATABASE, PGUSER, PGPASSWORD) — no default credentials.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aminopstwin.persistence import models  # noqa: E402, F401
from aminopstwin.persistence.base import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Build the SQLAlchemy URL from environment variables.

    No default credentials: PGHOST, PGDATABASE, PGUSER, and PGPASSWORD
    must come from the environment.  PGPORT defaults to 5432 (standard
    PostgreSQL port, not a credential) and PGSSLMODE defaults to
    verify-full (the security requirement, not a credential).
    """
    host = os.environ.get("PGHOST", "")
    if not host:
        raise RuntimeError(
            "PGHOST must be set — no default credentials in the repository"
        )
    port = os.environ.get("PGPORT", "5432")
    database = os.environ.get("PGDATABASE", "")
    if not database:
        raise RuntimeError(
            "PGDATABASE must be set — no default credentials in the repository"
        )
    username = os.environ.get("PGUSER", "")
    if not username:
        raise RuntimeError(
            "PGUSER must be set — no default credentials in the repository"
        )
    password = os.environ.get("PGPASSWORD", "")
    if not password:
        raise RuntimeError(
            "PGPASSWORD must be set — no default credentials in the repository"
        )
    sslmode = os.environ.get("PGSSLMODE", "verify-full")
    return (
        f"postgresql+psycopg://{username}:{password}@{host}:{port}/{database}"
        f"?sslmode={sslmode}"
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    config_section = config.get_section(config.config_ini_section, {})
    config_section["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
