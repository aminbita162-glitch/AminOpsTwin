"""Pytest configuration and shared fixtures for AminOpsTwin tests."""

from __future__ import annotations

import datetime as _dt
import sys
import uuid
from pathlib import Path

import pytest

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.contracts.canonical import canonical_hash
from src.contracts.clock import (
    SeededClock,
    SeededIdFactory,
    SystemClock,
    SystemIdFactory,
)
from src.contracts.envelope import Envelope
from src.gateway.gateway import (
    PolicyGateway,
    PolicyMatrix,
    PolicyMatrixEntry,
)


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
        tenant_id: str = "tenant-default",
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
