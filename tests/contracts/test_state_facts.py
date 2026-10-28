"""Tests for StateFacts and DecisionRecord hash (P12, G12.4).

G12.4: StateFacts hash present in every DecisionRecord.
"""

from __future__ import annotations

import datetime as _dt
import uuid

import pytest
from aminopstwin.contracts.canonical import canonical_hash
from aminopstwin.contracts.clock import SeededClock
from aminopstwin.contracts.decision import Decision, DecisionRecord, Stage
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.contracts.state_facts import (
    StateFacts,
    state_facts_hash,
)
from aminopstwin.gateway.gateway import (
    PolicyGateway,
    PolicyMatrix,
    PolicyMatrixEntry,
)


class TestStateFacts:
    """StateFacts — immutable snapshot for the Gateway."""

    def test_frozen(self) -> None:
        facts = StateFacts(
            idempotency_seen=False,
            budget_remaining=100,
            budget_limit=200,
            tenant_id="tenant-a",
            policy_epoch=0,
            policy_hash="abc123",
        )
        with pytest.raises((AttributeError, Exception)):
            facts.idempotency_seen = True  # type: ignore[misc]

    def test_to_canonical_dict(self) -> None:
        facts = StateFacts(
            idempotency_seen=True,
            budget_remaining=50,
            budget_limit=100,
            tenant_id="tenant-b",
            policy_epoch=2,
            policy_hash="deadbeef",
        )
        d = facts.to_canonical_dict()
        assert d == {
            "idempotency_seen": True,
            "budget_remaining": 50,
            "budget_limit": 100,
            "tenant_id": "tenant-b",
            "policy_epoch": 2,
            "policy_hash": "deadbeef",
        }

    def test_hash_deterministic(self) -> None:
        facts = StateFacts(
            idempotency_seen=False,
            budget_remaining=10,
            budget_limit=20,
            tenant_id="t",
            policy_epoch=0,
            policy_hash="h",
        )
        h1 = state_facts_hash(facts)
        h2 = state_facts_hash(facts)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_facts_different_hash(self) -> None:
        f1 = StateFacts(
            idempotency_seen=False,
            budget_remaining=10,
            budget_limit=20,
            tenant_id="t",
            policy_epoch=0,
            policy_hash="h",
        )
        f2 = StateFacts(
            idempotency_seen=True,  # different
            budget_remaining=10,
            budget_limit=20,
            tenant_id="t",
            policy_epoch=0,
            policy_hash="h",
        )
        assert state_facts_hash(f1) != state_facts_hash(f2)


class TestDecisionRecordStateFactsHash:
    """DecisionRecord — state_facts_hash present (G12.4)."""

    def test_record_has_state_facts_hash_field(self) -> None:
        record = DecisionRecord(
            decision=Decision.ALLOW,
            stage=Stage.GATEWAY,
            reason_code=None,
            policy_epoch=0,
            correlation_id=uuid.uuid4(),
            principal="A1",
            payload_hash="a" * 64,
            decided_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
            state_facts_hash="b" * 64,
        )
        assert record.state_facts_hash == "b" * 64

    def test_record_state_facts_hash_defaults_none(self) -> None:
        record = DecisionRecord(
            decision=Decision.DENY,
            stage=Stage.GATEWAY,
            reason_code="GW-AUTH-001",
            policy_epoch=0,
            correlation_id=uuid.uuid4(),
            principal="A1",
            payload_hash="a" * 64,
            decided_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )
        assert record.state_facts_hash is None


