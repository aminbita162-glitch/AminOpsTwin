"""Tenant quota engine and quota-aware Gateway (P18, G18.2).

Tracks per-tenant submission budgets and enforces quota at the Gateway
level. Over-budget requests are denied with reason code ``GW-BUDGET-001``
(stage ``Stage.BUDGET``), which is already in the reason-code registry.

The :class:`TenantQuotaEngine` is a simple counter keyed by tenant_id.
:class:`QuotaAwareGateway` wraps a :class:`PolicyGateway` and checks the
tenant's quota *before* delegating to the underlying gateway. If the
quota is exhausted, a DENY :class:`DecisionRecord` is returned immediately
without invoking the wrapped gateway.
"""

from __future__ import annotations

import datetime as _dt
import threading
from dataclasses import dataclass, field

from aminopstwin.contracts.decision import Decision, DecisionRecord, Stage
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.gateway.gateway import PolicyGateway, PolicyMatrix

__all__ = [
    "TenantQuotaEngine",
    "QuotaAwareGateway",
    "QUOTA_REASON_CODE",
]

#: Reason code for over-budget denials (in the reason registry).
QUOTA_REASON_CODE: str = "GW-BUDGET-001"


@dataclass
class TenantQuotaEngine:
    """Per-tenant submission quota tracker (G18.2).

    Maps ``tenant_id`` to a maximum number of submissions and tracks
    how many have been consumed. All mutations are thread-safe.

    Attributes:
        tenant_quotas: Mapping of tenant_id to max submissions.
    """

    tenant_quotas: dict[str, int] = field(default_factory=dict)
    _consumed: dict[str, int] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def check_quota(self, tenant_id: str) -> bool:
        """Return True if *tenant_id* has remaining quota."""
        with self._lock:
            return self.remaining(tenant_id) > 0

    def consume(self, tenant_id: str) -> bool:
        """Consume one unit of quota for *tenant_id*.

        Returns True if the consumption succeeded (quota was available),
        False if the tenant is over-budget or unknown to the engine.
        """
        with self._lock:
            if tenant_id not in self.tenant_quotas:
                return False
            current = self._consumed.get(tenant_id, 0)
            if current >= self.tenant_quotas[tenant_id]:
                return False
            self._consumed[tenant_id] = current + 1
            return True

    def remaining(self, tenant_id: str) -> int:
        """Return the remaining quota for *tenant_id* (0 if unknown)."""
        if tenant_id not in self.tenant_quotas:
            return 0
        return self.tenant_quotas[tenant_id] - self._consumed.get(
            tenant_id, 0
        )

    def reset(self, tenant_id: str) -> None:
        """Reset the consumed quota for *tenant_id* to zero."""
        with self._lock:
            self._consumed.pop(tenant_id, None)


class QuotaAwareGateway:
    """PolicyGateway wrapper that enforces tenant quota before evaluation.

    The quota check happens *before* the underlying :class:`PolicyGateway`
    is consulted. If the tenant is over-budget (or unknown to the quota
    engine), a DENY :class:`DecisionRecord` is returned with
    ``reason_code='GW-BUDGET-001'`` and ``stage=Stage.BUDGET``.

    Otherwise, one unit of quota is consumed and the request is
    delegated to the wrapped gateway.
    """

    def __init__(
        self,
        gateway: PolicyGateway,
        quota_engine: TenantQuotaEngine,
    ) -> None:
        self._gateway = gateway
        self._quota = quota_engine

    @property
    def current_epoch(self) -> int:
        return self._gateway.current_epoch

    @property
    def policy_matrix(self) -> PolicyMatrix:
        """Return the wrapped gateway's policy matrix."""
        return self._gateway._policy_matrix  # noqa: SLF001

    def evaluate(
        self,
        envelope: Envelope,
        principal: str,
        decided_at: _dt.datetime,
        capability: str = "default",
    ) -> DecisionRecord:
        """Evaluate an envelope, checking quota first.

        If the tenant is over-budget, return a DENY with
        ``GW-BUDGET-001`` and ``Stage.BUDGET``. Otherwise consume one
        unit and delegate to the wrapped :class:`PolicyGateway`.
        """
        if not self._quota.check_quota(envelope.tenant_id):
            return DecisionRecord(
                decision=Decision.DENY,
                stage=Stage.BUDGET,
                reason_code=QUOTA_REASON_CODE,
                secondary_codes=[],
                policy_epoch=self._gateway.current_epoch,
                rule_ids=["quota-exhausted"],
                correlation_id=envelope.correlation_id,
                principal=principal,
                payload_hash=envelope.payload_hash,
                decided_at=decided_at,
                state_facts_hash=None,
            )
        # Consume one unit; if that fails concurrently, deny.
        if not self._quota.consume(envelope.tenant_id):
            return DecisionRecord(
                decision=Decision.DENY,
                stage=Stage.BUDGET,
                reason_code=QUOTA_REASON_CODE,
                secondary_codes=[],
                policy_epoch=self._gateway.current_epoch,
                rule_ids=["quota-exhausted"],
                correlation_id=envelope.correlation_id,
                principal=principal,
                payload_hash=envelope.payload_hash,
                decided_at=decided_at,
                state_facts_hash=None,
            )
        # Quota available — delegate to the underlying pure gateway.
        return self._gateway.evaluate(
            envelope, principal, decided_at, capability
        )
