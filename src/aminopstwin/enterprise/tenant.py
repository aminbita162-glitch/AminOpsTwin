"""Tenant isolation guard (P8, G5.2, T10, §3.8).

Enforces that every memory read, write, and query is scoped to the
caller's tenant_id.  Cross-tenant access is denied with GW-TENANT-001.

The guard wraps MemoryStore operations and performs the isolation
check before delegating to the store.  It also tracks cross-tenant
access attempts for the G5.2 evidence pack (>= 40 attempts, 0
successes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aminopstwin.executor.memory import MemoryClass, MemoryRecord, MemoryStore

__all__ = [
    "TenantGuard",
    "TenantAccessError",
    "TenantScope",
]


class TenantAccessError(Exception):
    """Raised when a cross-tenant access attempt is detected (T10)."""


@dataclass(frozen=True)
class TenantScope:
    """Tenant scope for isolation checks."""

    tenant_id: str
    policy_epoch: int = 0

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id must be non-empty")


@dataclass
class TenantGuard:
    """Tenant isolation guard wrapping a MemoryStore (G5.2, T10).

    Every read, write, and query passes through the guard.  Cross-tenant
    access is denied and recorded as an attempt.  The guard tracks the
    total number of cross-tenant attempts and the number of successes
    (which must be zero).
    """

    store: MemoryStore = field(default_factory=MemoryStore)
    _cross_tenant_attempts: int = 0
    _cross_tenant_successes: int = 0

    @property
    def cross_tenant_attempts(self) -> int:
        """Total number of cross-tenant access attempts."""
        return self._cross_tenant_attempts

    @property
    def cross_tenant_successes(self) -> int:
        """Number of cross-tenant access attempts that succeeded (must be 0)."""
        return self._cross_tenant_successes

    def read(
        self,
        record_id: str,
        scope: TenantScope,
    ) -> MemoryRecord | None:
        """Read a record with tenant isolation enforcement.

        If the record belongs to a different tenant, the access is
        denied (returns None) and the attempt is recorded.
        """
        record = self.store._by_id.get(record_id)
        if record is not None and record.tenant_id != scope.tenant_id:
            self._cross_tenant_attempts += 1
            # Cross-tenant access is always denied
            return None
        result = self.store.read(
            record_id, scope.tenant_id, scope.policy_epoch
        )
        return result

    def write(
        self,
        record_id: str,
        memory_class: MemoryClass,
        scope: TenantScope,
        correlation_id: str,
        schema_id: str,
        payload_hash: str,
        recorded_at: str,
        **kwargs: Any,
    ) -> MemoryRecord:
        """Write a record with tenant isolation enforcement."""
        return self.store.write(
            record_id=record_id,
            memory_class=memory_class,
            tenant_id=scope.tenant_id,
            correlation_id=correlation_id,
            schema_id=schema_id,
            payload_hash=payload_hash,
            recorded_at=recorded_at,
            policy_epoch=scope.policy_epoch,
            **kwargs,
        )

    def read_class(
        self,
        memory_class: MemoryClass,
        scope: TenantScope,
    ) -> list[MemoryRecord]:
        """Read all records of a class for the scoped tenant."""
        return self.store.read_class(
            memory_class, scope.tenant_id, scope.policy_epoch
        )

    def read_by_correlation(
        self,
        correlation_id: str,
        scope: TenantScope,
    ) -> list[MemoryRecord]:
        """Read records by correlation_id with tenant isolation."""
        return self.store.read_by_correlation(
            correlation_id, scope.tenant_id, scope.policy_epoch
        )

    def attempt_cross_tenant(
        self,
        record_id: str,
        owning_tenant: str,
        requesting_tenant: str,
    ) -> bool:
        """Simulate a cross-tenant access attempt.

        Returns True if the access was denied (expected), False if
        it succeeded (which would be a security failure).

        Does NOT pre-increment ``_cross_tenant_attempts`` — the
        underlying :meth:`read` call already records the attempt
        when it detects a tenant mismatch.
        """
        scope = TenantScope(
            tenant_id=requesting_tenant,
            policy_epoch=0,
        )
        result = self.read(record_id, scope)
        if result is not None:
            # This should never happen
            self._cross_tenant_successes += 1
            return False
        return True  # Access was correctly denied

    def state_hash(self) -> str:
        """Return a deterministic state hash of the guard."""
        return self.store.state_hash()
