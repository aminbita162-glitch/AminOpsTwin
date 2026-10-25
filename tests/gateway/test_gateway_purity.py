"""Gateway purity test (G1.2).

Tests that the Gateway is a pure function: 1000 repeated calls on the
same input produce the same output.
"""

from __future__ import annotations

from aminopstwin.contracts.clock import SeededClock
from aminopstwin.contracts.decision import Decision, Stage
from aminopstwin.gateway.gateway import PolicyGateway, PolicyMatrix, PolicyMatrixEntry


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


class TestGatewayPurity1000:
    """G1.2: 1000 repeated calls on the same input give the same output."""

    def test_purity_1000(self, make_envelope) -> None:
        envelope = make_envelope()
        gw = _make_gateway()
        decided_at = SeededClock().now()

        records = [
            gw.evaluate(envelope, "A2", decided_at, "simulate")
            for _ in range(1000)
        ]

        first = records[0]
        for r in records[1:]:
            assert r.decision == first.decision
            assert r.reason_code == first.reason_code
            assert r.stage == first.stage
            assert r.policy_epoch == first.policy_epoch
            assert r.payload_hash == first.payload_hash
            assert r.correlation_id == first.correlation_id
            assert r.principal == first.principal
            assert r.rule_ids == first.rule_ids
            assert r.secondary_codes == first.secondary_codes

    def test_purity_deny_same(self, make_envelope) -> None:
        """Purity holds for DENY decisions too."""
        envelope = make_envelope()
        gw = _make_gateway()
        decided_at = SeededClock().now()

        r1 = gw.evaluate(envelope, "X1", decided_at, "simulate")
        r2 = gw.evaluate(envelope, "X1", decided_at, "simulate")

        assert r1.decision == Decision.DENY
        assert r1.decision == r2.decision
        assert r1.reason_code == r2.reason_code
        assert r1.stage == r2.stage
        assert r1.stage == Stage.GATEWAY
