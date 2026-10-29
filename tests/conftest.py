"""Pytest configuration and shared fixtures for AminOpsTwin tests."""

from __future__ import annotations

import datetime as _dt
import os
import secrets
import shutil
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aminopstwin.contracts.canonical import canonical_hash
from aminopstwin.contracts.clock import (
    SeededClock,
    SeededIdFactory,
    SystemClock,
    SystemIdFactory,
)
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.gateway.gateway import (
    PolicyGateway,
    PolicyMatrix,
    PolicyMatrixEntry,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker

_HAS_DOCKER = shutil.which("docker") is not None
_IS_LINUX = os.uname().sysname == "Linux"


@pytest.fixture
def seeded_clock() -> SeededClock:
    """Deterministic clock for tests."""
    return SeededClock(
        start=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
    )


@pytest.fixture
def seeded_id_factory() -> SeededIdFactory:
    """Deterministic IdFactory for tests."""
    return SeededIdFactory(seed=42)


@pytest.fixture
def system_clock() -> SystemClock:
    return SystemClock()


@pytest.fixture
def system_id_factory() -> SystemIdFactory:
    return SystemIdFactory()


# --- Gateway fixtures ---

@pytest.fixture
def schema_registry() -> set[str]:
    """Known schema_ids for the gateway."""
    return {
        "ops.sim.scenario@1",
        "ops.sim.baseline@1",
        "ops.evidence.query@1",
    }


@pytest.fixture
def envelope_type_registry() -> dict[str, str]:
    """schema_id -> envelope_type mapping."""
    return {
        "ops.sim.scenario@1": "scenario",
        "ops.sim.baseline@1": "baseline",
        "ops.evidence.query@1": "evidence_query",
    }


@pytest.fixture
def policy_matrix() -> PolicyMatrix:
    """Test policy matrix with a few allowed entries."""
    entries = {
        PolicyMatrixEntry("A1", "synthetic_fixture", "ingest"),
        PolicyMatrixEntry("A2", "scenario", "simulate"),
        PolicyMatrixEntry("A3", "evidence_query", "query"),
        PolicyMatrixEntry("S1", "gateway_decision", "evaluate"),
    }
    return PolicyMatrix(entries)


@pytest.fixture
def gateway(
    policy_matrix: PolicyMatrix,
    schema_registry: set[str],
    envelope_type_registry: dict[str, str],
) -> PolicyGateway:
    """Policy Gateway with epoch 0 and test registries."""
    return PolicyGateway(
        policy_matrix=policy_matrix,
        current_epoch=0,
        schema_registry=schema_registry,
        envelope_type_registry=envelope_type_registry,
    )


def _make_payload() -> dict:
    """A simple valid payload for envelope construction."""
    return {"site": "site-a", "capacity": 10, "queue": 3}


@pytest.fixture
def make_envelope(
    seeded_clock: SeededClock,
    seeded_id_factory: SeededIdFactory,
):
    """Factory fixture for creating valid Envelopes."""

    def _make(
        schema_id: str = "ops.sim.scenario@1",
        envelope_type: str = "scenario",
        payload: dict | None = None,
        policy_epoch: int = 0,
        tenant_id: str = "tenant-test",
        correlation_id: uuid.UUID | None = None,
        idempotency_key: str = "test-idempotency-key-001",
    ) -> Envelope:
        pl = payload if payload is not None else _make_payload()
        return Envelope(
            envelope_version="1.0",
            schema_id=schema_id,
            envelope_type=envelope_type,
            correlation_id=correlation_id
            or seeded_id_factory.new_id(),
            causation_id=None,
            tenant_id=tenant_id,
            policy_epoch=policy_epoch,
            idempotency_key=idempotency_key,
            payload=pl,
            payload_hash=canonical_hash(pl),
            created_at=seeded_clock.now(),
        )

    return _make


# ---------------------------------------------------------------------------
# PostgreSQL testcontainers fixtures (P27)
#
# These fixtures spin up a real PostgreSQL 16 container for the Postgres
# gate tests.  They must never be skipped on Linux (where a container
# runtime is available).  On macOS without a container runtime, they may
# skip — recorded in DEVIATIONS of the Hard-Stop Report.
#
# No default credentials: the container password is randomly generated
# at runtime.
# ---------------------------------------------------------------------------


def _wait_for_port(host: str, port: int, timeout: float = 30) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


@pytest.fixture(scope="module")
def pg_container() -> Iterator[dict[str, str]]:
    """Start a PostgreSQL 16 container and yield connection params.

    The password is randomly generated — no default credentials.
    On Linux without Docker, this is a hard failure (not a skip).
    On macOS without Docker, it skips (recorded in DEVIATIONS).
    """
    if not _HAS_DOCKER:
        if _IS_LINUX:
            pytest.fail(
                "Docker not available on Linux — Postgres gate tests "
                "must never be skipped on Linux"
            )
        pytest.skip(
            "Docker not available on macOS — Postgres tests skip "
            "where no container runtime exists"
        )

    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:
        try:
            from testcontainers.postgres import PostgresContainer
        except ImportError:
            if _IS_LINUX:
                pytest.fail(
                    "testcontainers not installed — Postgres gate tests "
                    "must never be skipped on Linux"
                )
            pytest.skip("testcontainers not installed")

    password = secrets.token_urlsafe(16)
    container = PostgresContainer(
        image="postgres:16",
        username="test_admin",
        password=password,
        dbname="test_db",
        driver="psycopg",
    )
    container.start()

    host = container.get_container_host_ip()
    port = int(container.get_exposed_port(5432))
    if not _wait_for_port(host, port):
        container.stop()
        pytest.fail(f"PostgreSQL container did not become ready at {host}:{port}")

    url = container.get_connection_url()
    if "sslmode" not in url:
        url = url + ("&" if "?" in url else "?") + "sslmode=prefer"

    yield {
        "url": url,
        "host": host,
        "port": str(port),
        "database": "test_db",
        "username": "test_admin",
        "password": password,
    }

    container.stop()


def _create_tables(engine: Engine) -> None:
    """Drop and recreate all tables from the SQLAlchemy models.

    Each test gets a clean schema so deterministic ID factories do
    not collide across tests sharing the same module-scoped container.
    """
    from aminopstwin.persistence import models  # noqa: F401
    from aminopstwin.persistence.base import Base

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture()
def pg_session_factory(
    pg_container: dict[str, str],
) -> Iterator[sessionmaker[Session]]:
    """Yield a session factory bound to the testcontainer PostgreSQL."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        pg_container["url"],
        future=True,
        echo=False,
    )
    _create_tables(engine)

    factory: sessionmaker[Session] = sessionmaker(
        bind=engine,
        future=True,
        expire_on_commit=False,
    )

    yield factory

    engine.dispose()
