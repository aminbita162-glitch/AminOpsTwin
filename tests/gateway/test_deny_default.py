"""Deny-by-default test (G1.4).

Tests that the Gateway denies unknown schema_id, unknown envelope_type,
and unknown capability with GW-DEFAULT-001.
"""

from __future__ import annotations

from aminopstwin.contracts.clock import SeededClock
from aminopstwin.contracts.decision import Decision, Stage
from aminopstwin.gateway.gateway import (
    PolicyGateway,
    PolicyMatrix,
    PolicyMatrixEntry,
)


def _make_gateway() -> PolicyGateway:
    entries = {
        PolicyMatrixEntry("A2", "scenario", "simulate"),
        PolicyMatrixEntry("A3", "evidence_query", "query"),
    }
    return PolicyGateway(
        policy_matrix=PolicyMatrix(entries),
        current_epoch=0,
        schema_registry={
            "ops.sim.scenario@1",
            "ops.evidence.query@1",
        },
        envelope_type_registry={
            "ops.sim.scenario@1": "scenario",
            "ops.evidence.query@1": "evidence_query",
        },
    )


class TestDenyByDefault:
    """G1.4: Deny-by-default for unknown schema_id / envelope_type."""

    def test_unknown_schema_id_denied(self, make_envelope) -> None:
        """Unknown schema_id => GW-DEFAULT-001."""
        envelope = make_envelope(schema_id="unknown.schema@1")
        gw = _make_gateway()
        decided_at = SeededClock().now()
        record = gw.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-DEFAULT-001"
        assert record.stage == Stage.SCHEMA

    def test_unknown_envelope_type_denied(self, make_envelope) -> None:
        """schema_id exists but envelope_type mismatch => GW-DEFAULT-001."""
        envelope = make_envelope(
            schema_id="ops.sim.scenario@1",
            envelope_type="nonexistent_type",
        )
        gw = _make_gateway()
        decided_at = SeededClock().now()
        record = gw.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-DEFAULT-001"

    def test_empty_schema_registry_denied(self, make_envelope) -> None:
        """Empty schema registry => everything denied as GW-DEFAULT-001."""
        envelope = make_envelope()
        gw = PolicyGateway(
            policy_matrix=PolicyMatrix({
                PolicyMatrixEntry("A2", "scenario", "simulate"),
            }),
            current_epoch=0,
            schema_registry=set(),
            envelope_type_registry={},
        )
        decided_at = SeededClock().now()
        record = gw.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-DEFAULT-001"
