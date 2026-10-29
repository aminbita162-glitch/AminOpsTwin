"""Session management for PostgreSQL persistence (P27).

Connection security (deliverable 8):
- TLS required (sslmode=verify-full by default in the connection string).
- Credentials read only from the environment.
- No default credentials in the repository.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

__all__ = [
    "PGConfig",
    "create_pg_engine",
    "create_pg_session_factory",
    "set_tenant_local",
]


@dataclass(frozen=True, slots=True)
class PGConfig:
    """PostgreSQL connection configuration.

    Credentials come from the environment, never from defaults.
    """

    host: str
    port: int
    database: str
    username: str
    password: str
    sslmode: str = "verify-full"

    @classmethod
    def from_env(cls) -> PGConfig:
        """Build a PGConfig from environment variables.

        Required environment variables:
            PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

        Optional:
            PGSSLMODE (default: verify-full)
        """
        host = os.environ.get("PGHOST", "")
        port = int(os.environ.get("PGPORT", "5432"))
        database = os.environ.get("PGDATABASE", "")
        username = os.environ.get("PGUSER", "")
        password = os.environ.get("PGPASSWORD", "")
        sslmode = os.environ.get("PGSSLMODE", "verify-full")
        if not all([host, database, username, password]):
            raise RuntimeError(
                "PostgreSQL credentials must come from the environment: "
                "PGHOST, PGDATABASE, PGUSER, PGPASSWORD are required"
            )
        return cls(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            sslmode=sslmode,
        )

    @property
    def url(self) -> str:
        """Build the SQLAlchemy URL with TLS and no embedded secrets.

        The password is passed separately to the engine via
        connect_args to avoid logging it in the URL.
        """
        return (
            f"postgresql+psycopg://{self.username}@"
            f"{self.host}:{self.port}/{self.database}"
            f"?sslmode={self.sslmode}"
        )


def create_pg_engine(config: PGConfig) -> Engine:
    """Create a SQLAlchemy engine from a PGConfig.

    The password is passed via connect_args, not embedded in the URL,
    so that it does not appear in logs.
    """
    from sqlalchemy import create_engine

    return create_engine(
        config.url,
        connect_args={"password": config.password},
        future=True,
        echo=False,
    )


def create_pg_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to *engine*."""
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def set_tenant_local(session: Session, tenant_id: str) -> None:
    """Set the tenant_id for the current transaction (RLS).

    Uses SET LOCAL so the setting is transaction-scoped and does not
    persist beyond the current transaction.
    """
    session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
