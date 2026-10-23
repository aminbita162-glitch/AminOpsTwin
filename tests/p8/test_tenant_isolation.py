"""G5.2 — Tenant isolation tests (P8, T10, §3.8).

G5.2: Tenant isolation — >= 40 cross-tenant attempts, 0 successes.
Every cross-tenant access attempt is denied with GW-TENANT-001.
"""

from __future__ import annotations

import hashlib

import pytest
from src.enterprise.tenant import TenantGuard, TenantScope
from src.executor.memory import MemoryClass, MemoryStore


def _make_guard_with_tenants(
    num_tenants: int = 5,
    records_per_tenant: int = 10,
) -> TenantGuard:
    """Build a guard with records for multiple tenants."""
    guard = TenantGuard()
    for t in range(num_tenants):
        tenant = f"tenant-{t:02d}"
        for r in range(records_per_tenant):
            guard.store.write(
                record_id=f"rec-{t:02d}-{r:04d}",
                memory_class=MemoryClass.M1_TASK_CONTEXT
                if r % 2 == 0
                else MemoryClass.M2_EXECUTION_HISTORY,
                tenant_id=tenant,
                correlation_id=f"corr-{t:02d}-{r:04d}",
                schema_id=f"schema.test@{r % 3 + 1}",
                payload_hash=hashlib.sha256(
                    f"{tenant}-{r}".encode()
                ).hexdigest(),
                recorded_at="2026-10-23T00:00:00Z",
            )
    return guard


class TestTenantIsolation:
    """G5.2: >= 40 cross-tenant attempts, 0 successes."""

    def test_cross_tenant_read_denied(self) -> None:
        """Cross-tenant read is denied."""
        guard = _make_guard_with_tenants()
        scope_a = TenantScope(tenant_id="tenant-00")
        scope_b = TenantScope(tenant_id="tenant-01")
        # tenant-00 owns rec-00-0000
        record = guard.read("rec-00-0000", scope_b)
        assert record is None

    def test_same_tenant_read_allowed(self) -> None:
        """Same-tenant read is allowed."""
        guard = _make_guard_with_tenants()
        scope_a = TenantScope(tenant_id="tenant-00")
        record = guard.read("rec-00-0000", scope_a)
        assert record is not None
        assert record.record_id == "rec-00-0000"

    def test_40_cross_tenant_attempts_zero_successes(self) -> None:
        """G5.2: >= 40 cross-tenant attempts, 0 successes."""
        guard = _make_guard_with_tenants(
            num_tenants=5, records_per_tenant=10
        )
        # Generate >= 40 cross-tenant access attempts
        attempts = 0
        successes = 0
        for owning_tenant in range(5):
            for requesting_tenant in range(5):
                if owning_tenant == requesting_tenant:
                    continue
                record_id = f"rec-{owning_tenant:02d}-0000"
                denied = guard.attempt_cross_tenant(
                    record_id,
                    f"tenant-{owning_tenant:02d}",
                    f"tenant-{requesting_tenant:02d}",
                )
                attempts += 1
                if not denied:
                    successes += 1

        assert attempts >= 40, (
            f"Need >= 40 attempts, got {attempts}"
        )
        assert successes == 0, (
            f"Cross-tenant access succeeded {successes} times"
        )
        assert guard.cross_tenant_attempts >= 40
        assert guard.cross_tenant_successes == 0

    def test_read_class_isolated_by_tenant(self) -> None:
        """read_class only returns records for the scoped tenant."""
        guard = _make_guard_with_tenants()
        scope_a = TenantScope(tenant_id="tenant-00")
        scope_b = TenantScope(tenant_id="tenant-01")
        a_records = guard.read_class(
            MemoryClass.M1_TASK_CONTEXT, scope_a
        )
        b_records = guard.read_class(
            MemoryClass.M1_TASK_CONTEXT, scope_b
        )
        # All records should belong to their respective tenants
        for r in a_records:
            assert r.tenant_id == "tenant-00"
        for r in b_records:
            assert r.tenant_id == "tenant-01"

    def test_read_by_correlation_isolated(self) -> None:
        """read_by_correlation is isolated by tenant."""
        guard = _make_guard_with_tenants()
        scope_b = TenantScope(tenant_id="tenant-01")
        # corr-00-0000 belongs to tenant-00
        records = guard.read_by_correlation("corr-00-0000", scope_b)
        assert len(records) == 0

    def test_write_scoped_to_tenant(self) -> None:
        """Write is scoped to the caller's tenant."""
        guard = TenantGuard()
        scope_a = TenantScope(tenant_id="tenant-a")
        guard.write(
            record_id="rec-write-001",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            scope=scope_a,
            correlation_id="corr-write-001",
            schema_id="schema.test@1",
            payload_hash=hashlib.sha256(b"w").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
        )
        # Read from same tenant
        record = guard.read("rec-write-001", scope_a)
        assert record is not None
        assert record.tenant_id == "tenant-a"

        # Read from different tenant
        scope_b = TenantScope(tenant_id="tenant-b")
        record_b = guard.read("rec-write-001", scope_b)
        assert record_b is None

    def test_state_hash_deterministic(self) -> None:
        """State hash is deterministic for identical stores."""
        guard1 = _make_guard_with_tenants()
        guard2 = _make_guard_with_tenants()
        assert guard1.state_hash() == guard2.state_hash()

    def test_cross_tenant_does_not_corrupt_state(self) -> None:
        """Cross-tenant access does not corrupt state."""
        guard = _make_guard_with_tenants()
        hash_before = guard.state_hash()
        # Attempt many cross-tenant reads
        for t in range(5):
            scope = TenantScope(tenant_id=f"tenant-{t:02d}")
            for r in range(10):
                guard.read(f"rec-00-{r:04d}", scope)
        hash_after = guard.state_hash()
        assert hash_before == hash_after

    def test_tenant_scope_validation(self) -> None:
        """TenantScope rejects empty tenant_id."""
        with pytest.raises(ValueError):
            TenantScope(tenant_id="")

    def test_cross_tenant_attempt_count_tracked(self) -> None:
        """Cross-tenant attempts are tracked by the guard."""
        guard = _make_guard_with_tenants()
        initial = guard.cross_tenant_attempts
        guard.attempt_cross_tenant(
            "rec-00-0000", "tenant-00", "tenant-01"
        )
        assert guard.cross_tenant_attempts == initial + 1
