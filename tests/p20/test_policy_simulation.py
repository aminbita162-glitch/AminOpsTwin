"""P20 policy simulation test (deliverable 2).

Verifies that the policy simulation mode evaluates candidate policies
against synthetic envelopes without committing effects.
"""

from __future__ import annotations

import datetime as _dt
import uuid

import pytest

from aminopstwin.contracts.canonical import canonical_hash
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.gateway.gateway import (
    PolicyGateway,
    PolicyMatrix,
    PolicyMatrixEntry,
)
from aminopstwin.policy_simulation import (
    PolicySimulator,
    SimulationReport,
    simulate_policy,
    build_candidate_gateway,
)


def _make_envelope(
    schema_id: str = "test_schema@1",
    envelope_type: str = "test_type",
    tenant_id: str = "tenant-default",
    policy_epoch: int = 0,
) -> Envelope:
    """Create a test envelope with a valid payload_hash."""
    payload: dict[str, bool] = {"test": True}
    return Envelope(
        envelope_version="1.0",
        schema_id=schema_id,
        envelope_type=envelope_type,
        correlation_id=uuid.uuid4(),
        causation_id=None,
        tenant_id=tenant_id,
        policy_epoch=policy_epoch,
        idempotency_key="abcdef0123456789abcdef0123456789",
        payload=payload,
        payload_hash=canonical_hash(payload),
        created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
    )


def _make_gateway(
    allowed_principal: str = "A1",
    allowed_envelope_type: str = "test_type",
    allowed_capability: str = "default",
    current_epoch: int = 0,
) -> PolicyGateway:
    """Create a test gateway with a single allowed entry."""
    matrix = PolicyMatrix()
    matrix.add(
        PolicyMatrixEntry(
            principal=allowed_principal,
            envelope_type=allowed_envelope_type,
            capability=allowed_capability,
        )
    )
    return PolicyGateway(
        policy_matrix=matrix,
        current_epoch=current_epoch,
        schema_registry={"test_schema@1"},
        envelope_type_registry={"test_schema@1": "test_type"},
    )


class TestPolicySimulation:
    """P20 deliverable 2: policy simulation mode."""

    def test_simulation_produces_report(self) -> None:
        """Simulation produces a report with decisions."""
        gw = _make_gateway()
        env = _make_envelope()
        decided_at = _dt.datetime(2026, 1, 1, 12, tzinfo=_dt.UTC)
        report = simulate_policy(
            gw,
            [(env, "A1", "default", decided_at)],
        )
        assert isinstance(report, SimulationReport)
        assert report.total == 1
        assert report.allowed_count == 1
        assert report.denied_count == 0

    def test_simulation_does_not_alter_live_state(self) -> None:
        """Simulation does not alter the gateway's policy matrix."""
        gw = _make_gateway()
        matrix_before = gw._policy_matrix.entries  # noqa: SLF001
        env = _make_envelope()
        decided_at = _dt.datetime(2026, 1, 1, 12, tzinfo=_dt.UTC)
        simulate_policy(gw, [(env, "A1", "default", decided_at)])
        matrix_after = gw._policy_matrix.entries  # noqa: SLF001
        assert matrix_before == matrix_after

    def test_simulation_evaluates_denial(self) -> None:
        """Simulation correctly reports denied envelopes."""
        gw = _make_gateway()
        env = _make_envelope()
        decided_at = _dt.datetime(2026, 1, 1, 12, tzinfo=_dt.UTC)
        # Use an unauthorized principal
        report = simulate_policy(
            gw,
            [(env, "UNKNOWN_AGENT", "default", decided_at)],
        )
        assert report.denied_count == 1
        assert report.allowed_count == 0
        assert report.results[0].decision.value == "DENY"

    def test_simulation_hash_is_deterministic(self) -> None:
        """Same inputs produce same report hash."""
        gw = _make_gateway()
        env = _make_envelope()
        decided_at = _dt.datetime(2026, 1, 1, 12, tzinfo=_dt.UTC)
        report1 = simulate_policy(
            gw, [(env, "A1", "default", decided_at)]
        )
        report2 = simulate_policy(
            gw, [(env, "A1", "default", decided_at)]
        )
        assert report1.hash == report2.hash

    def test_build_candidate_gateway_is_independent(self) -> None:
        """build_candidate_gateway creates a fresh, independent gateway."""
        matrix = PolicyMatrix()
        matrix.add(
            PolicyMatrixEntry("A1", "test_type", "default")
        )
        gw = build_candidate_gateway(
            matrix=matrix,
            current_epoch=0,
            schema_registry={"test_schema@1"},
            envelope_type_registry={"test_schema@1": "test_type"},
        )
        assert isinstance(gw, PolicyGateway)
        assert gw.current_epoch == 0

    def test_simulation_with_multiple_envelopes(self) -> None:
        """Simulation handles multiple envelopes with mixed decisions."""
        gw = _make_gateway()
        env1 = _make_envelope()
        env2 = _make_envelope()
        decided_at = _dt.datetime(2026, 1, 1, 12, tzinfo=_dt.UTC)
        report = simulate_policy(
            gw,
            [
                (env1, "A1", "default", decided_at),
                (env2, "UNKNOWN", "default", decided_at),
            ],
        )
        assert report.total == 2
        assert report.allowed_count == 1
        assert report.denied_count == 1
