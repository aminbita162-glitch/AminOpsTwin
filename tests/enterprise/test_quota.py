"""G18.2 — Tenant quota engine and quota-aware Gateway tests (P18).

Tests that:
- :class:`TenantQuotaEngine` allows within-budget and denies over-budget.
- :class:`QuotaAwareGateway` returns DENY with ``GW-BUDGET-001`` for
  over-budget requests and ALLOW for in-budget requests.
- Quota reset works and remaining quota decrements correctly.
"""

from __future__ import annotations

import datetime as _dt
import uuid as _uuid

from aminopstwin.contracts.clock import SeededClock
from aminopstwin.contracts.decision import Decision, Stage
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.gateway.gateway import (
    PolicyGateway,
    PolicyMatrix,
    PolicyMatrixEntry,
)
from aminopstwin.gateway.quota import (
    QUOTA_REASON_CODE,
    QuotaAwareGateway,
    TenantQuotaEngine,
)

_TENANT_A = "tenant-aa"
_TENANT_B = "tenant-bb"


def _make_gateway() -> PolicyGateway:
    entries = {
        PolicyMatrixEntry("A2", "scenario", "simulate"),
    }
    return PolicyGateway(
        policy_matrix=PolicyMatrix(entries),
        current_epoch=0,
        schema_registry={"ops.sim.scenario@1"},
        envelope_type_registry={"ops.sim.scenario@1": "scenario"},
    )


def _make_envelope(
    tenant_id: str = _TENANT_A,
    policy_epoch: int = 0,
) -> Envelope:
    payload = {"site": "site-a", "capacity": 10}
    return Envelope(
        envelope_version="1.0",
        schema_id="ops.sim.scenario@1",
        envelope_type="scenario",
        correlation_id=_uuid.uuid4(),
        causation_id=None,
        tenant_id=tenant_id,
        policy_epoch=policy_epoch,
        idempotency_key="test-idempotency-key-001",
        payload=payload,
        payload_hash=__import__(
            "aminopstwin.contracts.canonical", fromlist=["canonical_hash"]
        ).canonical_hash(payload),
        created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
    )


class TestQuotaEngineAllows:
    """TenantQuotaEngine allows submissions within budget."""

    def test_check_quota_true_within_budget(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 5})
        assert engine.check_quota(_TENANT_A) is True

    def test_consume_within_budget_returns_true(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 5})
        assert engine.consume(_TENANT_A) is True
        assert engine.consume(_TENANT_A) is True

    def test_remaining_full_initially(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 5})
        assert engine.remaining(_TENANT_A) == 5

    def test_unknown_tenant_has_zero_quota(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 5})
        assert engine.check_quota(_TENANT_B) is False
        assert engine.remaining(_TENANT_B) == 0
        assert engine.consume(_TENANT_B) is False


class TestQuotaEngineDeniesOverBudget:
    """TenantQuotaEngine denies over-budget requests."""

    def test_consume_denies_after_budget_exhausted(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 2})
        assert engine.consume(_TENANT_A) is True
        assert engine.consume(_TENANT_A) is True
        assert engine.consume(_TENANT_A) is False

    def test_check_quota_false_after_exhausted(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 1})
        engine.consume(_TENANT_A)
        assert engine.check_quota(_TENANT_A) is False

    def test_remaining_zero_after_exhausted(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 3})
        for _ in range(3):
            engine.consume(_TENANT_A)
        assert engine.remaining(_TENANT_A) == 0


class TestQuotaRemainingDecrements:
    """remaining() decrements correctly on each consume()."""

    def test_remaining_decrements(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 4})
        assert engine.remaining(_TENANT_A) == 4
        engine.consume(_TENANT_A)
        assert engine.remaining(_TENANT_A) == 3
        engine.consume(_TENANT_A)
        assert engine.remaining(_TENANT_A) == 2
        engine.consume(_TENANT_A)
        assert engine.remaining(_TENANT_A) == 1
        engine.consume(_TENANT_A)
        assert engine.remaining(_TENANT_A) == 0


class TestQuotaReset:
    """Quota reset restores remaining quota."""

    def test_reset_restores_full_quota(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 3})
        engine.consume(_TENANT_A)
        engine.consume(_TENANT_A)
        assert engine.remaining(_TENANT_A) == 1
        engine.reset(_TENANT_A)
        assert engine.remaining(_TENANT_A) == 3
        assert engine.check_quota(_TENANT_A) is True

    def test_reset_allows_consume_again(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 1})
        assert engine.consume(_TENANT_A) is True
        assert engine.consume(_TENANT_A) is False
        engine.reset(_TENANT_A)
        assert engine.consume(_TENANT_A) is True

    def test_reset_unknown_tenant_is_noop(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 5})
        # reset on unknown tenant should not raise
        engine.reset(_TENANT_B)


