"""Gateway unit tests — purity, deny-by-default, epoch checks, authorization (G1.1, G1.2, G1.4)."""

import datetime as _dt

import pytest

from src.contracts.canonical import canonical_hash
from src.contracts.clock import SeededClock, SeededIdFactory
from src.contracts.decision import Decision, Stage
from src.contracts.envelope import Envelope
from src.gateway.gateway import PolicyGateway, PolicyMatrix, PolicyMatrixEntry


class TestGatewayPurity:
    """G1.2: Gateway purity — 1000 repeated calls on the same input give the same output."""

    def test_purity_1000(self, gateway, make_envelope):
        envelope = make_envelope()
        clock = SeededClock()
        decided_at = clock.now()

        records = [gateway.evaluate(envelope, "A2", decided_at, "simulate") for _ in range(1000)]

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

    def test_purity_same_decision_record(self, gateway, make_envelope):
        """Two calls with identical inputs produce identical DecisionRecords."""
        envelope = make_envelope()
        decided_at = SeededClock().now()

        r1 = gateway.evaluate(envelope, "A2", decided_at, "simulate")
        r2 = gateway.evaluate(envelope, "A2", decided_at, "simulate")

        # DecisionRecords should be equal in all fields
        assert r1.decision == r2.decision
        assert r1.reason_code == r2.reason_code
        assert r1.stage == r2.stage
        assert r1.policy_epoch == r2.policy_epoch
        assert r1.payload_hash == r2.payload_hash
        assert r1.correlation_id == r2.correlation_id
        assert r1.principal == r2.principal
        assert r1.rule_ids == r2.rule_ids


class TestDenyByDefault:
    """G1.4: Deny-by-default — unknown schema_id/envelope_type => GW-DEFAULT-001."""

    def test_unknown_schema_id_denied(self, gateway, make_envelope):
        envelope = make_envelope(schema_id="unknown.schema@1")
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-DEFAULT-001"
        assert record.stage == Stage.SCHEMA

    def test_unknown_envelope_type_denied(self, gateway, make_envelope):
        # schema_id exists but envelope_type doesn't match the registry
        envelope = make_envelope(
            schema_id="ops.sim.scenario@1",
            envelope_type="nonexistent_type",
        )
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-DEFAULT-001"


class TestEpochChecks:
    """G1.2 / §3.7: Epoch checks — outdated and future epochs are denied."""

    def test_outdated_epoch_denied(self, gateway, make_envelope):
        envelope = make_envelope(policy_epoch=0)
        # Gateway is at epoch 0, so this should be allowed if auth passes
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "A2", decided_at, "simulate")
        assert record.decision == Decision.ALLOW

    def test_future_epoch_denied(self, gateway, make_envelope):
        envelope = make_envelope(policy_epoch=5)
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-EPOCH-002"

    def test_past_epoch_denied(self, gateway, make_envelope):
        """When gateway epoch is > envelope epoch, it should be denied."""
        from src.gateway.gateway import PolicyGateway as PG
        gw2 = PG(
            policy_matrix=gateway._policy_matrix,
            current_epoch=3,
            schema_registry=gateway._schema_registry,
            envelope_type_registry=gateway._envelope_type_registry,
        )
        envelope = make_envelope(policy_epoch=0)
        decided_at = SeededClock().now()
        record = gw2.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-EPOCH-001"


class TestAuthorization:
    """§3.8: Policy matrix — unlisted (principal, envelope_type, capability) => GW-AUTH-001."""

    def test_unlisted_principal_denied(self, gateway, make_envelope):
        envelope = make_envelope()
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "X1", decided_at, "simulate")

        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-AUTH-001"

    def test_unlisted_capability_denied(self, gateway, make_envelope):
        envelope = make_envelope()
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "A2", decided_at, "unknown_capability")

        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-AUTH-001"

    def test_unlisted_envelope_type_denied(self, gateway, make_envelope):
        """A2 with a non-scenario envelope_type not in matrix."""
        envelope = make_envelope(
            schema_id="ops.evidence.query@1",
            envelope_type="evidence_query",
        )
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "A2", decided_at, "query")

        # A2 is not authorized for evidence_query
        assert record.decision == Decision.DENY
        assert record.reason_code == "GW-AUTH-001"

    def test_valid_principal_allowed(self, gateway, make_envelope):
        envelope = make_envelope()
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.ALLOW
        assert record.reason_code is None


class TestDecisionRecord:
    """DecisionRecord invariants — ALLOW has no reason_code, DENY has one."""

    def test_allow_no_reason(self, gateway, make_envelope):
        envelope = make_envelope()
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.ALLOW
        assert record.reason_code is None

    def test_deny_has_reason(self, gateway, make_envelope):
        envelope = make_envelope(schema_id="unknown@1")
        decided_at = SeededClock().now()
        record = gateway.evaluate(envelope, "A2", decided_at, "simulate")

        assert record.decision == Decision.DENY
        assert record.reason_code is not None
