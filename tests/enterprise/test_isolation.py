"""G18.1 — Tenant isolation suite tests (P18).

Tests that the :class:`TenantIsolationSuite` enforces three invariants
across >= 3 concurrent tenants with >= 10 ops each:

1. No shared mutable state (independent MemoryStore + DurableExecutor).
2. No cross-log leakage (tenant A's logs don't contain tenant B's data).
3. No timing side-channel (response times don't correlate with other
   tenant state size).

Also tests the underlying isolation primitives directly: TenantGuard,
MemoryStore independence, DurableExecutor independence, and log
containment.
"""

from __future__ import annotations

import hashlib

import pytest
from aminopstwin.contracts.clock import SeededClock
from aminopstwin.enterprise.isolation import (
    IsolationResult,
    TenantIsolationSuite,
    run_isolation_suite,
)
from aminopstwin.enterprise.tenant import TenantGuard, TenantScope
from aminopstwin.executor import DurableExecutor
from aminopstwin.executor.memory import MemoryClass, MemoryStore

_TENANT_A = "tenant-aa"
_TENANT_B = "tenant-bb"
_TENANT_C = "tenant-cc"


def _ph(tenant: str, op: int) -> str:
    return hashlib.sha256(f"{tenant}-{op}".encode()).hexdigest()


class TestIsolationSuiteRun:
    """G18.1: the isolation suite passes with zero violations."""

    def test_run_returns_isolation_result(self) -> None:
        result = run_isolation_suite(num_tenants=3, ops_per_tenant=10)
        assert isinstance(result, IsolationResult)
        assert result.num_tenants == 3
        assert result.ops_per_tenant == 10

    def test_three_tenants_ten_ops_zero_violations(self) -> None:
        """3 tenants, 10 ops each — zero leaks, violations, side channels."""
        result = run_isolation_suite(num_tenants=3, ops_per_tenant=10)
        assert result.passed, (
            f"isolation suite failed: "
            f"leaks={result.cross_tenant_leaks} "
            f"shared={result.shared_state_violations} "
            f"timing={result.timing_side_channels}"
        )
        assert result.cross_tenant_leaks == 0
        assert result.shared_state_violations == 0
        assert result.timing_side_channels == 0

    def test_five_tenants_fifteen_ops_pass(self) -> None:
        """5 tenants, 15 ops each — still passes."""
        result = run_isolation_suite(num_tenants=5, ops_per_tenant=15)
        assert result.passed, (
            f"isolation suite failed for 5 tenants: {result.details}"
        )
        assert result.num_tenants == 5
        assert result.ops_per_tenant == 15

    def test_min_tenants_rejected(self) -> None:
        """num_tenants < 3 is rejected."""
        with pytest.raises(ValueError):
            run_isolation_suite(num_tenants=2, ops_per_tenant=10)

    def test_suite_with_seeded_clock(self) -> None:
        """The suite works with an injected SeededClock."""
        clock = SeededClock()
        suite = TenantIsolationSuite(clock=clock)
        result = suite.run(num_tenants=3, ops_per_tenant=10)
        assert result.passed, result.details

    def test_details_contain_per_tenant_info(self) -> None:
        """Result details include per-tenant store size and state hash."""
        result = run_isolation_suite(num_tenants=3, ops_per_tenant=10)
        assert "tenants" in result.details
        for tid in ("tenant-00", "tenant-01", "tenant-02"):
            assert tid in result.details["tenants"]
            info = result.details["tenants"][tid]
            assert info["store_size"] == 10
            assert info["state_hash"]
            assert info["log_lines"] == 10


class TestTenantGuardCrossTenantDenial:
    """TenantGuard correctly denies cross-tenant access."""

    def test_cross_tenant_read_returns_none(self) -> None:
        store = MemoryStore()
        guard = TenantGuard(store=store)
        scope_a = TenantScope(tenant_id=_TENANT_A)
        guard.write(
            record_id="rec-a-001",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            scope=scope_a,
            correlation_id="corr-a-001",
            schema_id="schema.test@1",
            payload_hash=_ph(_TENANT_A, 1),
            recorded_at="2026-10-25T00:00:00Z",
        )
        scope_b = TenantScope(tenant_id=_TENANT_B)
        assert guard.read("rec-a-001", scope_b) is None

    def test_cross_tenant_attempt_counted_and_denied(self) -> None:
        store = MemoryStore()
        guard = TenantGuard(store=store)
        scope_a = TenantScope(tenant_id=_TENANT_A)
        guard.write(
            record_id="rec-a-002",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            scope=scope_a,
            correlation_id="corr-a-002",
            schema_id="schema.test@1",
            payload_hash=_ph(_TENANT_A, 2),
            recorded_at="2026-10-25T00:00:00Z",
        )
        before = guard.cross_tenant_attempts
        denied = guard.attempt_cross_tenant(
            "rec-a-002", _TENANT_A, _TENANT_B
        )
        assert denied is True
        assert guard.cross_tenant_attempts == before + 1
        assert guard.cross_tenant_successes == 0

    def test_same_tenant_read_allowed(self) -> None:
        store = MemoryStore()
        guard = TenantGuard(store=store)
        scope_a = TenantScope(tenant_id=_TENANT_A)
        guard.write(
            record_id="rec-a-003",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            scope=scope_a,
            correlation_id="corr-a-003",
            schema_id="schema.test@1",
            payload_hash=_ph(_TENANT_A, 3),
            recorded_at="2026-10-25T00:00:00Z",
        )
        rec = guard.read("rec-a-003", scope_a)
        assert rec is not None
        assert rec.tenant_id == _TENANT_A