class TestQuotaAwareGatewayDeny:
    """QuotaAwareGateway returns DENY with GW-BUDGET-001 for over-budget."""

    def test_over_budget_returns_deny_budget(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 1})
        gw = QuotaAwareGateway(_make_gateway(), engine)
        env = _make_envelope(tenant_id=_TENANT_A)
        decided_at = SeededClock().now()
        # First request — within budget
        rec1 = gw.evaluate(env, "A2", decided_at, "simulate")
        assert rec1.decision == Decision.ALLOW
        # Second request — over budget
        env2 = _make_envelope(tenant_id=_TENANT_A)
        rec2 = gw.evaluate(env2, "A2", decided_at, "simulate")
        assert rec2.decision == Decision.DENY
        assert rec2.reason_code == QUOTA_REASON_CODE
        assert rec2.reason_code == "GW-BUDGET-001"
        assert rec2.stage == Stage.BUDGET

    def test_unknown_tenant_denied_budget(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 5})
        gw = QuotaAwareGateway(_make_gateway(), engine)
        env = _make_envelope(tenant_id=_TENANT_B)
        decided_at = SeededClock().now()
        rec = gw.evaluate(env, "A2", decided_at, "simulate")
        assert rec.decision == Decision.DENY
        assert rec.reason_code == "GW-BUDGET-001"
        assert rec.stage == Stage.BUDGET


class TestQuotaAwareGatewayAllow:
    """QuotaAwareGateway allows in-budget requests (delegates to gateway)."""

    def test_in_budget_returns_allow(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 10})
        gw = QuotaAwareGateway(_make_gateway(), engine)
        env = _make_envelope(tenant_id=_TENANT_A)
        decided_at = SeededClock().now()
        rec = gw.evaluate(env, "A2", decided_at, "simulate")
        assert rec.decision == Decision.ALLOW
        assert rec.reason_code is None
        assert rec.stage == Stage.GATEWAY

    def test_allow_decrements_quota(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 5})
        gw = QuotaAwareGateway(_make_gateway(), engine)
        env = _make_envelope(tenant_id=_TENANT_A)
        decided_at = SeededClock().now()
        gw.evaluate(env, "A2", decided_at, "simulate")
        assert engine.remaining(_TENANT_A) == 4

    def test_multiple_tenants_independent_quota(self) -> None:
        engine = TenantQuotaEngine(
            {_TENANT_A: 2, _TENANT_B: 2}
        )
        gw = QuotaAwareGateway(_make_gateway(), engine)
        decided_at = SeededClock().now()
        cap = "simulate"
        # A uses its quota
        gw.evaluate(_make_envelope(_TENANT_A), "A2", decided_at, cap)
        gw.evaluate(_make_envelope(_TENANT_A), "A2", decided_at, cap)
        # A is now exhausted; B still has budget
        rec_a = gw.evaluate(
            _make_envelope(_TENANT_A), "A2", decided_at, cap
        )
        assert rec_a.decision == Decision.DENY
        assert rec_a.reason_code == "GW-BUDGET-001"
        rec_b = gw.evaluate(
            _make_envelope(_TENANT_B), "A2", decided_at, cap
        )
        assert rec_b.decision == Decision.ALLOW


class TestQuotaAwareGatewayReset:
    """After quota reset, the gateway allows again."""

    def test_reset_then_allow(self) -> None:
        engine = TenantQuotaEngine({_TENANT_A: 1})
        gw = QuotaAwareGateway(_make_gateway(), engine)
        decided_at = SeededClock().now()
        cap = "simulate"
        env = _make_envelope(_TENANT_A)
        gw.evaluate(env, "A2", decided_at, cap)
        # Over budget now
        rec_deny = gw.evaluate(
            _make_envelope(_TENANT_A), "A2", decided_at, cap
        )
        assert rec_deny.decision == Decision.DENY
        # Reset and try again
        engine.reset(_TENANT_A)
        rec_allow = gw.evaluate(
            _make_envelope(_TENANT_A), "A2", decided_at, cap
        )
        assert rec_allow.decision == Decision.ALLOW