class TestGatewayStateFacts:
    """Gateway — passes state_facts_hash into DecisionRecord (G12.4)."""

    @pytest.fixture
    def gateway(self) -> PolicyGateway:
        entries = {
            PolicyMatrixEntry("A1", "scenario", "simulate"),
        }
        return PolicyGateway(
            policy_matrix=PolicyMatrix(entries),
            current_epoch=0,
            schema_registry={"ops.sim.scenario@1"},
            envelope_type_registry={"ops.sim.scenario@1": "scenario"},
        )

    @pytest.fixture
    def clock(self) -> SeededClock:
        return SeededClock(start=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC))

    @pytest.fixture
    def envelope(self, clock: SeededClock) -> Envelope:
        payload = {"site": "site-a", "capacity": 10}
        return Envelope(
            envelope_version="1.0",
            schema_id="ops.sim.scenario@1",
            envelope_type="scenario",
            correlation_id=uuid.uuid4(),
            causation_id=None,
            tenant_id="tenant-test",
            policy_epoch=0,
            idempotency_key="test-idempotency-key-001",
            payload=payload,
            payload_hash=canonical_hash(payload),
            created_at=clock.now(),
        )

    def test_allow_includes_state_facts_hash(
        self,
        gateway: PolicyGateway,
        envelope: Envelope,
        clock: SeededClock,
    ) -> None:
        facts = StateFacts(
            idempotency_seen=False,
            budget_remaining=100,
            budget_limit=200,
            tenant_id="tenant-test",
            policy_epoch=0,
            policy_hash="ph-001",
        )
        record = gateway.evaluate(
            envelope, "A1", clock.now(), capability="simulate",
            state_facts=facts,
        )
        assert record.decision is Decision.ALLOW
        assert record.state_facts_hash is not None
        assert record.state_facts_hash == state_facts_hash(facts)

    def test_deny_includes_state_facts_hash(
        self,
        gateway: PolicyGateway,
        envelope: Envelope,
        clock: SeededClock,
    ) -> None:
        facts = StateFacts(
            idempotency_seen=False,
            budget_remaining=100,
            budget_limit=200,
            tenant_id="tenant-test",
            policy_epoch=0,
            policy_hash="ph-001",
        )
        # Use a principal not in the matrix to trigger DENY
        record = gateway.evaluate(
            envelope, "A2", clock.now(), state_facts=facts
        )
        assert record.decision is Decision.DENY
        assert record.state_facts_hash is not None
        assert record.state_facts_hash == state_facts_hash(facts)

    def test_no_state_facts_hash_is_none(
        self,
        gateway: PolicyGateway,
        envelope: Envelope,
        clock: SeededClock,
    ) -> None:
        record = gateway.evaluate(envelope, "A1", clock.now())
        assert record.state_facts_hash is None

    def test_same_facts_same_hash_in_record(
        self,
        gateway: PolicyGateway,
        envelope: Envelope,
        clock: SeededClock,
    ) -> None:
        facts = StateFacts(
            idempotency_seen=False,
            budget_remaining=100,
            budget_limit=200,
            tenant_id="tenant-test",
            policy_epoch=0,
            policy_hash="ph-001",
        )
        r1 = gateway.evaluate(
            envelope, "A1", clock.now(), capability="simulate",
            state_facts=facts,
        )
        # Reset clock for the second call to get the same decided_at
        clock.reset()
        r2 = gateway.evaluate(
            envelope, "A1", clock.now(), capability="simulate",
            state_facts=facts,
        )
        assert r1.state_facts_hash == r2.state_facts_hash

    def test_different_facts_different_hash_in_record(
        self,
        gateway: PolicyGateway,
        envelope: Envelope,
        clock: SeededClock,
    ) -> None:
        f1 = StateFacts(
            idempotency_seen=False,
            budget_remaining=100,
            budget_limit=200,
            tenant_id="tenant-test",
            policy_epoch=0,
            policy_hash="ph-001",
        )
        f2 = StateFacts(
            idempotency_seen=True,
            budget_remaining=50,
            budget_limit=200,
            tenant_id="tenant-test",
            policy_epoch=0,
            policy_hash="ph-002",
        )
        r1 = gateway.evaluate(
            envelope, "A1", clock.now(), capability="simulate",
            state_facts=f1,
        )
        clock.reset()
        r2 = gateway.evaluate(
            envelope, "A1", clock.now(), capability="simulate",
            state_facts=f2,
        )
        assert r1.state_facts_hash != r2.state_facts_hash