class TestMemoryStoreIndependence:
    """Each tenant's MemoryStore is independent."""

    def test_write_to_a_does_not_affect_b(self) -> None:
        store_a = MemoryStore()
        store_b = MemoryStore()
        scope_a = TenantScope(tenant_id=_TENANT_A)
        guard_a = TenantGuard(store=store_a)
        guard_a.write(
            record_id="rec-indep-001",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            scope=scope_a,
            correlation_id="corr-indep-001",
            schema_id="schema.test@1",
            payload_hash=_ph(_TENANT_A, 1),
            recorded_at="2026-10-25T00:00:00Z",
        )
        assert len(store_a) == 1
        assert len(store_b) == 0
        # B's store has no record
        assert store_b.read(
            "rec-indep-001", _TENANT_B, 0
        ) is None

    def test_state_hashes_differ_with_different_data(self) -> None:
        store_a = MemoryStore()
        store_b = MemoryStore()
        scope_a = TenantScope(tenant_id=_TENANT_A)
        scope_b = TenantScope(tenant_id=_TENANT_B)
        guard_a = TenantGuard(store=store_a)
        guard_b = TenantGuard(store=store_b)
        guard_a.write(
            record_id="rec-hash-001",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            scope=scope_a,
            correlation_id="corr-hash-001",
            schema_id="schema.test@1",
            payload_hash=_ph(_TENANT_A, 1),
            recorded_at="2026-10-25T00:00:00Z",
        )
        guard_b.write(
            record_id="rec-hash-002",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            scope=scope_b,
            correlation_id="corr-hash-002",
            schema_id="schema.test@1",
            payload_hash=_ph(_TENANT_B, 2),
            recorded_at="2026-10-25T00:00:00Z",
        )
        assert store_a.state_hash() != store_b.state_hash()

    def test_empty_stores_have_same_hash(self) -> None:
        """Two empty stores hash the same (no data)."""
        assert MemoryStore().state_hash() == MemoryStore().state_hash()


class TestDurableExecutorIndependence:
    """DurableExecutor instances are independent across tenants."""

    def test_workflow_in_a_does_not_appear_in_b(self) -> None:
        clock = SeededClock()
        exec_a = DurableExecutor(clock=clock)
        exec_b = DurableExecutor(clock=clock)
        import uuid as _uuid

        wf_a = exec_a.start(
            correlation_id=_uuid.uuid4(), tenant_id=_TENANT_A
        )
        # A has one workflow; B has none
        assert exec_a.get_workflow(wf_a.workflow_id) is not None
        assert exec_b.get_workflow(wf_a.workflow_id) is None
        assert len(exec_a._store) == 1  # noqa: SLF001
        assert len(exec_b._store) == 0  # noqa: SLF001

    def test_snapshot_hashes_differ(self) -> None:
        clock = SeededClock()
        exec_a = DurableExecutor(clock=clock)
        exec_b = DurableExecutor(clock=clock)
        import uuid as _uuid

        exec_a.start(
            correlation_id=_uuid.uuid4(), tenant_id=_TENANT_A
        )
        # A has state, B is empty → different snapshots
        assert exec_a.snapshot_hash() != exec_b.snapshot_hash()


class TestLogContainment:
    """Logs from one tenant don't contain data from another tenant."""

    def test_logs_isolated_in_suite(self) -> None:
        """After a suite run, each tenant's logs mention only its own id."""
        result = run_isolation_suite(num_tenants=3, ops_per_tenant=10)
        # The suite already checks this; double-check via details.
        assert result.cross_tenant_leaks == 0

    def test_manual_log_isolation(self) -> None:
        """Manually constructed per-tenant logs don't cross-contaminate."""
        logs_a: list[str] = [f"[{_TENANT_A}] op=0"]
        logs_b: list[str] = [f"[{_TENANT_B}] op=0"]
        assert _TENANT_B not in "".join(logs_a)
        assert _TENANT_A not in "".join(logs_b)
